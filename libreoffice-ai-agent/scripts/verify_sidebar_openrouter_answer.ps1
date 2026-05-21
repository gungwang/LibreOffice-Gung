param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please summarize this selection in one sentence.",
	[string]$InitialSelection = "hello world",
	[string]$Model = "openai/gpt-4.1-mini",
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
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-openrouter-answer"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_openrouter_answer.py"

$previousProvider = Get-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
$previousModel = Get-Item -Path Env:LOAIA_DEFAULT_MODEL -ErrorAction SilentlyContinue

try {
	$env:LOAIA_DEFAULT_PROVIDER = "openrouter"
	$env:LOAIA_DEFAULT_MODEL = $Model

	$probeArguments = @{
		ProjectRoot = $projectRootPath
		LibreOfficeProgramPath = $LibreOfficeProgramPath
		UserProfileDir = $resolvedUserProfileDir
		ProbeScriptPath = $probeScriptPath
		ProbeArguments = @($Prompt, $InitialSelection, "openrouter", $Model)
		SidecarPythonPath = $PythonPath
		SkipBuild = $SkipBuild
		ResetUserProfileDir = -not $UserProfileDir
		StartSidecar = $true
	}

	$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
} finally {
	if ($null -ne $previousProvider) {
		$env:LOAIA_DEFAULT_PROVIDER = $previousProvider.Value
	} else {
		Remove-Item -Path Env:LOAIA_DEFAULT_PROVIDER -ErrorAction SilentlyContinue
	}

	if ($null -ne $previousModel) {
		$env:LOAIA_DEFAULT_MODEL = $previousModel.Value
	} else {
		Remove-Item -Path Env:LOAIA_DEFAULT_MODEL -ErrorAction SilentlyContinue
	}
}

exit $probeExitCode