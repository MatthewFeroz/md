---
name: track-career-impact
description: "Evidence-backed career progress tracking and promotion writing. Use when recording completed work, documenting a win, preparing a manager update, maintaining a brag document, or drafting a self-review or promotion case."
---

# Track Career Impact

Turn work into an accurate, durable record of ownership and company value. Preserve evidence and status so later promotion writing does not depend on memory.

## 1. Resolve the output branch

Choose the smallest branch that satisfies the request:

- **Record**: create or update one impact entry and its index row.
- **Share**: draft a concise manager-ready update from one or more entries.
- **Roll up**: synthesize entries for a week, month, quarter, self-review, or promotion case.

For a record request, use `career/impact/entries/YYYY-MM-DD-<slug>.md` and update `career/impact/index.md` in the user's `MatthewFeroz/md` checkout. Honor another destination when supplied. For share-only or rollup-only requests, write in chat unless the user asks for a file.

This step is complete when the branch, time period, source work, and output destination are explicit.

## 2. Build the evidence set

Inspect the available primary evidence before writing: commits, diffs, issues, pull requests, reviews, test output, release notes, screenshots, project documents, and user-provided context. Record links or stable identifiers.

Separate each claim into one of these states:

- **Delivered**: merged, released, deployed, adopted, or otherwise confirmed in use.
- **In review**: submitted but not merged or released.
- **Validated**: demonstrated by tests or an integration run but not yet delivered.
- **Expected**: a plausible impact mechanism that has not yet been measured.

Ask one concise question only when missing ownership, collaboration, outcome, or confidential-context details would materially change the record. Leave unknown metrics as follow-up evidence instead of estimating them.

This step is complete when every material claim has a source and an accurate state.

## 3. Write an impact entry

Use first person and this structure:

```markdown
# <Initiative>

- **Date:** YYYY-MM-DD
- **Status:** <Delivered | In review | Validated | Expected>
- **Scope:** <teams, products, repositories, or customers affected>

## Executive summary

<Two or three sentences covering the problem, ownership, and value.>

## Problem

<What was broken, risky, slow, or missing, and why it mattered.>

## My contribution

- <Specific action and decision owned>

## Evidence and outcomes

| Evidence | What it demonstrates |
| --- | --- |
| <link, test result, review, or artifact> | <grounded conclusion> |

## Company value

- **Customer:** <realized or expected effect>
- **Product:** <realized or expected effect>
- **Engineering:** <realized or expected effect>
- **Company:** <realized or expected effect>

## Promotion signals

- **Ownership:** <scope carried from problem to outcome>
- **Judgment:** <tradeoff or risk handled>
- **Execution:** <quality and completeness evidence>
- **Influence:** <coordination, enablement, or external contribution>

## Shareable update

<One short paragraph suitable for a manager or team update.>

## Follow-up evidence

- [ ] <metric, adoption signal, merge, release, or feedback to collect>
```

Use only relevant company-value and promotion-signal dimensions; omit empty ones. Distinguish personal ownership from team contributions and name collaborators when the evidence supports it. State the mechanism of value instead of relying on adjectives such as “major” or “transformative.”

This step is complete when the entry is source-grounded, first-person, and useful without additional conversation context.

## 4. Maintain visibility

Keep `career/impact/index.md` scannable. Add or update one row with the date, initiative, status, one-line value, and relative link. Preserve existing entries and ordering conventions.

For a share request, lead with the outcome, explain why it matters to the company, state the current delivery status, and include one evidence link when appropriate. Keep routine updates to 80–150 words.

For a rollup request, read every entry in the requested period. Group repeated work into initiatives, distinguish delivered outcomes from pipeline work, and organize the summary around the user's promotion rubric when supplied. Otherwise use ownership, judgment, execution, influence, and company impact as descriptive headings rather than claiming they are an official rubric.

This step is complete when the durable record and the requested audience-facing view agree on facts and status.

## 5. Audit

Verify all of the following:

- Every number, outcome, and status is traceable to evidence.
- Open work is described as in review or expected, not shipped.
- Expected impact is labeled and tied to a concrete mechanism.
- Ownership language is accurate about individual and collaborative work.
- Links resolve to the relevant evidence and expose no secret values.
- The summary is concise enough to paste into a manager update or review.

Remove unsupported claims and retain follow-up checkboxes for evidence that should be collected later.

This step is complete only when every check passes.
