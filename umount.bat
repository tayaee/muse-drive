@echo off
chcp 65001 >nul
setlocal

where muse-drive >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "MUSE_CMD=muse-drive"
) else (
    set "MUSE_CMD=uv tool run muse-drive"
)

set "DRIVE="
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
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="/?" goto show_help

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
if defined DRIVE (
    echo + %MUSE_CMD% umount %DRIVE% %EXTRA_ARGS%
    %MUSE_CMD% umount %DRIVE% %EXTRA_ARGS%
) else (
    echo + %MUSE_CMD% umount %EXTRA_ARGS%
    %MUSE_CMD% umount %EXTRA_ARGS%
)
exit /b %ERRORLEVEL%

:show_help
echo Usage: umount.bat [DRIVE]
echo.
echo Options:
echo   DRIVE / --drive, -d   Drive letter to unmount (optional, defaults to active mount)
echo   --help, -h            Show this help message
echo.
echo Examples:
echo   umount.bat
echo   umount.bat M:
echo   umount.bat --drive Z:
exit /b 0
