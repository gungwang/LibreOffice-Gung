param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialText = "hello world",
	[ValidateSet("invalid-selection", "unsupported-document", "transport-error")]
	[string]$Scenario = "invalid-selection",
	[string]$PipeAddress,
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$defaultProfileDir = if ($Scenario -eq "unsupported-document") {
	"build\lo-vfy-unsup"
	} elseif ($Scenario -eq "transport-error") {
	"build\lo-vfy-trerr"
} else {
	"build\lo-vfy-invsel"
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
	SidecarPythonPath = $PythonPath
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
	StartSidecar = ($Scenario -eq "transport-error")
}

$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
$resolvedStateRootDir = if ($null -ne $previousStateRoot -and $previousStateRoot.Value) {
	[System.IO.Path]::GetFullPath($previousStateRoot.Value)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $resolvedUserProfileDir "loaia-extension-state"))
}

try {
	$env:LOAIA_EXTENSION_STATE_ROOT = $resolvedStateRootDir
	$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
} finally {
	if ($null -ne $previousStateRoot) {
		$env:LOAIA_EXTENSION_STATE_ROOT = $previousStateRoot.Value
	} else {
		Remove-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
	}
}

exit $probeExitCode