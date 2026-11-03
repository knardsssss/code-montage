"""Tests for the newsletter-to-brief tools.

Run from the repository root: python -m unittest discover -s tests -v
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
SAMPLE_PDF = REPO_ROOT / "resources" / "newsletters" / "sample_newsletter.pdf"
sys.path.insert(0, str(TOOLS))

import extract_newsletter as extractor  # noqa: E402
from extract_newsletter import Line, Link  # noqa: E402
from newsletter_common import validate_selected_news  # noqa: E402

BODY = "AAAAAA+LiberationSans"
BOLD = "AAAAAA+LiberationSans-Bold"
SFC = "https://apps.sfc.hk/doc?refNo="


def run_tool(name, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(TOOLS / name), *map(str, args)],
        capture_output=True,
        text=True,
        input=stdin,
    )


def find(items, fragment):
    matches = [item for item in items if fragment in item["title"]]
    assert len(matches) == 1, f"{fragment!r} matched {len(matches)} items"
    return matches[0]


class SamplePdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SAMPLE_PDF.exists():
            raise unittest.SkipTest(f"{SAMPLE_PDF} is not present (resources/ is not in git)")
        cls.result = extractor.extract(SAMPLE_PDF)
        cls.items = cls.result["items"]

    def test_newsletter_details(self):
        newsletter = self.result["newsletter"]
        self.assertEqual(newsletter["title"], "3POINTS Hong Kong Regulatory Updates")
        self.assertEqual(newsletter["issue_date"], "2026-07")
        self.assertEqual(newsletter["file_path"], "resources/newsletters/sample_newsletter.pdf")

    def test_item_count_by_section(self):
        sections = [item["section"] for item in self.items]
        self.assertEqual(len(self.items), 19)
        self.assertEqual(sections.count("corporate"), 12)
        self.assertEqual(sections.count("enforcement"), 7)

    def test_every_item_has_a_url(self):
        self.assertEqual(self.result["items_without_source_url"], [])
        for item in self.items:
            self.assertTrue(item["source_url"].startswith("https://apps.sfc.hk/"), item["title"])

    def test_nothing_left_over(self):
        self.assertEqual(self.result["unmatched_links"], [])
        self.assertEqual(self.result["warnings"], [])

    def test_each_link_used_once(self):
        references = [item["source_ref"] for item in self.items]
        self.assertEqual(len(references), len(set(references)))

    def test_luk_fook_item(self):
        item = find(self.items, "Luk Fook")
        self.assertEqual(item["title"], "SFC Reprimands Luk Fook Securities for Cybersecurity Failures")
        self.assertEqual(item["pages"], [5])
        self.assertEqual(item["section"], "enforcement")
        self.assertEqual(item["source_ref"], "26PR118")
        # The PDF prints "$2.1 million"; the fine is HK$2.1m. Accept either spelling.
        self.assertRegex(" ".join(item["summary_bullets"]), r"(HK)?\$2\.1\s*(m\b|million)")

    def test_links_map_to_the_right_items(self):
        expected = {
            "enhances regulatory framework": "26PR115",
            "co-host industry roundtables": "26PR112",
            "sign MoU": "26PR111",
            "CSRC": "26PR109",
            "phishing-resistant": "26PR101",
            "Joint announcement": "26PR107",
            "AUM grew": "26PR103",
            "Dickson Poon": "26PR121",
            "Restricts Assets": "26PR119",
            "CISIAM": "26PR116",
            "BSSIHK": "26PR117",
            "Victory": "26PR113",
            "Wong Tim Hi": "26PR104",
        }
        for fragment, reference in expected.items():
            self.assertEqual(find(self.items, fragment)["source_ref"], reference, fragment)

    def test_bullet_counts(self):
        expected = {
            "enhances regulatory framework": 4,
            "co-host industry roundtables": 2,
            "sign MoU": 3,
            "CSRC": 2,
            "phishing-resistant": 3,
            "AUM grew": 2,
            # Enforcement items include the "What this means" bullet.
            "Dickson Poon": 3,
            "Restricts Assets": 3,
            "Luk Fook": 4,
            "CISIAM": 3,
            "BSSIHK": 4,
            "Victory": 3,
            "Wong Tim Hi": 3,
        }
        for fragment, count in expected.items():
            self.assertEqual(len(find(self.items, fragment)["summary_bullets"]), count, fragment)

    def test_table_columns_stay_separate(self):
        item = find(self.items, "Dickson Poon")
        self.assertEqual(item["title"], "SFC Market Misconduct Tribunal Finds Sir Dickson Poon Culpable of Insider Dealing")
        self.assertTrue(item["summary_bullets"][0].startswith("The SFC has found Sir Dickson Poon culpable of insider dealing"))

    def test_what_this_means_is_the_last_bullet_of_enforcement_items(self):
        for item in self.items:
            if item["section"] == "enforcement":
                self.assertTrue(item["summary_bullets"][-1].startswith("What this means: "), item["title"])

    def test_hyphenated_words_survive_wrapping(self):
        text = " ".join(find(self.items, "CSRC")["summary_bullets"])
        self.assertIn("17th high-level enforcement", text)
        self.assertIn("cross-boundary enforcement", text)

    def test_page_furniture_is_stripped(self):
        everything = json.dumps(self.items)
        for fragment in ("Page 1 of 7", "enquiry@", "852 8192", "Read more", "article source", "does not constitute"):
            self.assertNotIn(fragment, everything)

    def test_executive_summary_is_not_an_item(self):
        self.assertIn("cross-border fund offerings", self.result["executive_summary"])
        self.assertNotIn("cross-border fund offerings", json.dumps(self.items))


class PublicationDateTests(unittest.TestCase):
    def result(self, url=SFC + "26PR1", reference="26PR1"):
        return {"items": [{"id": "item-01", "source_url": url, "source_ref": reference}], "warnings": []}

    def fail(self, error):
        def fetch(reference):
            raise error
        return fetch

    def test_date_comes_from_the_source(self):
        result = self.result()
        extractor.add_publication_dates(result, lambda reference: "2026-07-28T16:18:28.305")
        self.assertEqual(result["items"][0]["publication_date"], "2026-07-28")
        self.assertEqual(result["warnings"], [])

    def test_failures_are_reported_and_no_date_is_guessed(self):
        fetches = [
            self.fail(OSError("offline")),
            self.fail(KeyError("issueDate")),
            lambda reference: "not a date",
            lambda reference: None,
        ]
        for fetch in fetches:
            result = self.result()
            extractor.add_publication_dates(result, fetch)
            self.assertNotIn("publication_date", result["items"][0])
            self.assertEqual(len(result["warnings"]), 1)

    def test_other_publishers_are_reported_without_a_request(self):
        result = self.result(url="https://example.com/a?refNo=1")
        extractor.add_publication_dates(result, self.fail(AssertionError("should not fetch")))
        self.assertNotIn("publication_date", result["items"][0])
        self.assertIn("not an SFC release", result["warnings"][0])

    def test_item_without_a_link_is_skipped(self):
        result = self.result(url=None, reference=None)
        extractor.add_publication_dates(result, self.fail(AssertionError("should not fetch")))
        self.assertEqual(result["warnings"], [])


class AssemblyTests(unittest.TestCase):
    """Layouts the sample PDF does not contain, built from positioned lines."""

    def corporate(self, *lines):
        banner = Line(1, 700, 70, BOLD, 13, "SFC Corporate Updates")
        return [banner, *lines]

    def build(self, lines, links=()):
        masthead, issue_date, summary, items, warnings = extractor.assemble(lines)
        unmatched = extractor.attach_links(list(links), lines, warnings)
        return extractor.build_output("x.pdf", masthead, issue_date, summary, items, unmatched, warnings)

    def test_item_spanning_two_pages_is_joined(self):
        lines = self.corporate(
            Line(1, 90, 61, BOLD, 12, "Headline"),
            Line(1, 70, 76, BODY, 11.5, "A bullet that wraps"),
            Line(2, 780, 76, BODY, 11.5, "onto the next page."),
            Line(2, 759, 76, BODY, 11.5, "Second bullet."),
            Line(2, 740, 61, BODY, 10.5, "article source"),
        )
        item = self.build(lines, [Link(2, 60, 735, 180, 750, SFC + "26PR1")])["items"][0]
        self.assertEqual(item["pages"], [1, 2])
        self.assertEqual(item["summary_bullets"], ["A bullet that wraps onto the next page.", "Second bullet."])
        self.assertEqual(item["source_ref"], "26PR1")

    def test_new_page_starts_a_new_bullet_after_a_full_stop(self):
        lines = self.corporate(
            Line(1, 90, 61, BOLD, 12, "Headline"),
            Line(1, 70, 76, BODY, 11.5, "First bullet."),
            Line(2, 780, 76, BODY, 11.5, "Second bullet."),
        )
        self.assertEqual(self.build(lines)["items"][0]["summary_bullets"], ["First bullet.", "Second bullet."])

    def test_item_without_a_link_is_reported_not_guessed(self):
        lines = self.corporate(
            Line(1, 600, 61, BOLD, 12, "Has a link"),
            Line(1, 580, 76, BODY, 11.5, "Text."),
            Line(1, 560, 61, BODY, 10.5, "article source"),
            Line(1, 500, 61, BOLD, 12, "No link"),
            Line(1, 480, 76, BODY, 11.5, "Text."),
        )
        result = self.build(lines, [Link(1, 60, 555, 180, 570, SFC + "26PR1")])
        self.assertEqual(result["items"][1]["source_url"], None)
        self.assertEqual([item["title"] for item in result["items_without_source_url"]], ["No link"])

    def test_link_outside_any_item_is_reported(self):
        lines = [Line(1, 500, 61, BODY, 11.5, "Loose text")]
        result = self.build(lines, [Link(1, 60, 495, 180, 510, SFC + "26PR9")])
        self.assertEqual(result["unmatched_links"], [{"page": 1, "url": SFC + "26PR9"}])

    def test_unknown_banner_becomes_other_and_mas_is_recognised(self):
        self.assertEqual(extractor.section_for("Something New"), "other")
        self.assertEqual(extractor.section_for("MAS Updates"), "mas")
        self.assertEqual(extractor.section_for("Christmas Notes"), "other")


def items_file(directory):
    path = Path(directory) / "newsletter_items.json"
    path.write_text(
        json.dumps(
            {
                "newsletter": {"title": "News", "issue_date": "2026-07", "file_path": "resources/news.pdf"},
                "items": [
                    {
                        "id": f"item-{number:02d}",
                        "section": "enforcement",
                        "title": f"Title {number}",
                        "summary_bullets": [f"Bullet {number}."],
                        "source_url": SFC + f"26PR{number}",
                        "source_ref": f"26PR{number}",
                        "publication_date": f"2026-07-0{number}",
                        "pages": [number],
                    }
                    for number in (1, 2, 3)
                ]
                + [
                    {
                        "id": "item-04",
                        "section": "other",
                        "title": "No link",
                        "summary_bullets": [],
                        "source_url": None,
                        "source_ref": None,
                        "pages": [4],
                    }
                ],
                "items_without_source_url": [{"id": "item-04", "title": "No link", "pages": [4]}],
            }
        ),
        encoding="utf-8",
    )
    return path


class SelectNewsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.items = items_file(self.root)

    def select(self, *args, stdin=None):
        return run_tool("select_news.py", self.items, "--root", self.root, *args, stdin=stdin)

    def output(self, project_id="demo"):
        return json.loads((self.root / "runs" / project_id / "selected_news.json").read_text(encoding="utf-8"))

    def test_flags_write_a_valid_file(self):
        result = self.select("--ids", "1,3", "--project-id", "demo", "--purpose", "reel", "--duration", "60s")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.output()
        self.assertEqual(validate_selected_news(document), [])
        self.assertEqual([item["id"] for item in document["items"] if item["selected"]], ["item-01", "item-03"])
        self.assertEqual(document["video"]["purpose"], "reel")
        self.assertEqual(document["video"]["subtitle_languages"], ["en", "zh-Hant", "zh-Hans"])

    def test_ranges_and_ids_are_accepted(self):
        self.assertEqual(self.select("--ids", "1-2,item-03", "--project-id", "demo").returncode, 0)
        self.assertEqual(sum(item["selected"] for item in self.output()["items"]), 3)

    def test_prompts_use_defaults(self):
        result = self.select(stdin="2\nfrom-prompts\n\n\n\n\n\n\n\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.output("from-prompts")
        self.assertEqual(document["video"]["purpose"], "training")
        self.assertEqual(document["video"]["duration_target"], "3-4 min")
        self.assertEqual(document["video"]["voiceover_language"], "en")
        self.assertEqual(document["video"]["aspect_ratio"], "16:9")
        self.assertNotIn("title", document["video"])

    def test_prompt_rejects_a_bad_slug_then_accepts_a_good_one(self):
        result = self.select(stdin="2\nweekly update\nweekly-update\n\n\n\n\n\n\n\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("weekly-update", result.stderr)
        self.assertEqual(self.output("weekly-update")["project_id"], "weekly-update")

    def test_prompt_rejects_an_unsupported_aspect_ratio_then_accepts_a_good_one(self):
        result = self.select(stdin="2\ndemo\n\n\n\n3:4\n9:16\n\n\n\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("aspect ratio must be", result.stderr)
        self.assertEqual(self.output()["video"]["aspect_ratio"], "9:16")

    def test_title_aspect_ratio_and_publication_date_reach_the_file(self):
        result = self.select("--ids", "1", "--project-id", "demo", "--title", "My video", "--aspect-ratio", "9:16")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = self.output()
        self.assertEqual(document["video"]["title"], "My video")
        self.assertEqual(document["video"]["aspect_ratio"], "9:16")
        self.assertEqual(document["items"][0]["publication_date"], "2026-07-01")

    def test_subtitles_can_be_turned_off(self):
        self.assertEqual(self.select("--ids", "1", "--project-id", "demo", "--subtitle-languages", "").returncode, 0)
        self.assertEqual(self.output()["video"]["subtitle_languages"], [])

    def test_aspect_ratios_match_the_schema(self):
        import select_news
        schema = json.loads((REPO_ROOT / "schemas" / "selected_news.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(select_news.ASPECT_RATIOS), schema["$defs"]["video"]["properties"]["aspect_ratio"]["enum"])

    def test_bad_slug_is_rejected(self):
        result = self.select("--ids", "1", "--project-id", "weekly update")
        self.assertEqual(result.returncode, 2)
        self.assertIn("weekly-update", result.stderr)

    def test_unknown_number_is_rejected(self):
        self.assertEqual(self.select("--ids", "9", "--project-id", "demo").returncode, 2)

    def test_item_without_url_cannot_be_selected(self):
        result = self.select("--ids", "4", "--project-id", "demo")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no source URL", result.stderr)

    def test_item_without_url_is_left_out_of_the_output(self):
        self.assertEqual(self.select("--ids", "1", "--project-id", "demo").returncode, 0)
        self.assertNotIn("item-04", [item["id"] for item in self.output()["items"]])

    def test_existing_project_needs_force(self):
        self.assertEqual(self.select("--ids", "1", "--project-id", "demo").returncode, 0)
        self.assertEqual(self.select("--ids", "2", "--project-id", "demo").returncode, 2)
        self.assertEqual(self.select("--ids", "2", "--project-id", "demo", "--force").returncode, 0)

    def test_running_out_of_input_is_a_clean_error(self):
        result = self.select(stdin="")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


class SchemaTests(unittest.TestCase):
    def document(self):
        return {
            "project_id": "demo",
            "newsletter": {"title": "News", "issue_date": "2026-07", "file_path": "news.pdf"},
            "items": [
                {
                    "id": "item-01",
                    "section": "enforcement",
                    "title": "Title",
                    "summary_bullets": ["Bullet."],
                    "source_url": SFC + "26PR1",
                    "selected": True,
                }
            ],
            "video": {"duration_target": "60s"},
        }

    def assert_invalid(self, document, fragment):
        problems = validate_selected_news(document)
        self.assertTrue(any(fragment in problem for problem in problems), problems)

    def test_minimal_document_is_valid(self):
        self.assertEqual(validate_selected_news(self.document()), [])

    def test_new_fields_are_checked(self):
        document = self.document()
        document["items"][0]["publication_date"] = "2026-07-28"
        document["video"].update(title="My video", aspect_ratio="9:16", purpose="reel")
        self.assertEqual(validate_selected_news(document), [])

        document["items"][0]["publication_date"] = "28 July 2026"
        self.assert_invalid(document, "publication_date")
        document = self.document()
        document["video"]["aspect_ratio"] = "3:4"
        self.assert_invalid(document, "aspect_ratio")
        document = self.document()
        document["video"]["title"] = ""
        self.assert_invalid(document, "title")

    def test_source_url_is_required_and_must_be_a_url(self):
        document = self.document()
        del document["items"][0]["source_url"]
        self.assert_invalid(document, "source_url")
        document = self.document()
        document["items"][0]["source_url"] = "not a url"
        self.assert_invalid(document, "source_url")

    def test_project_id_must_be_a_slug(self):
        for bad in ("weekly update", "Weekly", "../escape", "a/b", ""):
            document = self.document()
            document["project_id"] = bad
            self.assert_invalid(document, "project_id")

    def test_item_id_cannot_escape_its_folder(self):
        document = self.document()
        document["items"][0]["id"] = "../../secret"
        self.assert_invalid(document, "items/0/id")

    def test_duplicate_item_ids_are_rejected(self):
        document = self.document()
        document["items"].append(dict(document["items"][0]))
        self.assert_invalid(document, "duplicate id")

    def test_at_least_one_item_must_be_selected(self):
        document = self.document()
        document["items"][0]["selected"] = False
        self.assertNotEqual(validate_selected_news(document), [])

    def test_unknown_fields_and_sections_are_rejected(self):
        document = self.document()
        document["surprise"] = 1
        self.assert_invalid(document, "surprise")
        document = self.document()
        document["items"][0]["section"] = "gossip"
        self.assert_invalid(document, "section")


class BriefTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        result = run_tool(
            "select_news.py", items_file(self.root), "--root", self.root,
            "--ids", "1,3", "--project-id", "demo", "--audience", "compliance staff",
            "--duration", "30-50 seconds", "--remarks", "Keep it brisk.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.selected = self.root / "runs" / "demo" / "selected_news.json"

    def brief(self, *args):
        return run_tool("newsletter_to_brief.py", self.selected, "--root", self.root, *args)

    def brief_text(self):
        return (self.root / "runs" / "demo" / "brief.md").read_text(encoding="utf-8")

    def field(self, name):
        match = re.search(rf"^- {name}: (.*)$", self.brief_text(), re.MULTILINE)
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_brief_has_the_same_fields_as_the_example(self):
        self.assertEqual(self.brief().returncode, 0)
        example = (REPO_ROOT / "runs" / "example" / "brief.md").read_text(encoding="utf-8")
        fields = lambda text: re.findall(r"^- ([^:\n]+):", text, re.MULTILINE)
        self.assertEqual(fields(self.brief_text()), fields(example))

    def test_field_values(self):
        self.assertEqual(self.brief("--title", "My video").returncode, 0)
        self.assertEqual(self.field("Project ID"), "demo")
        self.assertEqual(self.field("Title"), "My video")
        self.assertEqual(self.field("Duration"), "30-50 seconds")
        self.assertEqual(self.field("Voiceover language"), "English")
        self.assertEqual(self.field("Subtitles language"), "English, Traditional Chinese, Simplified Chinese")
        self.assertEqual(self.field("Newspaper path"), "resources/demo/item-01.md, resources/demo/item-03.md")

    def test_remarks_carry_the_required_rules(self):
        self.assertEqual(self.brief().returncode, 0)
        remarks = self.field("Remarks")
        for phrase in ("AI summary", "cite it for every factual claim", "no AI-generated images or video",
                       "Flag any conflict", SFC + "26PR1", SFC + "26PR3", "compliance staff", "Keep it brisk."):
            self.assertIn(phrase, remarks)
        self.assertNotIn(SFC + "26PR2", remarks)

    def test_remarks_explain_how_to_read_sfc_pages_only_when_needed(self):
        self.assertEqual(self.brief().returncode, 0)
        self.assertIn("api/news/content", self.field("Remarks"))

        document = json.loads(self.selected.read_text(encoding="utf-8"))
        for item in document["items"]:
            item["source_url"] = "https://example.com/article"
        self.selected.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(self.brief("--force").returncode, 0)
        self.assertNotIn("api/news/content", self.field("Remarks"))

    def rewrite_video(self, **changes):
        document = json.loads(self.selected.read_text(encoding="utf-8"))
        document["video"].update(changes)
        self.selected.write_text(json.dumps(document), encoding="utf-8")

    def test_title_comes_from_the_file_unless_the_flag_overrides_it(self):
        self.rewrite_video(title="From the file")
        self.assertEqual(self.brief().returncode, 0)
        self.assertEqual(self.field("Title"), "From the file")
        self.assertEqual(self.brief("--force", "--title", "From the flag").returncode, 0)
        self.assertEqual(self.field("Title"), "From the flag")

    def test_remarks_state_the_aspect_ratio(self):
        self.rewrite_video(aspect_ratio="9:16")
        self.assertEqual(self.brief().returncode, 0)
        self.assertIn("Aspect ratio: 9:16.", self.field("Remarks"))

    def test_optional_settings_take_their_defaults(self):
        document = json.loads(self.selected.read_text(encoding="utf-8"))
        document["video"] = {"duration_target": "60s"}
        self.selected.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(self.brief().returncode, 0)
        remarks = self.field("Remarks")
        for phrase in ("Purpose: training.", "Aspect ratio: 16:9.", "Audience: compliance staff at licensed corporations."):
            self.assertIn(phrase, remarks)

    def test_first_subtitle_language_is_burned_in(self):
        self.assertEqual(self.brief().returncode, 0)
        self.assertIn(
            "burn English into the picture and embed Traditional Chinese, Simplified Chinese as selectable tracks",
            self.field("Remarks"),
        )
        self.rewrite_video(subtitle_languages=["zh-Hant"])
        self.assertEqual(self.brief("--force").returncode, 0)
        self.assertIn("burn Traditional Chinese into the picture.", self.field("Remarks"))

    def test_no_subtitles(self):
        self.rewrite_video(subtitle_languages=[])
        self.assertEqual(self.brief().returncode, 0)
        self.assertEqual(self.field("Subtitles language"), "None")
        self.assertIn("No subtitles.", self.field("Remarks"))

    def test_remarks_ask_for_one_final_approval(self):
        self.assertEqual(self.brief().returncode, 0)
        remarks = self.field("Remarks")
        for phrase in ("category approval_policy", "Final approval is not pre-authorized", "awaiting_human",
                       "If I request changes, apply only those, re-render and stop again."):
            self.assertIn(phrase, remarks)

    def test_remarks_rule_out_unsupported_relative_dates(self):
        self.assertEqual(self.brief().returncode, 0)
        self.assertIn("relative wording", self.field("Remarks"))

    def test_item_file_uses_the_publication_date_when_known(self):
        self.assertEqual(self.brief().returncode, 0)
        folder = self.root / "resources" / "demo"
        self.assertIn("- Date: 2026-07-03 (publication date", (folder / "item-03.md").read_text(encoding="utf-8"))

        document = json.loads(self.selected.read_text(encoding="utf-8"))
        for item in document["items"]:
            del item["publication_date"]
        self.selected.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(self.brief("--force").returncode, 0)
        self.assertIn("- Date: 2026-07 (newsletter issue", (folder / "item-03.md").read_text(encoding="utf-8"))

    def test_a_resource_file_for_each_selected_item_only(self):
        self.assertEqual(self.brief().returncode, 0)
        folder = self.root / "resources" / "demo"
        self.assertEqual(sorted(path.name for path in folder.iterdir()), ["item-01.md", "item-03.md"])
        text = (folder / "item-03.md").read_text(encoding="utf-8")
        for phrase in ("# Title 3", "2026-07", SFC + "26PR3", "- Bullet 3."):
            self.assertIn(phrase, text)

    def test_existing_brief_needs_force(self):
        self.assertEqual(self.brief().returncode, 0)
        path = self.root / "runs" / "demo" / "brief.md"
        path.write_text("hand edited", encoding="utf-8")
        self.assertEqual(self.brief().returncode, 2)
        self.assertEqual(path.read_text(encoding="utf-8"), "hand edited")
        self.assertEqual(self.brief("--force").returncode, 0)

    def test_invalid_file_writes_nothing(self):
        document = json.loads(self.selected.read_text(encoding="utf-8"))
        document["project_id"] = "../escape"
        self.selected.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(self.brief().returncode, 2)
        self.assertFalse((self.root / "runs" / "demo" / "brief.md").exists())
        self.assertFalse((self.root / "resources" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
