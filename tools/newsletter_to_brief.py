#!/usr/bin/env python3
"""Write a video brief and per-item source files from a selected_news.json.

Usage: python tools/newsletter_to_brief.py runs/<project_id>/selected_news.json [--title "..."]

Writes runs/<project_id>/brief.md and resources/<project_id>/<item_id>.md.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from newsletter_common import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_AUDIENCE,
    DEFAULT_PURPOSE,
    REPO_ROOT,
    load_json,
    validate_selected_news,
)

LANGUAGE_NAMES = {
    "en": "English",
    "zh-Hant": "Traditional Chinese",
    "zh-Hans": "Simplified Chinese",
}
DEFAULT_VOICEOVER = "en"
DEFAULT_SUBTITLES = ["en", "zh-Hant", "zh-Hans"]
SFC_HOST = "apps.sfc.hk"
SFC_CONTENT_API = "https://apps.sfc.hk/edistributionWeb/api/news/content?refNo=<source_ref>&lang=EN"


def language_name(code):
    return LANGUAGE_NAMES.get(code, code)


def default_title(newsletter):
    return f"{newsletter['title']}, {newsletter['issue_date']}"


def subtitle_instructions(subtitles):
    if not subtitles:
        return "No subtitles."
    burned, *others = [language_name(code) for code in subtitles]
    tracks = f" and embed {', '.join(others)} as selectable tracks" if others else ""
    return (
        f"Subtitles: burn {burned} into the picture{tracks}. "
        "Also save every language as assets/subtitles_<language code>.srt. "
        "Report translated subtitles as not independently verified so I can check them."
    )


APPROVAL_INSTRUCTIONS = (
    "Approval: I pre-authorize every review gate before the final video. Record that as a decision_log entry "
    "with category approval_policy and do not stop at those gates, except for a source you cannot fetch or any "
    "paid service. Final approval is not pre-authorized and is the only human review: after rendering, write the "
    "publish checkpoint (or the pipeline's last gate) as awaiting_human, give me the file paths, citations and any "
    "flags, and stop. If I request changes, apply only those, re-render and stop again."
)


def build_remarks(document, selected):
    video = document["video"]
    newsletter = document["newsletter"]
    sources = "; ".join(
        f"{item['id']}: {item['source_url']}" for item in selected
    )
    sentences = [
        f"Purpose: {video.get('purpose', DEFAULT_PURPOSE)}.",
        f"Aspect ratio: {video.get('aspect_ratio', DEFAULT_ASPECT_RATIO)}.",
    ]
    audience = video.get("audience", DEFAULT_AUDIENCE)
    if audience:
        sentences.append(f"Audience: {audience}.")
    sentences += [
        f"Only the items in the files above are in scope; the full newsletter is at {newsletter['file_path']} for context.",
        "The newsletter text in those files is an AI summary, not a primary source.",
        f"Fetch and read the original source_url for every item, and cite it for every factual claim: {sources}.",
    ]
    if any(urlparse(item["source_url"]).netloc == SFC_HOST for item in selected):
        sentences.append(
            f"The {SFC_HOST} pages render with JavaScript, so a plain fetch returns no article text. "
            f"Use a browser or read {SFC_CONTENT_API}, but cite the source_url."
        )
    sentences += [
        "If a source cannot be fetched, stop and tell me; do not fall back on the summary.",
        "Flag any conflict between the summary and the source for my review, including names, dates, amounts and currencies. Both may write amounts with a bare $, so flag any currency the source does not state.",
        "State each item's date as its source gives it, and do not use relative wording such as \"this week\" unless the sources support it.",
        "Use programmatic graphics or supplied/licensed media; no AI-generated images or video clips, including as fallbacks.",
        subtitle_instructions(video.get("subtitle_languages", DEFAULT_SUBTITLES)),
        APPROVAL_INSTRUCTIONS,
    ]
    if video.get("remarks"):
        sentences.append(video["remarks"].strip())
    return " ".join(sentences)


def render_brief(document, selected, item_paths, title):
    video = document["video"]
    voiceover = video.get("voiceover_language", DEFAULT_VOICEOVER)
    subtitles = video.get("subtitle_languages", DEFAULT_SUBTITLES)
    lines = [
        f"# Video brief: {title}",
        "",
        f"- Project ID: {document['project_id']}",
        f"- Title: {title}",
        f"- Duration: {video['duration_target']}",
        f"- Voiceover language: {language_name(voiceover)}",
        f"- Subtitles language: {', '.join(language_name(code) for code in subtitles) or 'None'}",
        f"- Newspaper path: {', '.join(item_paths)}",
        f"- Remarks: {build_remarks(document, selected)}",
        "",
    ]
    return "\n".join(lines)


def render_item(document, item):
    newsletter = document["newsletter"]
    published = item.get("publication_date")
    item_date = (
        f"{published} (publication date; confirm against the source)"
        if published
        else f"{newsletter['issue_date']} (newsletter issue; take the publication date from the source)"
    )
    lines = [
        f"# {item['title']}",
        "",
        f"- Item ID: {item['id']}",
        f"- Section: {item['section']}",
        f"- Date: {item_date}",
        f"- Source URL: {item['source_url']}",
        f"- Source host: {urlparse(item['source_url']).netloc}",
    ]
    if item.get("source_ref"):
        lines.append(f"- Source reference: {item['source_ref']}")
    pages = item.get("pages")
    where = f", page {', '.join(str(page) for page in pages)}" if pages else ""
    lines += [
        f"- Newsletter: {newsletter['title']} ({newsletter['file_path']}{where})",
        "",
        "## Newsletter bullets",
        "",
        "AI summary. Check every claim against the source URL above.",
        "",
    ]
    lines += [f"- {bullet}" for bullet in item["summary_bullets"]]
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write a video brief from selected_news.json.")
    parser.add_argument("selected_news", type=Path)
    parser.add_argument("--title", help="overrides the title in the file; defaults to the newsletter title and issue")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="overwrite an existing brief for this project")
    args = parser.parse_args(argv)

    document = load_json(args.selected_news)
    problems = validate_selected_news(document)
    if problems:
        print(f"error: {args.selected_news} does not match the schema:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    project_id = document["project_id"]
    selected = [item for item in document["items"] if item["selected"]]
    brief_path = args.root / "runs" / project_id / "brief.md"
    resource_dir = args.root / "resources" / project_id

    # The brief is meant to be edited by hand, so never replace it silently.
    if brief_path.exists() and not args.force:
        print(f"error: {brief_path} already exists; pass --force to replace it.", file=sys.stderr)
        return 2

    item_paths = [f"resources/{project_id}/{item['id']}.md" for item in selected]
    title = args.title or document["video"].get("title") or default_title(document["newsletter"])

    resource_dir.mkdir(parents=True, exist_ok=True)
    for item in selected:
        (resource_dir / f"{item['id']}.md").write_text(render_item(document, item), encoding="utf-8")
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(render_brief(document, selected, item_paths, title), encoding="utf-8")

    print(f"Wrote {brief_path}")
    for path in item_paths:
        print(f"Wrote {args.root / path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
