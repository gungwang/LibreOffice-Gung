param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$UserProfileDir,
	[string]$Prompt = "Please convert this selection to uppercase.",
	[string]$InitialText = "hello world",
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
		"C:\Program Files\LibreOffice\26\program",
		"C:\Program Files (x86)\LibreOffice\program"
	) | Where-Object { $_ }

	foreach ($candidate in $candidates) {
		if (Test-Path -LiteralPath $candidate) {
			return [System.IO.Path]::GetFullPath($candidate)
		}
	}

	throw "LibreOffice program directory not found. Pass -LibreOfficeProgramPath or set LIBREOFFICE_PROGRAM_PATH."
}

function Convert-ToFileUrl {
	param([string]$Path)

	return ([System.Uri]([System.IO.Path]::GetFullPath($Path))).AbsoluteUri
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$resolvedUserProfileDir = if ($UserProfileDir) {
	[System.IO.Path]::GetFullPath($UserProfileDir)
} else {
	[System.IO.Path]::GetFullPath((Join-Path $projectRootPath "build\lo-profile-verify-invalid-selection"))
}

$programPath = Resolve-LibreOfficeProgramPath -RequestedPath $LibreOfficeProgramPath
$probeScriptPath = Join-Path $PSScriptRoot "verify_sidebar_invalid_selection.py"
$sofficePath = Join-Path $programPath "soffice.exe"
$pythonPath = Join-Path $programPath "python.exe"

foreach ($requiredPath in @($probeScriptPath, $sofficePath, $pythonPath)) {
	if (-not (Test-Path -LiteralPath $requiredPath)) {
		throw "Required path not found: $requiredPath"
	}
}

$installArguments = @{
	ProjectRoot = $projectRootPath
	LibreOfficeProgramPath = $programPath
	UserProfileDir = $resolvedUserProfileDir
}
if ($SkipBuild) {
	$installArguments.SkipBuild = $true
}

$packagePath = & (Join-Path $PSScriptRoot "dev_install_oxt.ps1") @installArguments
Write-Output "PACKAGE_PATH=$packagePath"

$pipeName = "loaia" + [guid]::NewGuid().ToString("N")
$userInstallationUrl = Convert-ToFileUrl -Path $resolvedUserProfileDir
$sofficeProcess = Start-Process -FilePath $sofficePath -ArgumentList @(
	"--accept=pipe,name=$pipeName;urp",
	"-env:UserInstallation=$userInstallationUrl",
	"--quickstart=no",
	"--norestore",
	"--nologo"
) -PassThru
Write-Output "SOFFICE_PID=$($sofficeProcess.Id)"
Write-Output "PROFILE_URL=$userInstallationUrl"
Write-Output "PIPE_NAME=$pipeName"

$probeExitCode = 0
try {
	& $pythonPath $probeScriptPath $pipeName $Prompt $InitialText
	$probeExitCode = $LASTEXITCODE
} finally {
	if ($sofficeProcess -and -not $sofficeProcess.HasExited) {
		Stop-Process -Id $sofficeProcess.Id -Force
	}
}

exit $probeExitCode