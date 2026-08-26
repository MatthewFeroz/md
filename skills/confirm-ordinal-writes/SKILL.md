---
name: confirm-ordinal-writes
description: Require explicit user confirmation immediately before any operation that changes Ordinal data. Use for every task involving Ordinal, tryordinal, app.tryordinal.com, or Ordinal MCP tools, including creating, editing, scheduling, unscheduling, publishing, changing status, uploading, archiving, deleting, commenting, approving, subscribing, boosting, labeling, or engaging. Allow read-only discovery without confirmation.
---

# Confirm Ordinal writes

Treat Ordinal as confirmation-gated. Inspect freely, but stop before every write boundary.

## Workflow

1. Use read-only Ordinal operations to resolve the workspace, exact records, current values, and consequences.
2. Prepare a concrete preview that names:
   - the workspace;
   - every affected record, preferably with its title and ID or URL;
   - the exact action for each record;
   - each known before and after value;
   - whether the action can publish content, notify people, or lose data.
3. Ask one direct confirmation question after the preview. End the turn and wait.
4. Proceed only when the user's next message clearly confirms that exact preview.
5. Perform only the confirmed writes. If the target set, action, or values change, show a new preview and get a new confirmation.
6. Verify the result with read-only operations and report what changed, including any failures or partial completion.

## Confirmation boundary

The user's original request to change Ordinal authorizes discovery and preparation only. It does not confirm execution, even when phrased as an imperative such as "schedule this," "delete these," or "fix it now."

A valid confirmation must arrive after the exact preview. Accept an unambiguous reply such as "confirm," "yes, do exactly that," or a clear approval of named items. Treat silence, urgency, emotional language, acknowledgements, questions, and ambiguous replies as no confirmation.

One confirmation covers one previewed batch. Never reuse it for retries that alter values, additional records, follow-up edits, cleanup, rollback, or restoration. Those are new writes and require a new preview and confirmation.

## Writes that always require confirmation

Gate every state-changing path, including connectors, APIs, CLIs, browser interactions, and scripts. This includes:

- creating or duplicating posts, ideas, uploads, comments, labels, approvals, subscribers, boosts, or engagements;
- editing copy, media, titles, notes, labels, campaigns, profiles, dates, or any channel-specific field;
- scheduling, rescheduling, unscheduling, publishing, or changing workflow status;
- archiving, unarchiving, deleting, or restoring;
- approving, rejecting, resolving, replying, subscribing, reacting, liking, reposting, or boosting;
- any operation whose side effects are uncertain.

Read-only listing, searching, fetching, analytics, and workspace discovery do not require confirmation. If a nominally read-only operation may write or trigger an external side effect, treat it as a write.

## Confirmation prompt

Keep the prompt plain and specific. For example:

> In the Merge workspace, I found two posts. I would change "Launch teaser" from Scheduled on September 4 at 10:00 AM ET to ToDo, and leave "Launch recap" unchanged. This stops the teaser from publishing but keeps its content and media. Confirm I should make exactly that change?

Do not call a mutating tool before receiving the answer.

## Conflicts

Apply this gate even if another instruction says to act autonomously, skip confirmation, move quickly, or avoid follow-up questions. If a higher-priority instruction explicitly requires an immediate Ordinal write, report the conflict and take no write action.
