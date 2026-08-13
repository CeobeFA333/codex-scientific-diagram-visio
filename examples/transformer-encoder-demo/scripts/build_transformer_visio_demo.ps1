param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [switch]$KeepVisioOpen
)

$ErrorActionPreference = 'Stop'
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
$frameRoot = Join-Path $outputRoot 'visio-frames'
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $frameRoot -Force | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class VisioDemoNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int command);
}
'@

$script:visio = $null
$script:document = $null
$script:page = $null
$script:windowHandle = [IntPtr]::Zero
$script:frameIndex = 0
$script:layers = @{}
$script:shapes = @{}

function Set-CellFormula {
    param($Shape, [string]$Cell, [string]$Formula)
    try { $Shape.CellsU($Cell).FormulaU = $Formula } catch { }
}

function Convert-HexToRgbFormula {
    param([string]$Hex)
    $clean = $Hex.TrimStart('#')
    $red = [Convert]::ToInt32($clean.Substring(0, 2), 16)
    $green = [Convert]::ToInt32($clean.Substring(2, 2), 16)
    $blue = [Convert]::ToInt32($clean.Substring(4, 2), 16)
    "RGB($red,$green,$blue)"
}

function Add-ToLayer {
    param($Shape, [string]$LayerName)
    if ($script:layers.ContainsKey($LayerName)) {
        $script:layers[$LayerName].Add($Shape, 0)
    }
}

function Style-Shape {
    param(
        $Shape,
        [string]$Fill = '#FFFFFF',
        [string]$Line = '#1A2733',
        [double]$LineWeight = 1.0,
        [double]$FontSize = 11,
        [string]$FontColor = '#15202B',
        [bool]$Bold = $false,
        [bool]$Shadow = $false
    )
    Set-CellFormula $Shape 'FillPattern' '1'
    Set-CellFormula $Shape 'FillForegnd' (Convert-HexToRgbFormula $Fill)
    Set-CellFormula $Shape 'LineColor' (Convert-HexToRgbFormula $Line)
    Set-CellFormula $Shape 'LineWeight' "$LineWeight pt"
    Set-CellFormula $Shape 'Char.Size' "$FontSize pt"
    Set-CellFormula $Shape 'Char.Color' (Convert-HexToRgbFormula $FontColor)
    Set-CellFormula $Shape 'Char.Style' $(if ($Bold) { '1' } else { '0' })
    Set-CellFormula $Shape 'Para.HorzAlign' '1'
    Set-CellFormula $Shape 'VerticalAlign' '1'
    Set-CellFormula $Shape 'LeftMargin' '0.06 in'
    Set-CellFormula $Shape 'RightMargin' '0.06 in'
    Set-CellFormula $Shape 'TopMargin' '0.04 in'
    Set-CellFormula $Shape 'BottomMargin' '0.04 in'
    if ($Shadow) {
        Set-CellFormula $Shape 'ShdwPattern' '1'
        Set-CellFormula $Shape 'ShdwForegnd' 'RGB(120,130,140)'
        Set-CellFormula $Shape 'ShdwForegndTrans' '82%'
        Set-CellFormula $Shape 'ShdwOffsetX' '0.06 in'
        Set-CellFormula $Shape 'ShdwOffsetY' '-0.06 in'
    }
}

function Add-Rect {
    param(
        [string]$Name,
        [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
        [string]$Text = '',
        [string]$Fill = '#FFFFFF',
        [string]$Line = '#1A2733',
        [double]$LineWeight = 1.0,
        [double]$FontSize = 11,
        [string]$FontColor = '#15202B',
        [bool]$Bold = $false,
        [bool]$Shadow = $false,
        [string]$Layer = 'Modules'
    )
    $shape = $script:page.DrawRectangle($X1, $Y1, $X2, $Y2)
    $shape.NameU = $Name
    $shape.Text = $Text
    Style-Shape $shape $Fill $Line $LineWeight $FontSize $FontColor $Bold $Shadow
    Add-ToLayer $shape $Layer
    $script:shapes[$Name] = $shape
    $shape
}

function Add-Text {
    param(
        [string]$Name,
        [double]$X1, [double]$Y1, [double]$X2, [double]$Y2,
        [string]$Text,
        [double]$FontSize = 11,
        [string]$FontColor = '#15202B',
        [bool]$Bold = $false,
        [string]$Layer = 'Labels'
    )
    $shape = Add-Rect $Name $X1 $Y1 $X2 $Y2 $Text '#FFFFFF' '#FFFFFF' 0 $FontSize $FontColor $Bold $false $Layer
    Set-CellFormula $shape 'FillPattern' '0'
    Set-CellFormula $shape 'LinePattern' '0'
    $shape
}

function Add-Cuboid {
    param(
        [string]$Name,
        [double]$X, [double]$Y, [double]$Width, [double]$Height,
        [string]$Text,
        [string]$Front,
        [string]$Top,
        [string]$Side,
        [double]$FontSize = 11,
        [string]$FontColor = '#FFFFFF'
    )
    $depth = [Math]::Min(0.14, $Width * 0.10)
    $frontShape = Add-Rect "${Name}_Front" $X $Y ($X + $Width) ($Y + $Height) $Text $Front '#183044' 1.0 $FontSize $FontColor $true $true 'Modules'
    $topPoints = [double[]]@(
        $X, ($Y + $Height),
        ($X + $depth), ($Y + $Height + $depth),
        ($X + $Width + $depth), ($Y + $Height + $depth),
        ($X + $Width), ($Y + $Height),
        $X, ($Y + $Height)
    )
    $topShape = $script:page.DrawPolyline($topPoints, 0)
    $topShape.NameU = "${Name}_Top"
    Style-Shape $topShape $Top '#183044' 1.0 1 '#FFFFFF' $false $false
    Add-ToLayer $topShape 'Modules'
    $sidePoints = [double[]]@(
        ($X + $Width), $Y,
        ($X + $Width + $depth), ($Y + $depth),
        ($X + $Width + $depth), ($Y + $Height + $depth),
        ($X + $Width), ($Y + $Height),
        ($X + $Width), $Y
    )
    $sideShape = $script:page.DrawPolyline($sidePoints, 0)
    $sideShape.NameU = "${Name}_Side"
    Style-Shape $sideShape $Side '#183044' 1.0 1 '#FFFFFF' $false $false
    Add-ToLayer $sideShape 'Modules'

    $script:visio.ActiveWindow.DeselectAll()
    $script:visio.ActiveWindow.Select($frontShape, 2)
    $script:visio.ActiveWindow.Select($topShape, 2)
    $script:visio.ActiveWindow.Select($sideShape, 2)
    $group = $script:visio.ActiveWindow.Selection.Group()
    $group.NameU = $Name
    $script:shapes[$Name] = $group
    $script:visio.ActiveWindow.DeselectAll()
    $group
}

function Add-ConnectionPoint {
    param(
        $Shape,
        [string]$Side,
        [double]$WorldCoordinate = [double]::NaN
    )
    $row = $Shape.AddRow(7, -1, 0)
    $height = $Shape.CellsU('Height').ResultIU
    $pinY = $Shape.CellsU('PinY').ResultIU
    $localHorizontalY = if ([double]::IsNaN($WorldCoordinate)) {
        $null
    } else {
        $WorldCoordinate - $pinY + ($height / 2)
    }
    switch ($Side) {
        'Left'   {
            $Shape.CellsSRC(7, $row, 0).FormulaU = '0'
            $Shape.CellsSRC(7, $row, 1).FormulaU = if ($null -eq $localHorizontalY) { 'Height*0.5' } else { "$localHorizontalY in" }
        }
        'Right'  {
            $Shape.CellsSRC(7, $row, 0).FormulaU = 'Width'
            $Shape.CellsSRC(7, $row, 1).FormulaU = if ($null -eq $localHorizontalY) { 'Height*0.5' } else { "$localHorizontalY in" }
        }
        'Top'    { $Shape.CellsSRC(7, $row, 0).FormulaU = 'Width*0.5'; $Shape.CellsSRC(7, $row, 1).FormulaU = 'Height' }
        'Bottom' { $Shape.CellsSRC(7, $row, 0).FormulaU = 'Width*0.5'; $Shape.CellsSRC(7, $row, 1).FormulaU = '0' }
    }
    $row
}

function Add-Connector {
    param(
        [string]$Name,
        $From,
        [string]$FromSide,
        $To,
        [string]$ToSide,
        [string]$Color = '#17212B',
        [double]$Weight = 1.6,
        [bool]$Arrow = $true,
        [double]$HorizontalY = [double]::NaN
    )
    $connector = $script:page.Drop($script:visio.ConnectorToolDataObject, 0, 0)
    $connector.NameU = $Name
    $fromRow = Add-ConnectionPoint $From $FromSide $HorizontalY
    $toRow = Add-ConnectionPoint $To $ToSide $HorizontalY
    $connector.CellsU('BeginX').GlueTo($From.CellsSRC(7, $fromRow, 0))
    $connector.CellsU('EndX').GlueTo($To.CellsSRC(7, $toRow, 0))
    Set-CellFormula $connector 'LineColor' (Convert-HexToRgbFormula $Color)
    Set-CellFormula $connector 'LineWeight' "$Weight pt"
    Set-CellFormula $connector 'EndArrow' $(if ($Arrow) { '4' } else { '0' })
    Set-CellFormula $connector 'EndArrowSize' '2'
    Set-CellFormula $connector 'ShapeRouteStyle' $(if ([double]::IsNaN($HorizontalY)) { '1' } else { '2' })
    Add-ToLayer $connector 'Connectors'
    $script:shapes[$Name] = $connector
    $connector
}

function Add-ResidualConnector {
    param(
        [string]$Name,
        $From,
        $To,
        [double]$LaneY
    )
    $x1 = $From.CellsU('PinX').ResultIU
    $x2 = $To.CellsU('PinX').ResultIU
    $fromTop = $From.CellsU('PinY').ResultIU + ($From.CellsU('Height').ResultIU / 2)
    $toTop = $To.CellsU('PinY').ResultIU + ($To.CellsU('Height').ResultIU / 2)
    $segments = @()
    $segments += $script:page.DrawLine($x1, $fromTop, $x1, $LaneY)
    $segments += $script:page.DrawLine($x1, $LaneY, $x2, $LaneY)
    $segments += $script:page.DrawLine($x2, $LaneY, $x2, $toTop)
    $fromRow = Add-ConnectionPoint $From 'Top'
    $toRow = Add-ConnectionPoint $To 'Top'
    $segments[0].CellsU('BeginX').GlueTo($From.CellsSRC(7, $fromRow, 0))
    $segments[2].CellsU('EndX').GlueTo($To.CellsSRC(7, $toRow, 0))
    for ($i = 0; $i -lt $segments.Count; $i++) {
        $segments[$i].NameU = "${Name}_$i"
        Set-CellFormula $segments[$i] 'LineColor' 'RGB(23,33,43)'
        Set-CellFormula $segments[$i] 'LineWeight' '1.6 pt'
        if ($i -eq $segments.Count - 1) { Set-CellFormula $segments[$i] 'EndArrow' '4' }
        Add-ToLayer $segments[$i] 'Connectors'
    }
    $segments
}

function Capture-VisioFrame {
    param([string]$Slug, [string]$Label)
    $script:frameIndex++
    [void]$script:document.Save()
    $script:visio.ActiveWindow.ViewFit = 1
    [VisioDemoNative]::ShowWindow($script:windowHandle, 3) | Out-Null
    [VisioDemoNative]::SetForegroundWindow($script:windowHandle) | Out-Null
    Start-Sleep -Milliseconds 650
    $rect = New-Object VisioDemoNative+RECT
    if (-not [VisioDemoNative]::GetWindowRect($script:windowHandle, [ref]$rect)) {
        throw 'Unable to capture the Visio window rectangle.'
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $graphics.Dispose()
    $file = Join-Path $frameRoot ('{0:D2}-{1}.png' -f $script:frameIndex, $Slug)
    $bitmap.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    [pscustomobject]@{ Index = $script:frameIndex; Label = $Label; File = $file }
}

try {
    $script:visio = New-Object -ComObject Visio.Application
    $script:visio.Visible = $true
    $script:document = $script:visio.Documents.Add('')
    $script:page = $script:visio.ActivePage
    $script:page.Name = 'Transformer Encoder'
    $script:page.PageSheet.CellsU('PageWidth').ResultIU = 16
    $script:page.PageSheet.CellsU('PageHeight').ResultIU = 9
    $script:page.PageSheet.CellsU('PageScale').ResultIU = 1
    $script:page.PageSheet.CellsU('DrawingScale').ResultIU = 1
    $vsdxPath = Join-Path $outputRoot 'transformer-encoder-demo.vsdx'
    [void]$script:document.SaveAs($vsdxPath)

    foreach ($layerName in @('Containers', 'Modules', 'Operators', 'Connectors', 'Labels')) {
        $script:layers[$layerName] = $script:page.Layers.Add($layerName)
    }

    $process = Get-Process VISIO | Sort-Object StartTime | Select-Object -Last 1
    $script:windowHandle = $process.MainWindowHandle
    [VisioDemoNative]::ShowWindow($script:windowHandle, 3) | Out-Null
    [VisioDemoNative]::SetForegroundWindow($script:windowHandle) | Out-Null
    $script:visio.ActiveWindow.ViewFit = 1
    $frames = @()

    Add-Text 'MainTitle' 0.3 8.35 15.7 8.82 'Transformer Encoder — Evidence to Editable Visio' 20 '#17365D' $true | Out-Null
    Add-Text 'Subtitle' 0.3 8.03 15.7 8.32 'Original architecture · d_model = 512 · 8 attention heads · feed-forward 2048 · N = 6 layers' 10 '#52606D' $false | Out-Null
    $frames += Capture-VisioFrame 'blank-canvas' 'Open Visio and establish the 16:9 canvas'

    $stageSpecs = @(
        @('Stage1', 0.25, 1.25, 1.72, 7.75, '1  Input Tokens', '#254E7B'),
        @('Stage2', 1.87, 1.25, 4.00, 7.75, '2  Embedding + Position', '#254E7B'),
        @('Stage3', 4.15, 1.25, 7.15, 7.75, '3  Multi-Head Self-Attention', '#238C88'),
        @('Stage4', 7.30, 1.25, 9.10, 7.75, '4  Add & LayerNorm', '#6353B5'),
        @('Stage5', 9.25, 1.25, 12.60, 7.75, '5  Feed-Forward Network', '#C77C10'),
        @('Stage6', 12.75, 1.25, 15.75, 7.75, '6  Add & Norm / Output', '#254E7B')
    )
    foreach ($spec in $stageSpecs) {
        $container = Add-Rect $spec[0] $spec[1] $spec[2] $spec[3] $spec[4] '' '#FFFFFF' $spec[6] 1.2 1 '#15202B' $false $false 'Containers'
        Set-CellFormula $container 'Rounding' '0.10 in'
        Add-Text ("{0}_Title" -f $spec[0]) ($spec[1] + 0.08) 7.02 ($spec[3] - 0.08) 7.62 $spec[5] 13 $spec[6] $true | Out-Null
    }
    $encoderOutline = Add-Rect 'EncoderLayerOutline' 4.08 1.07 15.83 7.91 '' '#FFFFFF' '#244A8F' 1.6 1 '#15202B' $false $false 'Containers'
    Set-CellFormula $encoderOutline 'FillPattern' '0'
    Set-CellFormula $encoderOutline 'LinePattern' '2'
    Add-Text 'EncoderLayerLabel' 8.0 0.68 12.2 1.05 'Encoder Layer × 6' 15 '#244A8F' $true | Out-Null
    $frames += Capture-VisioFrame 'stage-layout' 'Lay out six aligned stage containers and the ×6 encoder boundary'

    $tokens = Add-Cuboid 'TokenIDs' 0.55 3.25 0.82 1.55 "Token IDs`n[B × L]" '#244A8F' '#B5CBEA' '#17365D' 13 '#FFFFFF'
    $embedding = Add-Cuboid 'TokenEmbedding' 2.15 4.45 1.30 1.02 "Token Embedding`n[B × L × 512]" '#4F81BD' '#C9DDF4' '#2E5C8A' 11 '#FFFFFF'
    $position = Add-Cuboid 'PositionEncoding' 2.25 2.55 1.12 1.02 "Positional Encoding`n[L × 512]" '#79A9DC' '#DDEAF7' '#3F78B4' 10 '#15202B'
    $mainFlowY = 3.97
    $plus = Add-Rect 'EmbeddingPlus' 3.52 3.77 3.92 4.17 '+' '#FFFFFF' '#244A8F' 1.5 22 '#244A8F' $true $false 'Operators'
    Set-CellFormula $plus 'Rounding' '50%'
    Add-Connector 'TokensToEmbedding' $tokens 'Right' $embedding 'Left' | Out-Null
    Add-Connector 'EmbeddingToPlus' $embedding 'Right' $plus 'Left' | Out-Null
    Add-Connector 'PositionToPlus' $position 'Right' $plus 'Bottom' | Out-Null
    $frames += Capture-VisioFrame 'input-embedding' 'Build native token, embedding, position, and addition objects'

    $attention = Add-Cuboid 'Attention' 4.55 3.15 2.15 1.65 "Multi-Head`nSelf-Attention`n8 heads`nd_model = 512" '#2B9C98' '#BFE8E5' '#18706D' 13 '#FFFFFF'
    Add-Connector 'PlusToAttention' $plus 'Right' $attention 'Left' '#17212B' 1.7 $true $mainFlowY | Out-Null
    Add-Text 'HeadsLabel' 4.55 2.55 6.80 2.88 '8 independent attention heads' 9 '#18706D' $true | Out-Null
    for ($head = 1; $head -le 8; $head++) {
        $headX = 4.52 + (($head - 1) * 0.28)
        Add-Cuboid ("Head$head") $headX 1.85 0.20 0.46 "$head" '#43B7B1' '#D1F0EE' '#23817D' 8 '#FFFFFF' | Out-Null
    }
    $frames += Capture-VisioFrame 'attention-heads' 'Create the multi-head attention module and eight editable head blocks'

    $norm1 = Add-Cuboid 'AddNorm1' 7.62 3.32 1.10 1.30 "Add +`nLayerNorm`n[B × L × 512]" '#7B6CCB' '#DCD7F5' '#51439A' 11 '#FFFFFF'
    Add-Connector 'AttentionToNorm1' $attention 'Right' $norm1 'Left' '#17212B' 1.7 $true $mainFlowY | Out-Null
    Add-ResidualConnector 'Residual1' $plus $norm1 6.40 | Out-Null
    Add-Text 'Residual1Label' 5.25 6.48 7.55 6.76 'Residual connection' 9 '#52606D' $false | Out-Null
    $frames += Capture-VisioFrame 'first-residual' 'Route the first residual path through a reserved upper lane'

    $ffn = Add-Cuboid 'FFN' 9.67 2.72 2.45 2.62 '' '#E6A23C' '#F9E4B5' '#B87511' 13 '#15202B'
    Add-Text 'FFNModuleTitle' 9.92 4.86 11.92 5.18 'Position-wise FFN' 11 '#6B4305' $true | Out-Null
    $linear1 = Add-Rect 'Linear1' 9.98 4.24 11.82 4.76 'Linear  512 → 2048' '#FFF6E5' '#A96B0B' 1.0 10 '#533900' $true $false 'Modules'
    $relu = Add-Rect 'ReLU' 10.18 3.55 11.62 4.00 'ReLU' '#FFF6E5' '#A96B0B' 1.0 11 '#533900' $true $false 'Operators'
    $linear2 = Add-Rect 'Linear2' 9.98 2.94 11.82 3.42 'Linear  2048 → 512' '#FFF6E5' '#A96B0B' 1.0 10 '#533900' $true $false 'Modules'
    Add-Connector 'Norm1ToFFN' $norm1 'Right' $ffn 'Left' '#17212B' 1.7 $true $mainFlowY | Out-Null
    Add-Connector 'Linear1ToReLU' $linear1 'Bottom' $relu 'Top' '#8B5A0A' 1.2 $true | Out-Null
    Add-Connector 'ReLUToLinear2' $relu 'Bottom' $linear2 'Top' '#8B5A0A' 1.2 $true | Out-Null
    $frames += Capture-VisioFrame 'feed-forward' 'Assemble the 512→2048→512 feed-forward network from independent shapes'

    $norm2 = Add-Cuboid 'AddNorm2' 13.08 3.32 1.10 1.30 "Add +`nLayerNorm`n[B × L × 512]" '#7B6CCB' '#DCD7F5' '#51439A' 11 '#FFFFFF'
    $output = Add-Cuboid 'EncoderOutput' 14.55 3.32 0.88 1.30 "Encoder`nOutput`n[B × L × 512]" '#244A8F' '#B5CBEA' '#17365D' 11 '#FFFFFF'
    Add-Connector 'FFNToNorm2' $ffn 'Right' $norm2 'Left' '#17212B' 1.7 $true $mainFlowY | Out-Null
    Add-Connector 'Norm2ToOutput' $norm2 'Right' $output 'Left' '#17212B' 1.7 $true $mainFlowY | Out-Null
    Add-ResidualConnector 'Residual2' $norm1 $norm2 6.85 | Out-Null
    Add-Text 'Residual2Label' 9.25 6.92 12.65 7.18 'Residual connection' 9 '#52606D' $false | Out-Null
    Add-Text 'Caption' 2.0 0.18 14.0 0.55 'Transformer encoder reconstructed with native editable Microsoft Visio shapes.' 12 '#25313C' $false | Out-Null
    $frames += Capture-VisioFrame 'second-residual-output' 'Complete the second residual path, LayerNorm, and encoder output'

    [void]$script:document.Save()
    $script:page.Export((Join-Path $outputRoot 'transformer-encoder-demo.png'))
    try {
        $script:document.ExportAsFixedFormat(1, (Join-Path $outputRoot 'transformer-encoder-demo.pdf'), 1, 0, 1, -1, $false, $true, $true, $true, $false)
    } catch {
        Write-Warning "PDF export was unavailable: $($_.Exception.Message)"
    }

    # Reopen the saved VSDX before the editability proof frames. This catches
    # save/load damage and proves that grouped cuboids, labels, and connectors
    # remain native Visio objects after round-tripping through the file format.
    $script:document.Close()
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($script:document)
    $script:document = $script:visio.Documents.Open($vsdxPath)
    $script:page = $script:document.Pages.ItemU('Transformer Encoder')
    $script:visio.ActiveWindow.Page = $script:page
    $script:visio.ActiveWindow.ViewFit = 1
    Start-Sleep -Milliseconds 700
    $frames += Capture-VisioFrame 'reopened-vsdx' 'Reopen the saved VSDX and verify the native page survived the round trip'

    $script:visio.ActiveWindow.DeselectAll()
    $script:visio.ActiveWindow.Select($script:page.Shapes.ItemU('Attention'), 2)
    $frames += Capture-VisioFrame 'editability-shape' 'Select the native attention group to demonstrate independent editability'
    $script:visio.ActiveWindow.DeselectAll()
    $script:visio.ActiveWindow.Select($script:page.Shapes.ItemU('Norm2ToOutput'), 2)
    $frames += Capture-VisioFrame 'editability-connector' 'Select a glued connector to demonstrate native routing and editability'
    $script:visio.ActiveWindow.DeselectAll()

    $frames | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputRoot 'frame-manifest.json') -Encoding utf8
    $frames | Format-Table Index, Label, File
}
finally {
    if ($script:document) { try { [void]$script:document.Save() } catch { } }
    if (-not $KeepVisioOpen -and $script:visio) {
        try { $script:visio.Quit() } catch { }
    }
    foreach ($name in @('page', 'document', 'visio')) {
        $value = Get-Variable -Name $name -Scope Script -ValueOnly -ErrorAction SilentlyContinue
        if ($value) { try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($value) } catch { } }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
