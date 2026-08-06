---
name: create-event-kit
description: "Event-kit creation for a multi-company event: a short brief, official logos, social positioning, a one-page HTML/PDF proposal, and an unpublished mockup in Luma's native create editor. Use when packaging or proposing an event for partners, Luma, and social promotion."
---

# Create Event Kit

Turn an event concept into one reviewable folder with exactly three artifacts. When requested, also populate Luma's native create editor as an unpublished, transient mockup.

## 1. Frame the event

Extract the premise, participating companies, audience, tone, and any supplied title, format, logistics, or call to action from the prompt and source material. The explicit participating-company list controls the logo set. Use supplied facts only and omit unspecified logistics, speakers, quotes, and commitments from audience-facing copy. Ask one concise question only when the premise or company list remains materially ambiguous after inspection.

This step is complete when every participating company is named and the premise, audience, and supplied facts are unambiguous enough to write without invention.

## 2. Build the three source artifacts

Use the requested output path. Otherwise create a non-colliding event-slug folder in the current working directory. Its complete structure is:

```text
<event-slug>/
├── event-brief.md
├── luma-event-poster/
│   └── <company-slug>-logo.<ext>
└── socials-description.md
```

### `event-brief.md`

Begin with one H1 event title, drafting a strong title when none is supplied. Follow with two or three prose paragraphs totaling 80–240 words:

1. Establish the timely change or tension.
2. State the event's thesis and the questions participants will examine.
3. Optionally add a distinct audience experience or takeaway.

Use precise, conversational language. Make every relationship claim no stronger than the user's wording.

### `luma-event-poster/`

Add one current primary logo per participating company. Source each from the company's official brand, press, media, or design-system page; a company-controlled CDN or official repository linked there also qualifies. Prefer a full SVG wordmark, then a transparent PNG, and accept an official JPEG or WebP only when that is the downloadable asset. User-supplied official assets qualify.

Name each file `<company-slug>-logo.<ext>` with lowercase ASCII letters, digits, and hyphens. Keep this folder asset-only: image files in `.svg`, `.png`, `.jpg`, `.jpeg`, or `.webp` formats. Use the official asset or report it missing; search thumbnails, favicons, logo aggregators, screenshots, recreated wordmarks, and generated logos are not substitutes.

Review the official usage terms and report any permission, attribution, background, or clear-space requirements in chat. Have the user confirm any required permission before public use.

### `socials-description.md`

Use this exact structure:

```markdown
# Socials / Description

## Main theme

<One memorable sentence, at most 30 words.>

## Main idea

<One plain-language paragraph, 50–100 words.>

## Social description

<One paste-ready paragraph, 70–140 words.>
```

Distinguish the broad theme from the event's specific point of view. In the social description, name the participating companies, explain why the discussion matters, and give the audience a concrete reason to attend. Add registration language only when a call to action or link is supplied; add hashtags or emoji only when requested or supported by the specified tone.

This step is complete when the three artifacts contain no drafts, manifests, source notes, hidden metadata, or internal placeholders.

## 3. Create a one-page proposal when requested

Keep the three-artifact event kit unchanged. Render a sibling proposal folder from the source kit:

```bash
python3 scripts/render_event_proposal.py <event-folder> <event-slug>-proposal \
  --company "<company one>" --company "<company two>" \
  --discussion "<question one>" --discussion "<question two>" \
  --discussion "<question three>" \
  --audience "<source-grounded audience>" \
  --outcome "<source-grounded desired outcome>" \
  --partner-guide-url "<supplied partner-guide URL>" \
  --pdf
```

Use only source-grounded content. Keep unresolved logistics in the default next-step statement. Verify that `event-proposal.pdf` is exactly one Letter page, render it to an image, and inspect the complete page for clipping, overlap, or unreadable text.

## 4. Populate an unpublished Luma mockup

Do this step only when the user asks for a Luma mockup or asks to populate Luma. Use the current in-app browser and open Luma's native create editor at `https://luma.com/create`. If Luma requires authentication, ask the user to sign in within that browser, then resume from the same create page.

Before entering other event content, set the event visibility to **Private** as a fail-safe. Then populate only supplied or source-grounded values:

- Set the Luma title to `<company names joined by ×>: <H1>`. If the H1 already names every company, use it unchanged.
- Use the brief's prose as the event description.
- Enter date, time, timezone, location, hosts, ticketing, capacity, and registration settings only when supplied.
- Upload a supplied final cover image when available. Do not treat the logo-only `luma-event-poster/` folder as a finished cover or invent a composite poster.
- Choose a native Luma theme or tint only when it follows supplied creative direction. Otherwise retain the editor default.

Leave unsupplied fields untouched. If Luma pre-fills required date or time values, identify them as editor defaults in the handoff rather than treating them as event facts. Use Luma's live preview as the authoritative representation of the public event page; do not create a substitute HTML imitation.

### Mockup safety boundary

Treat mockup mode as non-publishing work. Never click, press, or submit **Create Event**. Never call `POST /v1/events/create`, use a Luma API key, or call any mutating Luma endpoint in mockup mode. Luma's create API makes a real event and does not provide a draft state; private visibility is only a fail-safe and does not make API creation acceptable.

Leave the populated create editor open for review. Capture desktop and mobile screenshots when the browser supports non-mutating viewport inspection. Confirm all of the following before calling the mockup complete:

- The browser remains on Luma's create flow rather than an event URL.
- No event ID, event URL, or confirmation of creation exists.
- No create, update, publish, or ticket mutation was sent.
- The title and description match the event-kit sources.
- Every retained Luma default and missing input is named in the handoff.

Publishing is a separate task. Require an explicit user request to create the real event before crossing this boundary.

## 5. Audit and deliver

Verify that each logo is non-empty, matches its file extension, and traces to an official source. From this Skill directory, run:

```bash
python3 scripts/validate_event_kit.py <event-folder>
```

Fix every reported error. Then reread both Markdown files for a consistent premise, company list, audience, and logistics; remove unsupported claims and inflated language. Preserve open questions as questions. If a Luma mockup was requested, inspect the live editor preview without submitting it and apply the safety checks above.

Return the event-folder path, a one-sentence creative-direction summary, and each official logo source URL in chat so provenance stays outside the three-artifact package. If requested, also return the proposal HTML and PDF paths. Report whether the Luma editor was populated, which fields remain unresolved, and that no event was created.

This step is complete only when the validator passes, every claim is source-grounded, and every participating company has an official logo or an explicitly reported missing asset with usage requirements surfaced. If a Luma mockup was requested, it must also remain unpublished in the native create editor with no event ID or URL.
