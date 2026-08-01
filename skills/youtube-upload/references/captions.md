# YouTube Captions

Use this reference for the captions and complete-package branches.

## Deliverable

Write `<source-name>-corrected.srt` unless the user supplies another filename. A complete package requires this file; when no timecoded source exists, transcribe the video or report the missing caption artifact as a blocker.

## Corrections

- Preserve every block number and timecode.
- Correct misspelled speakers, companies, products, tools, and technical terms.
- Fix clear homophone, grammar, and transcription errors without rewriting the speaker's meaning or voice.
- Remove empty audio artifacts that add no value. Preserve meaningful cues such as `[APPLAUSE]`.
- Preserve useful speaker markers and correct known speaker names.

## Audit

- Compare the source and output block numbers line-for-line; they must be identical.
- Compare the source and output timecodes line-for-line; they must be identical.
- Confirm every text change is a correction supported by the audio, visuals, transcript context, or user clarification.
- Confirm the output parses as SRT and contains no editing notes or placeholders.
