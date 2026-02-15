"""
Script de test rapide pour verifier l'installation

Usage: python quick_test.py
"""

import sys
import os

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
        print("    2. Chargez deepseek-coder-6.7B-instruct-GGUF")
        print("    3. Demarrez le serveur local (onglet Local Server)")
        return False

def check_ghidra():
    """Verifie que Ghidra est installe"""
    # Chemin par defaut
    ghidra_path = r"C:\Users\themi\OneDrive - Institut Catholique de Lille\Bureau\CoursM1\M2\ghidra_12.0.1_PUBLIC"

    headless = os.path.join(ghidra_path, "support", "analyzeHeadless.bat")

    if os.path.exists(headless):
        print(f"[+] Ghidra trouve: {ghidra_path}")
        return True
    else:
        print(f"[!] Ghidra non trouve a: {ghidra_path}")
        return False

def check_scripts():
    """Verifie que les scripts sont presents"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)

    files_to_check = [
        os.path.join(script_dir, "pipeline.py"),
        os.path.join(script_dir, "ollama_client.py"),
        os.path.join(script_dir, "evaluate_results.py"),
        os.path.join(parent_dir, "ghidra_scripts", "extract_functions.py"),
        os.path.join(parent_dir, "ghidra_scripts", "inject_annotations.py"),
        os.path.join(parent_dir, "expected_results", "ground_truth.json"),
    ]

    all_ok = True
    for f in files_to_check:
        if os.path.exists(f):
            print(f"[+] {os.path.basename(f)} OK")
        else:
            print(f"[!] Manquant: {f}")
            all_ok = False

    return all_ok

def test_lm_studio_query():
    """Teste une requete LM Studio simple"""
    try:
        import requests

        print("\n[*] Test de requete LM Studio...")

        payload = {
            "model": "deepseek-coder-6.7b-instruct",
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
            print(f"[+] Reponse LM Studio: {result[:200]}...")
            return True
        else:
            print(f"[!] Erreur LM Studio: {response.status_code}")
            return False

    except Exception as e:
        print(f"[!] Erreur: {e}")
        return False

def main():
    print("="*60)
    print("TEST DE L'ENVIRONNEMENT - Pipeline Ghidra + LLM")
    print("="*60)

    results = []

    print("\n--- Verification Python ---")
    results.append(("Python", check_python()))

    print("\n--- Verification des dependances ---")
    results.append(("requests", check_requests()))

    print("\n--- Verification LM Studio ---")
    results.append(("LM Studio", check_lm_studio()))

    print("\n--- Verification Ghidra ---")
    results.append(("Ghidra", check_ghidra()))

    print("\n--- Verification des scripts ---")
    results.append(("Scripts", check_scripts()))

    # Test LM Studio uniquement si disponible
    if results[2][1]:  # LM Studio OK
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
        print('  python pipeline.py --ghidra "chemin/vers/ghidra" --binary "chemin/vers/binaire.exe" --model deepseek-coder-6.7b-instruct')
    else:
        print("\n[!] Certains composants ne sont pas prets.")
        print("    Consultez le TUTORIEL.md pour les instructions d'installation.")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
