"""
Script de test du pipeline SANS Ghidra
Utilise les fichiers d'extraction simules pour tester l'analyse LLM

Usage: python test_without_ghidra.py [--model deepseek-coder-6.7b-instruct]
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLM_client import LLMClient, TaskType, LLMSuggestion
from dataclasses import asdict


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test du pipeline sans Ghidra")
    parser.add_argument("--model", "-m", default="deepseek-coder-6.7b-instruct", help="Modele LM Studio")
    parser.add_argument("--input", "-i", default=None, help="Fichier JSON d'extraction (optionnel)")
    parser.add_argument("--task", "-t", default="full",
                       choices=["rename", "detect_apis", "comments", "full"])
    args = parser.parse_args()

    # Mapper les taches
    task_map = {
        "rename": TaskType.RENAME_FUNCTION,
        "detect_apis": TaskType.DETECT_APIS,
        "comments": TaskType.GENERATE_COMMENTS,
        "full": TaskType.FULL_ANALYSIS
    }

    # Repertoires
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    simulated_dir = project_dir / "test_binaries" / "simulated_extraction"
    results_dir = project_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Trouver les fichiers d'extraction
    if args.input:
        extraction_files = [Path(args.input)]
    else:
        extraction_files = list(simulated_dir.glob("*_extracted.json"))

    if not extraction_files:
        print("[!] Aucun fichier d'extraction trouve!")
        print(f"    Cherche dans: {simulated_dir}")
        return 1

    print("="*60)
    print("TEST DU PIPELINE SANS GHIDRA")
    print("="*60)
    print(f"Modele: {args.model}")
    print(f"Tache: {args.task}")
    print(f"Fichiers: {len(extraction_files)}")

    # Initialiser le client LM Studio (LLMClient est un alias)
    client = LLMClient(model=args.model)

    print("\n[*] Verification de LM Studio...")
    if not client.check_connection():
        print("[!] LM Studio n'est pas accessible!")
        print("    1. Lancez LM Studio")
        print("    2. Chargez le modele deepseek-coder")
        print("    3. Demarrez le serveur local")
        return 1

    print("[+] LM Studio OK")

    # Verifier le modele
    models = client.list_models()
    print(f"[*] Modeles disponibles: {models}")

    # Traiter chaque fichier
    for extraction_file in extraction_files:
        print(f"\n{'='*60}")
        print(f"Analyse de: {extraction_file.name}")
        print("="*60)

        with open(extraction_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        functions = data.get("functions", [])
        print(f"[*] {len(functions)} fonctions trouvees")

        # Analyser chaque fonction
        suggestions = []

        for i, func in enumerate(functions):
            name = func.get("name", "unknown")
            print(f"\n[{i+1}/{len(functions)}] Analyse de {name}...")

            suggestion = client.analyze_function(func, task_map[args.task])

            if suggestion:
                suggestions.append(asdict(suggestion))
                print(f"    -> Suggestion: {suggestion.suggested_name}")
                print(f"    -> Confiance: {suggestion.confidence}")
                if suggestion.detected_apis:
                    print(f"    -> APIs: {suggestion.detected_apis}")
            else:
                print(f"    [!] Pas de suggestion")

        # Sauvegarder les resultats
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = results_dir / f"{extraction_file.stem}_suggestions_{timestamp}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Resultats sauvegardes: {output_file}")

        # Afficher un resume
        print(f"\n--- Resume pour {extraction_file.name} ---")
        print(f"Fonctions analysees: {len(functions)}")
        print(f"Suggestions generees: {len(suggestions)}")

        if suggestions:
            avg_confidence = sum(s.get('confidence', 0) for s in suggestions) / len(suggestions)
            print(f"Confiance moyenne: {avg_confidence:.2f}")

    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60)
    print(f"Resultats dans: {results_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
