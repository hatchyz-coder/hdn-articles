#!/usr/bin/env python3
"""Smoke tests for Drive reader timeout boundaries."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_from_drive_knowledge import RunTimer, call_openai_once


def test_openai_mock_timeout() -> None:
    timer = RunTimer()
    started = time.monotonic()
    try:
        call_openai_once(
            {"id": "mock-doc", "name": "Mock Doc", "modifiedTime": "2026-01-01T00:00:00Z"},
            "mock source text",
            {"mode": "test"},
            timer,
            mock_timeout=True,
        )
    except TimeoutError:
        elapsed = time.monotonic() - started
        assert elapsed < 2, f"mock OpenAI timeout took too long: {elapsed:.2f}s"
        assert timer.metrics["apiCalls"] == 1
        return
    raise AssertionError("mock OpenAI timeout did not raise TimeoutError")


def test_gnu_timeout_command() -> None:
    timeout_bin = shutil.which("timeout")
    if not timeout_bin:
        print("SKIP GNU timeout command is not available on this platform")
        return
    probe = subprocess.run([timeout_bin, "--version"], capture_output=True, text=True)
    if probe.returncode != 0:
        print("SKIP timeout command is not GNU coreutils")
        return
    started = time.monotonic()
    result = subprocess.run(
        [timeout_bin, "--signal=TERM", "--kill-after=1s", "1s", sys.executable, "-c", "import time; time.sleep(10)"],
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    assert result.returncode in {124, 137, 143}, result.returncode
    assert elapsed < 4, f"GNU timeout did not stop promptly: {elapsed:.2f}s"


def main() -> int:
    test_openai_mock_timeout()
    test_gnu_timeout_command()
    print("Drive reader timeout smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
