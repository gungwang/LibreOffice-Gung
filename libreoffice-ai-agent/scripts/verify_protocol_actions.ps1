param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialSelection = "hello world",
	[string]$ExpectedText = "HELLO WORLD",
	[switch]$ExpectChangedText,
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

$changedTextSentinel = "__CHANGED_TEXT__"

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-protocol"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_protocol_actions.py"
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

$resolvedExpectedText = if ($ExpectChangedText) {
	$changedTextSentinel
} else {
	$ExpectedText
}

try {
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
			$InitialSelection,
			$resolvedExpectedText,
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
}

exit $probeExitCode