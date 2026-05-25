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
		"C:\Program Files\LibreOffice\26\program",
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

function Get-LoaiaProfileProcesses {
	param([string]$UserInstallationUrl)

	$processes = Get-CimInstance Win32_Process -Filter (
		"Name = 'soffice.exe' OR Name = 'soffice.bin' OR Name = 'unopkg.com' OR Name = 'unopkg.exe'"
	) -ErrorAction SilentlyContinue

	return @($processes | Where-Object {
		$_.CommandLine -and
		$_.CommandLine.IndexOf($UserInstallationUrl, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
	})
}

function Stop-LoaiaProfileProcesses {
	param(
		[string]$UserInstallationUrl,
		[int]$MaxAttempts = 10,
		[int]$DelayMilliseconds = 500
	)

	for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
		$processes = @(Get-LoaiaProfileProcesses -UserInstallationUrl $UserInstallationUrl)
		if ($processes.Count -eq 0) {
			return
		}

		foreach ($processInfo in $processes) {
			Stop-Process -Id $processInfo.ProcessId -Force -ErrorAction SilentlyContinue
		}

		[System.Threading.Thread]::Sleep($DelayMilliseconds)
	}

	$remainingProcesses = @(Get-LoaiaProfileProcesses -UserInstallationUrl $UserInstallationUrl)
	if ($remainingProcesses.Count -gt 0) {
		$processSummary = ($remainingProcesses | ForEach-Object {
			"{0}({1})" -f $_.Name, $_.ProcessId
		}) -join ", "
		throw (
			"Could not stop LibreOffice profile processes for {0}: {1}" -f
			$UserInstallationUrl,
			$processSummary
		)
	}
}

function Remove-LoaiaProfileDir {
	param(
		[string]$Path,
		[string]$UserInstallationUrl,
		[int]$MaxAttempts = 5,
		[int]$DelayMilliseconds = 500
	)

	if (-not (Test-Path -LiteralPath $Path)) {
		return
	}

	$lastError = $null
	for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
		Stop-LoaiaProfileProcesses -UserInstallationUrl $UserInstallationUrl

		try {
			Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
			return
		} catch {
			$lastError = $_
			if ($attempt -lt $MaxAttempts) {
				[System.Threading.Thread]::Sleep($DelayMilliseconds)
			}
		}
	}

	throw (
		"Could not remove install profile at {0}: {1}" -f
		$Path,
		$lastError.Exception.Message
	)
}

function Remove-LoaiaGeneratedInstallProfiles {
	param(
		[string]$BuildDir,
		[string]$ExcludePath,
		[int]$KeepNewest = 3
	)

	if (-not (Test-Path -LiteralPath $BuildDir)) {
		return
	}

	$excludeResolvedPath = if ($ExcludePath) {
		[System.IO.Path]::GetFullPath($ExcludePath)
	} else {
		$null
	}

	$installProfileDirs = @(
		Get-ChildItem -LiteralPath $BuildDir -Directory -ErrorAction SilentlyContinue |
			Where-Object {
				$_.Name -like "lo-profile-install-*" -and
				($null -eq $excludeResolvedPath -or $_.FullName -ne $excludeResolvedPath)
			} |
			Sort-Object LastWriteTimeUtc -Descending
	)

	$installProfileDirsToRemove = @($installProfileDirs | Select-Object -Skip $KeepNewest)
	foreach ($installProfileDir in $installProfileDirsToRemove) {
		$installProfileUrl = Convert-ToFileUrl -Path $installProfileDir.FullName
		if (@(Get-LoaiaProfileProcesses -UserInstallationUrl $installProfileUrl).Count -gt 0) {
			continue
		}

		Remove-LoaiaProfileDir -Path $installProfileDir.FullName -UserInstallationUrl $installProfileUrl
	}
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile"))
}
$buildDir = [System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build"))

Remove-LoaiaGeneratedInstallProfiles -BuildDir $buildDir -ExcludePath $resolvedUserProfileDir

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

$unopkgOutput = & $unopkgPath "-env:UserInstallation=$userInstallationUrl" add -f $resolvedPackagePath 2>&1
$unopkgExitCode = $LASTEXITCODE
if ($unopkgExitCode -ne 0) {
	foreach ($unopkgOutputLine in @($unopkgOutput)) {
		Write-Host $unopkgOutputLine
	}

	throw "unopkg add failed with exit code $unopkgExitCode"
}

Write-Output $resolvedPackagePath
