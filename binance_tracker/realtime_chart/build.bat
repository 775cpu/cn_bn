@echo off
setlocal enableextensions
rem ============================================================
rem  realtime_chart one-click build (vite -> dist/index.html)
rem  Usage:  double-click, or run:  build.bat [nopause]
rem ============================================================
cd /d "%~dp0"

rem --- 1) locate node.exe: prefer the system nodeenv, fallback to PATH ---
set "NODE_DIR=C:\Users\Administrator\.cache\pyright-python\nodeenv\src\node-v25.9.0-win-x64"
if exist "%NODE_DIR%\node.exe" set "PATH=%NODE_DIR%;%PATH%"

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] node.js not found. Install node or fix NODE_DIR in this script.
    goto :fail
)
for /f "delims=" %%v in ('node -v') do echo [INFO] node %%v

rem --- 2) install dependencies on first run ---
if not exist "node_modules" (
    echo [INFO] node_modules missing, running npm install ...
    call npm.cmd install --no-audit --no-fund
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        goto :fail
    )
)

rem --- 3) build ---
echo [INFO] building ...
call npm.cmd run build
if errorlevel 1 (
    echo [ERROR] vite build failed.
    goto :fail
)

echo.
echo [OK] build finished: dist\index.html
REM if /i not "%~1"=="nopause" pause
exit /b 0

:fail
REM if /i not "%~1"=="nopause" pause
exit /b 1
