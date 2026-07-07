@echo off
REM ============================================================
REM  Inicializa o PetroRAG Streamlit no ambiente conda correto.
REM  Execute com duplo clique ou via terminal.
REM ============================================================

SET CONDA_ENV=3W
SET SCRIPT_DIR=%~dp0

echo [PetroRAG] Iniciando no ambiente conda: %CONDA_ENV%

REM Tenta via "conda run" (nao requer init do shell — mais robusto)
where conda >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERRO] conda nao encontrado no PATH.
    echo Abra o "Anaconda Prompt" e execute: conda run -n "%CONDA_ENV%" streamlit run app.py
    pause
    exit /b 1
)

conda run -n "%CONDA_ENV%" --no-capture-output streamlit run "%SCRIPT_DIR%app.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Falha ao iniciar. Verifique se o ambiente "%CONDA_ENV%" existe:
    echo   conda env list
    echo Se o erro for de modulo faltando, execute fix_env.bat primeiro.
    pause
)
