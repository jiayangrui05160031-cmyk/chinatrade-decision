"""Tests for the policy updater CLI output used by GitHub Actions."""

from __future__ import annotations

import json
import sys

import pytest

from wto_policy.agent import update


def test_json_output_is_machine_readable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = {
        "started_at": "2026-08-08T00:00:00+00:00",
        "sources": {"federal_register": {"fetched": 1, "new": 1}},
        "total_new": 1,
        "total_fetched": 1,
    }

    def fake_run_update(**kwargs: object) -> dict[str, object]:
        console = kwargs["console"]
        assert isinstance(console, update.Console)
        assert console.file is sys.stderr
        return expected

    monkeypatch.setattr(update, "run_update", fake_run_update)
    monkeypatch.setattr(sys, "argv", ["wto-update", "--json"])

    with pytest.raises(SystemExit) as exc_info:
        update.main()

    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_list_and_json_are_mutually_exclusive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["wto-update", "--list", "--json"])

    with pytest.raises(SystemExit) as exc_info:
        update.main()

    assert exc_info.value.code == 2
    assert "cannot be used together" in capsys.readouterr().err
