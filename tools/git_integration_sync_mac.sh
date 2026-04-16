#!/usr/bin/env bash
# git_integration_sync_mac.sh — 第一步：Mac 推送到 integration
#
# 功能：
#   1. 检查工作区是否干净（有未提交内容则退出）
#   2. 双次 fetch + pull integration，确保本地 integration 与远端完全对齐
#   3. 将 origin/feat/mac-claude 以 --no-ff 合入本地 integration
#      → 有冲突立即停止，不 push
#   4. push integration 到远端
#   5. 切回 feat/mac-claude 并 pull，保持本地 mac 分支与远端同步
#
# 使用时机：
#   Mac 端本地提交完成后，准备将工作合入 integration 时执行。
#   执行完毕后通知 Win 端可以开始 push。
#   Win push 完成后，再执行 git_integration_pull_after_win.sh 收尾。
#
# 用法：
#   ./tools/git_integration_sync_mac.sh [options]
#
# Options:
#   --repo <path>           仓库路径（默认 ~/Documents/PlatformIO/Projects/Flytotal）
#   --integration <branch>  integration 分支名（默认 integration/multimodal-v1.2）
#   --mac-branch <branch>   Mac 功能分支名（默认 feat/mac-claude）
#   -h, --help              显示帮助

set -euo pipefail

REPO_PATH="${HOME}/Documents/PlatformIO/Projects/Flytotal"
INTEGRATION_BRANCH="integration/multimodal-v1.2"
MAC_BRANCH="feat/mac-claude"

usage() {
  sed -n '/^# 用法/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ -n "${2:-}" ]] || { echo "Missing value for --repo" >&2; exit 1; }
      REPO_PATH="$2"; shift 2 ;;
    --integration)
      [[ -n "${2:-}" ]] || { echo "Missing value for --integration" >&2; exit 1; }
      INTEGRATION_BRANCH="$2"; shift 2 ;;
    --mac-branch)
      [[ -n "${2:-}" ]] || { echo "Missing value for --mac-branch" >&2; exit 1; }
      MAC_BRANCH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

run_git() { echo ">> git $*"; git "$@"; }

[[ -d "${REPO_PATH}" ]] || { echo "Repo path not found: ${REPO_PATH}" >&2; exit 1; }
cd "${REPO_PATH}"
echo "=== [1/5] 检查工作区 ==="
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Please commit/stash first." >&2
  git status; exit 1
fi
echo "工作区干净，继续。"

echo "=== [2/5] 同步远端 integration ==="
run_git fetch origin --prune
run_git checkout "${INTEGRATION_BRANCH}"
run_git pull origin "${INTEGRATION_BRANCH}"
# 二次 fetch+pull，防止两次操作之间远端有新提交
run_git fetch origin --prune
run_git pull origin "${INTEGRATION_BRANCH}"

echo "=== [3/5] 合并 origin/${MAC_BRANCH} ==="
if ! git merge --no-ff "origin/${MAC_BRANCH}" --no-edit; then
  echo "Merge conflict detected. Stopped before push." >&2
  git status; exit 1
fi

echo "=== [4/5] Push integration ==="
run_git push origin "${INTEGRATION_BRANCH}"

echo "=== [5/5] 切回 ${MAC_BRANCH} 并同步 ==="
run_git checkout "${MAC_BRANCH}"
run_git pull origin "${MAC_BRANCH}"

git status
echo ""
echo "Done: Mac 已推送到 integration，已切回 ${MAC_BRANCH}。"
echo "请通知 Win 端 push，Win 完成后运行："
echo "  ./tools/git_integration_pull_after_win.sh"
