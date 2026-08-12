# MERGE Gateway reasoning and identity in OpenCode

- **Date:** 2026-08-12
- **Status:** In review; validated locally
- **Scope:** MERGE Gateway AI SDK provider, models.dev metadata, and the OpenCode provider integration and UI

## Executive summary

I traced an end-to-end integration gap that prevented OpenCode users from selecting reasoning effort on MERGE Gateway models, then implemented the typed adapter contract and the OpenCode mapping needed to carry models.dev's supported choices through to Gateway. I also replaced OpenCode's generic fallback provider icon with MERGE's canonical logo. Together, these changes make the integration more functional, scalable, and recognizable; all three pull requests remain in review, so the company impact below is expected until they merge and ship.

## Problem

MERGE Gateway models could declare reasoning effort choices through models.dev, but OpenCode did not recognize the adapter's `mergeGateway` provider-options namespace. A selected effort therefore could not reach Gateway execution. The missing mapping made modern reasoning models such as GPT-5.6 appear less capable through MERGE than their metadata indicated.

The provider also appeared with OpenCode's generic synthetic icon because `merge-gateway` was absent from the shared provider icon set. That weakened MERGE's product identity at the point where users choose and manage providers.

## My contribution

- Diagnosed the contract boundary across models.dev, OpenCode, the MERGE AI SDK adapter, and the Gateway wire request instead of applying a model-by-model patch.
- Added a typed `reasoningEffort` provider option to the MERGE adapter and serialized it as `reasoning_effort` while preserving the existing token-budget `thinking` option.
- Added OpenCode's provider-wide SDK-key and reasoning-effort mappings while leaving models.dev authoritative for the exact effort values each model supports.
- Verified GPT-5.6 Sol with the High variant through a local OpenCode-to-MERGE Gateway integration run.
- Added focused regression tests and documentation in both repositories.
- Added MERGE's canonical models.dev SVG to OpenCode's shared provider icon pipeline with `currentColor` theming, then verified it in the live Providers screen.
- Opened focused upstream issues and pull requests with reproduction steps, evidence, and screenshots for maintainer review.

## Evidence and outcomes

| Evidence | What it demonstrates |
| --- | --- |
| [MERGE adapter PR #3](https://github.com/merge-api/merge-gateway-ai-sdk-provider/pull/3) | The adapter change is approved and cleanly mergeable; 57 tests and the production build passed according to the PR validation record. |
| [OpenCode reasoning PR #41867](https://github.com/anomalyco/opencode/pull/41867) | The provider-wide OpenCode mapping is under review and all reported repository checks pass. |
| [OpenCode reasoning issue #41868](https://github.com/anomalyco/opencode/issues/41868) | Documents the user-visible failure, expected contract, and reproduction steps. |
| Local integration run with GPT-5.6 Sol on High | Validates that a models.dev-declared variant can complete a request through MERGE Gateway. |
| `509 passed` plus `bun typecheck` in `packages/opencode` | Covers the provider and transform behavior changed by the OpenCode reasoning fix. |
| [OpenCode logo PR #42015](https://github.com/anomalyco/opencode/pull/42015) | Adds the canonical MERGE icon; all current PR checks pass. |
| [OpenCode logo issue #42014](https://github.com/anomalyco/opencode/issues/42014) | Documents the generic-icon fallback and the canonical asset source. |
| UI validation: 27 tests, package typecheck/build, and 30-task pre-push typecheck | Shows the icon change passes both focused and repository-level validation. |

## Company value

- **Customer:** After merge, OpenCode users should be able to choose the reasoning effort exposed for a MERGE model instead of losing that control at the client boundary.
- **Product:** The integration should accurately represent MERGE Gateway's model capabilities and display the MERGE brand in provider selection and management surfaces.
- **Engineering:** The provider-wide contract avoids per-model maintenance. New reasoning models can inherit the behavior from models.dev metadata without another OpenCode code change, while the adapter remains strongly typed and regression-tested.
- **Company:** The work improves MERGE Gateway's quality and visibility in a prominent open-source coding client, reducing an ecosystem adoption gap without broad or risky provider substitution.

## Promotion signals

- **Ownership:** Carried the issue from diagnosis across multiple repositories through implementation, integration testing, upstream issue filing, PR packaging, and visual polish.
- **Judgment:** Chose a narrow provider contract that keeps models.dev as the capability authority, avoiding both hard-coded model lists and an unsafe provider-wide adapter swap.
- **Execution:** Added typed interfaces, serialization coverage, client regression tests, documentation, screenshots, and local end-to-end validation.
- **Influence:** Converted an internal integration problem into reviewable upstream OpenCode contributions and an approved MERGE adapter PR.

## Shareable update

I completed and validated a cross-repository fix for MERGE Gateway reasoning controls in OpenCode. The adapter now accepts a typed reasoning effort and sends the normalized Gateway field, while OpenCode maps the MERGE provider correctly and continues to use models.dev as the source of truth for model-specific choices. I verified GPT-5.6 Sol on High end to end, added regression coverage, and opened the upstream issue and PR. I also added MERGE's canonical logo to OpenCode's provider UI. The adapter PR is approved; the OpenCode reasoning and logo PRs are passing checks and awaiting review.

## Follow-up evidence

- [ ] Record merge and release dates for all three pull requests.
- [ ] Confirm the behavior in a released OpenCode build using the released adapter version.
- [ ] Capture maintainer or customer feedback after release.
- [ ] Add adoption, usage, or support-volume evidence if MERGE measures it.
