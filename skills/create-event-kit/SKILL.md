---
name: create-event-kit
description: "Event-kit creation for a multi-company event: a short brief, official logos, social positioning, and a responsive Luma-style HTML planning preview. Use when packaging an event for Luma and social promotion."
---

# Create Event Kit

Turn an event concept into one reviewable folder with three source artifacts and one generated Luma-style planning preview.

## 1. Frame the event

Extract the premise, participating companies, audience, tone, and any supplied title, format, logistics, or call to action from the prompt and source material. The explicit participating-company list controls the logo set. Use supplied facts only and omit unspecified logistics, speakers, quotes, and commitments from audience-facing copy. Ask one concise question only when the premise or company list remains materially ambiguous after inspection.

This step is complete when every participating company is named and the premise, audience, and supplied facts are unambiguous enough to write without invention.

## 2. Build the three source artifacts

Use the requested output path. Otherwise create a non-colliding event-slug folder in the current working directory. Its complete structure after rendering is:

```text
<event-slug>/
├── event-brief.md
├── luma-event-poster/
│   └── <company-slug>-logo.<ext>
├── socials-description.md
└── luma-preview.html
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

This step is complete when the three source artifacts are ready to render and contain no drafts, manifests, source notes, hidden metadata, or internal placeholders.

## 3. Render the Luma planning preview

Create `luma-preview.html` from the three source artifacts by running this command from the Skill directory:

```bash
python3 scripts/render_luma_preview.py <event-folder> \
  --date "<supplied date or Date to be announced>" \
  --time "<supplied time or Time to be announced>" \
  --location "<supplied location or Location to be announced>"
```

Pass `--presented-by`, one or more `--host`, `--registration-note`, `--cta`, `--theme-label`, or `--cover-image` only when the prompt or trusted source material supplies those details. Run `python3 scripts/render_luma_preview.py --help` for the full interface.

The renderer produces one self-contained responsive HTML file. It follows the current Luma event-page hierarchy: a square rounded cover and presenter context on the left; event title, date, location, registration card, and About Event copy on the right; and a single-column mobile layout. It embeds logo assets as data URLs and generates a CSS cover when no official cover is supplied. Do not remove the planning-preview badge or disclaimer, and do not represent the file as a published Luma page.

Never invent logistics. Use the renderer's explicit `to be announced` defaults for missing date, time, or location. Do not add working registration behavior: the button is a disabled visual preview until a real event is configured in Luma.

When a local browser preview is available, inspect `luma-preview.html` at approximately 1280×800 and 390×844. Confirm that the cover is square, content does not clip or overflow, the mobile layout is one column, every logo is visible, and the title, About Event copy, and known logistics match the Markdown sources.

This step is complete when `luma-preview.html` is self-contained, responsive, visually coherent at desktop and mobile sizes, and clearly labeled as a planning preview.

## 4. Audit and deliver

Verify that each logo is non-empty, matches its file extension, and traces to an official source. From this Skill directory, run:

```bash
python3 scripts/validate_event_kit.py <event-folder>
```

Fix every reported error. Then reread both Markdown files and the rendered preview for a consistent premise, company list, audience, and logistics; remove unsupported claims and inflated language. Preserve open questions as questions.

Return the event-folder path, a one-sentence creative-direction summary, and each official logo source URL in chat so provenance stays outside the four-artifact package.

This step is complete only when the validator passes, every claim is source-grounded, the desktop and mobile preview states have been checked when browser tooling is available, and every participating company has an official logo or an explicitly reported missing asset with usage requirements surfaced.
