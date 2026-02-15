"""
Pipeline Principal - Amelioration automatique Ghidra via LLM

Ce script orchestre le processus complet:
1. Extraction des fonctions depuis Ghidra (mode headless)
2. Analyse par LLM (Ollama)
3. Reinjection des annotations dans Ghidra

Usage:
    python pipeline.py --binary <chemin_binaire> --ghidra <chemin_ghidra> [options]

Exemple:
    python pipeline.py --binary test.exe --ghidra "C:/ghidra" --model codellama --task full
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ollama_client import OllamaClient, TaskType, LLMSuggestion


class GhidraLLMPipeline:
    """Pipeline complet d'amelioration Ghidra via LLM"""

    def __init__(self, ghidra_path: str, model: str = "codellama"):
        self.ghidra_path = Path(ghidra_path)
        self.model = model
        self.ollama = OllamaClient(model=model)

        # Chemins Ghidra
        if sys.platform == "win32":
            self.analyze_headless = self.ghidra_path / "support" / "analyzeHeadless.bat"
        else:
            self.analyze_headless = self.ghidra_path / "support" / "analyzeHeadless"

        # Repertoire des scripts Ghidra
        self.ghidra_scripts = Path(__file__).parent.parent / "ghidra_scripts"

        # Repertoire temporaire pour les projets Ghidra
        self.temp_project_dir = Path(__file__).parent.parent / "temp_projects"
        self.temp_project_dir.mkdir(exist_ok=True)

    def verify_setup(self) -> bool:
        """Verifie que tous les composants sont disponibles"""
        errors = []

        # Verifier Ghidra
        if not self.analyze_headless.exists():
            errors.append(f"analyzeHeadless non trouve: {self.analyze_headless}")

        # Verifier les scripts Ghidra
        extract_script = self.ghidra_scripts / "extract_functions.py"
        inject_script = self.ghidra_scripts / "inject_annotations.py"

        if not extract_script.exists():
            errors.append(f"Script d'extraction non trouve: {extract_script}")
        if not inject_script.exists():
            errors.append(f"Script d'injection non trouve: {inject_script}")

        # Verifier Ollama
        if not self.ollama.check_connection():
            errors.append("Ollama n'est pas accessible (http://localhost:11434)")

        if errors:
            print("[!] Erreurs de configuration:")
            for err in errors:
                print(f"    - {err}")
            return False

        # Verifier le modele
        available_models = self.ollama.list_models()
        print(f"[*] Modeles Ollama disponibles: {available_models}")

        if self.model not in available_models and not any(self.model in m for m in available_models):
            print(f"[!] Modele '{self.model}' non trouve. Telechargez-le avec: ollama pull {self.model}")
            return False

        print("[+] Configuration verifiee avec succes")
        return True

    def extract_functions(self, binary_path: str, output_json: str) -> bool:
        """Execute l'extraction Ghidra en mode headless"""
        binary_path = Path(binary_path).resolve()
        project_name = binary_path.stem + "_project"

        print(f"[*] Extraction des fonctions de: {binary_path}")

        cmd = [
            str(self.analyze_headless),
            str(self.temp_project_dir),
            project_name,
            "-import", str(binary_path),
            "-postScript", str(self.ghidra_scripts / "extract_functions.py"),
            "-deleteProject",  # Nettoyer apres
            "-scriptPath", str(self.ghidra_scripts)
        ]

        print(f"[*] Commande: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            if result.returncode != 0:
                print(f"[!] Erreur Ghidra:\n{result.stderr}")
                return False

            # Trouver le fichier JSON genere
            expected_json = binary_path.parent / (binary_path.name + "_extracted.json")

            if expected_json.exists():
                # Copier vers la destination
                import shutil
                shutil.copy(expected_json, output_json)
                print(f"[+] Extraction sauvegardee: {output_json}")
                return True
            else:
                print(f"[!] Fichier d'extraction non trouve: {expected_json}")
                return False

        except subprocess.TimeoutExpired:
            print("[!] Timeout lors de l'extraction Ghidra")
            return False
        except Exception as e:
            print(f"[!] Erreur: {e}")
            return False

    def analyze_with_llm(self, extracted_json: str, task: TaskType = TaskType.FULL_ANALYSIS) -> list:
        """Analyse les fonctions extraites avec le LLM"""
        print(f"[*] Chargement des fonctions depuis: {extracted_json}")

        with open(extracted_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        functions = data.get("functions", [])
        print(f"[*] {len(functions)} fonctions a analyser")

        # Filtrer les fonctions interessantes (pas les stubs systeme)
        filtered_functions = []
        for func in functions:
            name = func.get("name", "")
            # Ignorer les fonctions systeme evidentes
            if name.startswith("_") and not name.startswith("FUN_"):
                continue
            if func.get("size", 0) < 10:  # Ignorer les fonctions trop petites
                continue
            if not func.get("decompiled_code"):
                continue
            filtered_functions.append(func)

        print(f"[*] {len(filtered_functions)} fonctions filtrees pour analyse")

        # Analyser avec le LLM
        suggestions = self.ollama.analyze_batch(filtered_functions, task)

        return suggestions

    def save_suggestions(self, suggestions: list, output_path: str):
        """Sauvegarde les suggestions en JSON"""
        data = []
        for s in suggestions:
            if isinstance(s, LLMSuggestion):
                data.append(asdict(s))
            else:
                data.append(s)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[+] Suggestions sauvegardees: {output_path}")

    def inject_annotations(self, binary_path: str, suggestions_json: str) -> bool:
        """Reinjecte les annotations dans Ghidra"""
        binary_path = Path(binary_path).resolve()
        project_name = binary_path.stem + "_annotated"

        print(f"[*] Injection des annotations dans: {binary_path}")

        cmd = [
            str(self.analyze_headless),
            str(self.temp_project_dir),
            project_name,
            "-import", str(binary_path),
            "-postScript", str(self.ghidra_scripts / "inject_annotations.py"),
            str(suggestions_json),
            "-scriptPath", str(self.ghidra_scripts)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                print(f"[!] Erreur Ghidra:\n{result.stderr}")
                return False

            print("[+] Annotations injectees avec succes")
            return True

        except Exception as e:
            print(f"[!] Erreur: {e}")
            return False

    def run_full_pipeline(self, binary_path: str, output_dir: str, task: TaskType = TaskType.FULL_ANALYSIS) -> dict:
        """Execute le pipeline complet"""
        binary_path = Path(binary_path).resolve()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        binary_name = binary_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Fichiers intermediaires
        extracted_json = output_dir / f"{binary_name}_extracted_{timestamp}.json"
        suggestions_json = output_dir / f"{binary_name}_suggestions_{timestamp}.json"

        results = {
            "binary": str(binary_path),
            "timestamp": timestamp,
            "model": self.model,
            "task": task.value,
            "steps": {}
        }

        # Etape 1: Extraction
        print("\n" + "="*60)
        print("ETAPE 1: Extraction Ghidra")
        print("="*60)

        start_time = time.time()
        if self.extract_functions(str(binary_path), str(extracted_json)):
            results["steps"]["extraction"] = {
                "success": True,
                "output": str(extracted_json),
                "duration": time.time() - start_time
            }
        else:
            results["steps"]["extraction"] = {"success": False}
            print("[!] Echec de l'extraction")
            return results

        # Etape 2: Analyse LLM
        print("\n" + "="*60)
        print("ETAPE 2: Analyse LLM")
        print("="*60)

        start_time = time.time()
        suggestions = self.analyze_with_llm(str(extracted_json), task)

        if suggestions:
            self.save_suggestions(suggestions, str(suggestions_json))
            results["steps"]["llm_analysis"] = {
                "success": True,
                "functions_analyzed": len(suggestions),
                "output": str(suggestions_json),
                "duration": time.time() - start_time
            }
        else:
            results["steps"]["llm_analysis"] = {"success": False}
            print("[!] Echec de l'analyse LLM")
            return results

        # Etape 3: Injection
        print("\n" + "="*60)
        print("ETAPE 3: Injection des annotations")
        print("="*60)

        start_time = time.time()
        if self.inject_annotations(str(binary_path), str(suggestions_json)):
            results["steps"]["injection"] = {
                "success": True,
                "duration": time.time() - start_time
            }
        else:
            results["steps"]["injection"] = {"success": False}

        # Sauvegarder le rapport
        report_path = output_dir / f"{binary_name}_report_{timestamp}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

        print(f"\n[+] Rapport sauvegarde: {report_path}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline d'amelioration Ghidra via LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
    # Analyse complete
    python pipeline.py --binary test.exe --ghidra "C:/ghidra_12.0" --model codellama

    # Renommage uniquement
    python pipeline.py --binary test.exe --ghidra "C:/ghidra_12.0" --task rename

    # Avec modele specifique
    python pipeline.py --binary test.exe --ghidra "C:/ghidra_12.0" --model llama3.2
        """
    )

    parser.add_argument("--binary", "-b", required=True, help="Chemin du binaire a analyser")
    parser.add_argument("--ghidra", "-g", required=True, help="Chemin d'installation de Ghidra")
    parser.add_argument("--model", "-m", default="deepseek-coder-6.7b-instruct", help="Modele LM Studio (defaut: deepseek-coder-6.7b-instruct)")
    parser.add_argument("--task", "-t", default="full",
                       choices=["rename", "detect_apis", "comments", "full"],
                       help="Type de tache (defaut: full)")
    parser.add_argument("--output", "-o", default="./results", help="Repertoire de sortie")
    parser.add_argument("--verify-only", action="store_true", help="Verifier la configuration uniquement")

    args = parser.parse_args()

    # Mapper la tache
    task_map = {
        "rename": TaskType.RENAME_FUNCTION,
        "detect_apis": TaskType.DETECT_APIS,
        "comments": TaskType.GENERATE_COMMENTS,
        "full": TaskType.FULL_ANALYSIS
    }

    pipeline = GhidraLLMPipeline(args.ghidra, args.model)

    if not pipeline.verify_setup():
        sys.exit(1)

    if args.verify_only:
        print("[+] Configuration OK")
        sys.exit(0)

    # Verifier que le binaire existe
    if not os.path.exists(args.binary):
        print(f"[!] Binaire non trouve: {args.binary}")
        sys.exit(1)

    # Executer le pipeline
    results = pipeline.run_full_pipeline(
        args.binary,
        args.output,
        task_map[args.task]
    )

    # Afficher le resume
    print("\n" + "="*60)
    print("RESUME")
    print("="*60)
    for step, info in results.get("steps", {}).items():
        status = "OK" if info.get("success") else "ECHEC"
        duration = info.get("duration", 0)
        print(f"  {step}: {status} ({duration:.1f}s)")


if __name__ == "__main__":
    main()
