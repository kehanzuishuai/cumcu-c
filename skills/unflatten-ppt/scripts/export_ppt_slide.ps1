param(
    [Parameter(Mandatory=$true)]
    [string]$PptxPath,

    [Parameter(Mandatory=$true)]
    [string]$OutPngPath,

    [int]$SlideIndex = 1,
    [int]$Width = 0,
    [int]$Height = 0
)

$pptx = (Resolve-Path -LiteralPath $PptxPath).Path
$outDir = Split-Path -Parent $OutPngPath
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$app = $null
$pres = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    $pres = $app.Presentations.Open($pptx, $true, $false, $false)
    $slide = $pres.Slides.Item($SlideIndex)
    if ($Width -gt 0 -and $Height -gt 0) {
        $slide.Export($OutPngPath, "PNG", $Width, $Height)
    } else {
        $slide.Export($OutPngPath, "PNG")
    }
    Write-Output $OutPngPath
}
finally {
    if ($pres -ne $null) { $pres.Close() }
    if ($app -ne $null) { $app.Quit() }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
