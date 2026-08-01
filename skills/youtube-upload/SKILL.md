---
name: youtube-upload
description: "YouTube upload preparation from video, transcript, or SRT files. Use for a description or other metadata, corrected captions, or a complete upload package."
---

# YouTube Upload

Produce source-grounded YouTube artifacts. Match the requested branch instead of expanding a description request into a full upload package.

## 1. Resolve the branch and source

- Identify the exact video, transcript, or SRT in scope.
- Choose the metadata, captions, or complete-package branch from the user's request.
- Honor a requested output path. Otherwise, use the filenames defined by the selected branch and save beside the source.
- Inspect available files before asking questions. Ask once for any remaining proper-noun, speaker, or recording-context ambiguity that would materially change the output.

This step is complete when the exact source, branch, output files, and material unknowns are all resolved.

## 2. Ground the content

- Read a supplied transcript or SRT in full.
- For video input, inspect its duration, audio, and representative frames. Transcribe the narration when the requested artifact requires claims, quotes, or timestamps that cannot otherwise be verified.
- Treat the filename as a locator, not evidence.

This step is complete when every planned claim, proper noun, quote, and timestamp can be traced to the source or the user's clarification.

## 3. Execute the branch

- For a description or other metadata, read [references/metadata.md](references/metadata.md) and produce only the requested metadata.
- For corrected captions, read [references/captions.md](references/captions.md) and produce the corrected SRT.
- For a complete upload package, read both references and produce every artifact they define. Do not call the package complete while a required artifact is missing.

This step is complete when every requested artifact exists beside the source or at the user-specified destination, and the source media remains unchanged.

## 4. Audit

Apply every quality check in each reference loaded for the selected branch. Remove unsupported material instead of filling gaps with plausible copy.

This step is complete only when every applicable check passes and each output is paste-ready.
