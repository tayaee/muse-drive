@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo === Setting up muse-drive Development Environment ===

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Check if uv is installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Warning: 'uv' is not found in PATH.
    echo Attempting to install uv automatically via PowerShell...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %ERRORLEVEL% neq 0 (
        echo Error: Failed to install uv automatically.
        echo Please install uv manually: https://docs.astral.sh/uv/getting-started/installation/
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: uv was installed but is not found in PATH for this session.
    echo Please restart your Command Prompt / PowerShell and rerun this script.
    exit /b 1
)

cd /d "%SCRIPT_DIR%"

echo Syncing virtual environment and dependencies (.venv)...
uv sync
if %ERRORLEVEL% neq 0 (
    echo Error: uv sync failed.
    exit /b %ERRORLEVEL%
)

echo.
echo === Development Setup Complete! ===
echo Virtual environment is ready at: %SCRIPT_DIR%\.venv
echo.
echo To run during development without activating:
echo   uv run muse-drive --help
echo   uv run muse-drive mount
echo.
echo Or activate the virtual environment directly:
echo   .venv\Scripts\activate
echo   muse-drive --help
echo.

endlocal
