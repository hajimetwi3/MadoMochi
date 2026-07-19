# Screenshots can contain sensitive screen content: default the output to
# %TEMP% (never inside the repo), and *.png is gitignored as a second net.
param(
    [string]$Out = (Join-Path $env:TEMP "buddy_capture.png"),
    [int]$CropX = -1, [int]$CropY = 0, [int]$CropW = 0, [int]$CropH = 0,
    [int]$Zoom = 1
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System.Runtime.InteropServices;
public class DpiHelper { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
"@
[DpiHelper]::SetProcessDPIAware() | Out-Null
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
$g.Dispose()

if ($CropX -ge 0 -and $CropW -gt 0) {
    $crop = New-Object System.Drawing.Rectangle $CropX, $CropY, $CropW, $CropH
    $z = New-Object System.Drawing.Bitmap ($CropW * $Zoom), ($CropH * $Zoom)
    $g2 = [System.Drawing.Graphics]::FromImage($z)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
    $g2.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
    $g2.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $z.Width, $z.Height), $crop, [System.Drawing.GraphicsUnit]::Pixel)
    $g2.Dispose()
    $z.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $z.Dispose()
    $bmp.Dispose()
} else {
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}
Write-Host "saved $Out"
