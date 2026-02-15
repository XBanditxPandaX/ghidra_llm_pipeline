@echo off
REM Test du pipeline avec LM Studio uniquement (sans compilation, sans Ghidra)
REM Utilise des fichiers d'extraction simules

echo ==========================================
echo TEST LM STUDIO - Sans Ghidra ni compilation
echo ==========================================

cd /d "%~dp0scripts"

REM Verifier que LM Studio est lance
curl -s http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] LM Studio n'est pas demarre!
    echo     1. Lancez LM Studio
    echo     2. Chargez le modele deepseek-coder-6.7B-instruct-GGUF
    echo     3. Demarrez le serveur local (onglet Local Server)
    echo.
    pause
    exit /b 1
)

echo [+] LM Studio detecte

echo.
echo [*] Lancement du test...
echo.

python test_without_ghidra.py --model deepseek-coder-6.7b-instruct --task full

echo.
pause
