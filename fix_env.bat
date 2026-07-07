@echo off
REM ============================================================
REM  Corrige conflitos de versao no ambiente "3W".
REM
REM  Problema: torch e transformers instalados em versoes
REM  incompativeis causam AttributeError em DynamicInt.
REM
REM  Solucao: fixar versoes compativeis entre si:
REM    torch >= 2.5   (removeu DynamicInt — nao depende mais dele)
REM    transformers >= 4.46  (compativel com torch 2.5+)
REM    sentence-transformers >= 3.3
REM ============================================================

SET CONDA_ENV=3W

echo [PetroRAG] Corrigindo dependencias no ambiente: %CONDA_ENV%
echo.

where conda >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERRO] conda nao encontrado no PATH. Abra o Anaconda Prompt e execute manualmente:
    echo   conda activate %CONDA_ENV%
    echo   pip install "torch>=2.5.0" "transformers>=4.46.0" "sentence-transformers>=3.3.0" --upgrade
    pause
    exit /b 1
)

echo [1/3] Atualizando torch para versao compativel com Python 3.13...
conda run -n "%CONDA_ENV%" pip install "torch>=2.5.0" --upgrade --quiet
IF %ERRORLEVEL% NEQ 0 (
    echo [AVISO] Falha ao atualizar torch. Tentando versao CPU-only...
    conda run -n "%CONDA_ENV%" pip install "torch>=2.5.0" --index-url https://download.pytorch.org/whl/cpu --upgrade
)

echo [2/3] Atualizando transformers...
conda run -n "%CONDA_ENV%" pip install "transformers>=4.46.0" --upgrade --quiet

echo [3/3] Atualizando sentence-transformers...
conda run -n "%CONDA_ENV%" pip install "sentence-transformers>=3.3.0" --upgrade --quiet

echo.
echo [PetroRAG] Verificando importacao...
conda run -n "%CONDA_ENV%" python -c "import torch; import transformers; import sentence_transformers; print('OK — torch', torch.__version__, '| transformers', transformers.__version__, '| sbert', sentence_transformers.__version__)"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Conflitos resolvidos. Execute run_app.bat para iniciar o Streamlit.
) ELSE (
    echo.
    echo [ERRO] Ainda ha conflito. Veja a mensagem acima e reporte o erro.
)

pause
