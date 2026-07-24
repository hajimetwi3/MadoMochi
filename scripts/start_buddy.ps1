# Launch MadoMochi (floating pixel buddy), hidden console, single instance.
$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "buddy.py"

$pyw = $null
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $cand = Join-Path (Split-Path $py.Source) "pythonw.exe"
    if (Test-Path $cand) { $pyw = $cand }
}
if (-not $pyw) { $pyw = "pythonw" }
$pywCommand = Get-Command $pyw -ErrorAction SilentlyContinue
if (-not $pywCommand) {
    [Console]::Error.WriteLine("pythonw was not found. Install Python 3.10+ and try again.")
    exit 1
}
$pyw = $pywCommand.Source

# a manual start is explicit consent: lift any quit-snooze on auto-revival
$quitMarker = Join-Path $env:USERPROFILE ".claude\madomochi\quit.ts"
Remove-Item -LiteralPath $quitMarker -ErrorAction SilentlyContinue

try {
    $proc = Start-Process -FilePath $pyw -ArgumentList "`"$script`"" `
        -WindowStyle Hidden -PassThru -ErrorAction Stop
    Start-Sleep -Milliseconds 250
    if ($proc.HasExited -and $proc.ExitCode -ne 0) {
        throw "pythonw exited immediately with code $($proc.ExitCode)"
    }
} catch {
    [Console]::Error.WriteLine("Could not launch MadoMochi: $($_.Exception.Message)")
    exit 1
}
Write-Host "MadoMochi launch requested (duplicate instances exit by themselves)."
