function Get-LoaiaDotEnvPaths {
	param([string]$ProjectRoot)

	$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
	$workspaceRootPath = Split-Path -Parent $projectRootPath
	$candidates = @(
		(Join-Path $workspaceRootPath ".env"),
		(Join-Path $projectRootPath ".env")
	)

	$paths = New-Object System.Collections.Generic.List[string]
	foreach ($candidate in $candidates) {
		if (-not (Test-Path -LiteralPath $candidate)) {
			continue
		}

		$fullPath = [System.IO.Path]::GetFullPath($candidate)
		if (-not $paths.Contains($fullPath)) {
			$paths.Add($fullPath)
		}
	}

	return $paths
}

function ConvertFrom-LoaiaDotEnvLine {
	param([string]$Line)

	$trimmed = $Line.Trim()
	if (-not $trimmed -or $trimmed.StartsWith("#")) {
		return $null
	}

	if ($trimmed -notmatch '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
		return $null
	}

	$name = $matches[1]
	$value = $matches[2].Trim()
	if ($value.Length -ge 2) {
		if (
			($value.StartsWith('"') -and $value.EndsWith('"')) -or
			($value.StartsWith("'") -and $value.EndsWith("'"))
		) {
			$value = $value.Substring(1, $value.Length - 2)
		}
	}

	return [pscustomobject]@{
		Name = $name
		Value = $value
	}
}

function Import-LoaiaDotEnv {
	param(
		[string]$ProjectRoot,
		[switch]$PreserveExisting
	)

	foreach ($dotenvPath in Get-LoaiaDotEnvPaths -ProjectRoot $ProjectRoot) {
		foreach ($line in Get-Content -LiteralPath $dotenvPath) {
			$entry = ConvertFrom-LoaiaDotEnvLine -Line $line
			if ($null -eq $entry) {
				continue
			}

			if ($PreserveExisting) {
				$existingItem = Get-Item -Path ("Env:" + $entry.Name) -ErrorAction SilentlyContinue
				if ($null -ne $existingItem) {
					continue
				}
			}

			Set-Item -Path ("Env:" + $entry.Name) -Value $entry.Value
		}
	}
}