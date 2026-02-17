"""
Script de test rapide pour verifier l'installation

Usage: python quick_test.py [--ghidra "chemin/vers/ghidra"]
"""

import sys
import os
import argparse

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_python():
    """Verifie la version Python"""
    print(f"[*] Python: {sys.version}")
    if sys.version_info < (3, 8):
        print("[!] Python 3.8+ requis")
        return False
    print("[+] Python OK")
    return True


def check_requests():
    """Verifie que requests est installe"""
    try:
        import requests
        print(f"[+] requests {requests.__version__} OK")
        return True
    except ImportError:
        print("[!] requests non installe. Executez: pip install requests")
        return False


def check_nltk():
    """Verifie que nltk et rouge-score sont installes"""
    ok = True
    try:
        import nltk
        print(f"[+] nltk {nltk.__version__} OK")
    except ImportError:
        print("[!] nltk non installe. Executez: pip install nltk")
        ok = False

    try:
        from rouge_score import rouge_scorer
        print("[+] rouge-score OK")
    except ImportError:
        print("[!] rouge-score non installe. Executez: pip install rouge-score")
        ok = False

    return ok


def check_lm_studio():
    """Verifie que LM Studio est accessible"""
    try:
        import requests
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        if response.status_code == 200:
            models = [m["id"] for m in response.json().get("data", [])]
            print(f"[+] LM Studio OK. Modeles: {models}")
            return True
        else:
            print(f"[!] LM Studio repond mais erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"[!] LM Studio non accessible: {e}")
        print("    1. Lancez LM Studio")
        print("    2. Chargez un modele (ex: deepseek-r1-0528-qwen3-8b)")
        print("    3. Demarrez le serveur local (onglet Local Server)")
        return False


def check_ghidra(ghidra_path):
    """Verifie que Ghidra est installe"""
    if not ghidra_path:
        print("[*] Chemin Ghidra non specifie (utilisez --ghidra pour verifier)")
        return True  # On ne bloque pas si non specifie

    if sys.platform == "win32":
        headless = os.path.join(ghidra_path, "support", "analyzeHeadless.bat")
    else:
        headless = os.path.join(ghidra_path, "support", "analyzeHeadless")

    if os.path.exists(headless):
        print(f"[+] Ghidra trouve: {ghidra_path}")
        return True
    else:
        print(f"[!] Ghidra non trouve a: {ghidra_path}")
        print("    Telechargez Ghidra depuis https://ghidra-sre.org/")
        return False


def check_scripts():
    """Verifie que les scripts sont presents"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)

    files_to_check = [
        os.path.join(script_dir, "pipeline.py"),
        os.path.join(script_dir, "LLM_client.py"),
        os.path.join(script_dir, "evaluate_results.py"),
        os.path.join(script_dir, "multipass.py"),
        os.path.join(script_dir, "benchmark.py"),
        os.path.join(parent_dir, "ghidra_scripts", "java", "extract_functions.java"),
        os.path.join(parent_dir, "ghidra_scripts", "java", "inject_annotations.java"),
        os.path.join(parent_dir, "expected_results", "ground_truth.json"),
    ]

    all_ok = True
    for f in files_to_check:
        if os.path.exists(f):
            print(f"[+] {os.path.basename(f)} OK")
        else:
            print(f"[!] Manquant: {os.path.relpath(f, parent_dir)}")
            all_ok = False

    return all_ok


def test_lm_studio_query():
    """Teste une requete LM Studio simple"""
    try:
        import requests

        print("\n[*] Test de requete LM Studio...")

        # Recuperer le premier modele disponible
        models_resp = requests.get("http://localhost:1234/v1/models", timeout=5)
        models = [m["id"] for m in models_resp.json().get("data", [])]
        model = models[0] if models else "default"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "What does 'malloc' do in C? Answer in one sentence."}
            ],
            "max_tokens": 50,
            "stream": False
        }

        response = requests.post(
            "http://localhost:1234/v1/chat/completions",
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"[+] Reponse LM Studio ({model}): {result[:200]}")
            return True
        else:
            print(f"[!] Erreur LM Studio: {response.status_code}")
            return False

    except Exception as e:
        print(f"[!] Erreur: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test de l'environnement pipeline Ghidra + LLM")
    parser.add_argument("--ghidra", "-g", default=None, help="Chemin d'installation de Ghidra (sinon lu depuis config.json)")
    args = parser.parse_args()

    # Resoudre le chemin Ghidra via CLI ou config.json
    ghidra_path = args.ghidra
    if not ghidra_path:
        try:
            from config_loader import load_config
            config = load_config()
            ghidra_path = config.get("ghidra_path", "")
            if ghidra_path and "chemin/vers" not in ghidra_path:
                print(f"[*] Chemin Ghidra lu depuis config.json: {ghidra_path}")
        except Exception:
            pass

    print("="*60)
    print("TEST DE L'ENVIRONNEMENT - Pipeline Ghidra + LLM")
    print("="*60)

    results = []

    print("\n--- Verification Python ---")
    results.append(("Python", check_python()))

    print("\n--- Verification des dependances ---")
    results.append(("requests", check_requests()))
    results.append(("nltk/rouge", check_nltk()))

    print("\n--- Verification LM Studio ---")
    results.append(("LM Studio", check_lm_studio()))

    print("\n--- Verification Ghidra ---")
    results.append(("Ghidra", check_ghidra(ghidra_path)))

    print("\n--- Verification des scripts ---")
    results.append(("Scripts", check_scripts()))

    # Test LM Studio uniquement si disponible
    if results[3][1]:  # LM Studio OK
        results.append(("Test LM Studio", test_lm_studio_query()))

    # Resume
    print("\n" + "="*60)
    print("RESUME")
    print("="*60)

    all_ok = True
    for name, status in results:
        symbol = "[+]" if status else "[!]"
        print(f"{symbol} {name}: {'OK' if status else 'ECHEC'}")
        if not status:
            all_ok = False

    if all_ok:
        print("\n[+] Tout est pret! Vous pouvez executer le pipeline.")
        print("\nCommande de test:")
        print('  python scripts/pipeline.py --binary test_binaries/bin/test1_buffer.exe --ghidra "chemin/vers/ghidra"')
    else:
        print("\n[!] Certains composants ne sont pas prets.")
        print("    Consultez le TUTORIEL.md pour les instructions d'installation.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
