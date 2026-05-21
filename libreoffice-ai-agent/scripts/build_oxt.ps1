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

function Remove-PythonCaches {
	param([string]$Root)

	Get-ChildItem -Path $Root -Recurse -Directory -Filter "__pycache__" |
		Remove-Item -Recurse -Force
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

Remove-PythonCaches -Root $resolvedStageDir

$pythonRuntimeDir = Join-Path $resolvedStageDir "loaia"
if (Test-Path -LiteralPath $pythonRuntimeDir) {
	$pythonZipPath = Join-Path $resolvedStageDir "pythonpath.zip"
	$pythonZipStageDir = Join-Path $resolvedStageDir "pythonpath-stage"
	if (Test-Path -LiteralPath $pythonZipPath) {
		Remove-Item -LiteralPath $pythonZipPath -Force
	}
	Reset-Directory -Path $pythonZipStageDir
	Copy-Item -Path $pythonRuntimeDir -Destination $pythonZipStageDir -Recurse -Force

	[System.IO.Compression.ZipFile]::CreateFromDirectory($pythonZipStageDir, $pythonZipPath)
	Remove-Item -LiteralPath $pythonZipStageDir -Recurse -Force
	Remove-Item -LiteralPath $pythonRuntimeDir -Recurse -Force
}

$packagePath = Join-Path $resolvedOutputDir $PackageName
if (Test-Path -LiteralPath $packagePath) {
	Remove-Item -LiteralPath $packagePath -Force
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($resolvedStageDir, $packagePath)
Write-Output $packagePath
