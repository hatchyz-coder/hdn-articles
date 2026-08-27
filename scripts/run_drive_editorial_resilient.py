#!/usr/bin/env python3
"""Run the Drive editorial generator with bounded retry and candidate rotation.

This wrapper keeps the existing quality gate intact. It retries transient generation
failures inside the same publication slot and advances past permanently skipped seeds so
one weak candidate does not waste the entire scheduled slot.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TRANSIENT_REASONS = {"api_timeout"}
ROTATE_REASONS = {
    "low_score",
    "duplicate_source",
    "confidential",
    "manual_review_retry_limit",
}
STOP_REASONS = {"no_candidate", "dry_run"}
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_SECONDS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--backoff-seconds", type=int, default=DEFAULT_BACKOFF_SECONDS)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("generator_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def read_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_github_outputs(text: str) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for raw_line in text.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key:
            outputs[key] = value.strip()
    return outputs


def apply_generator_outputs(report: dict[str, Any], outputs: dict[str, str]) -> dict[str, Any]:
    merged = dict(report)
    if "selected" in outputs:
        merged["selected"] = outputs["selected"].lower() == "true"
    if outputs.get("reason"):
        merged["reason"] = outputs["reason"]
    return merged


def propagate_outputs(parent_output_path: str | None, output_text: str) -> None:
    if not parent_output_path or not output_text:
        return
    with open(parent_output_path, "a", encoding="utf-8") as handle:
        handle.write(output_text)
        if not output_text.endswith("\n"):
            handle.write("\n")


def should_continue(returncode: int, report: dict[str, Any]) -> tuple[bool, str]:
    if report.get("selected") is True:
        return False, "selected"

    reason = str(report.get("reason") or report.get("runMetrics", {}).get("exitReason") or "").strip()
    if reason in STOP_REASONS:
        return False, reason
    if reason in TRANSIENT_REASONS:
        return True, reason
    if reason in ROTATE_REASONS:
        return True, reason
    if returncode != 0:
        return True, reason or "generator_error"
    return False, reason or "completed_without_selection"


def run_once(generator_args: list[str], report_path: Path) -> tuple[int, dict[str, Any], str]:
    try:
        report_path.unlink()
    except FileNotFoundError:
        pass

    child_env = os.environ.copy()
    with tempfile.NamedTemporaryFile(prefix="drive-editorial-output-", delete=False) as tmp:
        child_output_path = Path(tmp.name)
    child_env["GITHUB_OUTPUT"] = str(child_output_path)

    try:
        command = [sys.executable, "scripts/generate_from_drive_editorial.py", *generator_args]
        completed = subprocess.run(command, check=False, env=child_env)
        output_text = child_output_path.read_text(encoding="utf-8") if child_output_path.exists() else ""
    finally:
        try:
            child_output_path.unlink()
        except FileNotFoundError:
            pass

    outputs = parse_github_outputs(output_text)
    report = apply_generator_outputs(read_report(report_path), outputs)
    return completed.returncode, report, output_text


def main() -> int:
    args = parse_args()
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1")
    if not args.generator_args:
        raise SystemExit("generator arguments are required after --")

    generator_args = list(args.generator_args)
    if generator_args and generator_args[0] == "--":
        generator_args = generator_args[1:]

    parent_output_path = os.environ.get("GITHUB_OUTPUT")
    last_returncode = 0
    last_reason = ""
    final_output_text = ""

    for attempt in range(1, args.max_attempts + 1):
        print(f"Drive editorial resilient attempt {attempt}/{args.max_attempts}", flush=True)
        returncode, report, output_text = run_once(generator_args, args.report_path)
        last_returncode = returncode
        final_output_text = output_text
        should_retry, reason = should_continue(returncode, report)
        last_reason = reason
        print(
            f"Drive editorial attempt result: returncode={returncode} reason={reason or 'unknown'} "
            f"selected={report.get('selected') is True}",
            flush=True,
        )

        if report.get("selected") is True:
            propagate_outputs(parent_output_path, output_text)
            return 0
        if not should_retry:
            propagate_outputs(parent_output_path, output_text)
            return returncode
        if attempt < args.max_attempts:
            time.sleep(max(0, args.backoff_seconds))

    propagate_outputs(parent_output_path, final_output_text)
    print(
        f"Drive editorial attempts exhausted without publication: reason={last_reason or 'unknown'}",
        file=sys.stderr,
        flush=True,
    )
    # Preserve the legacy behaviour for quality/no-candidate outcomes (successful slot
    # with selected=false), while surfacing persistent generator failures to Actions.
    return last_returncode if last_returncode != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
