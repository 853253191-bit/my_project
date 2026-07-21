# 登录/开机启动：挂上采集热键，并后台检查暂存目录（新增目录同步 + 待归档 txt）
# 由「启动」文件夹快捷方式调用；也可手动执行。

$ErrorActionPreference = "Stop"
$RuntimeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AhkScript = Join-Path $RuntimeDir "capture-idea.ahk"
$Wrapper = Join-Path $RuntimeDir "run_digest_wrapper.ps1"

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
    if ($running) { return }
    Start-Process -FilePath $AhkExe -ArgumentList ('"{0}"' -f $AhkScript)
}

$ahk = Find-AutoHotkey
if ($ahk -and (Test-Path -LiteralPath $AhkScript)) {
    Start-CaptureAhk $ahk
}

# 后台检查暂存：同步新目录、归档待处理文档（不阻塞登录）
if (Test-Path -LiteralPath $Wrapper) {
    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    Start-Process -FilePath $psExe -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", $Wrapper
    ) -WorkingDirectory $RuntimeDir -WindowStyle Hidden
}
