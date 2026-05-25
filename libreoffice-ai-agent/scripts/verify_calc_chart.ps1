param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt,
	[string]$ChartType = "Pie",
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-vfy-calc-chart"))
}

$resolvedChartType = if ([string]::IsNullOrWhiteSpace($ChartType)) {
	"Pie"
} else {
	$ChartType.Trim()
}

$resolvedPrompt = if ([string]::IsNullOrWhiteSpace($Prompt)) {
	"Create a $resolvedChartType chart from this selection."
} else {
	$Prompt
}

$probeScriptPath = Join-Path $PSScriptRoot "verify_calc_chart.py"

$probeArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $LibreOfficeProgramPath
	UserProfileDir = $resolvedUserProfileDir
	ProbeScriptPath = $probeScriptPath
	ProbeArguments = @(
		$resolvedPrompt,
		$resolvedChartType
	)
	SidecarPythonPath = $PythonPath
	SkipBuild = $SkipBuild
	ResetUserProfileDir = -not $UserProfileDir
	StartSidecar = $true
}

$probeExitCode = Invoke-LoaiaVerificationProbe @probeArguments
exit $probeExitCode