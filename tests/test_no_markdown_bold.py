from pathlib import Path


ARTICLE_DIRS = (
    Path("src/content/articles"),
    Path("src/content/articles-en"),
)


def test_articles_do_not_use_markdown_bold():
    violations = []
    for directory in ARTICLE_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if "**" in text:
                violations.append(str(path))

    assert not violations, (
        "Markdown bold syntax is prohibited in HDN articles. "
        "Remove double-asterisk emphasis from: " + ", ".join(violations)
    )
