param(
    [string]$RepoPath = "C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal",
    [string]$IntegrationBranch = "integration/multimodal-v1.2",
    [string]$WinBranch = "feat/win-codex",
    [switch]$SkipMacPause
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Run-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$GitArgs
    )
    Write-Host ">> git $($GitArgs -join ' ')" -ForegroundColor Cyan
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: git $($GitArgs -join ' ')"
    }
}

function Run-GitWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$GitArgs,
        [int]$MaxAttempts = 3,
        [int]$DelaySeconds = 3
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            Run-Git -GitArgs $GitArgs
            return
        } catch {
            if ($attempt -ge $MaxAttempts) {
                throw
            }
            Write-Host "Git command failed, retrying in $DelaySeconds s ($attempt/$MaxAttempts)..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

Set-Location -LiteralPath $RepoPath

Write-Host "Repository: $RepoPath" -ForegroundColor Yellow

# 0) Ensure working tree is clean before integration flow.
$dirty = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Failed to run: git status --porcelain"
}
if ($dirty) {
    Write-Host "Working tree is not clean. Please commit/stash first." -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}

# 1) Sync and move to integration branch.
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-Git -GitArgs @("branch")
Run-Git -GitArgs @("checkout", $IntegrationBranch)
Run-GitWithRetry -GitArgs @("pull", "origin", $IntegrationBranch)

# 2) Pause for Mac-side merge unless explicitly skipped.
if (-not $SkipMacPause) {
    Read-Host "Complete Mac-side merge+push to origin/$IntegrationBranch, then press Enter to continue"
}

# 3) Refresh integration again to avoid stale base, then merge win branch.
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-GitWithRetry -GitArgs @("pull", "origin", $IntegrationBranch)

Write-Host ">> git merge --no-ff origin/$WinBranch" -ForegroundColor Cyan
& git merge --no-ff "origin/$WinBranch"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge conflict detected. Stopped before push. Resolve conflicts manually." -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}

# 4) Verify and push integration.
Run-Git -GitArgs @("status")
Run-GitWithRetry -GitArgs @("push", "origin", $IntegrationBranch)

# 5) Final check and switch back to win branch.
Run-Git -GitArgs @("status")
Run-Git -GitArgs @("checkout", $WinBranch)
Run-Git -GitArgs @("status")

Write-Host "Done: integration pushed and switched back to $WinBranch" -ForegroundColor Green
