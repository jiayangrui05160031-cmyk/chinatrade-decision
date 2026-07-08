#!/usr/bin/env bash
# Push to GitHub (Windows Git Bash / macOS / Linux)
# 用法: ./push_to_github.sh [repo-name]
# 默认 repo: wto-policy-support
# 需要: gh CLI 已登录 (gh auth login) 或 手动建好空 repo

set -e

REPO_NAME="${1:-wto-policy-support}"
OWNER="jiayangrui05160031-cmyk"
REPO_FULL="${OWNER}/${REPO_NAME}"

cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "=== 检查 git 状态 ==="
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: 工作区有未提交变更, 请先 commit"
    git status
    exit 1
fi

echo "=== 确认 .env 不在 git 里 ==="
if git ls-files | grep -q "^\.env$"; then
    echo "ERROR: .env 在 git 里! 立即移除"
    exit 1
fi

echo "=== 推送到 GitHub ==="
# 方式 1: gh CLI (推荐, 一键创建)
if command -v gh &> /dev/null; then
    if ! gh repo view "$REPO_FULL" &>/dev/null; then
        echo "  -> gh repo create $REPO_FULL --public --source=. --remote=origin --push"
        gh repo create "$REPO_FULL" --public --source=. --remote=origin --push
    else
        echo "  -> repo 已存在, 添加 remote 并 push"
        git remote remove origin 2>/dev/null || true
        git remote add origin "https://github.com/${REPO_FULL}.git"
        git push -u origin main
    fi
else
    # 方式 2: 纯 git, 需要手动建空 repo
    echo "  -> gh CLI 未装, 请先在 https://github.com/new 建空 repo: $REPO_FULL"
    echo "  -> 然后: git remote add origin https://github.com/${REPO_FULL}.git && git push -u origin main"
    exit 0
fi

echo ""
echo "✅ 推送完成: https://github.com/${REPO_FULL}"
