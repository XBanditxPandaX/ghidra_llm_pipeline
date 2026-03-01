"""
Multi-pass iteratif - Enrichissement progressif du contexte entre les passes

Ce script implemente une analyse multi-passes:
1. Passe 1 (Renommage): identifie les noms de fonctions
2. Passe 2 (Analyse complete): analyse approfondie avec les noms enrichis
3. Passe 3 (Commentaires): generation de commentaires avec contexte maximal

Chaque passe enrichit le JSON extrait pour la passe suivante.
"""

import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from dataclasses import asdict
from typing import Dict, List, Optional

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLM_client import LMStudioClient, TaskType, LLMSuggestion
from evaluate_results import evaluate_binary, evaluate_function, BinaryEvaluation
from config_loader import get_model, get_lm_studio_url


def filter_functions(functions: List[Dict]) -> List[Dict]:
    """
    Filtre les fonctions interessantes (pas les stubs systeme).
    Logique partagee avec pipeline.py.
    """
    filtered = []
    for func in functions:
        name = func.get("name", "")
        # Ignorer les fonctions systeme evidentes
        if name.startswith("_") and not name.startswith("FUN_"):
            continue
        if func.get("size", 0) < 10:
            continue
        if not func.get("decompiled_code"):
            continue
        filtered.append(func)
    return filtered


def enrich_extracted_json(extracted_data: dict, suggestions: list) -> dict:
    """
    Enrichit le JSON extrait avec les suggestions du LLM.

    1. Construit name_map {ancien_nom: nouveau_nom} depuis suggestions (confidence >= 0.5)
    2. Deep copy de extracted_data
    3. Pour chaque fonction:
       - Renomme func["name"] si dans name_map
       - Met a jour called_functions[].name
       - Met a jour calling_functions[].name
       - re.sub ancien_nom -> nouveau_nom dans decompiled_code
    4. Retourne la copie enrichie
    """
    # 1. Construire le mapping des renommages
    name_map = {}
    for s in suggestions:
        if isinstance(s, LLMSuggestion):
            s_dict = asdict(s)
        else:
            s_dict = s

        original = s_dict.get('original_name', '')
        suggested = s_dict.get('suggested_name', '')
        confidence = s_dict.get('confidence', 0)

        if original and suggested and confidence >= 0.5 and original != suggested:
            name_map[original] = suggested

    if not name_map:
        return copy.deepcopy(extracted_data)

    # 2. Deep copy
    enriched = copy.deepcopy(extracted_data)

    # 3. Appliquer les renommages
    for func in enriched.get("functions", []):
        # Renommer la fonction elle-meme
        old_name = func.get("name", "")
        if old_name in name_map:
            # Conserver le nom original (avant toute passe) pour l'evaluation
            if "original_name" not in func:
                func["original_name"] = old_name
            func["name"] = name_map[old_name]

        # Mettre a jour called_functions
        for called in func.get("called_functions", []):
            if called.get("name") in name_map:
                called["name"] = name_map[called["name"]]

        # Mettre a jour calling_functions
        for calling in func.get("calling_functions", []):
            if calling.get("name") in name_map:
                calling["name"] = name_map[calling["name"]]

        # Mettre a jour le code decompile
        code = func.get("decompiled_code", "")
        if code:
            for old, new in name_map.items():
                code = re.sub(r'\b' + re.escape(old) + r'\b', new, code)
            func["decompiled_code"] = code

    return enriched


class MultiPassRunner:
    """Orchestrateur d'analyse multi-passes"""

    def __init__(self, llm_client: LMStudioClient, output_dir: str, ground_truth: dict):
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ground_truth = ground_truth

    def _save_json(self, data, filename: str):
        """Sauvegarde des donnees JSON"""
        path = self.output_dir / filename
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def _suggestions_to_dicts(self, suggestions: List[LLMSuggestion]) -> list:
        """Convertit les suggestions en liste de dicts"""
        return [asdict(s) if isinstance(s, LLMSuggestion) else s for s in suggestions]

    def _evaluate_suggestions(self, suggestions_dicts: list, binary_gt: dict) -> dict:
        """Evalue les suggestions contre le ground truth et retourne les metriques"""
        gt_functions = {f['original_name']: f for f in binary_gt.get('functions', [])}

        metrics_list = []
        for s in suggestions_dicts:
            original_name = s.get('original_name', '')
            if original_name in gt_functions:
                m = evaluate_function(s, gt_functions[original_name])
                metrics_list.append(m)

        if not metrics_list:
            return {
                "functions_evaluated": 0,
                "avg_semantic_score": 0,
                "avg_comment_score": 0,
                "avg_bleu": 0,
                "avg_rougeL": 0,
                "exact_match_rate": 0,
                "hallucination_rate": 0
            }

        n = len(metrics_list)
        exact = sum(1 for m in metrics_list if m.name_exact_match)
        hallucinations = sum(1 for m in metrics_list if m.is_hallucination)

        return {
            "functions_evaluated": n,
            "avg_semantic_score": sum(m.name_semantic_score for m in metrics_list) / n,
            "avg_comment_score": sum(m.comment_keyword_score for m in metrics_list) / n,
            "avg_bleu": sum(m.comment_bleu for m in metrics_list) / n,
            "avg_rouge1": sum(m.comment_rouge1 for m in metrics_list) / n,
            "avg_rouge2": sum(m.comment_rouge2 for m in metrics_list) / n,
            "avg_rougeL": sum(m.comment_rougeL for m in metrics_list) / n,
            "exact_match_rate": exact / n,
            "hallucination_rate": hallucinations / n
        }

    def run(self, extracted_json_path: str, binary_gt: dict) -> dict:
        """
        Execute l'analyse multi-passes sur un binaire.

        Args:
            extracted_json_path: Chemin vers le JSON extrait par Ghidra
            binary_gt: Ground truth pour ce binaire

        Returns:
            dict avec les resultats par passe et les gains
        """
        # Charger le JSON original
        with open(extracted_json_path, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)

        functions = filter_functions(extracted_data.get("functions", []))
        print(f"[*] Multi-pass: {len(functions)} fonctions filtrees")

        # === PASSE 1 : Renommage ===
        print("\n" + "="*50)
        print("PASSE 1 : Renommage")
        print("="*50)

        t1 = time.time()
        pass1_suggestions = self.llm_client.analyze_batch_with_context(functions, TaskType.RENAME_FUNCTION)
        t1_duration = time.time() - t1

        pass1_dicts = self._suggestions_to_dicts(pass1_suggestions)
        self._save_json(pass1_dicts, "pass1_suggestions.json")
        pass1_eval = self._evaluate_suggestions(pass1_dicts, binary_gt)
        pass1_eval["duration"] = t1_duration

        # Enrichir le JSON
        enriched1 = enrich_extracted_json(extracted_data, pass1_suggestions)
        self._save_json(enriched1, "pass1_enriched.json")
        enriched1_functions = filter_functions(enriched1.get("functions", []))

        print(f"[+] Passe 1 terminee: semantic={pass1_eval['avg_semantic_score']:.3f}, "
              f"match={pass1_eval['exact_match_rate']*100:.1f}% ({t1_duration:.1f}s)")

        # === PASSE 2 : Analyse complete ===
        print("\n" + "="*50)
        print("PASSE 2 : Analyse complete")
        print("="*50)

        t2 = time.time()
        pass2_suggestions = self.llm_client.analyze_batch_with_context(enriched1_functions, TaskType.FULL_ANALYSIS)
        t2_duration = time.time() - t2

        pass2_dicts = self._suggestions_to_dicts(pass2_suggestions)
        self._save_json(pass2_dicts, "pass2_suggestions.json")
        pass2_eval = self._evaluate_suggestions(pass2_dicts, binary_gt)
        pass2_eval["duration"] = t2_duration

        # Enrichir le JSON
        enriched2 = enrich_extracted_json(enriched1, pass2_suggestions)
        self._save_json(enriched2, "pass2_enriched.json")
        enriched2_functions = filter_functions(enriched2.get("functions", []))

        print(f"[+] Passe 2 terminee: semantic={pass2_eval['avg_semantic_score']:.3f}, "
              f"BLEU={pass2_eval['avg_bleu']:.3f} ({t2_duration:.1f}s)")

        # === PASSE 3 : Commentaires ===
        print("\n" + "="*50)
        print("PASSE 3 : Commentaires")
        print("="*50)

        t3 = time.time()
        pass3_suggestions = self.llm_client.analyze_batch_with_context(enriched2_functions, TaskType.GENERATE_COMMENTS)
        t3_duration = time.time() - t3

        pass3_dicts = self._suggestions_to_dicts(pass3_suggestions)
        self._save_json(pass3_dicts, "pass3_suggestions.json")
        pass3_eval = self._evaluate_suggestions(pass3_dicts, binary_gt)
        pass3_eval["duration"] = t3_duration

        print(f"[+] Passe 3 terminee: comment={pass3_eval['avg_comment_score']:.3f}, "
              f"ROUGE-L={pass3_eval['avg_rougeL']:.3f} ({t3_duration:.1f}s)")

        # Calculer les gains
        sem1 = pass1_eval['avg_semantic_score']
        sem2 = pass2_eval['avg_semantic_score']

        gains = {
            # Gain semantique : P1 (renommage) -> P2 (analyse complete avec contexte enrichi)
            # P3 est exclue car la tache COMMENTS ne produit pas de suggested_name
            "semantic_score": {
                "pass1": sem1,
                "pass2": sem2,
                "gain_p1_p2": f"{((sem2 - sem1) / sem1 * 100):+.1f}%" if sem1 > 0 else "N/A"
            },
            # Qualite des commentaires : uniquement P3
            "comments_quality": {
                "comment_score": pass3_eval['avg_comment_score'],
                "rougeL": pass3_eval['avg_rougeL'],
                "bleu": pass3_eval['avg_bleu'],
            }
        }

        result = {
            "pass1": pass1_eval,
            "pass2": pass2_eval,
            "pass3": pass3_eval,
            "gains": gains,
            "total_duration": t1_duration + t2_duration + t3_duration
        }

        self._save_json(result, "multipass_results.json")
        return result


def main():
    """Test du multi-pass"""
    import argparse

    parser = argparse.ArgumentParser(description="Analyse multi-passes avec enrichissement iteratif")
    parser.add_argument("--input", "-i", required=True, help="Fichier JSON extrait par Ghidra")
    parser.add_argument("--ground-truth", "-g", required=True, help="Fichier JSON ground truth")
    parser.add_argument("--model", "-m", default=None, help="Modele LM Studio (sinon lu depuis config.json)")
    parser.add_argument("--output", "-o", default="./results/multipass", help="Repertoire de sortie")

    args = parser.parse_args()

    # Resoudre le modele via CLI ou config.json
    model = get_model(args.model)

    # Charger le ground truth
    with open(args.ground_truth, 'r', encoding='utf-8') as f:
        gt_data = json.load(f)

    # Trouver le ground truth du binaire
    input_stem = Path(args.input).stem
    binary_gt = None
    for binary in gt_data.get('binaries', []):
        binary_name = binary['binary'].replace('.exe', '')
        if binary_name in input_stem:
            binary_gt = binary
            break

    if binary_gt is None:
        print(f"[!] Ground truth non trouve pour: {args.input}")
        sys.exit(1)

    # Creer le client et lancer
    client = LMStudioClient(base_url=get_lm_studio_url(), model=model)

    if not client.check_connection():
        print("[!] LM Studio n'est pas accessible. Lancez LM Studio et chargez un modele.")
        sys.exit(1)

    runner = MultiPassRunner(client, args.output, gt_data)
    result = runner.run(args.input, binary_gt)

    # Afficher le resume
    print("\n" + "="*60)
    print("RESUME MULTI-PASS")
    print("="*60)
    gains = result["gains"]
    for metric, values in gains.items():
        print(f"\n{metric}:")
        for k, v in values.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")

    print(f"\nDuree totale: {result['total_duration']:.1f}s")


if __name__ == "__main__":
    main()
