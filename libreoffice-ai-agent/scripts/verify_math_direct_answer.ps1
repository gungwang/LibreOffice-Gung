param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Explain what this formula represents.",
	[string]$InitialFormula = "a^2 + b^2 = c^2",
	[string]$Provider,
	[string]$Model,
	[string]$ExpectedProvider,
	[string]$ExpectedModel,
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-vfy-math-answer"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_math_direct_answer.py"
$previousProvider = Get-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
$previousModel = Get-Item -Path Env:LOAIA_DEFAULT_MODEL -ErrorAction SilentlyContinue

$resolvedExpectedProvider = if ($ExpectedProvider) {
	$ExpectedProvider
} elseif ($Provider) {
	$Provider
} elseif ($env:LOAIA_DEFAULT_PROVIDER) {
	$env:LOAIA_DEFAULT_PROVIDER
} else {
	"openai-compatible"
}

$resolvedExpectedModel = if ($ExpectedModel) {
	$ExpectedModel
} elseif ($Model) {
	$Model
} elseif ($env:LOAIA_DEFAULT_MODEL) {
	$env:LOAIA_DEFAULT_MODEL
} else {
	"local-default"
}

$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
$resolvedStateRootDir = if ($null -ne $previousStateRoot -and $previousStateRoot.Value) {
	[System.IO.Path]::GetFullPath($previousStateRoot.Value)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $resolvedUserProfileDir "loaia-extension-state"))
}

try {
	$env:LOAIA_EXTENSION_STATE_ROOT = $resolvedStateRootDir

	if ($Provider) {
		$env:LOAIA_DEFAULT_PROVIDER = $Provider
	}

	if ($Model) {
		$env:LOAIA_DEFAULT_MODEL = $Model
	}

	$probeArguments = @{
		ProjectRoot = $projectRootPath
		LibreOfficeProgramPath = $LibreOfficeProgramPath
		UserProfileDir = $resolvedUserProfileDir
		ProbeScriptPath = $probeScriptPath
		ProbeArguments = @(
			$Prompt,
			$InitialFormula,
			$resolvedExpectedProvider,
			$resolvedExpectedModel
		)
		SidecarPythonPath = $PythonPath
		SkipBuild = $SkipBuild
		ResetUserProfileDir = -not $UserProfileDir
		StartSidecar = $true
	}

	$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
} finally {
	if ($Provider) {
		if ($null -ne $previousProvider) {
			$env:LOAIA_DEFAULT_PROVIDER = $previousProvider.Value
		} else {
			Remove-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
		}
	}

	if ($Model) {
		if ($null -ne $previousModel) {
			$env:LOAIA_DEFAULT_MODEL = $previousModel.Value
		} else {
			Remove-Item -Path Env:LOAIA_DEFAULT_MODEL -ErrorAction SilentlyContinue
		}
	}

	if ($null -ne $previousStateRoot) {
		$env:LOAIA_EXTENSION_STATE_ROOT = $previousStateRoot.Value
	} else {
		Remove-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
	}
}

exit $probeExitCode
