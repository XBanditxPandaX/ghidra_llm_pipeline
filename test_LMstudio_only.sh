#!/bin/bash
# Test du pipeline avec LM Studio uniquement (sans compilation, sans Ghidra)
# Utilise des fichiers d'extraction simules

echo "=========================================="
echo "TEST LM STUDIO - Sans Ghidra ni compilation"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")/scripts" && pwd)"

# Verifier que LM Studio est lance
if ! curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo ""
    echo "[!] LM Studio n'est pas demarre!"
    echo "    1. Lancez LM Studio"
    echo "    2. Chargez le modele deepseek-r1-0528-qwen3-8b"
    echo "    3. Demarrez le serveur local (onglet Local Server)"
    exit 1
fi

echo "[+] LM Studio detecte"
echo ""
echo "[*] Lancement du test..."
echo ""

python3 "$SCRIPT_DIR/test_without_ghidra.py" --model deepseek-r1-0528-qwen3-8b --task full
