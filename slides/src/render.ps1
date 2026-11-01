# Render a built deck to one PNG per slide with PowerPoint itself (faithful fonts and layout), for visual QA.
#   pwsh slides/src/render.ps1 slides/dist/02-ai-ready-foundations.pptx [-Width 1600] [-Slides 3,7]
# Output: slides/dist/render/<deck-name>/slide-NN.png. A named mutex serialises concurrent runs, because every
# caller shares the one PowerPoint process.
param(
  [Parameter(Mandatory = $true)][string]$Deck,
  [int]$Width = 1600,
  [int[]]$Slides
)
$ErrorActionPreference = "Stop"
$deckPath = (Resolve-Path $Deck).Path
$name = [IO.Path]::GetFileNameWithoutExtension($deckPath)
$outDir = Join-Path (Split-Path $deckPath) "render\$name"
New-Item -ItemType Directory -Force $outDir | Out-Null

$mutex = [Threading.Mutex]::new($false, "Global\ai-ready-azure-pptx-render")
[void]$mutex.WaitOne()
try {
  $app = New-Object -ComObject PowerPoint.Application
  # Open(FileName, ReadOnly, Untitled, WithWindow)
  $pres = $app.Presentations.Open($deckPath, -1, 0, 0)
  try {
    $h = [int]($Width * $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth)
    if (-not $Slides) { Get-ChildItem $outDir -Filter "slide-*.png" | Remove-Item }
    foreach ($s in $pres.Slides) {
      if ($Slides -and ($Slides -notcontains $s.SlideIndex)) { continue }
      $file = Join-Path $outDir ("slide-{0:D2}.png" -f $s.SlideIndex)
      $s.Export($file, "PNG", $Width, $h)
    }
    Write-Output "$($pres.Slides.Count) slides -> $outDir"
  } finally {
    $pres.Close()
    if ($app.Presentations.Count -eq 0) { $app.Quit() }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
  }
} finally {
  $mutex.ReleaseMutex()
}
