"""
Pipeline Principal - Amelioration automatique Ghidra via LLM

Ce script orchestre le processus complet:
1. Extraction des fonctions depuis Ghidra (mode headless)
2. Analyse par LLM (LM Studio)
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

from LLM_client import LMStudioClient, TaskType, LLMSuggestion


class GhidraLLMPipeline:
    """Pipeline complet d'amelioration Ghidra via LLM"""

    def __init__(self, ghidra_path: str, model: str = "codellama"):
        self.ghidra_path = Path(ghidra_path)
        self.model = model
        self.llm_client = LMStudioClient(model=model)

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

        # Verifier les scripts Ghidra (Python prefere, Java en fallback)
        extract_py = self.ghidra_scripts / "python" / "extract_functions.py"
        extract_java = self.ghidra_scripts / "java" / "extract_functions.java"
        inject_py = self.ghidra_scripts / "python" / "inject_annotations.py"
        inject_java = self.ghidra_scripts / "java" / "inject_annotations.java"

        if not extract_py.exists() and not extract_java.exists():
            errors.append(f"Script d'extraction non trouve dans: {self.ghidra_scripts}")
        if not inject_py.exists() and not inject_java.exists():
            errors.append(f"Script d'injection non trouve dans: {self.ghidra_scripts}")

        # Verifier Ollama
        if not self.llm_client.check_connection():
            errors.append("LM Studio n'est pas accessible (http://localhost:1234)")

        if errors:
            print("[!] Erreurs de configuration:")
            for err in errors:
                print(f"    - {err}")
            return False

        # Verifier le modele
        available_models = self.llm_client.list_models()
        print(f"[*] Modeles LM Studio disponibles: {available_models}")

        if self.model not in available_models and not any(self.model in m for m in available_models):
            print(f"[!] Modele '{self.model}' non trouve. Chargez-le dans LM Studio.")
            return False

        print("[+] Configuration verifiee avec succes")
        return True

    def _get_output_dirs(self, binary_path: Path) -> dict:
        """Calcule les repertoires de sortie a partir du chemin du binaire.

        Structure:
            test_binaries/
                bin/                 <- binaires
                extracted_files/     <- JSONs extraits par Ghidra
                suggested_files/     <- suggestions LLM
                report_files/        <- rapports
        """
        base_dir = binary_path.parent.parent  # test_binaries/
        dirs = {
            "extracted": base_dir / "extracted_files",
            "suggested": base_dir / "suggested_files",
            "reports":   base_dir / "report_files",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    def extract_functions(self, binary_path: str, output_json: str) -> bool:
        """Execute l'extraction Ghidra en mode headless.
        Le JSON est sauvegarde directement dans extracted_files/ par le script Ghidra.
        output_json est le chemin attendu dans extracted_files/.
        """
        binary_path = Path(binary_path).resolve()
        project_name = binary_path.stem + "_project"

        print(f"[*] Extraction des fonctions de: {binary_path}")

        # Utiliser le script Java (Ghidra 12+ ne supporte plus Jython en headless)
        extract_script = self.ghidra_scripts / "java" / "extract_functions.java"
        if not extract_script.exists():
            extract_script = self.ghidra_scripts / "python" / "extract_functions.py"

        cmd = [
            str(self.analyze_headless),
            str(self.temp_project_dir),
            project_name,
            "-import", str(binary_path),
            "-postScript", str(extract_script),
            "-deleteProject",
            "-scriptPath", str(extract_script.parent)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            # Afficher uniquement les lignes de notre script et les erreurs critiques
            if result.stdout:
                for line in result.stdout.splitlines():
                    # Lignes de notre script (extract_functions.java> [...])
                    if 'extract_functions' in line and '>' in line:
                        # Extraire juste le message apres ">"
                        msg = line.split('>', 1)[-1].strip()
                        if msg:
                            print(f"    {msg}")
                    # Erreurs critiques (pas DWARF, pas les paths)
                    elif 'SCRIPT ERROR' in line or 'ClassNotFoundException' in line:
                        print(f"    [!] {line.strip()}")

            if result.returncode != 0:
                print(f"[!] Erreur Ghidra (code {result.returncode}):")
                if result.stderr:
                    print(result.stderr[:2000])
                return False

            # Verifier que le fichier a ete genere a l'emplacement attendu
            output_path = Path(output_json)
            if output_path.exists():
                print(f"[+] Extraction sauvegardee: {output_path}")
                return True

            # Recherche de secours si le script Ghidra a ecrit ailleurs
            search_locations = [
                binary_path.parent.parent / "extracted_files" / (binary_path.name + "_extracted.json"),
                binary_path.parent / (binary_path.name + "_extracted.json"),
                binary_path.parent / (binary_path.stem + "_extracted.json"),
                Path.cwd() / (binary_path.name + "_extracted.json"),
                self.temp_project_dir / (binary_path.name + "_extracted.json"),
            ]

            found_json = None
            for candidate in search_locations:
                if candidate.exists() and candidate != output_path:
                    found_json = candidate
                    break

            if not found_json:
                project_root = Path(__file__).parent.parent
                for match in project_root.glob(f"**/*{binary_path.stem}*extracted*.json"):
                    found_json = match
                    break

            if found_json:
                import shutil
                shutil.move(str(found_json), str(output_path))
                print(f"[+] Extraction trouvee: {found_json}")
                print(f"[+] Deplacee vers: {output_path}")
                return True
            else:
                print(f"[!] Fichier d'extraction non trouve.")
                print(f"    Emplacements verifies:")
                for loc in search_locations:
                    print(f"      - {loc} {'(existe)' if loc.exists() else '(absent)'}")
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
        suggestions = self.llm_client.analyze_batch(filtered_functions, task)

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
        """Reinjecte les annotations dans Ghidra.
        suggestions_json: chemin vers le fichier dans suggested_files/
        """
        binary_path = Path(binary_path).resolve()
        suggestions_json = Path(suggestions_json).resolve()
        project_name = binary_path.stem + "_annotated"

        print(f"[*] Injection des annotations dans: {binary_path.name}")

        inject_script = self.ghidra_scripts / "java" / "inject_annotations.java"
        if not inject_script.exists():
            inject_script = self.ghidra_scripts / "python" / "inject_annotations.py"

        cmd = [
            str(self.analyze_headless),
            str(self.temp_project_dir),
            project_name,
            "-import", str(binary_path),
            "-postScript", str(inject_script),
            str(suggestions_json),
            "-deleteProject",
            "-scriptPath", str(inject_script.parent)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes max
            )

            # Afficher uniquement les lignes de notre script
            if result.stdout:
                for line in result.stdout.splitlines():
                    if 'inject_annotations' in line and '>' in line:
                        msg = line.split('>', 1)[-1].strip()
                        if msg:
                            print(f"    {msg}")
                    elif 'SCRIPT ERROR' in line or 'ClassNotFoundException' in line:
                        print(f"    [!] {line.strip()}")

            if result.returncode != 0:
                print(f"[!] Erreur Ghidra (code {result.returncode})")
                return False

            print("[+] Annotations injectees avec succes")
            return True

        except subprocess.TimeoutExpired:
            print("[!] Timeout lors de l'injection (600s)")
            return False
        except Exception as e:
            print(f"[!] Erreur: {e}")
            return False

    def run_full_pipeline(self, binary_path: str, output_dir: str = None, task: TaskType = TaskType.FULL_ANALYSIS) -> dict:
        """Execute le pipeline complet.

        Structure de sortie (relative au dossier parent de bin/):
            extracted_files/   <- JSONs extraits par Ghidra
            suggested_files/   <- suggestions LLM
            report_files/      <- rapports
        """
        binary_path = Path(binary_path).resolve()
        binary_name = binary_path.stem

        # Calculer les repertoires de sortie
        dirs = self._get_output_dirs(binary_path)

        # Fichiers de sortie (noms simples, sans timestamp)
        extracted_json = dirs["extracted"] / f"{binary_path.name}_extracted.json"
        suggestions_json = dirs["suggested"] / f"{binary_name}_suggestions.json"
        report_path = dirs["reports"] / f"{binary_name}_report.json"

        results = {
            "binary": str(binary_path),
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
