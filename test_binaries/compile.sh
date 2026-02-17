#!/bin/bash
# Script de compilation des binaires de test
# Necessite GCC installe

echo "=========================================="
echo "Compilation des binaires de test"
echo "=========================================="

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# Creer le dossier de sortie
mkdir -p bin

# Verifier que GCC est installe
if ! command -v gcc &> /dev/null; then
    echo ""
    echo "ERREUR: GCC non trouve!"
    echo "Installez GCC:"
    echo "  - Debian/Ubuntu: sudo apt install gcc"
    echo "  - Fedora: sudo dnf install gcc"
    echo "  - Arch: sudo pacman -S gcc"
    echo "  - macOS: xcode-select --install"
    exit 1
fi

echo ""
echo "GCC trouve. Compilation en cours..."
echo ""

# Compilation standard (debug, non optimise)
gcc -o bin/test1_buffer src/test1_buffer_operations.c -O0 -g && echo "[OK] test1_buffer"
gcc -o bin/test2_string src/test2_string_utils.c -O0 -g && echo "[OK] test2_string"
gcc -o bin/test3_crypto src/test3_crypto_basic.c -O0 -g && echo "[OK] test3_crypto"
gcc -o bin/test4_linkedlist src/test4_linked_list.c -O0 -g && echo "[OK] test4_linkedlist"
gcc -o bin/test5_file src/test5_file_operations.c -O0 -g && echo "[OK] test5_file"

# Versions optimisees (plus difficiles a analyser)
echo ""
echo "Compilation des versions optimisees..."

gcc -o bin/test1_buffer_O2 src/test1_buffer_operations.c -O2 -s && echo "[OK] test1_buffer_O2 (stripped)"
gcc -o bin/test3_crypto_O2 src/test3_crypto_basic.c -O2 -s && echo "[OK] test3_crypto_O2 (stripped)"

echo ""
echo "Compilation terminee!"
