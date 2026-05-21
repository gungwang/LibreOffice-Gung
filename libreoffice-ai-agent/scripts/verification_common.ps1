. (Join-Path $PSScriptRoot "env_common.ps1")

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

function Resolve-ShellPath {
	$currentShellPath = (Get-Process -Id $PID).Path
	if ($currentShellPath -and (Test-Path -LiteralPath $currentShellPath)) {
		return $currentShellPath
	}

	foreach ($name in @("pwsh", "powershell")) {
		$command = Get-Command $name -ErrorAction SilentlyContinue
		if ($command -and $command.Path) {
			return $command.Path
		}
	}

	throw "Could not resolve a PowerShell executable for starting the sidecar."
}

function Invoke-LoaiaVerificationProbe {
	param(
		[string]$ProjectRoot,
		[string]$LibreOfficeProgramPath,
		[string]$UserProfileDir,
		[string]$ProbeScriptPath,
		[string[]]$ProbeArguments = @(),
		[string]$SidecarPythonPath,
		[int]$MaxProbeAttempts = 2,
		[switch]$ResetUserProfileDir,
		[switch]$SkipBuild,
		[switch]$StartSidecar
	)

	$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
	$resolvedUserProfileDir = [System.IO.Path]::GetFullPath($UserProfileDir)
	$resolvedProbeScriptPath = [System.IO.Path]::GetFullPath($ProbeScriptPath)
	$scriptRoot = Split-Path -Parent $resolvedProbeScriptPath
	$programPath = Resolve-LibreOfficeProgramPath -RequestedPath $LibreOfficeProgramPath
	$sofficePath = Join-Path $programPath "soffice.exe"
	$pythonPath = Join-Path $programPath "python.exe"
	$sidecarScriptPath = Join-Path $scriptRoot "run_sidecar.ps1"

	$requiredPaths = @($resolvedProbeScriptPath, $sofficePath, $pythonPath)
	if ($StartSidecar) {
		$requiredPaths += $sidecarScriptPath
	}

	foreach ($requiredPath in $requiredPaths) {
		if (-not (Test-Path -LiteralPath $requiredPath)) {
			throw "Required path not found: $requiredPath"
		}
	}

	Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

	if ($ResetUserProfileDir -and (Test-Path -LiteralPath $resolvedUserProfileDir)) {
		Remove-Item -LiteralPath $resolvedUserProfileDir -Recurse -Force
	}

	$installArguments = @{
		ProjectRoot = $projectRootPath
		LibreOfficeProgramPath = $programPath
		UserProfileDir = $resolvedUserProfileDir
	}
	if ($SkipBuild) {
		$installArguments.SkipBuild = $true
	}

	$packagePath = & (Join-Path $scriptRoot "dev_install_oxt.ps1") @installArguments
	Write-Host "PACKAGE_PATH=$packagePath"

	$sidecarProcess = $null
	$userInstallationUrl = Convert-ToFileUrl -Path $resolvedUserProfileDir
	try {
		if ($StartSidecar) {
			$shellPath = Resolve-ShellPath
			$sidecarArguments = @(
				"-NoProfile",
				"-File",
				$sidecarScriptPath,
				"-ProjectRoot",
				$projectRootPath
			)
			if ($SidecarPythonPath) {
				$sidecarArguments += @("-PythonPath", $SidecarPythonPath)
			}

			$sidecarProcess = Start-Process -FilePath $shellPath -ArgumentList $sidecarArguments -PassThru
			Write-Host "SIDECAR_PID=$($sidecarProcess.Id)"
		}

		$probeExitCode = 1
		for ($attempt = 1; $attempt -le $MaxProbeAttempts; $attempt++) {
			if ($MaxProbeAttempts -gt 1) {
				Write-Host "PROBE_ATTEMPT=$attempt"
			}

			$pipeName = "loaia" + [guid]::NewGuid().ToString("N")
			$sofficeProcess = Start-Process -FilePath $sofficePath -ArgumentList @(
				"--accept=pipe,name=$pipeName;urp",
				"-env:UserInstallation=$userInstallationUrl",
				"--quickstart=no",
				"--norestore",
				"--nologo"
			) -PassThru
			Write-Host "SOFFICE_PID=$($sofficeProcess.Id)"
			Write-Host "PROFILE_URL=$userInstallationUrl"
			Write-Host "PIPE_NAME=$pipeName"

			try {
				& $pythonPath $resolvedProbeScriptPath $pipeName @ProbeArguments
				$probeExitCode = $LASTEXITCODE
			} finally {
				if ($sofficeProcess -and -not $sofficeProcess.HasExited) {
					Stop-Process -Id $sofficeProcess.Id -Force
				}
			}

			if ($probeExitCode -eq 0) {
				break
			}
		}
	} finally {
		if ($sidecarProcess -and -not $sidecarProcess.HasExited) {
			Stop-Process -Id $sidecarProcess.Id -Force
		}
	}

	return $probeExitCode
}