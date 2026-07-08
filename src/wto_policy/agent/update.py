"""实时政策 updater — 拉新政策入 SQLite 缓存.

设计:
- 一次性跑: wto-update        (手动 / cron)
- 拉 3 个源: USTR / Federal Register / 商务部
- 写到 SQLite (data/cache/policies.db)
- 记录每次抓取到 crawl_log
- 失败源不阻塞其他源
- 输出: 拉了多少条 / 多少是新的 / 哪条最新
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from rich.console import Console
from rich.table import Table

from wto_policy.agent.policy_cache import (
    init_schema,
    record_crawl,
    stats,
    upsert_items,
)
from wto_policy.agent.policy_fetcher import (
    fetch_federal_register,
    fetch_mofcom_rss,
    fetch_ustr_press,
    to_dict,
)


def _fetch_one(source: str, query: str | None) -> list[dict]:
    """拉一个源, 失败返回空列表."""
    try:
        if source == "ustr":
            items = fetch_ustr_press(limit=10)
        elif source == "federal_register":
            items = fetch_federal_register(query=query or "section 301", limit=10)
        elif source == "mofcom":
            items = fetch_mofcom_rss(limit=10)
        else:
            return []
        return to_dict(items)
    except Exception:
        return []


def run_update(
    *,
    sources: list[str] | None = None,
    query: str | None = None,
    console: Console | None = None,
) -> dict:
    """跑一次完整 update. 返回统计 dict."""
    console = console or Console()
    sources = sources or ["ustr", "federal_register", "mofcom"]
    init_schema()  # 幂等, 首次自动建表

    summary = {
        "started_at": datetime.now(UTC).isoformat(),
        "sources": {},
        "total_new": 0,
        "total_fetched": 0,
    }

    console.print("[bold cyan]🔄 WTO Policy Updater[/bold cyan]")
    console.print(f"  时间: {summary['started_at']}")
    console.print(f"  源: {', '.join(sources)}")
    console.print()

    for source in sources:
        items = _fetch_one(source, query)
        new = upsert_items(items)
        summary["sources"][source] = {"fetched": len(items), "new": new}
        summary["total_new"] += new
        summary["total_fetched"] += len(items)

        status = "ok" if items is not None else "error"
        record_crawl(
            source=source, query=query,
            new_items=new, total_items=len(items),
            status=status,
        )

        icon = "✓" if items else "✗"
        color = "green" if items else "red"
        console.print(
            f"  [{color}]{icon} {source:<20}[/{color}] "
            f"fetched={len(items):>3}  new={new:>3}"
        )

    # 总览
    s = stats()
    console.print()
    console.print(
        f"  [bold]缓存总计: {s['total']} 条 "
        f"(USTR={s['per_source'].get('ustr', 0)}, "
        f"FR={s['per_source'].get('federal_register', 0)}, "
        f"MOFCOM={s['per_source'].get('mofcom', 0)})[/bold]"
    )
    console.print(f"  本次新增: {summary['total_new']} 条")
    return summary


def main() -> None:
    """CLI 入口: wto-update."""
    import argparse

    p = argparse.ArgumentParser(description="拉新政策入缓存")
    p.add_argument("--query", default="section 301", help="Federal Register 搜索词")
    p.add_argument(
        "--source", action="append",
        choices=["ustr", "federal_register", "mofcom"],
        help="只跑指定源 (可多次)",
    )
    p.add_argument("--list", action="store_true", help="只显示当前缓存统计")
    args = p.parse_args()

    if args.list:
        init_schema()
        s = stats()
        console = Console()
        table = Table(title="政策缓存统计")
        table.add_column("源", style="cyan")
        table.add_column("条数", justify="right")
        for src, cnt in s["per_source"].items():
            table.add_row(src, str(cnt))
        table.add_row("TOTAL", str(s["total"]), style="bold")
        console.print(table)
        return

    run_update(sources=args.source, query=args.query)
    sys.exit(0)


if __name__ == "__main__":
    main()
