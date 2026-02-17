"""
Script d'evaluation des resultats du pipeline LLM

Ce script compare les suggestions du LLM avec le ground truth pour calculer:
- Precision du renommage
- Recall des APIs detectees
- Qualite des commentaires (score semantique)
- Taux d'hallucinations
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re
from collections import defaultdict
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer


def compute_bleu(reference: str, hypothesis: str) -> float:
    """Calcule le score BLEU entre une reference et une hypothese"""
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    if not ref_tokens or not hyp_tokens:
        return 0.0
    smoothie = SmoothingFunction().method1
    return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothie)


def compute_rouge(reference: str, hypothesis: str) -> dict:
    """Calcule les scores ROUGE entre une reference et une hypothese"""
    if not reference or not hypothesis:
        return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    scores = scorer.score(reference, hypothesis)
    return {k: v.fmeasure for k, v in scores.items()}


@dataclass
class EvaluationMetrics:
    """Metriques d'evaluation pour une fonction"""
    function_name: str
    name_exact_match: bool = False
    name_acceptable_match: bool = False
    name_semantic_score: float = 0.0
    return_type_correct: bool = False
    apis_precision: float = 0.0
    apis_recall: float = 0.0
    comment_keyword_score: float = 0.0
    comment_bleu: float = 0.0
    comment_rouge1: float = 0.0
    comment_rouge2: float = 0.0
    comment_rougeL: float = 0.0
    is_hallucination: bool = False
    confidence: float = 0.0


@dataclass
class BinaryEvaluation:
    """Resultats d'evaluation pour un binaire"""
    binary_name: str
    functions_evaluated: int = 0
    functions_with_suggestions: int = 0
    exact_name_matches: int = 0
    acceptable_name_matches: int = 0
    avg_semantic_score: float = 0.0
    return_type_accuracy: float = 0.0
    avg_api_precision: float = 0.0
    avg_api_recall: float = 0.0
    avg_comment_score: float = 0.0
    avg_bleu: float = 0.0
    avg_rouge1: float = 0.0
    avg_rouge2: float = 0.0
    avg_rougeL: float = 0.0
    hallucination_count: int = 0
    hallucination_rate: float = 0.0
    function_metrics: List[EvaluationMetrics] = field(default_factory=list)


def normalize_name(name: str) -> str:
    """Normalise un nom de fonction pour la comparaison"""
    # Convertir en minuscules
    name = name.lower()
    # Remplacer les separateurs par des underscores
    name = re.sub(r'[-\s]+', '_', name)
    # Supprimer les prefixes/suffixes communs
    name = re.sub(r'^(func_|fn_|f_)', '', name)
    name = re.sub(r'(_func|_fn|_f)$', '', name)
    return name


def calculate_semantic_similarity(suggested: str, expected: str, acceptable: List[str]) -> float:
    """
    Calcule un score de similarite semantique simple.
    Dans un vrai projet, utiliser un modele d'embeddings.
    """
    suggested_norm = normalize_name(suggested)
    expected_norm = normalize_name(expected)

    # Match exact
    if suggested_norm == expected_norm:
        return 1.0

    # Match avec noms acceptables
    for acc in acceptable:
        if suggested_norm == normalize_name(acc):
            return 0.95

    # Similarite basee sur les mots communs
    suggested_words = set(suggested_norm.split('_'))
    expected_words = set(expected_norm.split('_'))

    if not suggested_words or not expected_words:
        return 0.0

    common = suggested_words.intersection(expected_words)
    union = suggested_words.union(expected_words)

    jaccard = len(common) / len(union) if union else 0

    # Bonus si les mots principaux sont presents
    important_words = {'read', 'write', 'copy', 'free', 'alloc', 'create',
                      'delete', 'find', 'search', 'sort', 'hash', 'encrypt',
                      'decrypt', 'xor', 'list', 'node', 'string', 'buffer',
                      'file', 'open', 'close', 'count', 'length', 'size'}

    bonus = 0
    for word in common:
        if word in important_words:
            bonus += 0.1

    return min(jaccard + bonus, 1.0)


def calculate_keyword_score(comment: str, expected_keywords: List[str]) -> float:
    """Calcule le score de presence des mots-cles dans le commentaire"""
    if not comment or not expected_keywords:
        return 0.0

    comment_lower = comment.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in comment_lower)
    return found / len(expected_keywords)


def detect_hallucination(suggestion: Dict, ground_truth: Dict) -> bool:
    """
    Detecte si la suggestion est une hallucination.
    Une hallucination est une suggestion qui:
    - Mentionne des APIs non presentes
    - Attribue un comportement incorrect
    - A une confiance elevee mais est completement fausse
    """
    confidence = suggestion.get('confidence', 0)

    # Si confiance elevee mais nom completement different
    if confidence > 0.8:
        suggested_name = normalize_name(suggestion.get('suggested_name', ''))
        expected_name = normalize_name(ground_truth.get('expected_name', ''))
        acceptable = [normalize_name(n) for n in ground_truth.get('acceptable_names', [])]

        all_valid = [expected_name] + acceptable
        if suggested_name and not any(w in suggested_name for name in all_valid for w in name.split('_')):
            return True

    # APIs mentionnees qui n'existent pas dans le ground truth
    detected_apis = set(suggestion.get('detected_apis', []) or [])
    expected_apis = set(ground_truth.get('expected_apis', []) or [])

    if detected_apis:
        false_apis = detected_apis - expected_apis
        # Plus de la moitie des APIs sont fausses
        if len(false_apis) > len(detected_apis) / 2:
            return True

    return False


def evaluate_function(suggestion: Dict, ground_truth: Dict) -> EvaluationMetrics:
    """Evalue une suggestion de fonction"""
    metrics = EvaluationMetrics(
        function_name=suggestion.get('original_name', 'unknown'),
        confidence=suggestion.get('confidence', 0)
    )

    expected_name = ground_truth.get('expected_name', '')
    acceptable_names = ground_truth.get('acceptable_names', [])
    suggested_name = suggestion.get('suggested_name', '')

    # Evaluation du nom
    if suggested_name:
        metrics.name_exact_match = normalize_name(suggested_name) == normalize_name(expected_name)
        metrics.name_acceptable_match = (
            metrics.name_exact_match or
            normalize_name(suggested_name) in [normalize_name(n) for n in acceptable_names]
        )
        metrics.name_semantic_score = calculate_semantic_similarity(
            suggested_name, expected_name, acceptable_names
        )

    # Evaluation du type de retour
    expected_return = ground_truth.get('expected_return_type', '')
    suggested_return = suggestion.get('suggested_return_type', '')
    if expected_return and suggested_return:
        metrics.return_type_correct = (
            suggested_return.lower().replace(' ', '') ==
            expected_return.lower().replace(' ', '')
        )

    # Evaluation des APIs
    expected_apis = set(ground_truth.get('expected_apis', []) or [])
    detected_apis = set(suggestion.get('detected_apis', []) or [])

    if expected_apis:
        true_positives = len(detected_apis.intersection(expected_apis))
        metrics.apis_precision = true_positives / len(detected_apis) if detected_apis else 0
        metrics.apis_recall = true_positives / len(expected_apis) if expected_apis else 0

    # Evaluation des commentaires
    expected_keywords = ground_truth.get('expected_comment_keywords', [])
    comment = suggestion.get('comments', '') or suggestion.get('reasoning', '')
    metrics.comment_keyword_score = calculate_keyword_score(comment, expected_keywords)

    # BLEU / ROUGE
    if expected_keywords and comment:
        reference = " ".join(expected_keywords)
        hypothesis = comment
        metrics.comment_bleu = compute_bleu(reference, hypothesis)
        rouge_scores = compute_rouge(reference, hypothesis)
        metrics.comment_rouge1 = rouge_scores['rouge1']
        metrics.comment_rouge2 = rouge_scores['rouge2']
        metrics.comment_rougeL = rouge_scores['rougeL']

    # Detection d'hallucination
    metrics.is_hallucination = detect_hallucination(suggestion, ground_truth)

    return metrics


def evaluate_binary(suggestions_file: str, ground_truth: Dict) -> BinaryEvaluation:
    """Evalue toutes les suggestions pour un binaire"""

    with open(suggestions_file, 'r', encoding='utf-8') as f:
        suggestions = json.load(f)

    binary_name = Path(suggestions_file).stem
    eval_result = BinaryEvaluation(binary_name=binary_name)

    # Creer un index des fonctions ground truth
    gt_functions = {f['original_name']: f for f in ground_truth.get('functions', [])}

    eval_result.functions_evaluated = len(gt_functions)
    eval_result.functions_with_suggestions = 0

    semantic_scores = []
    api_precisions = []
    api_recalls = []
    comment_scores = []
    bleu_scores = []
    rouge1_scores = []
    rouge2_scores = []
    rougeL_scores = []
    return_type_correct = 0

    for suggestion in suggestions:
        original_name = suggestion.get('original_name', '')

        if original_name not in gt_functions:
            continue

        eval_result.functions_with_suggestions += 1
        gt = gt_functions[original_name]

        metrics = evaluate_function(suggestion, gt)
        eval_result.function_metrics.append(metrics)

        if metrics.name_exact_match:
            eval_result.exact_name_matches += 1
        if metrics.name_acceptable_match:
            eval_result.acceptable_name_matches += 1

        semantic_scores.append(metrics.name_semantic_score)

        if metrics.return_type_correct:
            return_type_correct += 1

        if gt.get('expected_apis'):
            api_precisions.append(metrics.apis_precision)
            api_recalls.append(metrics.apis_recall)

        comment_scores.append(metrics.comment_keyword_score)
        bleu_scores.append(metrics.comment_bleu)
        rouge1_scores.append(metrics.comment_rouge1)
        rouge2_scores.append(metrics.comment_rouge2)
        rougeL_scores.append(metrics.comment_rougeL)

        if metrics.is_hallucination:
            eval_result.hallucination_count += 1

    # Calculer les moyennes
    n = eval_result.functions_with_suggestions
    if n > 0:
        eval_result.avg_semantic_score = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0
        eval_result.return_type_accuracy = return_type_correct / n
        eval_result.avg_api_precision = sum(api_precisions) / len(api_precisions) if api_precisions else 0
        eval_result.avg_api_recall = sum(api_recalls) / len(api_recalls) if api_recalls else 0
        eval_result.avg_comment_score = sum(comment_scores) / len(comment_scores) if comment_scores else 0
        eval_result.avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0
        eval_result.avg_rouge1 = sum(rouge1_scores) / len(rouge1_scores) if rouge1_scores else 0
        eval_result.avg_rouge2 = sum(rouge2_scores) / len(rouge2_scores) if rouge2_scores else 0
        eval_result.avg_rougeL = sum(rougeL_scores) / len(rougeL_scores) if rougeL_scores else 0
        eval_result.hallucination_rate = eval_result.hallucination_count / n

    return eval_result


def generate_report(evaluations: List[BinaryEvaluation], output_file: str):
    """Genere un rapport d'evaluation complet"""

    report = {
        "summary": {},
        "per_binary": [],
        "detailed_metrics": []
    }

    # Agregation globale
    total_functions = sum(e.functions_with_suggestions for e in evaluations)
    total_exact = sum(e.exact_name_matches for e in evaluations)
    total_acceptable = sum(e.acceptable_name_matches for e in evaluations)
    total_hallucinations = sum(e.hallucination_count for e in evaluations)

    all_semantic = [m.name_semantic_score for e in evaluations for m in e.function_metrics]
    all_comment = [m.comment_keyword_score for e in evaluations for m in e.function_metrics]
    all_bleu = [m.comment_bleu for e in evaluations for m in e.function_metrics]
    all_rouge1 = [m.comment_rouge1 for e in evaluations for m in e.function_metrics]
    all_rouge2 = [m.comment_rouge2 for e in evaluations for m in e.function_metrics]
    all_rougeL = [m.comment_rougeL for e in evaluations for m in e.function_metrics]

    report["summary"] = {
        "total_binaries": len(evaluations),
        "total_functions_evaluated": total_functions,
        "exact_name_match_rate": total_exact / total_functions if total_functions else 0,
        "acceptable_name_match_rate": total_acceptable / total_functions if total_functions else 0,
        "average_semantic_score": sum(all_semantic) / len(all_semantic) if all_semantic else 0,
        "average_comment_score": sum(all_comment) / len(all_comment) if all_comment else 0,
        "average_bleu": sum(all_bleu) / len(all_bleu) if all_bleu else 0,
        "average_rouge1": sum(all_rouge1) / len(all_rouge1) if all_rouge1 else 0,
        "average_rouge2": sum(all_rouge2) / len(all_rouge2) if all_rouge2 else 0,
        "average_rougeL": sum(all_rougeL) / len(all_rougeL) if all_rougeL else 0,
        "hallucination_rate": total_hallucinations / total_functions if total_functions else 0,
        "confidence_calibration": "TODO"  # A implementer
    }

    # Par binaire
    for e in evaluations:
        report["per_binary"].append({
            "binary": e.binary_name,
            "functions_evaluated": e.functions_evaluated,
            "functions_with_suggestions": e.functions_with_suggestions,
            "exact_match_rate": e.exact_name_matches / e.functions_with_suggestions if e.functions_with_suggestions else 0,
            "acceptable_match_rate": e.acceptable_name_matches / e.functions_with_suggestions if e.functions_with_suggestions else 0,
            "semantic_score": e.avg_semantic_score,
            "return_type_accuracy": e.return_type_accuracy,
            "api_precision": e.avg_api_precision,
            "api_recall": e.avg_api_recall,
            "comment_score": e.avg_comment_score,
            "bleu": e.avg_bleu,
            "rouge1": e.avg_rouge1,
            "rouge2": e.avg_rouge2,
            "rougeL": e.avg_rougeL,
            "hallucination_rate": e.hallucination_rate
        })

        # Details par fonction
        for m in e.function_metrics:
            report["detailed_metrics"].append({
                "binary": e.binary_name,
                "function": m.function_name,
                "exact_match": m.name_exact_match,
                "acceptable_match": m.name_acceptable_match,
                "semantic_score": m.name_semantic_score,
                "return_type_correct": m.return_type_correct,
                "api_precision": m.apis_precision,
                "api_recall": m.apis_recall,
                "comment_score": m.comment_keyword_score,
                "bleu": m.comment_bleu,
                "rouge1": m.comment_rouge1,
                "rouge2": m.comment_rouge2,
                "rougeL": m.comment_rougeL,
                "is_hallucination": m.is_hallucination,
                "confidence": m.confidence
            })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def print_summary(report: Dict):
    """Affiche un resume des resultats"""
    s = report["summary"]

    print("\n" + "="*60)
    print("RAPPORT D'EVALUATION")
    print("="*60)

    print(f"\nBinaires evalues: {s['total_binaries']}")
    print(f"Fonctions evaluees: {s['total_functions_evaluated']}")

    print("\n--- Metriques de Renommage ---")
    print(f"Correspondance exacte: {s['exact_name_match_rate']*100:.1f}%")
    print(f"Correspondance acceptable: {s['acceptable_name_match_rate']*100:.1f}%")
    print(f"Score semantique moyen: {s['average_semantic_score']*100:.1f}%")

    print("\n--- Qualite des Commentaires ---")
    print(f"Score mots-cles moyen: {s['average_comment_score']*100:.1f}%")
    print(f"BLEU moyen: {s.get('average_bleu', 0):.4f}")
    print(f"ROUGE-1 moyen: {s.get('average_rouge1', 0):.4f}")
    print(f"ROUGE-2 moyen: {s.get('average_rouge2', 0):.4f}")
    print(f"ROUGE-L moyen: {s.get('average_rougeL', 0):.4f}")

    print("\n--- Fiabilite ---")
    print(f"Taux d'hallucination: {s['hallucination_rate']*100:.1f}%")

    print("\n--- Par Binaire ---")
    for b in report["per_binary"]:
        print(f"\n{b['binary']}:")
        print(f"  Match exact: {b['exact_match_rate']*100:.1f}%")
        print(f"  Score semantique: {b['semantic_score']*100:.1f}%")
        print(f"  Hallucinations: {b['hallucination_rate']*100:.1f}%")


def main():
    """Point d'entree principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluation des resultats du pipeline LLM")
    parser.add_argument("--suggestions", "-s", required=True, nargs='+',
                       help="Fichiers JSON de suggestions")
    parser.add_argument("--ground-truth", "-g", required=True,
                       help="Fichier JSON ground truth")
    parser.add_argument("--output", "-o", default="evaluation_report.json",
                       help="Fichier de sortie du rapport")

    args = parser.parse_args()

    # Charger le ground truth
    with open(args.ground_truth, 'r', encoding='utf-8') as f:
        ground_truth_data = json.load(f)

    # Index par binaire
    gt_by_binary = {}
    for binary in ground_truth_data.get('binaries', []):
        # Matcher par nom partiel
        binary_name = binary['binary'].replace('.exe', '')
        gt_by_binary[binary_name] = binary

    # Evaluer chaque fichier de suggestions
    evaluations = []

    for suggestions_file in args.suggestions:
        # Trouver le ground truth correspondant
        file_stem = Path(suggestions_file).stem

        gt = None
        for key in gt_by_binary:
            if key in file_stem:
                gt = gt_by_binary[key]
                break

        if gt is None:
            print(f"[!] Ground truth non trouve pour: {suggestions_file}")
            continue

        print(f"[*] Evaluation de: {suggestions_file}")
        eval_result = evaluate_binary(suggestions_file, gt)
        evaluations.append(eval_result)

    # Generer le rapport
    if evaluations:
        report = generate_report(evaluations, args.output)
        print_summary(report)
        print(f"\n[+] Rapport sauvegarde: {args.output}")
    else:
        print("[!] Aucune evaluation effectuee")


if __name__ == "__main__":
    main()
