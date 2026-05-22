param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Provider = "openai-compatible",
	[string]$Model = "local-default",
	[string]$Prompt = "Please summarize this selection.",
	[string]$InitialSelection = "hello world",
	[string]$ExpectedAnswer = "Sidecar scaffold is running. Planner and provider execution are not implemented yet.",
	[string]$ExpectedApiKeyStatus = "not required",
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$requestedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-sidebar-persistence"))
}

$resolvedUserProfileDir = if ($UserProfileDir) {
	$requestedUserProfileDir
} else {
	$profileParentDir = Split-Path -Parent $requestedUserProfileDir
	$profileLeafName = Split-Path -Leaf $requestedUserProfileDir
	[System.IO.Path]::GetFullPath((Join-Path $profileParentDir (
		"{0}-run-{1}" -f $profileLeafName, [guid]::NewGuid().ToString("N")
	)))
}

$userInstallationUrl = Convert-ToFileUrl -Path $resolvedUserProfileDir
$stateRootDir = Join-Path $resolvedUserProfileDir "loaia-extension-state"
$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_persistence.py"

if (-not $UserProfileDir) {
	Remove-LoaiaGeneratedRunProfiles -BaseProfileDir $requestedUserProfileDir -ExcludePath $resolvedUserProfileDir
	if (Test-Path -LiteralPath $resolvedUserProfileDir) {
		Remove-LoaiaProfileDir -Path $resolvedUserProfileDir -UserInstallationUrl $userInstallationUrl
	}
}

$baseProbeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	SidecarPythonPath = $PythonPath
	ResetUserProfileDir = $false
	StartSidecar = $true
}

$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
$saveExitCode = 1
$restoreExitCode = 1

try {
	$env:LOAIA_EXTENSION_STATE_ROOT = $stateRootDir

	$saveArguments = @(
		"save",
		$Provider,
		$Model,
		$Prompt,
		$ExpectedAnswer,
		$ExpectedApiKeyStatus,
		$InitialSelection
	)
	$saveProbeArguments = $baseProbeArguments.Clone()
	$saveProbeArguments.ProbeArguments = $saveArguments
	if ($SkipBuild) {
		$saveProbeArguments.SkipBuild = $true
	}

	$saveExitCode = Invoke-LoaiaVerificationProbe @saveProbeArguments
	if ($saveExitCode -ne 0) {
		exit $saveExitCode
	}

	$restoreArguments = @(
		"restore",
		$Provider,
		$Model,
		$Prompt,
		$ExpectedAnswer,
		$ExpectedApiKeyStatus
	)
	$restoreProbeArguments = $baseProbeArguments.Clone()
	$restoreProbeArguments.ProbeArguments = $restoreArguments
	$restoreProbeArguments.SkipBuild = $true

	$restoreExitCode = Invoke-LoaiaVerificationProbe @restoreProbeArguments
	if ($restoreExitCode -ne 0) {
		exit $restoreExitCode
	}
} finally {
	if ($null -ne $previousStateRoot) {
		$env:LOAIA_EXTENSION_STATE_ROOT = $previousStateRoot.Value
	} else {
		Remove-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
	}

	if (-not $UserProfileDir -and $saveExitCode -eq 0 -and $restoreExitCode -eq 0 -and (Test-Path -LiteralPath $resolvedUserProfileDir)) {
		Remove-LoaiaProfileDir -Path $resolvedUserProfileDir -UserInstallationUrl $userInstallationUrl
	}
}

exit $restoreExitCode