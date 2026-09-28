@echo off
set WORKSPACE=%~1
if "%WORKSPACE%"=="" (
    echo Usage: launch_local.bat WORKSPACE [ENDPOINT_OR_IP] [MODEL] [LANG]
    exit /b 1
)
set ENDPOINT=%~2
if "%ENDPOINT%"=="" set ENDPOINT=http://100.115.25.30:1234/v1/chat/completions
set MODEL=%~3
if "%MODEL%"=="" set MODEL=auto
set LANG=%~4
if "%LANG%"=="" set LANG=th

start /b python -X utf8 "%~dp0process_chunks_local.py" "%WORKSPACE%" --endpoint "%ENDPOINT%" --model %MODEL% --lang %LANG% > "%WORKSPACE%\timestamper.log" 2>&1
echo Timestamper launched in background.
echo Check progress: type "%WORKSPACE%\timestamper.log"
