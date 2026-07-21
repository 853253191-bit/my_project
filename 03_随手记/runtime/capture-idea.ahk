; 全局热键采集：Ctrl+Alt+K 想法暂存，Ctrl+Alt+J 日记暂存
; 需要 AutoHotkey v2

#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

IdeaInboxPath := A_ScriptDir "\..\暂存文件\04_每日知识点整理\想法暂存.txt"
DiaryInboxPath := A_ScriptDir "\..\暂存文件\11_小陈日记\日记暂存.txt"
LogPath := A_ScriptDir "\logs\ahk-capture.log"

; Ctrl+Alt+K：知识点
^!k:: {
    CaptureSelection(IdeaInboxPath, "想法暂存", "知识点采集")
}

; Ctrl+Alt+J：日记
^!j:: {
    CaptureSelection(DiaryInboxPath, "日记暂存", "日记采集")
}

CaptureSelection(inboxPath, inboxKeyword, title) {
    global LogPath

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
            AppendInbox(inboxPath, block)
            DiscardOpenInboxEditors(inboxKeyword)
            ShowSaveOk(text, title)
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
    MsgBox("保存失败，请稍后重试。", title, "IconX T2")
}

AppendInbox(inboxPath, block) {
    parentDir := RegExReplace(inboxPath, "\\[^\\]+$")
    DirCreate(parentDir)
    f := FileOpen(inboxPath, "a", "UTF-8-RAW")
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

DiscardOpenInboxEditors(inboxKeyword) {
    for hwnd in WinGetList("ahk_exe notepad.exe") {
        try {
            title := WinGetTitle("ahk_id " hwnd)
            if InStr(title, inboxKeyword) {
                WinKill("ahk_id " hwnd)
            }
        }
    }
}

ShowSaveOk(text, title) {
    preview := text
    if (StrLen(preview) > 80) {
        preview := SubStr(preview, 1, 80) "..."
    }
    MsgBox("已保存到磁盘`n`n" preview, title, "Iconi T1.5")
}
