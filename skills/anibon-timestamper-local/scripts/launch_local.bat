@echo off
set WORKSPACE=%~1
if "%WORKSPACE%"=="" (
    echo Usage: launch_local.bat WORKSPACE [MODEL] [LANG]
    exit /b 1
)
set MODEL=%~2
if "%MODEL%"=="" set MODEL=auto
set LANG=%~3
if "%LANG%"=="" set LANG=th

start /b python -X utf8 "%~dp0process_chunks_local.py" "%WORKSPACE%" --model %MODEL% --lang %LANG% > "%WORKSPACE%\timestamper.log" 2>&1
echo Timestamper launched in background.
echo Check progress: type "%WORKSPACE%\timestamper.log"
