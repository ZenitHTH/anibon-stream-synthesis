param(
    [Parameter(Mandatory=$true)]
    [string]$Workspace,
    [string]$Model = "auto",
    [string]$Lang = "th"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunnerScript = Join-Path $ScriptDir "process_chunks_local.py"
$LogFile = Join-Path $Workspace "timestamper.log"
$ErrFile = Join-Path $Workspace "timestamper_err.log"

if (-not (Test-Path $Workspace)) {
    Write-Error "Workspace directory does not exist: $Workspace"
    exit 1
}

# Launch python runner detached in background
$ArgList = "-X utf8 `"$RunnerScript`" `"$Workspace`" --model $Model --lang $Lang"
Start-Process -FilePath "python" -ArgumentList $ArgList -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -WindowStyle Hidden

Write-Host "✅ Timestamper launched in background."
Write-Host "   Monitor log : $LogFile"
Write-Host "   State file  : $(Join-Path $Workspace 'anibon_timestamper_state.json')"
