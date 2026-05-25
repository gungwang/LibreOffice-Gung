param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$OutputDir,
	[string]$StageDir,
	[string]$PackageName = "libreoffice-ai-agent.oxt",
	[string]$PythonPath
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
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath (
		"build\oxt-stage-{0}" -f [guid]::NewGuid().ToString("N")
	)))
}
$shouldCleanupStageDir = -not $StageDir

$assetRoot = Join-Path $projectRootPath "extension\oxt"
$sourceRoot = Join-Path $projectRootPath "extension\src"
$sharedSourceRoot = Join-Path $projectRootPath "shared\src"

if (-not (Test-Path -LiteralPath $assetRoot)) {
	throw "OXT asset directory not found: $assetRoot"
}

if (-not (Test-Path -LiteralPath $sourceRoot)) {
	throw "Extension source directory not found: $sourceRoot"
}

if (-not (Test-Path -LiteralPath $sharedSourceRoot)) {
	throw "Shared source directory not found: $sharedSourceRoot"
}

Reset-Directory -Path $resolvedStageDir
New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null

Copy-Item -Path (Join-Path $assetRoot "*") -Destination $resolvedStageDir -Recurse -Force
Copy-Item -Path (Join-Path $sourceRoot "*") -Destination $resolvedStageDir -Recurse -Force
Copy-Item -Path (Join-Path $sharedSourceRoot "loaia_shared") -Destination $resolvedStageDir -Recurse -Force

Remove-PythonCaches -Root $resolvedStageDir


$pythonRuntimePackages = @("loaia", "loaia_shared")
$pythonRuntimeDirs = @(
	$pythonRuntimePackages |
		ForEach-Object {
			Join-Path $resolvedStageDir $_
		} |
		Where-Object {
			Test-Path -LiteralPath $_
		}
)

if ($pythonRuntimeDirs.Count -gt 0) {
	# Use a pythonpath/ directory (not zip) because pydantic_core has compiled .pyd files.
	$pythonpathDir = Join-Path $resolvedStageDir "pythonpath"
	if (Test-Path -LiteralPath $pythonpathDir) {
		Remove-Item -LiteralPath $pythonpathDir -Recurse -Force
	}
	New-Item -ItemType Directory -Path $pythonpathDir -Force | Out-Null

	foreach ($pythonRuntimeDir in $pythonRuntimeDirs) {
		Copy-Item -Path $pythonRuntimeDir -Destination $pythonpathDir -Recurse -Force
	}

	# Vendor pydantic and its runtime dependencies using the target Python
	# so the compiled pydantic_core .pyd matches the LibreOffice Python ABI.
	$resolvedPythonPath = if ($PythonPath) {
		$PythonPath
	} else {
		$loCandidates = @(
			"C:\Program Files\LibreOffice\26\program\python.exe",
			"C:\Program Files\LibreOffice\program\python.exe"
		)
		$found = $loCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
		if ($found) { $found } else { "python" }
	}
	$vendorDepsDir = Join-Path $resolvedStageDir "vendor-deps"
	if (Test-Path -LiteralPath $vendorDepsDir) {
		Remove-Item -LiteralPath $vendorDepsDir -Recurse -Force
	}
	New-Item -ItemType Directory -Path $vendorDepsDir -Force | Out-Null
	& $resolvedPythonPath -m pip install --target $vendorDepsDir "pydantic>=2.7,<3" 2>&1 | Out-Null
	# Copy all installed packages (dirs and single-file modules), skipping dist-info.
	Get-ChildItem -LiteralPath $vendorDepsDir -Directory |
		Where-Object { $_.Name -notlike "*.dist-info" -and $_.Name -ne "__pycache__" } |
		ForEach-Object {
			Copy-Item -Path $_.FullName -Destination $pythonpathDir -Recurse -Force
		}
	Get-ChildItem -LiteralPath $vendorDepsDir -File -Filter "*.py" |
		ForEach-Object {
			Copy-Item -Path $_.FullName -Destination $pythonpathDir -Force
		}
	Remove-Item -LiteralPath $vendorDepsDir -Recurse -Force

	# Remove the old pythonpath.zip if it exists and the top-level source dirs.
	$pythonZipPath = Join-Path $resolvedStageDir "pythonpath.zip"
	if (Test-Path -LiteralPath $pythonZipPath) {
		Remove-Item -LiteralPath $pythonZipPath -Force
	}
	foreach ($pythonRuntimeDir in $pythonRuntimeDirs) {
		Remove-Item -LiteralPath $pythonRuntimeDir -Recurse -Force
	}

	Remove-PythonCaches -Root $pythonpathDir
}

$packagePath = Join-Path $resolvedOutputDir $PackageName
if (Test-Path -LiteralPath $packagePath) {
	Remove-Item -LiteralPath $packagePath -Force
}

[System.IO.Compression.ZipFile]::CreateFromDirectory($resolvedStageDir, $packagePath)
if ($shouldCleanupStageDir -and (Test-Path -LiteralPath $resolvedStageDir)) {
	Remove-Item -LiteralPath $resolvedStageDir -Recurse -Force
}
Write-Output $packagePath
