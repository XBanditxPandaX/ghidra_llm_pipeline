"""
Benchmark comparatif multi-modeles

Boucle sur plusieurs modeles LM Studio, execute single-pass et multi-pass
sur chaque binaire extrait, puis genere un rapport comparatif.

Usage:
    python scripts/benchmark.py \
        --models "deepseek-r1-0528-qwen3-8b" "qwen2.5-coder-7b-instruct" "codellama-7b-instruct" \
        --inputs test_binaries/bin/*_extracted.json \
        --ground-truth expected_results/ground_truth.json \
        --output results/benchmark/ \
        --multipass
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dataclasses import asdict

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLM_client import LMStudioClient, TaskType, LLMSuggestion
from evaluate_results import evaluate_function
from multipass import MultiPassRunner, filter_functions
from config_loader import get_lm_studio_url


def evaluate_suggestions_vs_gt(suggestions_dicts: list, binary_gt: dict) -> dict:
    """Evalue les suggestions contre le ground truth"""
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
            "exact_match_rate": 0, "avg_semantic_score": 0,
            "avg_comment_score": 0, "avg_bleu": 0,
            "avg_rouge1": 0, "avg_rouge2": 0, "avg_rougeL": 0,
            "hallucination_rate": 0, "avg_time_per_function": 0
        }

    n = len(metrics_list)
    exact = sum(1 for m in metrics_list if m.name_exact_match)
    hallucinations = sum(1 for m in metrics_list if m.is_hallucination)

    return {
        "functions_evaluated": n,
        "exact_match_rate": exact / n,
        "avg_semantic_score": sum(m.name_semantic_score for m in metrics_list) / n,
        "avg_comment_score": sum(m.comment_keyword_score for m in metrics_list) / n,
        "avg_bleu": sum(m.comment_bleu for m in metrics_list) / n,
        "avg_rouge1": sum(m.comment_rouge1 for m in metrics_list) / n,
        "avg_rouge2": sum(m.comment_rouge2 for m in metrics_list) / n,
        "avg_rougeL": sum(m.comment_rougeL for m in metrics_list) / n,
        "hallucination_rate": hallucinations / n,
    }


def find_binary_gt(gt_data: dict, input_path: str) -> dict:
    """Trouve le ground truth correspondant a un fichier d'entree"""
    input_stem = Path(input_path).stem
    for binary in gt_data.get('binaries', []):
        binary_name = binary['binary'].replace('.exe', '')
        if binary_name in input_stem:
            return binary
    return None


def print_single_pass_table(results: dict):
    """Affiche le tableau comparatif single-pass"""
    print("\n" + "="*90)
    print("BENCHMARK SINGLE-PASS")
    print("="*90)

    header = f"{'Modele':<30} | {'Match%':>7} | {'Semantic':>8} | {'BLEU':>6} | {'ROUGE-L':>7} | {'Halluc%':>7} | {'Temps/fn':>8}"
    sep = "-"*30 + "-+-" + "-"*7 + "-+-" + "-"*8 + "-+-" + "-"*6 + "-+-" + "-"*7 + "-+-" + "-"*7 + "-+-" + "-"*8
    print(header)
    print(sep)

    for model_name, model_data in results.items():
        sp = model_data.get("single_pass_avg", {})
        match_pct = sp.get("exact_match_rate", 0) * 100
        semantic = sp.get("avg_semantic_score", 0)
        bleu = sp.get("avg_bleu", 0)
        rougeL = sp.get("avg_rougeL", 0)
        halluc = sp.get("hallucination_rate", 0) * 100
        time_fn = sp.get("avg_time_per_function", 0)

        print(f"{model_name:<30} | {match_pct:>6.1f}% | {semantic:>8.4f} | {bleu:>6.4f} | {rougeL:>7.4f} | {halluc:>6.1f}% | {time_fn:>7.1f}s")


def print_multipass_table(results: dict):
    """Affiche le tableau comparatif multi-pass en deux sections."""

    # --- Section 1 : gain semantique P1 -> P2 ---
    print("\n" + "="*65)
    print("MULTI-PASS : Gain semantique (Passe 1 Renommage -> Passe 2 Analyse)")
    print("="*65)
    header = f"{'Modele':<30} | {'Pass 1':>7} | {'Pass 2':>7} | {'Gain':>8}"
    sep    = "-"*30 + "-+-" + "-"*7 + "-+-" + "-"*7 + "-+-" + "-"*8
    print(header)
    print(sep)

    for model_name, model_data in results.items():
        mp = model_data.get("multipass_avg", {})
        if not mp:
            continue
        sem = mp.get("semantic", {})
        p1       = sem.get("pass1", 0)
        p2       = sem.get("pass2", 0)
        gain_str = sem.get("gain_p1_p2", "N/A")
        print(f"{model_name:<30} | {p1:>7.4f} | {p2:>7.4f} | {gain_str:>8}")

    # --- Section 2 : qualite des commentaires (Passe 3) ---
    print("\n" + "="*65)
    print("MULTI-PASS : Qualite des commentaires (Passe 3)")
    print("="*65)
    header = f"{'Modele':<30} | {'Comment':>7} | {'ROUGE-L':>7} | {'BLEU':>6}"
    sep    = "-"*30 + "-+-" + "-"*7 + "-+-" + "-"*7 + "-+-" + "-"*6
    print(header)
    print(sep)

    for model_name, model_data in results.items():
        mp = model_data.get("multipass_avg", {})
        if not mp:
            continue
        cq      = mp.get("comments_quality", {})
        comment = cq.get("comment_score", 0)
        rougeL  = cq.get("rougeL", 0)
        bleu    = cq.get("bleu", 0)
        print(f"{model_name:<30} | {comment:>7.4f} | {rougeL:>7.4f} | {bleu:>6.4f}")


def run_benchmark(models: list, input_files: list, gt_data: dict,
                  output_dir: str, do_multipass: bool = True) -> dict:
    """Execute le benchmark complet"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for model_name in models:
        print("\n" + "#"*70)
        print(f"# MODELE: {model_name}")
        print("#"*70)

        # Verifier la connexion
        client = LMStudioClient(base_url=get_lm_studio_url(), model=model_name)

        if not client.check_connection():
            print(f"\n[!] LM Studio n'est pas accessible.")
            print(f"    Chargez le modele '{model_name}' dans LM Studio.")
            input("    Appuyez sur Entree quand le modele est charge...")

            if not client.check_connection():
                print(f"[!] Toujours inaccessible, on passe au modele suivant.")
                continue

        # Verifier que le modele est charge
        available = client.list_models()
        print(f"[*] Modeles disponibles: {available}")

        model_results = {
            "model": model_name,
            "single_pass": {},
            "multipass": {},
        }

        model_output = output_dir / model_name.replace("/", "_")

        for input_file in input_files:
            input_path = Path(input_file)
            if not input_path.exists():
                print(f"[!] Fichier non trouve: {input_file}")
                continue

            binary_name = input_path.stem
            print(f"\n[*] Analyse de: {binary_name}")

            # Trouver le ground truth
            binary_gt = find_binary_gt(gt_data, str(input_path))
            if binary_gt is None:
                print(f"[!] Ground truth non trouve pour: {binary_name}")
                continue

            # Charger les fonctions
            with open(input_file, 'r', encoding='utf-8') as f:
                extracted_data = json.load(f)

            functions = filter_functions(extracted_data.get("functions", []))
            print(f"[*] {len(functions)} fonctions filtrees")

            # === Single-pass ===
            print(f"\n--- Single-pass: {binary_name} ---")
            single_dir = model_output / "single"
            single_dir.mkdir(parents=True, exist_ok=True)

            t_start = time.time()
            suggestions = client.analyze_batch_with_context(functions, TaskType.FULL_ANALYSIS)
            t_duration = time.time() - t_start

            suggestions_dicts = [asdict(s) if isinstance(s, LLMSuggestion) else s for s in suggestions]

            # Sauvegarder
            suggestions_path = single_dir / f"{binary_name}_suggestions.json"
            with open(suggestions_path, 'w', encoding='utf-8') as f:
                json.dump(suggestions_dicts, f, indent=2, ensure_ascii=False)

            # Evaluer
            single_eval = evaluate_suggestions_vs_gt(suggestions_dicts, binary_gt)
            single_eval["duration"] = t_duration
            single_eval["avg_time_per_function"] = t_duration / len(functions) if functions else 0

            model_results["single_pass"][binary_name] = single_eval
            print(f"[+] Single-pass: semantic={single_eval['avg_semantic_score']:.3f}, "
                  f"match={single_eval['exact_match_rate']*100:.1f}%, "
                  f"BLEU={single_eval['avg_bleu']:.3f} ({t_duration:.1f}s)")

            # === Multi-pass ===
            if do_multipass:
                print(f"\n--- Multi-pass: {binary_name} ---")
                mp_dir = model_output / "multipass" / binary_name
                mp_dir.mkdir(parents=True, exist_ok=True)

                runner = MultiPassRunner(client, str(mp_dir), gt_data)
                mp_result = runner.run(str(input_path), binary_gt)
                model_results["multipass"][binary_name] = mp_result

        # Calculer les moyennes pour ce modele
        sp_evals = list(model_results["single_pass"].values())
        if sp_evals:
            model_results["single_pass_avg"] = {
                "exact_match_rate": sum(e["exact_match_rate"] for e in sp_evals) / len(sp_evals),
                "avg_semantic_score": sum(e["avg_semantic_score"] for e in sp_evals) / len(sp_evals),
                "avg_comment_score": sum(e["avg_comment_score"] for e in sp_evals) / len(sp_evals),
                "avg_bleu": sum(e["avg_bleu"] for e in sp_evals) / len(sp_evals),
                "avg_rouge1": sum(e.get("avg_rouge1", 0) for e in sp_evals) / len(sp_evals),
                "avg_rouge2": sum(e.get("avg_rouge2", 0) for e in sp_evals) / len(sp_evals),
                "avg_rougeL": sum(e["avg_rougeL"] for e in sp_evals) / len(sp_evals),
                "hallucination_rate": sum(e["hallucination_rate"] for e in sp_evals) / len(sp_evals),
                "avg_time_per_function": sum(e["avg_time_per_function"] for e in sp_evals) / len(sp_evals),
            }

        if do_multipass:
            mp_evals = list(model_results["multipass"].values())
            if mp_evals:
                # Moyenne gain semantique P1->P2
                p1_vals = [e["gains"]["semantic_score"].get("pass1", 0) for e in mp_evals]
                p2_vals = [e["gains"]["semantic_score"].get("pass2", 0) for e in mp_evals]
                p1_avg = sum(p1_vals) / len(p1_vals)
                p2_avg = sum(p2_vals) / len(p2_vals)

                # Moyenne qualite commentaires P3
                cq_vals = [e["gains"].get("comments_quality", {}) for e in mp_evals]
                comment_avg = sum(c.get("comment_score", 0) for c in cq_vals) / len(cq_vals)
                rougeL_avg  = sum(c.get("rougeL", 0) for c in cq_vals) / len(cq_vals)
                bleu_avg    = sum(c.get("bleu", 0) for c in cq_vals) / len(cq_vals)

                model_results["multipass_avg"] = {
                    "semantic": {
                        "pass1": p1_avg,
                        "pass2": p2_avg,
                        "gain_p1_p2": f"{((p2_avg - p1_avg) / p1_avg * 100):+.1f}%" if p1_avg > 0 else "N/A"
                    },
                    "comments_quality": {
                        "comment_score": comment_avg,
                        "rougeL": rougeL_avg,
                        "bleu": bleu_avg,
                    }
                }

        all_results[model_name] = model_results

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark comparatif multi-modeles pour le pipeline Ghidra-LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--models", "-m", nargs='+', required=True,
                        help="Liste des modeles LM Studio a tester")
    parser.add_argument("--inputs", "-i", nargs='+', required=True,
                        help="Fichiers JSON extraits par Ghidra")
    parser.add_argument("--ground-truth", "-g", required=True,
                        help="Fichier JSON ground truth")
    parser.add_argument("--output", "-o", default="results/benchmark",
                        help="Repertoire de sortie")
    parser.add_argument("--multipass", action="store_true", default=False,
                        help="Activer l'analyse multi-passes")
    parser.add_argument("--no-multipass", action="store_true", default=False,
                        help="Desactiver l'analyse multi-passes")

    args = parser.parse_args()

    do_multipass = args.multipass and not args.no_multipass

    # Expansion des wildcards (necessaire sous Windows/PowerShell)
    import glob as _glob
    input_files = []
    for pattern in args.inputs:
        expanded = _glob.glob(pattern)
        if expanded:
            input_files.extend(sorted(expanded))
        else:
            input_files.append(pattern)
    args.inputs = input_files

    # Charger le ground truth
    with open(args.ground_truth, 'r', encoding='utf-8') as f:
        gt_data = json.load(f)

    print("[*] Benchmark multi-modeles")
    print(f"    Modeles: {args.models}")
    print(f"    Inputs: {args.inputs}")
    print(f"    Multi-pass: {'Oui' if do_multipass else 'Non'}")
    print(f"    Sortie: {args.output}")

    # Lancer le benchmark
    results = run_benchmark(
        models=args.models,
        input_files=args.inputs,
        gt_data=gt_data,
        output_dir=args.output,
        do_multipass=do_multipass
    )

    # Sauvegarder le rapport JSON (fusion avec resultats existants)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "benchmark_results.json"

    # Charger les resultats existants et fusionner
    existing = {}
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    # Fusion fine : pour chaque modele, on merge single_pass et multipass
    # separement pour ne pas ecraser un run precedent
    for model_name, model_data in results.items():
        if model_name not in existing:
            existing[model_name] = model_data
        else:
            # Fusionner single_pass si present dans le nouveau run
            if model_data.get("single_pass"):
                existing[model_name]["single_pass"] = model_data["single_pass"]
                existing[model_name]["single_pass_avg"] = model_data.get("single_pass_avg", {})
            # Fusionner multipass si present dans le nouveau run
            if model_data.get("multipass"):
                existing[model_name]["multipass"] = model_data["multipass"]
                existing[model_name]["multipass_avg"] = model_data.get("multipass_avg", {})

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Rapport JSON sauvegarde: {report_path}")

    # Afficher les tableaux (tous les resultats cumules)
    print_single_pass_table(existing)

    if do_multipass:
        print_multipass_table(existing)

    print("\n[+] Benchmark termine.")


if __name__ == "__main__":
    main()
