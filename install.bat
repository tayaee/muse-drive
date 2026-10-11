@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo === Installing muse-drive via uv tool ===

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Check if uv is installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Warning: 'uv' is not found in PATH.
    echo Attempting to install uv automatically via PowerShell...
    echo + powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
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

echo Installing muse-drive as a tool...
echo + uv tool install "%SCRIPT_DIR%" --force
uv tool install "%SCRIPT_DIR%" --force

:: Ensure current session has uv bin in PATH
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
uv tool update-shell >nul 2>&1

echo.
echo === Mounting Workspace to M: Drive ===
call "%SCRIPT_DIR%\mount.bat"
if %ERRORLEVEL% equ 0 goto mount_ok

echo.
echo === Installation Completed ===
echo Note: Could not mount automatically - session cookies may be required.
echo Please ensure session cookies exist at:
echo   %%USERPROFILE%%\.config\muse-cli\cookies.txt
echo and then run:
echo   mount.bat
goto script_end

:mount_ok
echo.
echo === Installation and Mount Successful ===
echo Workspace is mounted at: M:\

:script_end
echo.
echo Commands:
echo   mount.bat             # Mount workspace
echo   umount.bat            # Unmount workspace
echo   muse-drive status     # Check mount status
echo   muse-drive --help

endlocal
