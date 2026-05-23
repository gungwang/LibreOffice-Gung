param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[ValidateRange(0, 1000)]
	[int]$KeepNewest = 5,
	[switch]$IncludeInstallProfiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "verification_common.ps1")

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$buildDir = [System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build"))

if (-not (Test-Path -LiteralPath $buildDir)) {
	Write-Output "REMAINING_COUNT=0"
	exit 0
}

$namePatterns = @(
	"^lo-profile-verify-",
	"^lo-vfy-",
	"^lo-profile-invalid-selection-shape$",
	"^lo-test$"
)

if ($IncludeInstallProfiles) {
	$namePatterns += "^lo-profile-install-"
}

$matchingProfileDirs = @(
	Get-ChildItem -LiteralPath $buildDir -Directory -ErrorAction SilentlyContinue |
		Where-Object {
			$directoryName = $_.Name
			@($namePatterns | Where-Object { $directoryName -match $_ }).Count -gt 0
		} |
		Sort-Object LastWriteTimeUtc -Descending
)

$profileDirsToRemove = @($matchingProfileDirs | Select-Object -Skip $KeepNewest)
foreach ($profileDir in $profileDirsToRemove) {
	$profileUrl = Convert-ToFileUrl -Path $profileDir.FullName
	if (@(Get-LoaiaProfileProcesses -UserInstallationUrl $profileUrl).Count -gt 0) {
		Write-Output ("SKIPPED_ACTIVE={0}" -f $profileDir.Name)
		continue
	}

	Remove-LoaiaProfileDir -Path $profileDir.FullName -UserInstallationUrl $profileUrl
	Write-Output ("REMOVED={0}" -f $profileDir.Name)
}

$remainingProfileDirs = @(
	Get-ChildItem -LiteralPath $buildDir -Directory -ErrorAction SilentlyContinue |
		Where-Object {
			$directoryName = $_.Name
			@($namePatterns | Where-Object { $directoryName -match $_ }).Count -gt 0
		} |
		Sort-Object Name
)

Write-Output ("REMAINING_COUNT={0}" -f $remainingProfileDirs.Count)
if ($remainingProfileDirs.Count -gt 0) {
	Write-Output ("REMAINING={0}" -f (($remainingProfileDirs | ForEach-Object { $_.Name }) -join ","))
}