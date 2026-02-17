#!/bin/bash
# Script de lancement du pipeline Ghidra + LLM (LM Studio)
# Usage: ./run_pipeline.sh <chemin_binaire> [chemin_ghidra] [modele]
#
# Si chemin_ghidra n'est pas fourni, il est lu depuis config.json

SCRIPT_DIR="$(cd "$(dirname "$0")/scripts" && pwd)"

if [ -z "$1" ]; then
    echo "Usage: ./run_pipeline.sh <chemin_binaire> [chemin_ghidra] [modele]"
    echo ""
    echo "Le chemin Ghidra et le modele sont lus depuis config.json si non fournis."
    echo ""
    echo "Exemples:"
    echo "  ./run_pipeline.sh test_binaries/bin/test1_buffer"
    echo "  ./run_pipeline.sh test_binaries/bin/test1_buffer /opt/ghidra_12.0.1_PUBLIC"
    echo "  ./run_pipeline.sh test_binaries/bin/test1_buffer /opt/ghidra qwen2.5-coder-7b-instruct"
    exit 1
fi

BINARY="$1"

# Verifier que le binaire existe
if [ ! -f "$BINARY" ]; then
    echo "[!] Erreur: Binaire non trouve: $BINARY"
    exit 1
fi

# Verifier que LM Studio est accessible
if ! curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo "[!] Erreur: LM Studio n'est pas accessible"
    echo "    1. Lancez LM Studio"
    echo "    2. Chargez un modele"
    echo "    3. Demarrez le serveur local"
    exit 1
fi

# Construire la commande avec les arguments optionnels
CMD="python3 \"$SCRIPT_DIR/pipeline.py\" --binary \"$BINARY\" --task full"

if [ -n "$2" ]; then
    CMD="$CMD --ghidra \"$2\""
fi

if [ -n "$3" ]; then
    CMD="$CMD --model $3"
fi

echo "=========================================="
echo "Pipeline Ghidra + LLM (LM Studio)"
echo "=========================================="
echo "Binaire: $BINARY"
echo "=========================================="

# Executer le pipeline
eval $CMD

if [ $? -ne 0 ]; then
    echo "[!] Le pipeline a echoue"
    exit 1
fi

echo ""
echo "[+] Pipeline termine!"
