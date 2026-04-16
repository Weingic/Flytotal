param(
    [string]$RepoPath = "C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal",
    [string]$IntegrationBranch = "integration/multimodal-v1.2",
    [string]$WinBranch = "feat/win-codex",
    [switch]$SkipMacPause
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Run-Git {
    param([string[]]$Args)
    Write-Host ">> git $($Args -join ' ')" -ForegroundColor Cyan
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: git $($Args -join ' ')"
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
    Run-Git @("status")
    exit 1
}

# 1) Sync and move to integration branch.
Run-Git @("fetch", "origin", "--prune")
Run-Git @("branch")
Run-Git @("checkout", $IntegrationBranch)
Run-Git @("pull", "origin", $IntegrationBranch)

# 2) Pause for Mac-side merge unless explicitly skipped.
if (-not $SkipMacPause) {
    Read-Host "Complete Mac-side merge+push to origin/$IntegrationBranch, then press Enter to continue"
}

# 3) Refresh integration again to avoid stale base, then merge win branch.
Run-Git @("fetch", "origin", "--prune")
Run-Git @("pull", "origin", $IntegrationBranch)

Write-Host ">> git merge --no-ff origin/$WinBranch" -ForegroundColor Cyan
& git merge --no-ff "origin/$WinBranch"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge conflict detected. Stopped before push. Resolve conflicts manually." -ForegroundColor Red
    Run-Git @("status")
    exit 1
}

# 4) Verify and push integration.
Run-Git @("status")
Run-Git @("push", "origin", $IntegrationBranch)

# 5) Final check and switch back to win branch.
Run-Git @("status")
Run-Git @("checkout", $WinBranch)
Run-Git @("status")

Write-Host "Done: integration pushed and switched back to $WinBranch" -ForegroundColor Green
