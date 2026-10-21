import re

import bleach
import markdown
from markupsafe import Markup


ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "code": ["class"],
}

LIST_ITEM_PATTERN = re.compile(r"^[ \t]{0,3}(?:[-+*]|\d+[.)])[ \t]+")


def _normalise_lists(source):
    """Accept Gemini lists even when it omits the blank line before them."""
    lines = source.splitlines()
    normalized = []
    in_fenced_code = False
    previous_was_list_item = False

    for line in lines:
        if line.lstrip().startswith("```"):
            in_fenced_code = not in_fenced_code

        is_list_item = not in_fenced_code and bool(LIST_ITEM_PATTERN.match(line))
        if (
            is_list_item
            and normalized
            and normalized[-1].strip()
            and not previous_was_list_item
        ):
            normalized.append("")

        normalized.append(line)
        previous_was_list_item = is_list_item

    return "\n".join(normalized)


def render_markdown(value):
    """Convert Markdown to a small, safe HTML subset for chat messages."""
    source = _normalise_lists(str(value or ""))
    rendered = markdown.markdown(
        source,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    cleaned = bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )
    return Markup(cleaned)
