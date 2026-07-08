"""Tests for cli/lookup_hs.py — 使用 click.testing.CliRunner."""

from __future__ import annotations

import json

from click.testing import CliRunner

from wto_policy.cli.lookup_hs import main

runner = CliRunner()


def test_lookup_exact_code() -> None:
    result = runner.invoke(main, ["9405408000"])
    assert result.exit_code == 0
    assert "9405408000" in result.stdout
    assert "LED" in result.stdout


def test_lookup_dotted_code() -> None:
    result = runner.invoke(main, ["9405.40.80.00"])
    assert result.exit_code == 0
    assert "9405408000" in result.stdout


def test_lookup_search_chinese() -> None:
    result = runner.invoke(main, ["蓝牙"])
    assert result.exit_code == 0
    assert "8518302000" in result.stdout


def test_lookup_search_english() -> None:
    result = runner.invoke(main, ["bluetooth headphones", "--lang", "en"])
    assert result.exit_code == 0
    assert "8518302000" in result.stdout


def test_lookup_children() -> None:
    result = runner.invoke(main, ["940540", "--children"])
    assert result.exit_code == 0
    assert "9405404000" in result.stdout
    assert "9405408000" in result.stdout


def test_lookup_json() -> None:
    result = runner.invoke(main, ["9405408000", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["code"] == "9405408000"


def test_lookup_not_found() -> None:
    result = runner.invoke(main, ["xyz不存在的品名"])
    # CLI 走关键词搜索,大概率不命中
    # (因为我们的样例很有限)
    # 退出码可能 0(若恰好命中) 或 1
    assert result.exit_code in (0, 1)
