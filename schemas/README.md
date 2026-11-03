# selected_news.json

`selected_news.schema.json` (JSON Schema draft 2020-12) defines the file that hands selected newsletter items to the video pipeline. It is the contract with Team A's newsletter system: anything that produces a valid file can feed `tools/newsletter_to_brief.py`.

Unknown fields are rejected, so a typo fails validation instead of being ignored.

## Top level

| Field | Required | Meaning |
| --- | --- | --- |
| `project_id` | Yes | Lowercase hyphenated slug, such as `weekly-update`. Unique per video. Becomes the folder name under `runs/` and `resources/`. |
| `newsletter` | Yes | The issue the items came from. |
| `items` | Yes | All candidate items. At least one must have `selected: true`. |
| `video` | Yes | Production settings. |

## `newsletter`

| Field | Required | Meaning |
| --- | --- | --- |
| `title` | Yes | Newsletter title. |
| `issue_date` | Yes | `YYYY-MM`, or `YYYY-MM-DD` if the issue has an exact date. |
| `file_path` | Yes | Path to the PDF, relative to the repository root. |

## `items[]`

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | Yes | Unique within the file. Letters, digits, `-` and `_` only, because it becomes a file name. |
| `section` | Yes | `corporate`, `enforcement`, `mas` or `other`. |
| `title` | Yes | Item headline. |
| `summary_bullets` | Yes | The newsletter's text for the item. Enforcement items end with a bullet starting `What this means:`. This text is an AI summary, not a primary source. |
| `source_url` | Yes | Link to the original article. Must start with `http://` or `https://`. |
| `source_ref` | No | Publisher's reference, such as `26PR115`. |
| `publication_date` | No | `YYYY-MM-DD` date the source was published, not the newsletter's issue date. `extract_newsletter.py --fetch-dates` fills it for SFC releases. |
| `pages` | No | Newsletter pages the item appears on, starting at 1. |
| `selected` | Yes | `true` if the item goes into the video. |

## `video`

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `duration_target` | Yes | | Free text, such as `3-4 min` or `60s`. |
| `title` | No | Newsletter title and issue | Video title. |
| `purpose` | No | `training` | `training` or `reel`. |
| `aspect_ratio` | No | `16:9` | `16:9`, `1:1` or `9:16`. |
| `voiceover_language` | No | `en` | BCP 47 language tag. |
| `subtitle_languages` | No | `["en", "zh-Hant", "zh-Hans"]` | BCP 47 language tags, without repeats. The first is burned into the picture and the rest are selectable tracks. Every language is also saved as an `.srt` file, because browsers often don't show embedded tracks. Empty means no subtitles. |
| `audience` | No | `compliance staff at licensed corporations` | Who the video is for. Empty leaves it out of the brief. |
| `remarks` | No | | Extra instructions, copied into the brief's Remarks. |

## Checks the schema cannot express

JSON Schema cannot compare values across items or look at the file system, so the tools check these separately:

- Item `id` values must be unique within the file (`tools/select_news.py` and `tools/newsletter_to_brief.py`).
- `project_id` must not already be in use: both tools refuse to overwrite an existing run unless you pass `--force`.

## Example

```json
{
  "project_id": "weekly-update",
  "newsletter": {
    "title": "3POINTS Hong Kong Regulatory Updates",
    "issue_date": "2026-07",
    "file_path": "resources/newsletters/sample_newsletter.pdf"
  },
  "items": [
    {
      "id": "item-15",
      "section": "enforcement",
      "title": "SFC Reprimands Luk Fook Securities for Cybersecurity Failures",
      "summary_bullets": ["The SFC reprimanded Luk Fook Securities (HK) Limited ..."],
      "source_url": "https://apps.sfc.hk/edistributionWeb/gateway/EN/news-and-announcements/news/enforcement-news/doc?refNo=26PR118",
      "source_ref": "26PR118",
      "publication_date": "2026-07-28",
      "pages": [5],
      "selected": true
    }
  ],
  "video": {
    "title": "Weekly update: phishing-resistant login and the Luk Fook cybersecurity fine",
    "purpose": "training",
    "duration_target": "30-50 seconds",
    "aspect_ratio": "16:9",
    "voiceover_language": "en",
    "subtitle_languages": ["en", "zh-Hant", "zh-Hans"],
    "audience": "compliance staff at licensed corporations",
    "remarks": ""
  }
}
```
