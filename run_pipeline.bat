@echo off
REM Script de lancement du pipeline Ghidra + LLM (LM Studio)
REM Usage: run_pipeline.bat <chemin_binaire> [chemin_ghidra] [modele]
REM
REM Si chemin_ghidra n'est pas fourni, il est lu depuis config.json

setlocal

set SCRIPT_DIR=%~dp0scripts

if "%~1"=="" (
    echo Usage: run_pipeline.bat ^<chemin_binaire^> [chemin_ghidra] [modele]
    echo.
    echo Le chemin Ghidra et le modele sont lus depuis config.json si non fournis.
    echo.
    echo Exemples:
    echo   run_pipeline.bat test_binaries\bin\test1_buffer.exe
    echo   run_pipeline.bat test_binaries\bin\test1_buffer.exe "C:\ghidra_12.0.1_PUBLIC"
    echo   run_pipeline.bat test_binaries\bin\test1_buffer.exe "C:\ghidra" qwen2.5-coder-7b-instruct
    exit /b 1
)

set BINARY=%~1

REM Verifier que le binaire existe
if not exist "%BINARY%" (
    echo [!] Erreur: Binaire non trouve: %BINARY%
    exit /b 1
)

REM Verifier que LM Studio est accessible
curl -s http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo [!] Erreur: LM Studio n'est pas accessible
    echo     1. Lancez LM Studio
    echo     2. Chargez un modele
    echo     3. Demarrez le serveur local
    exit /b 1
)

REM Construire la commande avec les arguments optionnels
set CMD=python "%SCRIPT_DIR%\pipeline.py" --binary "%BINARY%" --task full

if not "%~2"=="" (
    set CMD=%CMD% --ghidra "%~2"
)

if not "%~3"=="" (
    set CMD=%CMD% --model %~3
)

echo ==========================================
echo Pipeline Ghidra + LLM (LM Studio)
echo ==========================================
echo Binaire: %BINARY%
echo ==========================================

REM Executer le pipeline
%CMD%

if errorlevel 1 (
    echo [!] Le pipeline a echoue
    exit /b 1
)

echo.
echo [+] Pipeline termine!

endlocal
