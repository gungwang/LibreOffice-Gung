param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please summarize this selection.",
	[string]$InitialSelection = "hello world",
	[string]$ExpectedAnswer = "Sidecar scaffold is running. Planner and provider execution are not implemented yet.",
	[switch]$ExpectNonScaffoldAnswer,
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

$defaultScaffoldAnswer = "Sidecar scaffold is running. Planner and provider execution are not implemented yet."

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-vfy-da"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_direct_answer.py"
$sentinelAnswer = "__NON_SCAFFOLD__"


$resolvedProvider = if ($Provider) {
	$Provider
} elseif ($env:LOAIA_DEFAULT_PROVIDER) {
	$env:LOAIA_DEFAULT_PROVIDER
} else {
	"openai-compatible"
}

$resolvedModel = if ($Model) {
	$Model
} elseif ($env:LOAIA_DEFAULT_MODEL) {
	$env:LOAIA_DEFAULT_MODEL
} else {
	"local-default"
}

$resolvedExpectedProvider = if ($ExpectedProvider) {
	$ExpectedProvider
} else {
	$resolvedProvider
}

$resolvedExpectedModel = if ($ExpectedModel) {
	$ExpectedModel
} else {
	$resolvedModel
}

if (
	-not $ExpectNonScaffoldAnswer -and
	$ExpectedAnswer -eq $defaultScaffoldAnswer -and
	$resolvedProvider -ne "openai-compatible"
) {
	$ExpectNonScaffoldAnswer = $true
}


$shouldAssertProviderDetails = (
	$ExpectNonScaffoldAnswer -or
	$PSBoundParameters.ContainsKey("Provider") -or
	$PSBoundParameters.ContainsKey("Model") -or
	$PSBoundParameters.ContainsKey("ExpectedProvider") -or
	$PSBoundParameters.ContainsKey("ExpectedModel")
)

$resolvedProbeArguments = if ($ExpectNonScaffoldAnswer) {
	@($Prompt, $InitialSelection, $sentinelAnswer, $resolvedExpectedProvider, $resolvedExpectedModel)
	} elseif ($shouldAssertProviderDetails) {
	@($Prompt, $InitialSelection, $ExpectedAnswer, $resolvedExpectedProvider, $resolvedExpectedModel)
} else {
	@($Prompt, $InitialSelection, $ExpectedAnswer)
}

$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = $resolvedProbeArguments
	SidecarPythonPath = $PythonPath
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
	StartSidecar = $true
}

$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
$resolvedStateRootDir = if ($null -ne $previousStateRoot -and $previousStateRoot.Value) {
	[System.IO.Path]::GetFullPath($previousStateRoot.Value)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $resolvedUserProfileDir "loaia-extension-state"))
}

$previousProvider = Get-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
$previousModel = Get-Item -Path Env:LOAIA_DEFAULT_MODEL -ErrorAction SilentlyContinue

try {
	$env:LOAIA_EXTENSION_STATE_ROOT = $resolvedStateRootDir

	if ($PSBoundParameters.ContainsKey("Provider")) {
		$env:LOAIA_DEFAULT_PROVIDER = $Provider
	}

	if ($PSBoundParameters.ContainsKey("Model")) {
		$env:LOAIA_DEFAULT_MODEL = $Model
	}

	$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
} finally {
	if ($PSBoundParameters.ContainsKey("Provider")) {
		if ($null -ne $previousProvider) {
			$env:LOAIA_DEFAULT_PROVIDER = $previousProvider.Value
		} else {
			Remove-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
		}
	}

	if ($PSBoundParameters.ContainsKey("Model")) {
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