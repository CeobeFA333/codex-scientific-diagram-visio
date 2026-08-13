param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot ".codex-plugin\plugin.json"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$version = [string]$manifest.version
$pluginName = [string]$manifest.name
$outputRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
$expectedRoot = [System.IO.Path]::GetFullPath($repoRoot)

if (-not $outputRoot.StartsWith($expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output directory must remain inside the repository: $outputRoot"
}

if (Test-Path -LiteralPath $outputRoot) {
    Remove-Item -LiteralPath $outputRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $outputRoot | Out-Null

$stageRoot = Join-Path $outputRoot "stage"
$pluginStage = Join-Path $stageRoot $pluginName
New-Item -ItemType Directory -Path $pluginStage | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot ".codex-plugin") -Destination $pluginStage -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "skills") -Destination $pluginStage -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $repoRoot "PRIVACY.md") -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $repoRoot "TERMS.md") -Destination $pluginStage

$pluginZip = Join-Path $outputRoot "$pluginName-plugin-v$version.zip"
Compress-Archive -LiteralPath $pluginStage -DestinationPath $pluginZip -CompressionLevel Optimal

$teamStage = Join-Path $stageRoot "$pluginName-team-trial-v$version"
New-Item -ItemType Directory -Path $teamStage | Out-Null
Copy-Item -LiteralPath $pluginStage -Destination (Join-Path $teamStage $pluginName) -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "TEAM-TRIAL.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "README.zh-CN.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "DESIGN.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "SECURITY.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "PRIVACY.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "TERMS.md") -Destination $teamStage
Copy-Item -LiteralPath (Join-Path $repoRoot "examples\transformer-encoder-demo") -Destination (Join-Path $teamStage "transformer-encoder-demo") -Recurse

$teamZip = Join-Path $outputRoot "$pluginName-team-trial-v$version.zip"
Compress-Archive -LiteralPath $teamStage -DestinationPath $teamZip -CompressionLevel Optimal

Remove-Item -LiteralPath $stageRoot -Recurse -Force

$artifacts = Get-Item -LiteralPath $pluginZip, $teamZip
$checksums = $artifacts | ForEach-Object {
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
    [PSCustomObject]@{
        File = $_.Name
        Bytes = $_.Length
        SHA256 = $hash.Hash
    }
}

$checksumPath = Join-Path $outputRoot "SHA256SUMS.txt"
$checksums | ForEach-Object { "$($_.SHA256)  $($_.File)" } |
    Set-Content -LiteralPath $checksumPath -Encoding ascii
$checksums | Format-Table -AutoSize
Write-Host "Checksums: $checksumPath"
