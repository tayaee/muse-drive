@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\.venv\Scripts\muse-drive.exe" (
    set "MUSE_CMD="%SCRIPT_DIR%\.venv\Scripts\muse-drive.exe""
) else (
    where muse-drive >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "MUSE_CMD=muse-drive"
    ) else (
        set "MUSE_CMD=uv run --directory "%SCRIPT_DIR%" muse-drive"
    )
)

set "DRIVE=M:"
set "LABEL=Muse Drive"
set "EXTRA_ARGS="

:parse_loop
if "%~1"=="" goto run_cmd

if /i "%~1"=="--drive" (
    set "DRIVE=%~2"
    shift
    shift
    goto parse_loop
)
if /i "%~1"=="-d" (
    set "DRIVE=%~2"
    shift
    shift
    goto parse_loop
)
if /i "%~1"=="--label" (
    set "LABEL=%~2"
    shift
    shift
    goto parse_loop
)
if /i "%~1"=="-l" (
    set "LABEL=%~2"
    shift
    shift
    goto parse_loop
)

set "CUR_ARG=%~1"
set "FIRST_CHAR=%CUR_ARG:~0,1%"
set "SECOND_CHAR=%CUR_ARG:~1,1%"

if "%SECOND_CHAR%"==":" (
    set "DRIVE=%CUR_ARG%"
    shift
    goto parse_loop
)

if "%FIRST_CHAR%"=="-" (
    set "EXTRA_ARGS=%EXTRA_ARGS% %1"
    shift
    goto parse_loop
)

set "DRIVE=%CUR_ARG%"
shift
goto parse_loop

:run_cmd
:: Normalize DRIVE (e.g. M -> M:)
if "%DRIVE:~-1%" neq ":" set "DRIVE=%DRIVE%:"

:: If already mounted, unmount first
%MUSE_CMD% status 2>nul | findstr /i "Mounted" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo An existing mount was detected. Stopping it first...
    echo + %MUSE_CMD% umount
    %MUSE_CMD% umount >nul 2>&1
    timeout /t 1 /nobreak >nul 2>&1
)

echo + start "Muse Drive" cmd /k "%MUSE_CMD% mount %DRIVE% --label \"%LABEL%\" --foreground %EXTRA_ARGS%"
start "Muse Drive" cmd /k "%MUSE_CMD% mount %DRIVE% --label \"%LABEL%\" --foreground %EXTRA_ARGS%"

echo Waiting for %DRIVE% to be mounted...
set /a ATTEMPTS=0

:check_loop
timeout /t 1 /nobreak >nul 2>&1
set /a ATTEMPTS+=1

if exist %DRIVE%\ (
    echo Workspace mounted successfully on %DRIVE%
    exit /b 0
)

net use %DRIVE% >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Workspace mounted successfully on %DRIVE%
    exit /b 0
)

%MUSE_CMD% status 2>nul | findstr /i "Mounted" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Workspace mounted successfully on %DRIVE%
    exit /b 0
)

if !ATTEMPTS! geq 30 (
    echo Warning: Mount check timed out after 30 seconds.
    echo Please check the "Muse Drive" window for logs.
    exit /b 1
)

goto check_loop
