# MadoMochi uninstaller
#
# Interactive:      powershell -ExecutionPolicy Bypass -File uninstall.ps1
# Scripted:         uninstall.ps1 -Global            (remove the global wiring)
#                   uninstall.ps1 -Project <dir>     (remove one project's wiring)
#                   add -PurgeData to also delete ~/.claude/buddy (state/config/cache)
#                   add -Lang en / -Lang ja to force the prompt language
param(
    [switch]$Global,
    [string]$Project = "",
    [switch]$PurgeData,
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
        where      = "Which MadoMochi wiring should be removed?"
        opt_global = "  [1] Global (~/.claude/settings.json)"
        opt_here   = "  [2] This project only ({0})"
        opt_other  = "  [3] Another project folder"
        ask_num    = "Enter a number (1/2/3)"
        ask_path   = "Full path of the project folder"
        not_found  = "Folder not found: {0}"
        cancelled  = "Cancelled"
        ask_purge  = "Also delete the buddy's data (~/.claude/buddy: settings, cache, logs)? (y/N)"
        purged     = "Buddy data deleted."
        kept       = "Buddy data kept (position, skin and audio settings survive a reinstall)."
        done       = "Uninstall complete. Sessions already open keep their hooks until they end"
    }
    ja = @{
        no_python  = "python が見つかりません。Python 3.10+ をインストールしてから再実行してください。"
        where      = "どの MadoMochi 配線を外しますか？"
        opt_global = "  [1] グローバル (~/.claude/settings.json)"
        opt_here   = "  [2] このプロジェクトのみ ({0})"
        opt_other  = "  [3] 別のプロジェクトフォルダを指定"
        ask_num    = "番号を入力 (1/2/3)"
        ask_path   = "プロジェクトフォルダのフルパス"
        not_found  = "フォルダが見つかりません: {0}"
        cancelled  = "中止しました"
        ask_purge  = "バディのデータ (~/.claude/buddy: 設定・キャッシュ・ログ) も削除しますか？ (y/N)"
        purged     = "バディのデータを削除しました。"
        kept       = "バディのデータは残しました（位置・スキン・音の設定は再インストール後も生きます）。"
        done       = "アンインストール完了。開いているセッションのフックはセッション終了まで残ります"
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

# dismiss the buddy first (also snoozes prompt-revival for open sessions)
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\scripts\stop_buddy.ps1" | Out-Null

if ($Global) {
    python "$root\scripts\install_hooks.py" --uninstall
} else {
    if (-not (Test-Path $Project)) { Write-Host ($L.not_found -f $Project); exit 1 }
    python "$root\scripts\install_hooks.py" --uninstall --project $Project
}
if ($LASTEXITCODE -ne 0) { exit 1 }

$dataDir = Join-Path $env:USERPROFILE ".claude\buddy"
$purge = $PurgeData
if ($interactive -and (Test-Path $dataDir)) {
    $ans = Read-Host $L.ask_purge
    if ($ans -eq "y") { $purge = $true }
}
if ($purge -and (Test-Path $dataDir)) {
    Remove-Item -Recurse -Force $dataDir
    # keep the quit marker so hooks still loaded in open sessions stay polite
    New-Item -ItemType Directory -Force $dataDir | Out-Null
    Set-Content -Path (Join-Path $dataDir "quit.ts") -Value "uninstalled"
    Write-Host $L.purged
} else {
    Write-Host $L.kept
}

Write-Host ""
Write-Host "$($L.done) 🐱"
