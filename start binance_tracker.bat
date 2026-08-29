@echo on
chcp 65001
cd /d "%~dp0binance_tracker"

: 可按本机环境修改 Python 路径
set "PY_PATH=C:\QGB\miniforge3\python.exe"
if not exist "%PY_PATH%" set "PY_PATH=python"

set "PYTHONPATH=%~dp0binance_tracker\src;%PYTHONPATH%"
"%PY_PATH%" -m binance_tracker.main --network-mode direct %*

pause