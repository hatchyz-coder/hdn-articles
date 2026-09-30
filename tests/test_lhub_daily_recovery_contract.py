from pathlib import Path

WORKFLOW = Path(".github/workflows/daily-drive-editorial-fallback.yml").read_text(encoding="utf-8")


def test_recovery_uses_daily_preflight():
    assert "python scripts/lhub_daily_preflight.py" in WORKFLOW
    assert "steps.preflight.outputs.published == 'true'" in WORKFLOW


def test_recovery_does_not_reintroduce_two_per_day_target():
    assert "DAILY_TARGET: '2'" not in WORKFLOW
    assert "two Drive-origin pairs" not in WORKFLOW


def test_recovery_dispatches_at_most_once():
    assert "for attempt in" not in WORKFLOW
    assert WORKFLOW.count("gh workflow run daily-drive-editorial-publish.yml --ref main") == 1


def test_already_published_path_stops_before_heavy_pipeline():
    assert "Recovery exits before dependency setup, API, reserve, tests/build, PR, or deploy." in WORKFLOW
