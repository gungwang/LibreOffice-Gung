param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialSelection = "hello world",
	[string]$ExpectedText = "HELLO WORLD",
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
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-protocol"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_protocol_actions.py"
$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = @($Prompt, $InitialSelection, $ExpectedText)
	SidecarPythonPath = $PythonPath
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
	StartSidecar = $true
}

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode