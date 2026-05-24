param(
	[string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
	[string]$LibreOfficeProgramPath,
	[string]$Provider,
	[string]$Model,
	[string]$PythonPath,
	[switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env_common.ps1")

function Invoke-SmokeScript {
	param(
		[string]$Scenario,
		[scriptblock]$Invocation,
		[string]$StateRootDir,
		[switch]$UseStateIsolation
	)

	$previousStateRoot = Get-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
	try {
		if ($UseStateIsolation) {
			if (Test-Path -LiteralPath $StateRootDir) {
				Remove-Item -LiteralPath $StateRootDir -Recurse -Force -ErrorAction Stop
			}
			New-Item -ItemType Directory -Path $StateRootDir -Force | Out-Null
			$env:LOAIA_EXTENSION_STATE_ROOT = $StateRootDir
		}

		Write-Host "SMOKE_SCENARIO=$Scenario"
		& $Invocation
		$exitCode = $LASTEXITCODE
	} catch {
		Write-Host ("SMOKE_EXCEPTION={0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
		$exitCode = 1
	} finally {
		if ($null -ne $previousStateRoot) {
			$env:LOAIA_EXTENSION_STATE_ROOT = $previousStateRoot.Value
		} else {
			Remove-Item -Path Env:LOAIA_EXTENSION_STATE_ROOT -ErrorAction SilentlyContinue
		}
	}

	Write-Host ("SMOKE_SCENARIO_RESULT={0}:{1}" -f $Scenario, $(if ($exitCode -eq 0) { "PASS" } else { "FAIL" }))
	return $exitCode
}

$projectRootPath = [System.IO.Path]::GetFullPath($ProjectRoot)
Import-LoaiaDotEnv -ProjectRoot $projectRootPath -PreserveExisting

$resolvedProvider = if ($Provider) {
	$Provider
} elseif ($env:LOAIA_DEFAULT_PROVIDER) {
	$env:LOAIA_DEFAULT_PROVIDER
} else {
	""
}

$resolvedModel = if ($Model) {
	$Model
} elseif ($env:LOAIA_DEFAULT_MODEL) {
	$env:LOAIA_DEFAULT_MODEL
} else {
	""
}

if ([string]::IsNullOrWhiteSpace($resolvedProvider) -or [string]::IsNullOrWhiteSpace($resolvedModel)) {
	throw "Release smoke requires a real provider-backed -Provider and -Model, or LOAIA_DEFAULT_PROVIDER and LOAIA_DEFAULT_MODEL in the environment."
}

if ($resolvedProvider -eq "openai-compatible") {
	throw "Release smoke requires a real provider-backed configuration; openai-compatible is scaffold-only."
}

$stateRootBaseDir = Join-Path $projectRootPath "build\release-smoke-state"
New-Item -ItemType Directory -Path $stateRootBaseDir -Force | Out-Null

$results = New-Object System.Collections.Generic.List[object]
$shouldSkipBuild = [bool]$SkipBuild

$directAnswerArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Answer this question about the selected text without rewriting it: what does it ask the reader to do?"
	InitialSelection = "Please send the latest budget numbers by tomorrow morning."
	Provider = $resolvedProvider
	Model = $resolvedModel
	ExpectNonScaffoldAnswer = $true
}
if ($LibreOfficeProgramPath) {
	$directAnswerArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$directAnswerArgumentMap.PythonPath = $PythonPath
}
if ($shouldSkipBuild) {
	$directAnswerArgumentMap.SkipBuild = $true
}

$directAnswerExitCode = Invoke-SmokeScript `
	-Scenario "install-direct-answer" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_sidebar_direct_answer.ps1") @directAnswerArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "install-direct-answer") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Install"; ExitCode = $directAnswerExitCode; CoveredBy = "verify_sidebar_direct_answer.ps1" }) | Out-Null
$results.Add([pscustomobject]@{ Scenario = "Direct answer"; ExitCode = $directAnswerExitCode; CoveredBy = "verify_sidebar_direct_answer.ps1" }) | Out-Null
$shouldSkipBuild = $true

$safeFormattingArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Make this bold."
	InitialSelection = "hello world"
	ExpectedToolId = "Writer.ToggleBold"
	Provider = $resolvedProvider
	Model = $resolvedModel
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$safeFormattingArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$safeFormattingArgumentMap.PythonPath = $PythonPath
}

$safeFormattingExitCode = Invoke-SmokeScript `
	-Scenario "safe-formatting" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_safe_formatting.ps1") @safeFormattingArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "safe-formatting") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Safe formatting"; ExitCode = $safeFormattingExitCode; CoveredBy = "verify_safe_formatting.ps1" }) | Out-Null

$calcSafeFormattingArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Make this bold."
	InitialValue = "12345"
	ExpectedToolId = "Calc.ToggleBold"
	Provider = $resolvedProvider
	Model = $resolvedModel
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$calcSafeFormattingArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$calcSafeFormattingArgumentMap.PythonPath = $PythonPath
}

$calcSafeFormattingExitCode = Invoke-SmokeScript `
	-Scenario "calc-safe-formatting" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_calc_safe_formatting.ps1") @calcSafeFormattingArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "calc-safe-formatting") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Calc safe formatting"; ExitCode = $calcSafeFormattingExitCode; CoveredBy = "verify_calc_safe_formatting.ps1" }) | Out-Null

$calcFormulaArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Insert a SUM formula for cells A1 through A10."
	InitialValue = "100"
	Provider = $resolvedProvider
	Model = $resolvedModel
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$calcFormulaArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$calcFormulaArgumentMap.PythonPath = $PythonPath
}

$calcFormulaExitCode = Invoke-SmokeScript `
	-Scenario "calc-formula" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_calc_formula.ps1") @calcFormulaArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "calc-formula") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Calc formula"; ExitCode = $calcFormulaExitCode; CoveredBy = "verify_calc_formula.ps1" }) | Out-Null

$calcChartArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Create a Pie chart from this selection."
	ChartType = "Pie"
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$calcChartArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$calcChartArgumentMap.PythonPath = $PythonPath
}

$calcChartExitCode = Invoke-SmokeScript `
	-Scenario "calc-chart" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_calc_chart.ps1") @calcChartArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "calc-chart") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Calc chart"; ExitCode = $calcChartExitCode; CoveredBy = "verify_calc_chart.ps1" }) | Out-Null

$drawSafeFormattingArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Make this bold."
	InitialText = "Hello Draw"
	ExpectedToolId = "Draw.ToggleBold"
	Provider = $resolvedProvider
	Model = $resolvedModel
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$drawSafeFormattingArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$drawSafeFormattingArgumentMap.PythonPath = $PythonPath
}

$drawSafeFormattingExitCode = Invoke-SmokeScript `
	-Scenario "draw-safe-formatting" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_draw_safe_formatting.ps1") @drawSafeFormattingArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "draw-safe-formatting") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Draw safe formatting"; ExitCode = $drawSafeFormattingExitCode; CoveredBy = "verify_draw_safe_formatting.ps1" }) | Out-Null

$mathDirectAnswerArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Explain what this formula represents."
	InitialFormula = "a^2 + b^2 = c^2"
	Provider = $resolvedProvider
	Model = $resolvedModel
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$mathDirectAnswerArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$mathDirectAnswerArgumentMap.PythonPath = $PythonPath
}

$mathDirectAnswerExitCode = Invoke-SmokeScript `
	-Scenario "math-direct-answer" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_math_direct_answer.ps1") @mathDirectAnswerArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "math-direct-answer") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Math direct answer"; ExitCode = $mathDirectAnswerExitCode; CoveredBy = "verify_math_direct_answer.ps1" }) | Out-Null

$previewArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Rewrite this selection into a more formal sentence."
	InitialSelection = "hey team, can you send the budget numbers by tomorrow morning? thanks!"
	Provider = $resolvedProvider
	Model = $resolvedModel
	ExpectChangedText = $true
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$previewArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$previewArgumentMap.PythonPath = $PythonPath
}

$previewExitCode = Invoke-SmokeScript `
	-Scenario "preview-and-apply" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_protocol_actions.ps1") @previewArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "preview-and-apply") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Preview and apply"; ExitCode = $previewExitCode; CoveredBy = "verify_protocol_actions.ps1" }) | Out-Null

$providerFailureArgumentMap = @{
	ProjectRoot = $projectRootPath
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$providerFailureArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$providerFailureArgumentMap.PythonPath = $PythonPath
}

$providerFailureExitCode = Invoke-SmokeScript `
	-Scenario "provider-failure" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_sidebar_provider_failure.ps1") @providerFailureArgumentMap
	}
$results.Add([pscustomobject]@{ Scenario = "Provider failure"; ExitCode = $providerFailureExitCode; CoveredBy = "verify_sidebar_provider_failure.ps1" }) | Out-Null

$sidecarFailureArgumentMap = @{
	ProjectRoot = $projectRootPath
	Prompt = "Please summarize this selection."
	InitialText = "hello world"
	Scenario = "transport-error"
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$sidecarFailureArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}

$sidecarFailureExitCode = Invoke-SmokeScript `
	-Scenario "sidecar-failure" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_sidebar_invalid_selection.ps1") @sidecarFailureArgumentMap
	} `
	-StateRootDir (Join-Path $stateRootBaseDir "sidecar-failure") `
	-UseStateIsolation
$results.Add([pscustomobject]@{ Scenario = "Sidecar failure"; ExitCode = $sidecarFailureExitCode; CoveredBy = "verify_sidebar_invalid_selection.ps1" }) | Out-Null

$persistenceArgumentMap = @{
	ProjectRoot = $projectRootPath
	Provider = $resolvedProvider
	Model = $resolvedModel
	Prompt = "What single word does this text begin with?"
	InitialSelection = "hello world"
	ExpectedAnswer = "*"
	ExpectedApiKeyStatus = "configured"
	SkipBuild = $true
}
if ($LibreOfficeProgramPath) {
	$persistenceArgumentMap.LibreOfficeProgramPath = $LibreOfficeProgramPath
}
if ($PythonPath) {
	$persistenceArgumentMap.PythonPath = $PythonPath
}

$persistenceExitCode = Invoke-SmokeScript `
	-Scenario "restart-persistence" `
	-Invocation {
		& (Join-Path $PSScriptRoot "verify_sidebar_persistence.ps1") @persistenceArgumentMap
	}
$results.Add([pscustomobject]@{ Scenario = "Restart persistence"; ExitCode = $persistenceExitCode; CoveredBy = "verify_sidebar_persistence.ps1" }) | Out-Null

$failedResults = @($results | Where-Object { $_.ExitCode -ne 0 })

Write-Host "SMOKE_SUMMARY_BEGIN"
foreach ($result in $results) {
	$status = if ($result.ExitCode -eq 0) { "PASS" } else { "FAIL" }
	Write-Host ("SMOKE_SUMMARY={0}:{1}:{2}" -f $result.Scenario, $status, $result.CoveredBy)
}
Write-Host "SMOKE_SUMMARY_END"

if ($failedResults.Count -gt 0) {
	exit 1
}

exit 0