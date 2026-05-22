param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please summarize this selection.",
	[string]$InitialSelection = "hello world",
	[string]$Provider = "openrouter",
	[string]$Model = "openai/gpt-4.1-mini",
	[string]$ExpectedError = "OpenRouter API key is not configured. Set OPENROUTER_API_KEY or LOAIA_OPENROUTER_API_KEY.",
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-provider-failure"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_provider_failure.py"
$stateRootDir = Join-Path $resolvedUserProfileDir "loaia-extension-state"
$keyEnvVars = @("LOAIA_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")
$missingKeyPlaceholder = " "
$previousKeyItems = @{}
$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue

foreach ($envVar in $keyEnvVars) {
	$previousKeyItems[$envVar] = Get-Item -Path ("Env:" + $envVar) -ErrorAction SilentlyContinue
}

try {
	$env:LOAIA_EXTENSION_STATE_ROOT = $stateRootDir

	foreach ($envVar in $keyEnvVars) {
		Set-Item -Path ("Env:" + $envVar) -Value $missingKeyPlaceholder
	}

	$probeArguments = @{
		ProjectRoot = $projectRootPath
		LibreOfficeProgramPath = $LibreOfficeProgramPath
		UserProfileDir = $resolvedUserProfileDir
		ProbeScriptPath = $probeScriptPath
		ProbeArguments = @(
			$Prompt,
			$InitialSelection,
			$Provider,
			$Model,
			$ExpectedError
		)
		SidecarPythonPath = $PythonPath
		SidecarExtraArguments = @(
			"-ClearEnvVars",
			"LOAIA_OPENROUTER_API_KEY;OPENROUTER_API_KEY"
		)
		SidecarEnvironment = @{
			LOAIA_OPENROUTER_API_KEY = $missingKeyPlaceholder
			OPENROUTER_API_KEY = $missingKeyPlaceholder
		}
		SkipBuild = $SkipBuild
		ResetUserProfileDir = -not $UserProfileDir
		StartSidecar = $true
	}

	$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
} finally {
	if ($null -ne $previousStateRoot) {
		$env:LOAIA_EXTENSION_STATE_ROOT = $previousStateRoot.Value
	} else {
		Remove-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
	}

	foreach ($envVar in $keyEnvVars) {
		$previousItem = $previousKeyItems[$envVar]
		if ($null -ne $previousItem) {
			Set-Item -Path ("Env:" + $envVar) -Value $previousItem.Value
		} else {
			Remove-Item -Path ("Env:" + $envVar) -ErrorAction SilentlyContinue
		}
	}
}

exit $probeExitCode