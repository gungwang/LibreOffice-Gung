param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please summarize this selection.",
	[string]$InitialSelection = "hello world",
	[string]$ExpectedAnswer = "Sidecar scaffold is running. Planner and provider execution are not implemented yet.",
	[switch]$ExpectNonScaffoldAnswer,
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
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-direct-answer"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_direct_answer.py"
$sentinelAnswer = "__NON_SCAFFOLD__"

$resolvedExpectedProvider = if ($ExpectedProvider) {
	$ExpectedProvider
} elseif ($env:LOAIA_DEFAULT_PROVIDER) {
	$env:LOAIA_DEFAULT_PROVIDER
} else {
	"openai-compatible"
}

$resolvedExpectedModel = if ($ExpectedModel) {
	$ExpectedModel
} elseif ($env:LOAIA_DEFAULT_MODEL) {
	$env:LOAIA_DEFAULT_MODEL
} else {
	"local-default"
}

if (
	-not $ExpectNonScaffoldAnswer -and
	$ExpectedAnswer -eq $defaultScaffoldAnswer -and
	$resolvedExpectedProvider -ne "openai-compatible"
) {
	$ExpectNonScaffoldAnswer = $true
}

$resolvedProbeArguments = if ($ExpectNonScaffoldAnswer) {
	@($Prompt, $InitialSelection, $sentinelAnswer, $resolvedExpectedProvider, $resolvedExpectedModel)
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

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode