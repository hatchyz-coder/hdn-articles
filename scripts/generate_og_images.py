#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "public" / "og"
WIDTH, HEIGHT = 1200, 630

NAVY = "#10263F"
NAVY_2 = "#183B5B"
BLUE = "#4D8FB5"
WHITE = "#FFFFFF"
MUTED = "#AFC4D2"
ACCENT = "#C9684B"
GRID = "#214664"
LINE = "#38546C"

BOLD_FONT_CANDIDATES = [
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
REGULAR_FONT_CANDIDATES = [
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def find_font(candidates: list[Path]) -> Path:
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("No suitable font found. Install fonts-noto-cjk before generating OGP images.")


BOLD_FONT = find_font(BOLD_FONT_CANDIDATES)
REGULAR_FONT = find_font(REGULAR_FONT_CANDIDATES)


def get_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not match:
        raise ValueError(f"Missing frontmatter: {path}")
    data: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        if not raw or raw[0].isspace() or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def fit_title(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start_size: int, min_size: int):
    for size in range(start_size, min_size - 1, -2):
        title_font = get_font(BOLD_FONT, size)
        lines: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if draw.textbbox((0, 0), candidate, font=title_font)[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        if len(lines) <= max_lines:
            return title_font, lines

    title_font = get_font(BOLD_FONT, min_size)
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textbbox((0, 0), candidate, font=title_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if "".join(lines) != text and lines:
        lines[-1] = lines[-1].rstrip("…") + "…"
    return title_font, lines


def draw_card(title: str, category: str, lang: str, output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH, 14), fill=ACCENT)
    draw.rectangle((820, 0, WIDTH, HEIGHT), fill=NAVY_2)
    for x in range(850, WIDTH, 70):
        draw.line((x, 0, x, HEIGHT), fill=GRID, width=1)
    for y in range(70, HEIGHT, 70):
        draw.line((820, y, WIDTH, y), fill=GRID, width=1)

    kicker_font = get_font(BOLD_FONT, 26)
    label_font = get_font(BOLD_FONT, 30)
    small_font = get_font(REGULAR_FONT, 22)
    mark_font = get_font(BOLD_FONT, 78)

    draw.text((70, 62), "HDN ARTICLES", font=kicker_font, fill=BLUE)
    draw.text((70, 110), category[:42], font=label_font, fill=WHITE)

    start_size = 58 if lang == "ja" else 52
    title_font, lines = fit_title(draw, title, 690, 4, start_size, 38)
    y = 186
    for line in lines:
        draw.text((70, y), line, font=title_font, fill=WHITE)
        bbox = draw.textbbox((70, y), line, font=title_font)
        y = bbox[3] + 15

    draw.line((70, 535, 740, 535), fill=LINE, width=2)
    footer = (
        "Clinic management / patient journey / practical implementation"
        if lang == "en"
        else "クリニック経営・患者導線・実務ナレッジ"
    )
    draw.text((70, 555), footer, font=small_font, fill=MUTED)

    draw.text((872, 198), "HDN", font=mark_font, fill=WHITE)
    draw.text((875, 290), "INSIGHT", font=kicker_font, fill=BLUE)
    draw.text((875, 455), "article.hdnjapan.com", font=small_font, fill=MUTED)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def generate_collection(directory: Path, lang: str) -> int:
    count = 0
    if not directory.exists():
        return 0
    for path in sorted(directory.glob("*.md")):
        data = parse_frontmatter(path)
        if data.get("draft", "false").lower() == "true":
            continue
        draw_card(
            data.get("title", path.stem),
            data.get("category", "HDN Articles"),
            lang,
            OUTPUT_ROOT / lang / f"{path.stem}.png",
        )
        count += 1
    return count


def main() -> None:
    ja = generate_collection(ROOT / "src" / "content" / "articles", "ja")
    en = generate_collection(ROOT / "src" / "content" / "articles-en", "en")
    print(f"Generated {ja} Japanese and {en} English OGP images in {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
