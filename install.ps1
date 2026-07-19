# MadoMochi installer
#
# Interactive:      powershell -ExecutionPolicy Bypass -File install.ps1
# Scripted:         install.ps1 -Global            (all projects)
#                   install.ps1 -Project <dir>     (one project)
#                   add -Start to launch the buddy right away
#                   add -Lang en / -Lang ja to force the prompt language
#                   (default: follows the Windows display language)
param(
    [switch]$Global,
    [string]$Project = "",
    [switch]$Start,
    [ValidateSet("", "ja", "en")][string]$Lang = ""
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$interactive = (-not $Global) -and (-not $Project)

if ($Lang -notin @("ja", "en")) {
    # same source of truth as the buddy itself (scripts/i18n.py): the Windows
    # display language via Win32 — Get-UICulture can disagree with it
    try {
        Add-Type -Namespace Native -Name UiLang -MemberDefinition `
            '[DllImport("kernel32.dll")] public static extern ushort GetUserDefaultUILanguage();'
        $Lang = if (([Native.UiLang]::GetUserDefaultUILanguage() -band 0x3FF) -eq 0x11) { "ja" } else { "en" }
    } catch {
        $Lang = "en"
    }
}
$S = @{
    en = @{
        no_python  = "python not found. Install Python 3.10+ and run this again."
        where      = "Where should MadoMochi be wired?"
        opt_global = "  [1] Global (reacts in every project)"
        opt_here   = "  [2] This project only ({0})"
        opt_other  = "  [3] Another project folder"
        ask_num    = "Enter a number (1/2/3)"
        ask_path   = "Full path of the project folder"
        not_found  = "Folder not found: {0}"
        cancelled  = "Cancelled"
        ask_launch = "Launch the buddy now? (Y/n)"
        done       = "Setup complete. Hooks take effect from the next Claude Code session"
    }
    ja = @{
        no_python  = "python が見つかりません。Python 3.10+ をインストールしてから再実行してください。"
        where      = "MadoMochi をどこに配線しますか？"
        opt_global = "  [1] グローバル（すべてのプロジェクトで反応）"
        opt_here   = "  [2] このプロジェクトのみ ({0})"
        opt_other  = "  [3] 別のプロジェクトフォルダを指定"
        ask_num    = "番号を入力 (1/2/3)"
        ask_path   = "プロジェクトフォルダのフルパス"
        not_found  = "フォルダが見つかりません: {0}"
        cancelled  = "中止しました"
        ask_launch = "今すぐバディを起動しますか？ (Y/n)"
        done       = "セットアップ完了。フックは新しい Claude Code セッションから有効になります"
    }
}
$L = $S[$Lang]

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host $L.no_python
    exit 1
}

if ($interactive) {
    Write-Host ""
    Write-Host $L.where
    Write-Host $L.opt_global
    Write-Host ($L.opt_here -f $root)
    Write-Host $L.opt_other
    $c = Read-Host $L.ask_num
    switch ($c) {
        "1" { $Global = $true }
        "2" { $Project = $root }
        "3" {
            $Project = Read-Host $L.ask_path
            if (-not (Test-Path $Project)) { Write-Host ($L.not_found -f $Project); exit 1 }
        }
        default { Write-Host $L.cancelled; exit 1 }
    }
}

if ($Global) {
    python "$root\scripts\install_hooks.py"
} else {
    if (-not (Test-Path $Project)) { Write-Host ($L.not_found -f $Project); exit 1 }
    python "$root\scripts\install_hooks.py" --project $Project
}
if ($LASTEXITCODE -ne 0) { exit 1 }

if ($Start) {
    powershell -NoProfile -ExecutionPolicy Bypass -File "$root\scripts\start_buddy.ps1"
} elseif ($interactive) {
    $ans = Read-Host $L.ask_launch
    if ($ans -ne "n") {
        powershell -NoProfile -ExecutionPolicy Bypass -File "$root\scripts\start_buddy.ps1"
    }
}

Write-Host ""
Write-Host "$($L.done) 🐱"
