@echo off
chcp 65001 >nul
setlocal

where muse-drive >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "MUSE_CMD=muse-drive"
) else (
    set "MUSE_CMD=uv tool run muse-drive"
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
echo + %MUSE_CMD% mount %DRIVE% --label "%LABEL%" %EXTRA_ARGS%
%MUSE_CMD% mount %DRIVE% --label "%LABEL%" %EXTRA_ARGS%
exit /b %ERRORLEVEL%

:show_help
echo Usage: mount.bat [DRIVE] [--label "LABEL"] [--port PORT]
echo.
echo Options:
echo   DRIVE / --drive, -d   Drive letter to mount (default: M:)
echo   --label, -l           Drive label in Explorer (default: "Muse Drive")
echo   --port, -p            Custom WebDAV port (default: auto-scan 18844..18853)
echo   --help, -h            Show this help message
echo.
echo Examples:
echo   mount.bat
echo   mount.bat Z:
echo   mount.bat --drive M: --label "Muse Drive"
echo   mount.bat --drive Z: --label "Workspace" --port 8844
exit /b 0
