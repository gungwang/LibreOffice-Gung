param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$PythonPath,
	[string]$ClearEnvVars = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env_common.ps1")

function Resolve-PythonPath {
	param([string]$RequestedPath)

	$candidates = @($RequestedPath)
	$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
	if ($pythonCommand -and $pythonCommand.Path) {
		$candidates += $pythonCommand.Path
	}

	foreach ($candidate in $candidates | Where-Object { $_ }) {
		if (Test-Path -LiteralPath $candidate) {
			return [System.IO.Path]::GetFullPath($candidate)
		}
	}

	throw "Python executable not found. Pass -PythonPath or make python available on PATH."
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
if (-not (Test-Path -LiteralPath $projectRootPath)) {
	throw "Project root not found: $projectRootPath"
}

foreach ($envVar in @($ClearEnvVars -split ";")) {
	if (-not [string]::IsNullOrWhiteSpace($envVar)) {
		Set-Item -Path ("Env:" + $envVar.Trim()) -Value " "
	}
}

Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedPythonPath = Resolve-PythonPath -RequestedPath $PythonPath
$pythonPathEntries = @(
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "sidecar\src")),
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "shared\src")),
	$env:PYTHONPATH
) | Where-Object { $_ }
$env:PYTHONPATH = $pythonPathEntries -join [System.IO.Path]::PathSeparator

$exitCode = 0
Push-Location $projectRootPath
try {
	& $resolvedPythonPath -m loaia_sidecar.main
	$exitCode = $LASTEXITCODE
} finally {
	Pop-Location
}

exit $exitCode
