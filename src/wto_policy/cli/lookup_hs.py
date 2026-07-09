"""CLI: HS 编码速查.

Examples:
    wto-lookup-hs 9405408000
    wto-lookup-hs "led lamp" --lang en
    wto-lookup-hs 9405 --children
    wto-lookup-hs 9405408000 --json
"""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from wto_policy.core.hs_resolver import HsResolver, default_resolver
from wto_policy.data.seed import load_sample


def _resolver_with_sample() -> HsResolver:
    """MVP 阶段, CLI 用内置样例; 真实数据由 update.py 加载."""
    try:
        r = default_resolver()
        if r is not None and len(r._by_code) > 0:
            return r
    except Exception:
        pass
    return HsResolver.from_list(load_sample())


@click.command()
@click.argument("query")
@click.option("--lang", default="zh", type=click.Choice(["zh", "en"]), help="搜索语言")
@click.option("--limit", default=10, type=int, help="搜索结果上限")
@click.option("--children", is_flag=True, help="查看子级")
@click.option("--json", "as_json", is_flag=True, help="JSON 输出")
def main(query: str, lang: str, limit: int, children: bool, as_json: bool) -> None:
    """查询 HS 编码.

    QUERY 可以是:
    - 完整或部分 HS 编码 (例 9405408000, 9405.40.80.00)
    - 关键词 (例 "led lamp" 或 "蓝牙耳机")
    """
    resolver = _resolver_with_sample()
    console = Console()

    # 1. 先尝试当作编码查
    code = resolver.normalize(query)
    if code.isdigit() and len(code) >= 6:
        h = resolver.lookup(code)
        if h is not None:
            if children:
                _print_children(resolver, h, console, as_json)
            else:
                _print_one(h, console, as_json)
            return
        # 不是已知的编码,降级为搜索
        console.print(f"[yellow]未找到编码 {code}, 尝试搜索...[/yellow]")

    # 2. 关键词搜索
    results = resolver.search(query, lang=lang, limit=limit)
    if not results:
        console.print(f"[red]未匹配到任何 HS 编码: {query!r}[/red]")
        sys.exit(1)

    if as_json:
        click.echo(json.dumps([h.model_dump() for h in results], ensure_ascii=False, indent=2))
    else:
        table = Table(title=f"搜索结果: {query!r} (lang={lang})")
        table.add_column("HS 编码", style="cyan", no_wrap=True)
        table.add_column("粒度", justify="right")
        table.add_column("中文", style="green")
        table.add_column("English", style="blue")
        for h in results:
            table.add_row(h.code, str(h.level), h.description_zh, h.description_en)
        console.print(table)


def _print_one(h, console: Console, as_json: bool) -> None:  # type: ignore[no-untyped-def]
    if as_json:
        click.echo(json.dumps(h.model_dump(), ensure_ascii=False, indent=2))
    else:
        console.print(f"[bold cyan]{h.code}[/bold cyan]  (level {h.level})")
        console.print(f"  父级: {h.parent_code or '—'}")
        console.print(f"  章节: {h.chapter}")
        console.print(f"  中文: {h.description_zh}")
        console.print(f"  English: {h.description_en}")
        console.print(f"  来源: {h.source}")


def _print_children(resolver: HsResolver, h, console: Console, as_json: bool) -> None:  # type: ignore[no-untyped-def]
    kids = resolver.children(h.code)
    if as_json:
        click.echo(json.dumps([k.model_dump() for k in kids], ensure_ascii=False, indent=2))
    else:
        if not kids:
            console.print(f"[yellow]{h.code} 没有子级[/yellow]")
            return
        table = Table(title=f"{h.code} 的子级 ({len(kids)})")
        table.add_column("HS 编码", style="cyan")
        table.add_column("中文", style="green")
        table.add_column("English", style="blue")
        for k in kids:
            table.add_row(k.code, k.description_zh, k.description_en)
        console.print(table)


if __name__ == "__main__":
    main()
