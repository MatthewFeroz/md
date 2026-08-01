# YouTube Metadata

Use this reference for the metadata and complete-package branches.

## Deliverable

- Description-only request: `<source-name>-youtube-description.md`
- Any other metadata request or complete package: `<source-name>-youtube-metadata.md`
- A user-provided filename takes precedence.

Include only requested sections. A complete package includes all sections below.

## Titles

For a complete package, write three truthful options with different click intents:

- A: the most concrete outcome or useful result.
- B: the product, tool, or method for practitioners.
- C: a specific question or tension.

Avoid hype and claims the source does not support.

## Description

Open with two or three sentences stating what the viewer will see or learn, what is demonstrated or discussed, and the key takeaway. Use a knowledgeable peer's voice rather than a press release.

Add chapters only when accurate timestamps are available:

```text
Chapters:
0:00 Opening topic
1:16 First major transition
2:01 Next useful section
```

- Start at `0:00`.
- Use real topic transitions in ascending order.
- Keep titles short and specific.
- Aim for 8-14 chapters for a typical 10-30 minute video; follow the content rather than a quota.

Add two to four resources only when the user supplied the URLs or they can be verified:

```text
Resources:
→ Label: https://example.com
```

Omit empty sections instead of inserting placeholders.

## Tags

Write comma-separated tags with no hashtags or quotation marks. Cover title phrases, named products or companies, techniques, and broader category terms found in the source. Keep the entire tag string at 500 characters or fewer.

## Cards

Suggest no more than five cards. Give each card an exact timestamp, a short verified quote or faithful paraphrase, a specific related-video topic or verified URL, and the reason that moment creates follow-up interest. Never invent a quote, timestamp, or URL.

## Formats

Description-only:

```markdown
# YouTube Description

[Paste-ready summary]

Chapters:
0:00 [Chapter title]

Resources:
→ [Label]: [URL]
```

Complete package:

```markdown
# YouTube Upload Package
## [Video title or topic]

## TITLE OPTIONS

A - [Title A]

B - [Title B]

C - [Title C]

## YOUTUBE DESCRIPTION

[Paste-ready description]

Chapters:
0:00 [Chapter title]

Resources:
→ [Label]: [URL]

## TAGS

[Comma-separated tags]

## CARD RECOMMENDATIONS

1. @ [timecode] "[Short quote or paraphrase]"
[Suggestion and reasoning]
```

## Audit

- Trace every factual claim, proper noun, quote, and timestamp to the source or user clarification.
- Confirm chapters begin at `0:00`, increase monotonically, and match real transitions.
- Confirm the tag string is comma-separated and no longer than 500 characters.
- Confirm every resource and card URL is verified.
- Confirm the file contains no placeholders, editing notes, or unrequested sections.
