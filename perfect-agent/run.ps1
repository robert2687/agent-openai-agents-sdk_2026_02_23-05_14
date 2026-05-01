# run.ps1 - Launch PERFECT-AGENT
#
# Usage (from the perfect-agent directory):
#   .\run.ps1                    # interactive REPL
#   .\run.ps1 -m "question"      # single message
#   .\run.ps1 -v -m "question"   # verbose

param(
    [Alias("m")][string]$Message,
    [Alias("v")][switch]$Verbose
)

$ErrorActionPreference = "Stop"

# ---- Find Python ----
$venvPy = Join-Path $PSScriptRoot "..\agent-openai-agents-sdk_2026_02_23-05_14\agent-openai-agents-sdk\.venv\Scripts\python.exe"
$venvPy = [System.IO.Path]::GetFullPath($venvPy)

$py = $null
foreach ($candidate in @($venvPy, "python3.exe", "python.exe")) {
    try {
        $v = & $candidate --version 2>&1
        if ($v -match "Python 3") { $py = $candidate; break }
    } catch {}
}

if (-not $py) {
    Write-Host "ERROR: Python 3 not found." -ForegroundColor Red
    Write-Host "Venv checked: $venvPy" -ForegroundColor Yellow
    exit 1
}

Write-Host "Python: $py" -ForegroundColor DarkGray

# ---- Check / create .env ----
$envFile = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"

if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host ".env created from .env.example" -ForegroundColor Yellow
}

# Read current key values
$envContent = Get-Content $envFile -Raw
$orKey = ""
$oaKey = ""
if ($envContent -match '(?m)^OPENROUTER_API_KEY=(.+)') { $orKey = $Matches[1].Trim() }
if ($envContent -match '(?m)^OPENAI_API_KEY=(.+)')     { $oaKey = $Matches[1].Trim() }

if ((-not $orKey) -and (-not $oaKey)) {
    Write-Host ""
    Write-Host "No API key found in .env!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option A (free) - OpenRouter: https://openrouter.ai/keys" -ForegroundColor Cyan
    Write-Host "Option B        - OpenAI:     https://platform.openai.com/api-keys" -ForegroundColor Cyan
    Write-Host ""
    $choice = Read-Host "[O]penRouter / [A]I / [S]kip"

    if ($choice -match "^[Oo]") {
        $key = Read-Host "Paste OpenRouter key (sk-or-...)"
        if ($key) {
            $envContent = $envContent -replace '(?m)^OPENROUTER_API_KEY=.*', "OPENROUTER_API_KEY=$key"
            [System.IO.File]::WriteAllText($envFile, $envContent)
            Write-Host "Saved." -ForegroundColor Green
        }
    } elseif ($choice -match "^[Aa]") {
        $key = Read-Host "Paste OpenAI key (sk-...)"
        if ($key) {
            $envContent = $envContent -replace '(?m)^OPENAI_API_KEY=.*', "OPENAI_API_KEY=$key"
            [System.IO.File]::WriteAllText($envFile, $envContent)
            Write-Host "Saved." -ForegroundColor Green
        }
    } else {
        Write-Host "Edit '$envFile' then re-run .\run.ps1" -ForegroundColor Cyan
        exit 0
    }
}

# ---- Build argument list ----
$script = Join-Path $PSScriptRoot "agent\runner.py"
$runArgs = [System.Collections.Generic.List[string]]::new()
$runArgs.Add($script)
if ($Verbose) { $runArgs.Add("--verbose") }
if ($Message) { $runArgs.Add("--message"); $runArgs.Add($Message) }

Write-Host ""
& $py @runArgs

