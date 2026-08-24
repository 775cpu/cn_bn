@echo on
chcp 65001
cd /d "%~dp0"
:: ===== 基础配置（可按需修改） =====
set "PY_PATH=C:\QGB\miniforge3\python.exe"
set "GIT_PATH=C:\QGB\PortableGit\bin\git.exe"
set "BRANCH=master"
set "SIZE_THRESHOLD=104857600"
:: ==================================

:: 判断输入参数是否为空，为空则默认参数 -v3 -u push
if "%*"=="" (
    "%PY_PATH%" "D:\test\github\git.bat\git_logic.py" -v3 -u push
) else (
    "%PY_PATH%" "D:\test\github\git.bat\git_logic.py" %*
)

pause
