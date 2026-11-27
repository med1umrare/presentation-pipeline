# Renders every slide of a PPTX to PNG through installed PowerPoint (COM).
# Usage: powershell -File scripts/render_pptx_png.ps1 -Pptx output/dataviz-demo.pptx -OutDir renders
param(
  [Parameter(Mandatory = $true)][string]$Pptx,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [int]$Width = 1600,
  [int]$Height = 900
)
$pptxPath = (Resolve-Path $Pptx).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$outPath = (Resolve-Path $OutDir).Path
$app = New-Object -ComObject PowerPoint.Application
try {
  # ReadOnly, Untitled = false, WithWindow = false
  $deck = $app.Presentations.Open($pptxPath, -1, 0, 0)
  foreach ($slide in $deck.Slides) {
    $file = Join-Path $outPath ("slide-{0:D2}.png" -f $slide.SlideIndex)
    $slide.Export($file, "PNG", $Width, $Height)
    Write-Output $file
  }
  $deck.Close()
} finally {
  $app.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
