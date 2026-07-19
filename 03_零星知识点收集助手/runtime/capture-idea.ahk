; 全局热键 Ctrl+Alt+K：将当前选中文字追加到桌面「想法暂存.txt」
; 需要 AutoHotkey v2

#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

InboxPath := EnvGet("USERPROFILE") "\Desktop\想法暂存.txt"
LogPath := A_ScriptDir "\logs\ahk-capture.log"

; Ctrl+Alt+K
^!k:: {
    CaptureSelection()
}

CaptureSelection() {
    global InboxPath, LogPath

    ; 备份剪贴板，避免长期污染用户剪贴板
    clipBackup := ClipboardAll()
    A_Clipboard := ""

    Send("^c")
    if !ClipWait(0.8) {
        A_Clipboard := clipBackup
        return
    }

    text := Trim(A_Clipboard)
    A_Clipboard := clipBackup

    if (text = "") {
        return
    }

    ts := FormatTime(, "yyyy-MM-dd HH:mm")
    block := "`n---`n" ts "`n" text "`n---`n"

    Loop 3 {
        try {
            ; 追加后立即 Close，内容已落盘（无需再点「保存」）
            AppendInbox(block)
            ; 关掉仍开着该文件的记事本旧窗口，避免脏缓冲弹出「是否保存」
            DiscardOpenInboxEditors()
            ShowSaveOk(text)
            return
        } catch as err {
            Sleep(150)
            lastErr := err
        }
    }

    try {
        DirCreate(A_ScriptDir "\logs")
        FileAppend(
            FormatTime(, "yyyy-MM-dd HH:mm:ss") " 写入失败: " lastErr.Message "`n",
            LogPath,
            "UTF-8-RAW"
        )
    }
    MsgBox("保存失败，请稍后重试。", "知识点采集", "IconX T2")
}

; 追加写入并强制关闭文件句柄（= 已保存到磁盘）
AppendInbox(block) {
    global InboxPath
    f := FileOpen(InboxPath, "a", "UTF-8-RAW")
    if !IsObject(f) {
        throw Error("无法打开暂存文件")
    }
    try {
        f.Seek(0, 2)
        f.Write(block)
    } finally {
        f.Close()
    }
}

; 关闭标题含「想法暂存」的记事本窗口（丢弃未保存缓冲，磁盘内容为准）
DiscardOpenInboxEditors() {
    for hwnd in WinGetList("ahk_exe notepad.exe") {
        try {
            title := WinGetTitle("ahk_id " hwnd)
            if InStr(title, "想法暂存") {
                WinKill("ahk_id " hwnd)
            }
        }
    }
}

; 保存成功弹窗：展示摘要，约 1.5 秒后自动关闭
ShowSaveOk(text) {
    preview := text
    if (StrLen(preview) > 80) {
        preview := SubStr(preview, 1, 80) "..."
    }
    MsgBox("已保存到磁盘`n`n" preview, "知识点采集", "Iconi T1.5")
}
