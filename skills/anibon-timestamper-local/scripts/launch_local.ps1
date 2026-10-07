param(
    [Parameter(Mandatory=$true)]
    [string]$Workspace,
    [string]$Endpoint = "http://100.115.25.30:1234/v1/chat/completions",
    [string]$Model = "auto",
    [string]$Lang = "th",
    [string]$Mode = "recursive",
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

if (-not ($Endpoint -match "^https?://")) {
    $Endpoint = "http://$Endpoint"
}
if (-not ($Endpoint -match ":\d+")) {
    $Endpoint = "${Endpoint}:1234"
}

# Auto-probe: If endpoint is on 100.115.25.30, test reachability. Fallback to 127.0.0.1 if unreachable.
if ($Endpoint -match "100\.115\.25\.30") {
    $TestUri = $Endpoint -replace "/v1/.*$", ""
    if (-not ($TestUri -match ":\d+$")) { $TestUri = "${TestUri}:1234" }
    $IsReachable = $false
    try {
        $TcpClient = New-Object System.Net.Sockets.TcpClient
        $Connect = $TcpClient.BeginConnect("100.115.25.30", 1234, $null, $null)
        $Success = $Connect.AsyncWaitHandle.WaitOne(1000, $false)
        if ($Success -and $TcpClient.Connected) {
            $IsReachable = $true
            $TcpClient.EndConnect($Connect)
        }
        $TcpClient.Close()
    } catch {
        $IsReachable = $false
    }
    if (-not $IsReachable) {
        Write-Host "⚠️ Endpoint 100.115.25.30 is unreachable. Falling back to localhost (127.0.0.1:1234)..."
        $Endpoint = $Endpoint -replace "100\.115\.25\.30", "127.0.0.1"
    }
}

if (-not ($Endpoint -match "/v1/chat/completions$")) {
    $Endpoint = "${Endpoint}/v1/chat/completions"
}

# Launch python runner detached in background
$ArgList = "-X utf8 `"$RunnerScript`" `"$Workspace`" --endpoint `"$Endpoint`" --mode $Mode --model $Model --lang $Lang$Extra"
Start-Process -FilePath "python" -ArgumentList $ArgList -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -WindowStyle Hidden

Write-Host "✅ Timestamper launched in background."
Write-Host "   Monitor log : $LogFile"
Write-Host "   State file  : $(Join-Path $Workspace 'anibon_timestamper_state.json')"
