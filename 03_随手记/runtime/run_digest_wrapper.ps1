# Digest wrapper: load DASHSCOPE_API_KEY then run run_nightly.py
# Used by scheduled task DailyKnowledgeDigest and 现在就整理.bat

$ErrorActionPreference = "Stop"
$RuntimeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RuntimeDir

$key = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY", "User")
if ([string]::IsNullOrWhiteSpace($key)) {
    $key = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY", "Machine")
}
if ([string]::IsNullOrWhiteSpace($key)) {
    $key = $env:DASHSCOPE_API_KEY
}
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Error "DASHSCOPE_API_KEY is not set. Add it to User environment variables."
    exit 1
}
$env:DASHSCOPE_API_KEY = $key
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Resolve-Python {
    $candidates = @(
        "D:\python3.11\python.exe",
        (Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"),
        (Join-Path $env:ProgramFiles "Python311\python.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) {
            return @{ Exe = $p; Args = @() }
        }
    }
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{ Exe = $pyLauncher.Source; Args = @("-3.11") }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*WindowsApps*") {
        return @{ Exe = $python.Source; Args = @() }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Error "Python not found. Install Python 3.11 and ensure it is on PATH."
    exit 1
}

$script = Join-Path $RuntimeDir "run_nightly.py"
& $py.Exe @($py.Args + @($script))
exit $LASTEXITCODE
