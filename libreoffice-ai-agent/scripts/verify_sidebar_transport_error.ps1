param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialSelection = "hello world",
	[string]$PipeAddress,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-transport-error"))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_transport_error.py"
$resolvedPipeAddress = if ($PipeAddress) {
	$PipeAddress
} else {
	"\\.\pipe\loaia-sidecar-missing-" + [guid]::NewGuid().ToString("N")
}

$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = @($Prompt, $InitialSelection, $resolvedPipeAddress)
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
}

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode