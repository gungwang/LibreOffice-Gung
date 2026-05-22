param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialText = "hello world",
	[ValidateSet("invalid-selection", "unsupported-document")]
	[string]$Scenario = "invalid-selection",
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$defaultProfileDir = if ($Scenario -eq "unsupported-document") {
	"build\lo-profile-verify-unsupported-document"
} else {
	"build\lo-profile-verify-invalid-selection"
}

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath $defaultProfileDir))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_invalid_selection.py"

$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = @($Prompt, $InitialText, $Scenario)
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
}

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode