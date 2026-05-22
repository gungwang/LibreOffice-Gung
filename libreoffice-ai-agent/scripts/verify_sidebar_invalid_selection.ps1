param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialText = "hello world",
	[ValidateSet("invalid-selection", "unsupported-document", "transport-error")]
	[string]$Scenario = "invalid-selection",
	[string]$PipeAddress,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$defaultProfileDir = if ($Scenario -eq "unsupported-document") {
	"build\lo-profile-verify-unsupported-document"
	} elseif ($Scenario -eq "transport-error") {
	"build\lo-profile-verify-transport-error"
} else {
	"build\lo-profile-verify-invalid-selection"
}

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath $defaultProfileDir))
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_invalid_selection.py"
$resolvedPipeAddress = if ($Scenario -eq "transport-error") {
	if ($PipeAddress) {
		$PipeAddress
	} else {
		"\\.\pipe\loaia-sidecar-missing-" + [guid]::NewGuid().ToString("N")
	}
} else {
	$null
}

$resolvedProbeArguments = if ($Scenario -eq "transport-error") {
	@($Prompt, $InitialText, $Scenario, $resolvedPipeAddress)
} else {
	@($Prompt, $InitialText, $Scenario)
}

$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = $resolvedProbeArguments
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
}

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode