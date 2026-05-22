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

function Get-LoaiaProfileOfficeProcesses {
	param([string]$UserInstallationUrl)

	$officeProcessNames = @("soffice.exe", "soffice.bin")
	return @(
		Get-LoaiaProfileProcesses -UserInstallationUrl $UserInstallationUrl |
			Where-Object { $officeProcessNames -contains $_.Name.ToLowerInvariant() }
	)
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

function Stop-LoaiaProfileOfficeProcesses {
	param(
		[string]$UserInstallationUrl,
		[int]$MaxAttempts = 10,
		[int]$DelayMilliseconds = 500
	)

	for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
		$processes = @(Get-LoaiaProfileOfficeProcesses -UserInstallationUrl $UserInstallationUrl)
		if ($processes.Count -eq 0) {
			return
		}

		foreach ($processInfo in $processes) {
			Stop-Process -Id $processInfo.ProcessId -Force -ErrorAction SilentlyContinue
		}

		[System.Threading.Thread]::Sleep($DelayMilliseconds)
	}

	$remainingProcesses = @(Get-LoaiaProfileOfficeProcesses -UserInstallationUrl $UserInstallationUrl)
	if ($remainingProcesses.Count -gt 0) {
		$processSummary = ($remainingProcesses | ForEach-Object {
			"{0}({1})" -f $_.Name, $_.ProcessId
		}) -join ", "
		throw (
			"Could not stop LibreOffice office processes for {0}: {1}" -f
			$UserInstallationUrl,
			$processSummary
		)
	}
}

function Wait-LoaiaOfficeStartup {
	param(
		[string]$UserInstallationUrl,
		[int]$TimeoutSeconds = 10,
		[int]$DelayMilliseconds = 250,
		[int]$StabilizationMilliseconds = 1000
	)

	$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

	do {
		$officeProcesses = @(Get-LoaiaProfileOfficeProcesses -UserInstallationUrl $UserInstallationUrl)
		if ($officeProcesses.Count -gt 0) {
			[System.Threading.Thread]::Sleep($StabilizationMilliseconds)
			return
		}

		[System.Threading.Thread]::Sleep($DelayMilliseconds)
	} while ((Get-Date) -lt $deadline)

	throw ("LibreOffice did not finish starting for {0}." -f $UserInstallationUrl)
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
		"Could not remove verification profile at {0}: {1}" -f
		$Path,
		$lastError.Exception.Message
	)
}

function Remove-LoaiaGeneratedRunProfiles {
	param(
		[string]$BaseProfileDir,
		[string]$ExcludePath,
		[int]$KeepNewest = 3
	)

	$resolvedBaseProfileDir = [System.IO.Path]::GetFullPath($BaseProfileDir)
	$profileParentDir = Split-Path -Parent $resolvedBaseProfileDir
	$profileLeafName = Split-Path -Leaf $resolvedBaseProfileDir
	$excludeResolvedPath = if ($ExcludePath) {
		[System.IO.Path]::GetFullPath($ExcludePath)
	} else {
		$null
	}

	if (-not (Test-Path -LiteralPath $profileParentDir)) {
		return
	}

	$runProfileDirs = @(
		Get-ChildItem -LiteralPath $profileParentDir -Directory -ErrorAction SilentlyContinue |
			Where-Object {
				$_.Name -like ("{0}-run-*" -f $profileLeafName) -and
				($null -eq $excludeResolvedPath -or $_.FullName -ne $excludeResolvedPath)
			} |
			Sort-Object LastWriteTimeUtc -Descending
	)

	$runProfileDirsToRemove = @($runProfileDirs | Select-Object -Skip $KeepNewest)
	foreach ($runProfileDir in $runProfileDirsToRemove) {
		$runProfileUrl = Convert-ToFileUrl -Path $runProfileDir.FullName
		if (@(Get-LoaiaProfileProcesses -UserInstallationUrl $runProfileUrl).Count -gt 0) {
			continue
		}

		Remove-LoaiaProfileDir -Path $runProfileDir.FullName -UserInstallationUrl $runProfileUrl
	}
}

function Invoke-LoaiaVerificationProbe {
	param(
		[string]$ProjectRoot,
		[string]$LibreOfficeProgramPath,
		[string]$UserProfileDir,
		[string]$ProbeScriptPath,
		[string[]]$ProbeArguments = @(),
		[string]$SidecarPythonPath,
		[string[]]$SidecarExtraArguments = @(),
		[hashtable]$SidecarEnvironment,
		[int]$MaxProbeAttempts = 3,
		[switch]$ResetUserProfileDir,
		[switch]$SkipBuild,
		[switch]$StartSidecar
	)

	$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
	$requestedUserProfileDir = [System.IO.Path]::GetFullPath($UserProfileDir)
	$resolvedUserProfileDir = if ($ResetUserProfileDir) {
		$profileParentDir = Split-Path -Parent $requestedUserProfileDir
		$profileLeafName = Split-Path -Leaf $requestedUserProfileDir
		[System.IO.Path]::GetFullPath((Join-Path $profileParentDir (
			"{0}-run-{1}" -f $profileLeafName, [guid]::NewGuid().ToString("N")
		)))
	} else {
		$requestedUserProfileDir
	}
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
	$userInstallationUrl = Convert-ToFileUrl -Path $resolvedUserProfileDir

	if ($ResetUserProfileDir) {
		Remove-LoaiaGeneratedRunProfiles -BaseProfileDir $requestedUserProfileDir -ExcludePath $resolvedUserProfileDir
		if (Test-Path -LiteralPath $resolvedUserProfileDir) {
			Remove-LoaiaProfileDir -Path $resolvedUserProfileDir -UserInstallationUrl $userInstallationUrl
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

	$packagePath = & (Join-Path $scriptRoot "dev_install_oxt.ps1") @installArguments
	Write-Host "PACKAGE_PATH=$packagePath"

	$sidecarProcess = $null
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
			if ($SidecarExtraArguments) {
				$sidecarArguments += $SidecarExtraArguments
			}

			$sidecarProcessArguments = @{
				FilePath = $shellPath
				ArgumentList = $sidecarArguments
				PassThru = $true
			}
			if ($SidecarEnvironment -and $SidecarEnvironment.Count -gt 0) {
				$startProcessCommand = Get-Command Start-Process -ErrorAction Stop
				if ($startProcessCommand.Parameters.ContainsKey("Environment")) {
					$sidecarProcessArguments.Environment = $SidecarEnvironment
				}
				# Else: fall back to -ClearEnvVars passed via SidecarExtraArguments
			}

			$sidecarProcess = Start-Process @sidecarProcessArguments
			Write-Host "SIDECAR_PID=$($sidecarProcess.Id)"
		}

		$probeExitCode = 1
		for ($attempt = 1; $attempt -le $MaxProbeAttempts; $attempt++) {
			if ($MaxProbeAttempts -gt 1) {
				Write-Host "PROBE_ATTEMPT=$attempt"
			}

			Stop-LoaiaProfileOfficeProcesses -UserInstallationUrl $userInstallationUrl

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
			Wait-LoaiaOfficeStartup -UserInstallationUrl $userInstallationUrl

			try {
				$probeOutput = & $pythonPath -u $resolvedProbeScriptPath $pipeName @ProbeArguments 2>&1
				$probeExitCode = $LASTEXITCODE
				foreach ($probeOutputLine in @($probeOutput)) {
					Write-Host $probeOutputLine
				}
				Write-Host "PROBE_EXIT_CODE=$probeExitCode"
			} finally {
				if ($sofficeProcess -and -not $sofficeProcess.HasExited) {
					Stop-Process -Id $sofficeProcess.Id -Force -ErrorAction SilentlyContinue
				}

				Stop-LoaiaProfileOfficeProcesses -UserInstallationUrl $userInstallationUrl
			}

			if ($probeExitCode -eq 0) {
				break
			}
		}
	} finally {
		if ($sidecarProcess -and -not $sidecarProcess.HasExited) {
			Stop-Process -Id $sidecarProcess.Id -Force
		}

		if ($ResetUserProfileDir -and $probeExitCode -eq 0 -and (Test-Path -LiteralPath $resolvedUserProfileDir)) {
			Remove-LoaiaProfileDir -Path $resolvedUserProfileDir -UserInstallationUrl $userInstallationUrl
		}
	}

	return $probeExitCode
}