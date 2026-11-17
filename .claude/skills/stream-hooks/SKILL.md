---
name: stream-hooks
description: Rules for choosing and judging short-form clip moments and their first 1-3 seconds (hook). Use whenever selecting clips from a stream transcript, judging hook variants, writing on-screen hook text, or reviewing candidates in work/**/selection.json or post.json "hook" fields.
---

# Stream hooks

Apply `docs/HOOKS.md` strictly. Summary:

- Fewer, stronger clips. Score 8+ only if you would bet on it.
- Cold start: begin mid-action, first word within 0.4 s, no fragment, no greeting or loading screen.
- First sentence must create curiosity on its own; otherwise use a 0.5-1.5 s flash-forward of the climax.
- Hook text: max 8 words, top safe area, 0-2 s, opens a question the clip answers, never a lie. Campaign overlay rules win.
- Ad disclosure at the start when the campaign requires it.
- Clear payoff at the end, cut right after it; loop back to the start where possible.
- Never make the streamer or brand look bad, never invent results or drama.

## When judging in a Claude session

1. Read the candidates (`work/<campaign>/<video>/selection.json`) or the variants in each `post.json` → `hook.variants`.
2. For each, read the first 3 s of transcript, the overlay text and the data fields (`loud_rel_db`, `motion`, `face_frames`, `first_word_gap`, `fragment`).
3. Return picks as JSON (id, score 0-10, start, end, hook_text, reason). Keep answers short.
4. Use Sonnet for this; never run it on Opus in routine operation.
