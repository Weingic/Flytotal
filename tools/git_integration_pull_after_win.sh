#!/usr/bin/env bash
# git_integration_pull_after_win.sh — 第二步：Win push 完成后 Mac 收尾同步
#
# 功能：
#   1. 检查工作区是否干净（有未提交内容则退出）
#   2. 拉取最新 integration（包含 Win 端刚 push 的内容）
#   3. 将更新后的 integration 合入本地 mac 分支（--no-ff）
#      → 有冲突立即停止，不 push
#   4. push mac 分支到远端，保持 origin/feat/mac-claude 与 integration 对齐
#
# 使用时机：
#   Win 端确认已将工作 push 到 integration 之后，在 Mac 端执行本脚本。
#   执行完毕后 Mac 本地 mac 分支、origin/mac 分支均包含 Win 的最新内容。
#
# 用法：
#   ./tools/git_integration_pull_after_win.sh [options]
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
    -h|--help)
      sed -n '/^# 用法/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

run_git() { echo ">> git $*"; git "$@"; }

[[ -d "${REPO_PATH}" ]] || { echo "Repo path not found: ${REPO_PATH}" >&2; exit 1; }
cd "${REPO_PATH}"

echo "=== [1/4] 检查工作区 ==="
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Please commit/stash first." >&2
  git status; exit 1
fi
echo "工作区干净，继续。"

echo "=== [2/4] 拉取最新 integration（含 Win 端内容）==="
run_git fetch origin --prune
run_git checkout "${INTEGRATION_BRANCH}"
run_git pull origin "${INTEGRATION_BRANCH}"

echo "=== [3/4] 将 integration 合入 ${MAC_BRANCH} ==="
run_git checkout "${MAC_BRANCH}"
if ! git merge --no-ff "${INTEGRATION_BRANCH}" --no-edit; then
  echo "Merge conflict detected. Resolve conflicts then run: git merge --continue" >&2
  git status; exit 1
fi

echo "=== [4/4] Push ${MAC_BRANCH} ==="
run_git push origin "${MAC_BRANCH}"

git status
echo ""
echo "Done: Mac 已同步 Win 端内容，${MAC_BRANCH} 与 integration 对齐。"
