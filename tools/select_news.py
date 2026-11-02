#!/usr/bin/env python3
"""Choose news items and video settings, and write a validated selected_news.json.

Interactive:     python tools/select_news.py newsletter_items.json
Non-interactive: python tools/select_news.py newsletter_items.json \\
                     --ids 7,15 --purpose training --duration "30-50 seconds" --project-id weekly-update

Passing both --ids and --project-id skips all prompts; anything else not given
takes its default. The output defaults to runs/<project_id>/selected_news.json.
"""

import argparse
import re
import sys
from pathlib import Path

from newsletter_common import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_AUDIENCE,
    DEFAULT_PURPOSE,
    REPO_ROOT,
    load_json,
    validate_selected_news,
    write_json,
)

ASPECT_RATIOS = ("16:9", "1:1", "9:16")
DEFAULT_DURATION = {"training": "3-4 min", "reel": "60s"}
DEFAULT_VOICEOVER = "en"
DEFAULT_SUBTITLES = ["en", "zh-Hant", "zh-Hans"]
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SelectionError(ValueError):
    pass


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_selection(text, items):
    """Turn "1,3-5", item ids or "all" into a set of item ids."""
    by_number = {str(number): item for number, item in enumerate(items, start=1)}
    by_id = {item["id"]: item for item in items}
    if text.strip().lower() == "all":
        chosen = [item for item in items if item.get("source_url")]
    else:
        chosen = []
        for token in filter(None, (part.strip() for part in text.split(","))):
            bounds = re.fullmatch(r"(\d+)-(\d+)", token)
            numbers = range(int(bounds[1]), int(bounds[2]) + 1) if bounds else [token]
            for number in numbers:
                item = by_number.get(str(number)) or by_id.get(str(number))
                if item is None:
                    raise SelectionError(f"no item {number!r}; choose from 1-{len(items)}")
                chosen.append(item)
    if not chosen:
        raise SelectionError("select at least one item")
    for item in chosen:
        if not item.get("source_url"):
            raise SelectionError(f"{item['id']} has no source URL, so it cannot be selected")
    return {item["id"] for item in chosen}


def print_items(items):
    for number, item in enumerate(items, start=1):
        pages = ",".join(str(page) for page in item["pages"])
        reference = item.get("source_ref") or "NO SOURCE URL"
        print(f"{number:>3}. [{item['section']}] {item['title']}  (p{pages}, {reference})")
        if item["summary_bullets"]:
            print(f"     {item['summary_bullets'][0][:90]}")


def ask(prompt, default=None, input_fn=input):
    suffix = f" [{default}]" if default else ""
    answer = input_fn(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_until_valid(prompt, default, parse, input_fn=input):
    while True:
        try:
            return parse(ask(prompt, default, input_fn))
        except SelectionError as error:
            print(f"  {error}", file=sys.stderr)


def parse_project_id(text):
    if SLUG.fullmatch(text):
        return text
    suggestion = slugify(text)
    hint = f" Try {suggestion!r}." if suggestion else ""
    raise SelectionError(f"project ID must be a lowercase hyphenated slug.{hint}")


def parse_purpose(text):
    if text in DEFAULT_DURATION:
        return text
    raise SelectionError("purpose must be training or reel")


def parse_aspect_ratio(text):
    if text in ASPECT_RATIOS:
        return text
    raise SelectionError(f"aspect ratio must be one of {', '.join(ASPECT_RATIOS)}")


def split_languages(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def build_document(source, selected_ids, project_id, video):
    # selected_news.json cannot hold an item without a URL, so those stay out.
    items = [
        {
            "id": item["id"],
            "section": item["section"],
            "title": item["title"],
            "summary_bullets": item["summary_bullets"],
            "source_url": item["source_url"],
            **({"source_ref": item["source_ref"]} if item.get("source_ref") else {}),
            **({"publication_date": item["publication_date"]} if item.get("publication_date") else {}),
            "pages": item["pages"],
            "selected": item["id"] in selected_ids,
        }
        for item in source["items"]
        if item.get("source_url")
    ]
    return {
        "project_id": project_id,
        "newsletter": source["newsletter"],
        "items": items,
        "video": video,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Select news items for one video.")
    parser.add_argument("items_file", type=Path, help="newsletter_items.json from extract_newsletter.py")
    parser.add_argument("--ids", help='item numbers or ids, for example "7,15", "1,3-5" or "all"')
    parser.add_argument("--project-id", help="lowercase hyphenated slug, unique per video")
    parser.add_argument("--title", help="video title; defaults to the newsletter title and issue")
    parser.add_argument("--purpose", choices=sorted(DEFAULT_DURATION))
    parser.add_argument("--duration", help='for example "3-4 min" or "60s"')
    parser.add_argument("--aspect-ratio", choices=ASPECT_RATIOS)
    parser.add_argument("--voiceover-language")
    parser.add_argument("--subtitle-languages", help='comma-separated, first is burned in, for example "en,zh-Hant,zh-Hans"; empty for none')
    parser.add_argument("--audience")
    parser.add_argument("--remarks")
    parser.add_argument("-o", "--output", type=Path, help="default: runs/<project_id>/selected_news.json")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="overwrite an existing selection for this project")
    args = parser.parse_args(argv)

    source = load_json(args.items_file)
    items = source["items"]
    for missing in source.get("items_without_source_url", []):
        print(f"warning: {missing['id']} has no source URL and cannot be selected", file=sys.stderr)

    interactive = not (args.ids and args.project_id)
    try:
        if interactive:
            print_items(items)
            print()
            if args.ids:
                selected_ids = parse_selection(args.ids, items)
            else:
                selected_ids = ask_until_valid(
                    'Items to include (for example "7,15", "1,3-5" or "all")',
                    None,
                    lambda text: parse_selection(text, items),
                )
            issue = source["newsletter"].get("issue_date") or "video"
            project_id = args.project_id or ask_until_valid(
                "Project ID", f"regulatory-update-{issue}", parse_project_id
            )
            title = args.title or ask("Video title (optional)")
            purpose = args.purpose or ask_until_valid("Purpose (training/reel)", DEFAULT_PURPOSE, parse_purpose)
            duration = args.duration or ask("Duration target", DEFAULT_DURATION[purpose])
            aspect_ratio = args.aspect_ratio or ask_until_valid(
                f"Aspect ratio ({', '.join(ASPECT_RATIOS)})", DEFAULT_ASPECT_RATIO, parse_aspect_ratio
            )
            voiceover = args.voiceover_language or ask("Voiceover language", DEFAULT_VOICEOVER)
            subtitles = (
                args.subtitle_languages
                if args.subtitle_languages is not None
                else ask("Subtitle languages, first is burned in", ",".join(DEFAULT_SUBTITLES))
            )
            audience = args.audience if args.audience is not None else ask("Audience", DEFAULT_AUDIENCE)
            remarks = args.remarks if args.remarks is not None else ask("Remarks (optional)")
        else:
            selected_ids = parse_selection(args.ids, items)
            project_id = parse_project_id(args.project_id)
            title = args.title
            purpose = args.purpose or DEFAULT_PURPOSE
            duration = args.duration or DEFAULT_DURATION[purpose]
            aspect_ratio = args.aspect_ratio or DEFAULT_ASPECT_RATIO
            voiceover = args.voiceover_language or DEFAULT_VOICEOVER
            subtitles = args.subtitle_languages if args.subtitle_languages is not None else ",".join(DEFAULT_SUBTITLES)
            audience = args.audience if args.audience is not None else DEFAULT_AUDIENCE
            remarks = args.remarks or ""
    except SelectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except EOFError:
        print("error: ran out of input; pass --ids and --project-id to skip the prompts", file=sys.stderr)
        return 2

    document = build_document(
        source,
        selected_ids,
        project_id,
        {
            **({"title": title} if title else {}),
            "purpose": purpose,
            "duration_target": duration,
            "aspect_ratio": aspect_ratio,
            "voiceover_language": voiceover,
            "subtitle_languages": split_languages(subtitles),
            "audience": audience,
            "remarks": remarks,
        },
    )

    problems = validate_selected_news(document)
    if problems:
        print("error: the selection does not match the schema:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    output = args.output or args.root / "runs" / project_id / "selected_news.json"
    if output.exists() and not args.force:
        print(f"error: {output} already exists. Project IDs are unique per video; pass --force to replace it.", file=sys.stderr)
        return 2

    write_json(output, document)
    print(f"Wrote {output} with {len(selected_ids)} selected of {len(document['items'])} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
