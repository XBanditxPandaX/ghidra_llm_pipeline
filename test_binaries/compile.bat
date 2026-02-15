@echo off
REM Script de compilation des binaires de test
REM Necessite MinGW ou Visual Studio installé

echo ==========================================
echo Compilation des binaires de test
echo ==========================================

REM Créer le dossier de sortie
if not exist "bin" mkdir bin

REM Compilation avec GCC (MinGW)
echo.
echo Tentative de compilation avec GCC...

where gcc >nul 2>nul
if %errorlevel% equ 0 (
    echo GCC trouve. Compilation en cours...

    gcc -o bin/test1_buffer.exe src/test1_buffer_operations.c -O0 -g
    if %errorlevel% equ 0 echo [OK] test1_buffer.exe

    gcc -o bin/test2_string.exe src/test2_string_utils.c -O0 -g
    if %errorlevel% equ 0 echo [OK] test2_string.exe

    gcc -o bin/test3_crypto.exe src/test3_crypto_basic.c -O0 -g
    if %errorlevel% equ 0 echo [OK] test3_crypto.exe

    gcc -o bin/test4_linkedlist.exe src/test4_linked_list.c -O0 -g
    if %errorlevel% equ 0 echo [OK] test4_linkedlist.exe

    gcc -o bin/test5_file.exe src/test5_file_operations.c -O0 -g
    if %errorlevel% equ 0 echo [OK] test5_file.exe

    REM Versions optimisees (plus difficiles a analyser)
    echo.
    echo Compilation des versions optimisees...

    gcc -o bin/test1_buffer_O2.exe src/test1_buffer_operations.c -O2 -s
    if %errorlevel% equ 0 echo [OK] test1_buffer_O2.exe (stripped)

    gcc -o bin/test3_crypto_O2.exe src/test3_crypto_basic.c -O2 -s
    if %errorlevel% equ 0 echo [OK] test3_crypto_O2.exe (stripped)

    echo.
    echo Compilation terminee!
    goto end
)

REM Tentative avec cl.exe (Visual Studio)
echo GCC non trouve. Tentative avec Visual Studio...

where cl >nul 2>nul
if %errorlevel% equ 0 (
    echo Visual Studio trouve. Compilation en cours...

    cl /Fe:bin/test1_buffer.exe src/test1_buffer_operations.c /Od /Zi
    cl /Fe:bin/test2_string.exe src/test2_string_utils.c /Od /Zi
    cl /Fe:bin/test3_crypto.exe src/test3_crypto_basic.c /Od /Zi
    cl /Fe:bin/test4_linkedlist.exe src/test4_linked_list.c /Od /Zi
    cl /Fe:bin/test5_file.exe src/test5_file_operations.c /Od /Zi

    echo Compilation terminee!
    goto end
)

echo.
echo ERREUR: Aucun compilateur trouve!
echo Installez MinGW (GCC) ou Visual Studio.
echo.
echo Pour MinGW:
echo   - Telecharger: https://www.mingw-w64.org/
echo   - Ou via chocolatey: choco install mingw
echo.

:end
pause
