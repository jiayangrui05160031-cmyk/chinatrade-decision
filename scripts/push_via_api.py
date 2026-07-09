"""通过 GitHub Data API 把整个本地仓库推送到 main — 绕过 github.com:443 阻塞.

策略:
- 用 git ls-tree -r HEAD 拿所有文件
- 全部上传 blob, 全做 tree
- 创建 1 个 commit (parent = remote tip)
- force update main ref

风险: 历史简化, 但能 push.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

import httpx

TOKEN = os.environ.get("GH_TOKEN")  # 必设: export GH_TOKEN=ghp_xxx
if not TOKEN:
    print("ERROR: 请先 export GH_TOKEN=ghp_xxx", file=sys.stderr)
    sys.exit(1)
REPO = "chinatrade-decision"
OWNER = "jiayangrui05160031-cmyk"
BRANCH = "main"
API = "https://api.github.com"

H = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "push-via-api",
}

# 排除规则 (不推的)
SKIP_PATHS = [
    ".env",
    "data/cloud.db",
    "data/raw/",
    "data/eval_v",
    "__pycache__",
    ".pyc",
    "node_modules",
    "*.egg-info",
]


def get_ref() -> str | None:
    r = httpx.get(
        f"{API}/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
        headers=H, timeout=15,
    )
    if r.status_code == 200:
        return r.json()["object"]["sha"]
    return None


def get_commit(sha: str) -> dict:
    r = httpx.get(
        f"{API}/repos/{OWNER}/{REPO}/git/commits/{sha}",
        headers=H, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def upload_blob(content: bytes) -> str:
    r = httpx.post(
        f"{API}/repos/{OWNER}/{REPO}/git/blobs",
        headers=H,
        json={"content": base64.b64encode(content).decode(), "encoding": "base64"},
        timeout=60,
    )
    if r.status_code >= 400:
        # 提示 422 原因
        body = r.text[:500]
        raise RuntimeError(f"blob 422 ({len(content)} bytes): {body}")
    return r.json()["sha"]


def create_tree(base_tree: str, items: list[dict]) -> str:
    r = httpx.post(
        f"{API}/repos/{OWNER}/{REPO}/git/trees",
        headers=H,
        json={"base_tree": base_tree, "tree": items},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["sha"]


def create_commit(message: str, tree: str, parents: list[str]) -> str:
    r = httpx.post(
        f"{API}/repos/{OWNER}/{REPO}/git/commits",
        headers=H,
        json={"message": message, "tree": tree, "parents": parents},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["sha"]


def update_ref(sha: str) -> bool:
    r = httpx.patch(
        f"{API}/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
        headers=H,
        json={"sha": sha, "force": True},
        timeout=15,
    )
    return r.status_code in (200, 204)


def should_skip(path: str) -> bool:
    for p in SKIP_PATHS:
        if p in path:
            return True
    return False


def main() -> int:
    repo = Path("D:/wto-policy-support")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(repo)
    ).decode().strip()
    print(f"local HEAD:  {head[:12]}")

    remote = get_ref()
    if remote:
        print(f"remote tip:  {remote[:12]}")
    else:
        print("remote: (empty)")

    # 列所有 tracked 文件
    files_raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=str(repo)
    ).decode().strip().split("\n")
    files = [
        f for f in files_raw
        if f.strip()
        and not should_skip(f)
        and not f.startswith("data/ui_")  # 截图 (.png) 太大, 不放 git
        and not f.startswith("data/v")  # 同上
    ]
    print(f"files to push: {len(files)}")

    # 上传每个
    items = []
    for f in files:
        p = repo / f
        if not p.exists() or p.is_dir():
            continue
        try:
            content = p.read_bytes()
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {f}: {e}")
            continue
        if len(content) > 5_000_000:
            # 5MB 上限, 跳过
            print(f"  ! skip (too big): {f} ({len(content)} bytes)")
            continue
        sha = upload_blob(content)
        items.append({"path": f, "mode": "100644", "type": "blob", "sha": sha})
        print(f"  + {f} ({len(content)} bytes) -> {sha[:10]}")

    if not items:
        print("Nothing to push")
        return 0

    # 拿 base tree
    if remote:
        base_tree = get_commit(remote)["tree"]["sha"]
    else:
        base_tree = None

    new_tree = create_tree(base_tree, items) if base_tree else create_tree_no_base(items)
    print(f"new tree:    {new_tree[:12]}")

    # commit (parent = remote tip 或空)
    parents = [remote] if remote else []
    new_commit = create_commit("chore: sync from local (API push)", new_tree, parents)
    print(f"new commit:  {new_commit[:12]}")

    if update_ref(new_commit):
        print(f"✓ Pushed:    {remote[:12] if remote else '(empty)'} -> {new_commit[:12]}")
        return 0
    print("✗ ref update failed")
    return 1


def create_tree_no_base(items: list[dict]) -> str:
    r = httpx.post(
        f"{API}/repos/{OWNER}/{REPO}/git/trees",
        headers=H,
        json={"tree": items},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["sha"]


if __name__ == "__main__":
    sys.exit(main())
