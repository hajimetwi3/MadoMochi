# Launch MadoMochi (floating pixel buddy), hidden console, single instance.
$ErrorActionPreference = "SilentlyContinue"
$script = Join-Path $PSScriptRoot "buddy.py"

$pyw = $null
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $cand = Join-Path (Split-Path $py.Source) "pythonw.exe"
    if (Test-Path $cand) { $pyw = $cand }
}
if (-not $pyw) { $pyw = "pythonw" }

# a manual start is explicit consent: lift any quit-snooze on auto-revival
Remove-Item (Join-Path $env:USERPROFILE ".claude\buddy\quit.ts") -ErrorAction SilentlyContinue

Start-Process -FilePath $pyw -ArgumentList "`"$script`"" -WindowStyle Hidden
Write-Host "MadoMochi launched (duplicate instances exit by themselves)."
