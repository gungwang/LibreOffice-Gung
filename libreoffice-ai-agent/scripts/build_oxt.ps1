param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$OutputDir,
	[string]$StageDir,
	[string]$PackageName = "libreoffice-ai-agent.oxt"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Reset-Directory {
	param([string]$Path)

	if (Test-Path -LiteralPath $Path) {
		Remove-Item -LiteralPath $Path -Recurse -Force
	}

	New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedOutputDir = if ($OutputDir) {
	[System.IO.Path]::GetFullPath($OutputDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "dist"))
}
$resolvedStageDir = if ($StageDir) {
	[System.IO.Path]::GetFullPath($StageDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\oxt-stage"))
}

$assetRoot = Join-Path $projectRootPath "extension\oxt"
$sourceRoot = Join-Path $projectRootPath "extension\src"

if (-not (Test-Path -LiteralPath $assetRoot)) {
	throw "OXT asset directory not found: $assetRoot"
}

if (-not (Test-Path -LiteralPath $sourceRoot)) {
	throw "Extension source directory not found: $sourceRoot"
}

Reset-Directory -Path $resolvedStageDir
New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null

Copy-Item -Path (Join-Path $assetRoot "*") -Destination $resolvedStageDir -Recurse -Force
Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $resolvedStageDir -Recurse -Force

$packagePath = Join-Path $resolvedOutputDir $PackageName
if (Test-Path -LiteralPath $packagePath) {
	Remove-Item -LiteralPath $packagePath -Force
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($resolvedStageDir, $packagePath)
Write-Output $packagePath
