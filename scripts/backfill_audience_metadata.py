from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JP_DIR = ROOT / "src/content/articles"
EN_DIR = ROOT / "src/content/articles-en"

FIELDS = ("audiences", "section", "industry", "series", "contentType")

# Explicit editorial taxonomy for every current Japanese article slug.
# This is intentionally slug-based rather than keyword-based so article routing
# does not change because of incidental wording in a title, tag, or body.
CATALOG = {
    "clinic-first-10-videos": dict(audiences=["clinic"], section="clinic-marketing", industry="medical", series="clinic-content", contentType="practical-guide"),
    "clinic-video-strategy": dict(audiences=["clinic"], section="clinic-marketing", industry="medical", series="clinic-content", contentType="practical-guide"),
    "electronic-prescription-clinic-operations-2026": dict(audiences=["clinic"], section="clinic-compliance", industry="medical", series="clinic-regulation", contentType="regulation"),
    "health-food-advertising-story-context": dict(audiences=["clinic", "general"], section="research", industry="other", series="advertising-compliance", contentType="regulation"),
    "lhub-beauty-clinic-unified-ops": dict(audiences=["clinic", "lhub"], section="lhub-usecase", industry="medical", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-create-vintage-fan-community": dict(audiences=["lhub"], section="lhub-usecase", industry="retail", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-creator-monetization-deliverables": dict(audiences=["lhub"], section="lhub-usecase", industry="creator", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-creator-monetization-line": dict(audiences=["lhub"], section="lhub-usecase", industry="creator", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-for-rental-management": dict(audiences=["lhub"], section="lhub-usecase", industry="real-estate", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-handmade-ec-unified-management": dict(audiences=["lhub"], section="lhub-usecase", industry="retail", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-high-ticket-fortune-sales": dict(audiences=["lhub"], section="lhub-usecase", industry="fortune", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-commerce-operations": dict(audiences=["lhub"], section="lhub-usecase", industry="retail", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-consultation-parenting-trust": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-fanclub-management": dict(audiences=["lhub"], section="lhub-usecase", industry="creator", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-for-teachers-practical-guide": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-sales-reservations-customer-management": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-line-salon-reservation": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-recurring-revenue-line-operations": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "lhub-retention-guide-line-subscription": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "line-booking-payment-flow": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "line-electronic-prescription-checklist-online-clinic": dict(audiences=["clinic", "lhub"], section="clinic-compliance", industry="medical", series="clinic-regulation", contentType="practical-guide"),
    "line-lhub-uranaishi-reservation-payment": dict(audiences=["lhub"], section="lhub-usecase", industry="fortune", series="lhub-use-cases", contentType="practical-guide"),
    "medical-fee-revision-clinic-facility-standards-2026": dict(audiences=["clinic", "general"], section="research", industry="medical", series="official-sources", contentType="regulation"),
    "medical-sns-attack-vs-incitement": dict(audiences=["clinic"], section="clinic-marketing", industry="medical", series="medical-sns", contentType="opinion"),
    "mhlw-drug-loss-meeting-2026-09": dict(audiences=["clinic", "general"], section="research", industry="medical", series="official-sources", contentType="news-analysis"),
    "online-care-patient-journey-2026": dict(audiences=["clinic"], section="clinic-journey", industry="medical", series="patient-journey", contentType="practical-guide"),
    "prevent-patient-forgetfulness-lhub-dental-clinics": dict(audiences=["clinic", "lhub"], section="lhub-usecase", industry="dental", series="lhub-use-cases", contentType="practical-guide"),
    "regenerative-medicine-improvement-orders": dict(audiences=["clinic", "general"], section="research", industry="medical", series="official-sources", contentType="regulation"),
    "roots-lhub-self-pay-partnership": dict(audiences=["clinic", "lhub"], section="lhub-usecase", industry="medical", series="lhub-use-cases", contentType="case-study"),
    "seitai-sekkotsuin-smart-lhub": dict(audiences=["lhub"], section="lhub-usecase", industry="other", series="lhub-use-cases", contentType="practical-guide"),
    "seiyu-lhub-recording-requests": dict(audiences=["lhub"], section="lhub-usecase", industry="creator", series="lhub-use-cases", contentType="practical-guide"),
    "sell-unique-vintage-lhub-speed-rev": dict(audiences=["lhub"], section="lhub-usecase", industry="retail", series="lhub-use-cases", contentType="practical-guide"),
    "subscription-model-for-fortune-tellers-lhub-membership": dict(audiences=["lhub"], section="lhub-usecase", industry="fortune", series="lhub-use-cases", contentType="practical-guide"),
}


def split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Markdown file has no opening frontmatter delimiter")
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("Markdown file has no closing frontmatter delimiter") from exc
    return lines[1:close], lines[close + 1 :]


def strip_managed_fields(front: list[str]) -> list[str]:
    output: list[str] = []
    i = 0
    while i < len(front):
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):", front[i])
        key = match.group(1) if match else None
        if key not in FIELDS:
            output.append(front[i])
            i += 1
            continue

        i += 1
        if key == "audiences":
            while i < len(front) and re.match(r"^\s+-\s+", front[i]):
                i += 1
    while output and output[-1] == "":
        output.pop()
    return output


def render_metadata(meta: dict[str, object]) -> list[str]:
    lines = ["audiences:"]
    lines.extend(f'  - "{value}"' for value in meta["audiences"])
    lines.extend(
        [
            f'section: "{meta["section"]}"',
            f'industry: "{meta["industry"]}"',
            f'series: "{meta["series"]}"',
            f'contentType: "{meta["contentType"]}"',
        ]
    )
    return lines


def apply_metadata(path: Path, meta: dict[str, object], write: bool) -> bool:
    original = path.read_text(encoding="utf-8")
    front, body = split_frontmatter(original)
    new_lines = ["---", *strip_managed_fields(front), *render_metadata(meta), "---", *body]
    updated = "\n".join(new_lines)
    if original.endswith("\n"):
        updated += "\n"
    changed = updated != original
    if write and changed:
        path.write_text(updated, encoding="utf-8")
    return changed


def current_jp_slugs() -> set[str]:
    return {path.stem for path in JP_DIR.glob("*.md")}


def validate_catalog() -> None:
    actual = current_jp_slugs()
    configured = set(CATALOG)
    missing = sorted(actual - configured)
    stale = sorted(configured - actual)
    if missing or stale:
        raise SystemExit(f"Catalog mismatch: missing={missing}, stale={stale}")

    for slug, meta in CATALOG.items():
        if meta["section"] == "lhub-usecase" and meta["industry"] not in {"medical", "dental"}:
            if "clinic" in meta["audiences"]:
                raise SystemExit(f"Non-medical LHub article must not enter clinic lane: {slug}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write metadata into JP and matching EN files")
    args = parser.parse_args()

    validate_catalog()
    changed: list[str] = []
    for slug, meta in CATALOG.items():
        jp = JP_DIR / f"{slug}.md"
        if apply_metadata(jp, meta, args.write):
            changed.append(str(jp.relative_to(ROOT)))
        en = EN_DIR / f"{slug}.md"
        if en.exists() and apply_metadata(en, meta, args.write):
            changed.append(str(en.relative_to(ROOT)))

    if args.write:
        print(f"Backfilled metadata in {len(changed)} file(s)")
        for path in changed:
            print(path)
    elif changed:
        raise SystemExit(f"Metadata backfill required for {len(changed)} file(s). Run with --write.")
    else:
        print("Audience metadata is fully backfilled and normalized.")


if __name__ == "__main__":
    main()
