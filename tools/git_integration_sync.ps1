# Win-side integration sync helper.
#
# Flow:
# 1. Require a clean working tree.
# 2. Fetch origin and switch to the integration branch.
# 3. Merge origin/feat/mac-claude.
# 4. Merge origin/feat/win-codex.
# 5. Push the integration branch.
# 6. Switch back to feat/win-codex and pull.

param(
    [string]$RepoPath = "C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal",
    [string]$IntegrationBranch = "integration/multimodal-v1.2",
    [string]$WinBranch = "feat/win-codex",
    [string]$MacBranch = "feat/mac-claude"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$MacOwnedFiles = @(
    "tools/evidence_hash_证据链哈希.py",
    "tools/vision_bridge_视觉桥接.py",
    "tools/vision_dashboard.html",
    "tools/vision_web_server_视觉网页服务.py"
)

function Run-Git {
    param(
        [Parameter(Mandatory)]
        [string[]]$GitArgs
    )

    Write-Host ">> git $($GitArgs -join ' ')" -ForegroundColor Cyan
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed"
    }
}

function Run-GitWithRetry {
    param(
        [Parameter(Mandatory)]
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
            Write-Host "Retrying in ${DelaySeconds}s ($attempt/$MaxAttempts)..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Resolve-MacFiles {
    Write-Host ">> Resolving Mac-owned file conflicts with --ours" -ForegroundColor Yellow
    foreach ($file in $MacOwnedFiles) {
        $unmerged = & git ls-files --unmerged -- $file
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files --unmerged failed for $file"
        }
        if ($unmerged) {
            Write-Host "   ours: $file" -ForegroundColor Yellow
            & git checkout --ours -- $file
            if ($LASTEXITCODE -ne 0) {
                throw "git checkout --ours failed for $file"
            }
            & git add -- $file
            if ($LASTEXITCODE -ne 0) {
                throw "git add failed for $file"
            }
        }
    }
}

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}

Set-Location -LiteralPath $RepoPath
Write-Host "Repository: $RepoPath" -ForegroundColor Yellow

Write-Host ""
Write-Host "=== [1/6] Check working tree ===" -ForegroundColor Green
$dirty = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "git status failed"
}
if ($dirty) {
    Write-Host "Working tree is not clean. Please commit or stash first." -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}
Write-Host "Working tree is clean." -ForegroundColor Green

Write-Host ""
Write-Host "=== [2/6] Sync remote integration ===" -ForegroundColor Green
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-Git -GitArgs @("checkout", $IntegrationBranch)
Run-Git -GitArgs @("pull", "origin", $IntegrationBranch)
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-Git -GitArgs @("pull", "origin", $IntegrationBranch)

Write-Host ""
Write-Host "=== [3/6] Merge origin/$MacBranch ===" -ForegroundColor Green
& git merge --no-ff "origin/$MacBranch" --no-edit
if ($LASTEXITCODE -ne 0) {
    Resolve-MacFiles
    $remaining = & git ls-files --unmerged
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files --unmerged failed"
    }
    if ($remaining) {
        Write-Host "Non-Mac conflicts remain. Resolve them manually, then run: git merge --continue" -ForegroundColor Red
        Run-Git -GitArgs @("status")
        exit 1
    }
    & git merge --continue --no-edit
    if ($LASTEXITCODE -ne 0) {
        throw "git merge --continue failed"
    }
}

Write-Host ""
Write-Host "=== [4/6] Merge origin/$WinBranch ===" -ForegroundColor Green
& git merge --no-ff "origin/$WinBranch" --no-edit
if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge conflict while merging $WinBranch. Resolve manually, then run: git merge --continue" -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}

Write-Host ""
Write-Host "=== [5/6] Push integration ===" -ForegroundColor Green
Run-GitWithRetry -GitArgs @("push", "origin", $IntegrationBranch)

Write-Host ""
Write-Host "=== [6/6] Switch back to $WinBranch and sync ===" -ForegroundColor Green
Run-Git -GitArgs @("checkout", $WinBranch)
Run-Git -GitArgs @("pull", "origin", $WinBranch)

& git status
if ($LASTEXITCODE -ne 0) {
    throw "git status failed at the end of the script"
}

Write-Host ""
Write-Host "Done: integration sync finished and switched back to $WinBranch." -ForegroundColor Green
Write-Host "Notify Mac to run: ./tools/git_integration_pull_after_win.sh" -ForegroundColor Green
