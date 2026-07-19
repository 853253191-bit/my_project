# 一键启动：挂上 AHK 采集热键 + 注册每天 22:00 整理任务
# 用法：在 runtime 目录执行  .\bootstrap.ps1

$ErrorActionPreference = "Stop"
$RuntimeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AhkScript = Join-Path $RuntimeDir "capture-idea.ahk"
$Wrapper = Join-Path $RuntimeDir "run_digest_wrapper.ps1"
$TaskName = "DailyKnowledgeDigest"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = Join-Path $StartupDir "KnowledgeCapture-CtrlAltK.lnk"

function Write-Info([string]$Msg) {
    Write-Host "[OK] $Msg"
}

function Write-Warn([string]$Msg) {
    Write-Host "[!!] $Msg" -ForegroundColor Yellow
}

function Find-AutoHotkey {
    $candidates = @(
        (Join-Path $env:ProgramFiles "AutoHotkey\v2\AutoHotkey64.exe"),
        (Join-Path $env:ProgramFiles "AutoHotkey\v2\AutoHotkey.exe"),
        (Join-Path $env:ProgramFiles "AutoHotkey\AutoHotkey64.exe"),
        (Join-Path $env:ProgramFiles "AutoHotkey\AutoHotkey.exe"),
        (Join-Path $env:LocalAppData "Programs\AutoHotkey\v2\AutoHotkey64.exe"),
        (Join-Path $env:LocalAppData "Programs\AutoHotkey\v2\AutoHotkey.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $cmd = Get-Command AutoHotkey64.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd2 = Get-Command AutoHotkey.exe -ErrorAction SilentlyContinue
    if ($cmd2) { return $cmd2.Source }
    return $null
}

function Start-CaptureAhk([string]$AhkExe) {
    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Name -eq "AutoHotkey64.exe" -or $_.Name -eq "AutoHotkey.exe") -and
            $_.CommandLine -and
            ($_.CommandLine -like "*capture-idea.ahk*")
        }
    if ($running) {
        Write-Info "capture-idea.ahk already running"
        return
    }
    Start-Process -FilePath $AhkExe -ArgumentList ('"{0}"' -f $AhkScript)
    Write-Info "started capture-idea.ahk (Ctrl+Alt+K)"
}

function Install-StartupShortcut([string]$AhkExe) {
    if (-not (Test-Path -LiteralPath $StartupDir)) {
        New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null
    }
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($ShortcutPath)
    $sc.TargetPath = $AhkExe
    $sc.Arguments = ('"{0}"' -f $AhkScript)
    $sc.WorkingDirectory = $RuntimeDir
    $sc.WindowStyle = 7
    $sc.Description = "Knowledge capture hotkey Ctrl+Alt+K"
    $sc.Save()
    Write-Info ("startup shortcut: {0}" -f $ShortcutPath)
}

function Register-DigestTask {
    $key = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY", "User")
    if ([string]::IsNullOrWhiteSpace($key)) {
        $key = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY", "Machine")
    }
    if ([string]::IsNullOrWhiteSpace($key)) {
        Write-Warn "DASHSCOPE_API_KEY not found. Task will be registered anyway."
    } else {
        Write-Info "DASHSCOPE_API_KEY detected (wrapper will load User env)"
    }

    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$Wrapper`""

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Info ("removed old task {0}" -f $TaskName)
    }

    $action = New-ScheduledTaskAction -Execute $psExe -Argument $argList -WorkingDirectory $RuntimeDir
    $trigger = New-ScheduledTaskTrigger -Daily -At 22:00
    $settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable:$false
    # Interactive: only when user is logged on
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Info ("scheduled task ready: {0} @ 22:00 daily" -f $TaskName)
    Write-Host ("    manual run: schtasks /Run /TN {0}" -f $TaskName)
}

Write-Host "=== Knowledge digest bootstrap ==="
Write-Host ("runtime: {0}" -f $RuntimeDir)

if (-not (Test-Path -LiteralPath $AhkScript)) {
    throw ("missing file: {0}" -f $AhkScript)
}
if (-not (Test-Path -LiteralPath $Wrapper)) {
    throw ("missing file: {0}" -f $Wrapper)
}

$ahk = Find-AutoHotkey
if (-not $ahk) {
    Write-Warn "AutoHotkey v2 not found. Install from https://www.autohotkey.com/"
    Write-Warn "Re-run this script after install to enable Ctrl+Alt+K."
} else {
    Write-Info ("AutoHotkey: {0}" -f $ahk)
    Start-CaptureAhk $ahk
    Install-StartupShortcut $ahk
}

Register-DigestTask

Write-Host ""
Write-Host "Done. Capture with Ctrl+Alt+K; digest runs daily at 22:00."
Write-Host ("Logs: {0}" -f (Join-Path $RuntimeDir "logs"))
Write-Host ("Stop hotkey: exit AutoHotkey tray, or delete {0}" -f $ShortcutPath)
Write-Host ("Disable schedule: schtasks /Delete /TN {0} /F" -f $TaskName)
