#!/usr/bin/env python3
"""Split a newsletter PDF into news items and match each to its source link.

Usage: python tools/extract_newsletter.py <pdf> [-o newsletter_items.json]

The output defaults to newsletter_items.json next to the PDF. Exits with 2 if
any item has no source link; those items are reported with source_url null,
never guessed.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent

# Running headers and footers sit in these margins on every page.
HEADER_Y = 800
FOOTER_Y = 40

BANNER_SIZE = (12.5, 14.0)
MASTHEAD_MIN_SIZE = 24
DISCLAIMER_MAX_SIZE = 10

# Lines in one headline sit closer than this many font sizes apart.
TITLE_LINE_GAP = 1.7
# Bullets are drawn as shapes, not text, so only the wider gap between lines
# separates them: about 21pt between bullets against 17pt within one.
BULLET_GAP = 1.6

MONTHS = {
    name: number
    for number, name in enumerate(
        "January February March April May June July August September October November December".split(),
        start=1,
    )
}
ISSUE_DATE = re.compile(rf"^({'|'.join(MONTHS)})\s+(\d{{4}})$")
WHAT_THIS_MEANS = "What this means:"


@dataclass
class Line:
    page: int
    y: float
    x: float
    font: str
    size: float
    text: str
    owner: object = None

    @property
    def bold(self):
        return "Bold" in self.font

    @property
    def italic(self):
        return "Italic" in self.font or "Oblique" in self.font


@dataclass
class Link:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    url: str


@dataclass
class Item:
    section: str
    title_lines: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    pages: list = field(default_factory=list)
    urls: list = field(default_factory=list)
    title_at: tuple = None
    body_at: tuple = None

    def touch(self, page):
        if page not in self.pages:
            self.pages.append(page)


def join_wrapped(lines):
    """Join wrapped lines. A line ending in a hyphen is a compound word, so keep it."""
    text = ""
    for line in lines:
        line = " ".join(line.split())
        if not text or text.endswith("-"):
            text += line
        else:
            text += " " + line
    return text


def section_for(banner):
    lowered = banner.lower()
    if "corporate" in lowered:
        return "corporate"
    if "enforcement" in lowered:
        return "enforcement"
    if re.search(r"\bmas\b|monetary authority of singapore", lowered):
        return "mas"
    return "other"


def read_pdf(path):
    """Return the positioned text lines and web links on every page."""
    lines, links = [], []
    for number, page in enumerate(PdfReader(path).pages, start=1):

        def visit(text, cm, tm, font, size, page_number=number):
            for part in text.splitlines():
                if not part.strip():
                    continue
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                scale = abs(tm[0]) * abs(cm[0]) or 1
                name = str((font or {}).get("/BaseFont", ""))
                lines.append(
                    Line(page_number, round(y, 1), round(x, 1), name, round(size * scale, 1), part.strip())
                )

        page.extract_text(visitor_text=visit)

        for annotation in page.get("/Annots") or []:
            annotation = annotation.get_object()
            action = annotation.get("/A") or {}
            url = str(action.get("/URI") or "")
            if url.lower().startswith(("http://", "https://")):
                x0, y0, x1, y1 = (float(value) for value in annotation["/Rect"])
                links.append(Link(number, x0, y0, x1, y1, url))
    return lines, links


def assemble(lines):
    """Turn positioned lines into items plus the newsletter's own details."""
    masthead, summary, warnings, items = [], [], [], []
    issue_date = None
    section = None
    current = None

    # Sort by height then column, so a table row's title and body interleave.
    ordered = sorted(lines, key=lambda line: (line.page, -line.y, line.x))
    for line in ordered:
        if line.y > HEADER_Y or line.y < FOOTER_Y:
            continue
        if line.size >= MASTHEAD_MIN_SIZE:
            masthead.append(line.text)
            continue
        if line.size < DISCLAIMER_MAX_SIZE:
            current = None
            continue
        if line.bold and BANNER_SIZE[0] <= line.size <= BANNER_SIZE[1]:
            section = "summary" if "summary" in line.text.lower() else section_for(line.text)
            current = None
            continue
        if section is None:
            match = ISSUE_DATE.match(line.text)
            if match:
                issue_date = f"{match.group(2)}-{MONTHS[match.group(1)]:02d}"
            continue
        if section == "summary":
            summary.append(line.text)
            continue

        if line.bold and not line.italic:
            continues_title = (
                current is not None
                and current.title_at is not None
                and current.title_at[0] == line.page
                and current.title_at[1] - line.y < TITLE_LINE_GAP * line.size
            )
            if not continues_title:
                current = Item(section)
                items.append(current)
            current.title_lines.append(line.text)
            current.title_at = (line.page, line.y)
            current.touch(line.page)
            line.owner = current
            continue

        if current is None:
            warnings.append(f"page {line.page}: text outside any item: {line.text!r}")
            continue

        current.touch(line.page)
        line.owner = current
        if line.text.startswith("Read more") or line.text == "article source":
            continue

        if line.italic:
            # "What this means" is one paragraph, kept as the item's last bullet.
            if line.text.startswith(WHAT_THIS_MEANS) or not current.bullets:
                current.bullets.append([line.text])
            else:
                current.bullets[-1].append(line.text)
        elif starts_bullet(current, line):
            current.bullets.append([line.text])
        else:
            current.bullets[-1].append(line.text)
        current.body_at = (line.page, line.y)

    return masthead, issue_date, summary, items, warnings


def starts_bullet(item, line):
    if not item.bullets or item.body_at is None:
        return True
    page, y = item.body_at
    if page == line.page:
        return y - line.y > BULLET_GAP * line.size
    # Across a page break the gap means nothing, so go by how the text ended.
    return item.bullets[-1][-1].rstrip().endswith((".", "!", "?", ":"))


def attach_links(links, lines, warnings):
    """Give each link to the item owning the text underneath it. Returns unmatched URLs."""
    unmatched = []
    for link in links:
        underneath = [
            line
            for line in lines
            if line.page == link.page and link.y0 - 2 <= line.y <= link.y1 + 2 and line.x <= link.x1
        ]
        underneath.sort(key=lambda line: abs(line.x - link.x0))
        owner = underneath[0].owner if underneath else None
        if owner is None:
            unmatched.append({"page": link.page, "url": link.url})
        elif link.url not in owner.urls:
            owner.urls.append(link.url)
    return unmatched


def source_ref(url):
    match = re.search(r"[?&]refNo=([^&#]+)", url)
    return match.group(1) if match else None


def build_output(path, masthead, issue_date, summary, items, unmatched_links, warnings):
    records, missing = [], []
    for number, item in enumerate(items, start=1):
        record = {
            "id": f"item-{number:02d}",
            "section": item.section,
            "title": join_wrapped(item.title_lines),
            "summary_bullets": [join_wrapped(bullet) for bullet in item.bullets],
            "source_url": item.urls[0] if item.urls else None,
            "source_ref": source_ref(item.urls[0]) if item.urls else None,
            "pages": item.pages,
        }
        if len(item.urls) > 1:
            warnings.append(f"{record['id']}: more than one link, kept the first: {item.urls}")
        if not item.urls:
            missing.append({"id": record["id"], "title": record["title"], "pages": item.pages})
        records.append(record)

    if not masthead:
        warnings.append("newsletter title not found")
    if not issue_date:
        warnings.append("issue date not found")

    return {
        "newsletter": {
            "title": " ".join(masthead) or None,
            "issue_date": issue_date,
            "file_path": display_path(path),
        },
        "executive_summary": join_wrapped(summary),
        "items": records,
        "items_without_source_url": missing,
        "unmatched_links": unmatched_links,
        "warnings": warnings,
    }


def display_path(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def extract(path):
    lines, links = read_pdf(path)
    masthead, issue_date, summary, items, warnings = assemble(lines)
    unmatched_links = attach_links(links, lines, warnings)
    return build_output(path, masthead, issue_date, summary, items, unmatched_links, warnings)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Split a newsletter PDF into news items.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="default: newsletter_items.json next to the PDF")
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        parser.error(f"no such file: {args.pdf}")

    result = extract(args.pdf)
    if not result["items"]:
        print("error: no news items found. Does this PDF have a text layer?", file=sys.stderr)
        return 1

    output = args.output or args.pdf.parent / "newsletter_items.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"Wrote {len(result['items'])} items to {output}")
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    for link in result["unmatched_links"]:
        print(f"warning: page {link['page']}: link not inside any item: {link['url']}", file=sys.stderr)
    if result["items_without_source_url"]:
        for item in result["items_without_source_url"]:
            print(f"NO SOURCE URL: {item['id']} (pages {item['pages']}): {item['title']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
