param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$PackagePath,
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-LibreOfficeProgramPath {
	param([string]$RequestedPath)

	$candidates = @(
		$RequestedPath,
		$env:LIBREOFFICE_PROGRAM_PATH,
		"C:\Program Files\LibreOffice\program",
		"C:\Program Files (x86)\LibreOffice\program"
	) | Where-Object { $_ }

	foreach ($candidate in $candidates) {
		if (Test-Path -LiteralPath $candidate) {
			return [System.IO.Path]::GetFullPath($candidate)
		}
	}

	throw "LibreOffice program directory not found. Pass -LibreOfficeProgramPath or set LIBREOFFICE_PROGRAM_PATH."
}

function Resolve-UnopkgPath {
	param([string]$ProgramPath)

	$candidates = @(
		(Join-Path $ProgramPath "unopkg.com"),
		(Join-Path $ProgramPath "unopkg.exe")
	)

	foreach ($candidate in $candidates) {
		if (Test-Path -LiteralPath $candidate) {
			return $candidate
		}
	}

	throw "unopkg executable not found under $ProgramPath"
}

function Convert-ToFileUrl {
	param([string]$Path)

	return ([System.Uri]([System.IO.Path]::GetFullPath($Path))).AbsoluteUri
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile"))
}

if (-not $SkipBuild -or -not $PackagePath) {
	$PackagePath = & (Join-Path $PSScriptRoot "build_oxt.ps1") -ProjectRoot $projectRootPath
}

if (-not $PackagePath) {
	throw "Package path could not be determined."
}

$resolvedPackagePath = [System.IO.Path]::GetFullPath($PackagePath)
if (-not (Test-Path -LiteralPath $resolvedPackagePath)) {
	throw "OXT package not found: $resolvedPackagePath"
}

$programPath = Resolve-LibreOfficeProgramPath -RequestedPath $LibreOfficeProgramPath
$unopkgPath = Resolve-UnopkgPath -ProgramPath $programPath

New-Item -ItemType Directory -Path $resolvedUserProfileDir -Force | Out-Null
$userInstallationUrl = Convert-ToFileUrl -Path $resolvedUserProfileDir

& $unopkgPath "-env:UserInstallation=$userInstallationUrl" add -f $resolvedPackagePath

Write-Output $resolvedPackagePath
