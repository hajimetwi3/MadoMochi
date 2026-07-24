# Ask MadoMochi to close, then confirm that its window is gone.
$ErrorActionPreference = "Stop"
Add-Type -Namespace MadoMochi -Name NativeWindow -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
public static extern System.IntPtr FindWindow(string lpClassName, string lpWindowName);
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true)]
[return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
public static extern bool PostMessage(System.IntPtr hWnd, uint Msg, System.IntPtr wParam, System.IntPtr lParam);
'@

$window = [MadoMochi.NativeWindow]::FindWindow($null, "MadoMochi")
if ($window -eq [IntPtr]::Zero) {
    Write-Host "MadoMochi is not running."
    exit 0
}
if (-not [MadoMochi.NativeWindow]::PostMessage(
        $window, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)) {
    [Console]::Error.WriteLine("Could not request MadoMochi to close.")
    exit 1
}
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Milliseconds 200
    if ([MadoMochi.NativeWindow]::FindWindow($null, "MadoMochi") -eq [IntPtr]::Zero) {
        Write-Host "MadoMochi stopped."
        exit 0
    }
}
[Console]::Error.WriteLine("MadoMochi is still running after the close request.")
exit 1
