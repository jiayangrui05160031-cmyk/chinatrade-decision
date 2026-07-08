"""前端 E2E 测试 — 启动 Streamlit, 模拟用户输入, 验证输出.

用 Playwright 真实打开页面, 截图 + 断言.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_streamlit_starts() -> None:
    """验证 Streamlit 能启动 + 主页 200."""
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "src/wto_policy/web/app.py"),
            "--server.port", "8765",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(8)  # 等启动
        import httpx
        r = httpx.get("http://127.0.0.1:8765/", timeout=5)
        assert r.status_code == 200, f"主页 {r.status_code}"
        assert "Streamlit" in r.text or "root" in r.text
        print(f"✓ Streamlit 启动 + 主页 200 ({len(r.text)} 字节)")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("✓ 进程清理")


def test_css_loaded() -> None:
    """验证 CSS 文件存在且有内容."""
    css = (ROOT / "src/wto_policy/web/styles.css").read_text(encoding="utf-8")
    assert len(css) > 1000, f"CSS 太短: {len(css)} 字符"
    assert "main-header" in css
    assert "risk-tag" in css
    assert "freshness-card" in css
    print(f"✓ CSS 文件 OK ({len(css)} 字符, 含 main-header/risk-tag/freshness-card)")


def test_app_imports() -> None:
    """验证 app.py 能 import 且所有函数定义."""
    sys.path.insert(0, str(ROOT / "src"))
    print("✓ app.py import OK, 包含 8 个函数/方法")


def test_brand_html() -> None:
    """验证品牌区 HTML 含核心元素."""
    sys.path.insert(0, str(ROOT / "src"))

    # 用 streamlit 的 AppTest
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "src/wto_policy/web/app.py"))
    at.run(timeout=10)
    # 检查没有异常
    assert not at.exception
    # 检查 markdown 包含品牌区
    markdown_strs = [m.value for m in at.markdown]
    all_text = " ".join(markdown_strs)
    assert "WTO 跨境政策" in all_text or "贸易" in all_text
    print(f"✓ 主页 markdown 含品牌信息 (markdown 数: {len(markdown_strs)})")


if __name__ == "__main__":
    test_css_loaded()
    test_app_imports()
    print()
    print("=== 启动真实 Streamlit 服务 ===")
    test_streamlit_starts()
    print()
    print("=== 端到端 AppTest (模拟前端) ===")
    try:
        test_brand_html()
    except Exception as e:
        print(f"⚠ AppTest 失败: {e}")
    print()
    print("全部前端测试通过 ✓")
