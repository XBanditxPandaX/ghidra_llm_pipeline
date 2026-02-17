@echo off
REM Script de lancement du pipeline Ghidra + LLM (LM Studio)
REM Usage: run_pipeline.bat <chemin_binaire> [modele]

setlocal

set GHIDRA_PATH=C:\Users\themi\Bureau\CoursM1\M2\ghidra_12.0.1_PUBLIC
set SCRIPT_DIR=%~dp0scripts
set MODEL=Deepseek R1 0528 Qwen3 8B

if "%~1"=="" (
    echo Usage: run_pipeline.bat ^<chemin_binaire^> [modele]
    echo.
    echo Exemple:
    echo   run_pipeline.bat test_binaries\bin\test1_buffer.exe
    echo   run_pipeline.bat C:\path\to\binary.exe Deepseek R1 0528 Qwen3 8B
    exit /b 1
)

set BINARY=%~1

if not "%~2"=="" (
    set MODEL=%~2
)

echo ==========================================
echo Pipeline Ghidra + LLM (LM Studio)
echo ==========================================
echo Binaire: %BINARY%
echo Modele: %MODEL%
echo ==========================================

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
    echo     2. Chargez Deepseek R1 0528 Qwen3 8B
    echo     3. Demarrez le serveur local
    exit /b 1
)

REM Executer le pipeline
python "%SCRIPT_DIR%\pipeline.py" ^
    --binary "%BINARY%" ^
    --ghidra "%GHIDRA_PATH%" ^
    --model %MODEL% ^
    --task full ^
    --output "%~dp0results"

if errorlevel 1 (
    echo [!] Le pipeline a echoue
    exit /b 1
)

echo.
echo [+] Pipeline termine!
echo     Resultats dans: %~dp0results

endlocal
