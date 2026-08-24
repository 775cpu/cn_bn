@echo on
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: 可按本机环境修改 Python 路径
set "PY_PATH=C:\QGB\miniforge3\python.exe"
if not exist "%PY_PATH%" set "PY_PATH=python"

set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
"%PY_PATH%" -m binance_tracker.main %*
