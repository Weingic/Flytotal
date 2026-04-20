# git_integration_sync.ps1 — Win 端一键同步脚本
#
# 功能：
#   1. 检查工作区是否干净（有未提交内容则退出）
#   2. 双次 fetch + 切到 integration，确保本地与远端对齐
#   3. 合并 origin/feat/mac-claude（Mac 侧文件冲突自动保留 Mac 版）
#   4. 合并 origin/feat/win-codex（Win 侧文件冲突自动保留 Win 版）
#   5. push integration 到远端
#   6. 切回 feat/win-codex 并 pull，保持本地 Win 分支与远端同步
#
# 使用时机：
#   Win 端本地提交完成后执行，Mac 端已提前 push 到 origin/feat/mac-claude。
#   执行完毕后通知 Mac 端运行 git_integration_pull_after_win.sh 收尾。
#
# 用法：
#   .\tools\git_integration_sync.ps1
#   .\tools\git_integration_sync.ps1 -RepoPath "D:\Projects\Flytotal"

param(
    [string]$RepoPath = "C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal",
    [string]$IntegrationBranch = "integration/multimodal-v1.2",
    [string]$WinBranch = "feat/win-codex",
    [string]$MacBranch = "feat/mac-claude"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Mac 侧文件：冲突时保留 integration（Mac 版），不动内容
$MacOwnedFiles = @(
    "tools/evidence_hash_证据链哈希.py",
    "tools/vision_bridge_视觉桥接.py",
    "tools/vision_dashboard.html",
    "tools/vision_web_server_视觉网页服务.py"
)

function Run-Git {
    param([Parameter(Mandatory)][string[]]$GitArgs)
    Write-Host ">> git $($GitArgs -join ' ')" -ForegroundColor Cyan
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed" }
}

function Run-GitWithRetry {
    param(
        [Parameter(Mandatory)][string[]]$GitArgs,
        [int]$MaxAttempts = 3,
        [int]$DelaySeconds = 3
    )
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try { Run-Git -GitArgs $GitArgs; return }
        catch {
            if ($i -ge $MaxAttempts) { throw }
            Write-Host "Retrying in ${DelaySeconds}s ($i/$MaxAttempts)..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Resolve-MacFiles {
    Write-Host ">> 自动保留 Mac 侧文件版本（--ours）" -ForegroundColor Yellow
    foreach ($file in $MacOwnedFiles) {
        $exists = & git ls-files --unmerged -- $file
        if ($exists) {
            Write-Host "   ours: $file" -ForegroundColor Yellow
            & git checkout --ours -- $file
            & git add -- $file
        }
    }
}

# ── 检查仓库路径 ──────────────────────────────────────────
if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "Repo path does not exist: $RepoPath"
}
Set-Location -LiteralPath $RepoPath
Write-Host "Repository: $RepoPath" -ForegroundColor Yellow

# ── [1/6] 检查工作区 ─────────────────────────────────────
Write-Host "`n=== [1/6] 检查工作区 ===" -ForegroundColor Green
$dirty = & git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "git status failed" }
if ($dirty) {
    Write-Host "Working tree is not clean. Please commit/stash first." -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}
Write-Host "工作区干净，继续。"

# ── [2/6] 同步远端 integration ───────────────────────────
Write-Host "`n=== [2/6] 同步远端 integration ===" -ForegroundColor Green
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-Git -GitArgs @("checkout", $IntegrationBranch)
Run-Git -GitArgs @("pull", "origin", $IntegrationBranch)
# 二次 fetch+pull，防止两次操作之间远端有新提交
Run-GitWithRetry -GitArgs @("fetch", "origin", "--prune")
Run-Git -GitArgs @("pull", "origin", $IntegrationBranch)

# ── [3/6] 合并 Mac 分支（Mac 侧文件冲突保留 Mac 版）───────
Write-Host "`n=== [3/6] 合并 origin/$MacBranch ===" -ForegroundColor Green
& git merge --no-ff "origin/$MacBranch" --no-edit
if ($LASTEXITCODE -ne 0) {
    Resolve-MacFiles
    $remaining = & git ls-files --unmerged
    if ($remaining) {
        Write-Host "仍有非 Mac 文件冲突，请手动解决后运行：git merge --continue" -ForegroundColor Red
        Run-Git -GitArgs @("status")
        exit 1
    }
    & git merge --continue --no-edit
    if ($LASTEXITCODE -ne 0) { throw "git merge --continue failed" }
}

# ── [4/6] 合并 Win 分支 ──────────────────────────────────
Write-Host "`n=== [4/6] 合并 origin/$WinBranch ===" -ForegroundColor Green
& git merge --no-ff "origin/$WinBranch" --no-edit
if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge conflict (win). Resolve manually then run: git merge --continue" -ForegroundColor Red
    Run-Git -GitArgs @("status")
    exit 1
}

# ── [5/6] Push integration ───────────────────────────────
Write-Host "`n=== [5/6] Push integration ===" -ForegroundColor Green
Run-GitWithRetry -GitArgs @("push", "origin", $IntegrationBranch)

# ── [6/6] 切回 Win 分支并同步 ────────────────────────────
Write-Host "`n=== [6/6] 切回 $WinBranch 并同步 ===" -ForegroundColor Green
Run-Git -GitArgs @("checkout", $WinBranch)
Run-Git -GitArgs @("pull", "origin", $WinBranch)

& git status
Write-Host "`nDone: Win 已推送到 integration，已切回 $WinBranch。" -ForegroundColor Green
Write-Host "通知 Mac 端运行：./tools/git_integration_pull_after_win.sh" -ForegroundColor Green
