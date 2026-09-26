param(
    [Parameter(Mandatory=$true)]
    [string]$Workspace,
    [string]$Model = "auto",
    [string]$Lang = "th",
    [switch]$NoResume,
    [string]$AdditionalArgs = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunnerScript = Join-Path $ScriptDir "process_chunks_local.py"
$LogFile = Join-Path $Workspace "timestamper.log"
$ErrFile = Join-Path $Workspace "timestamper_err.log"

if (-not (Test-Path $Workspace)) {
    Write-Error "Workspace directory does not exist: $Workspace"
    exit 1
}

$Extra = ""
if ($NoResume) { $Extra += " --no-resume" }
if ($AdditionalArgs) { $Extra += " $AdditionalArgs" }

# Launch python runner detached in background
$ArgList = "-X utf8 `"$RunnerScript`" `"$Workspace`" --model $Model --lang $Lang$Extra"
Start-Process -FilePath "python" -ArgumentList $ArgList -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -WindowStyle Hidden

Write-Host "✅ Timestamper launched in background."
Write-Host "   Monitor log : $LogFile"
Write-Host "   State file  : $(Join-Path $Workspace 'anibon_timestamper_state.json')"
