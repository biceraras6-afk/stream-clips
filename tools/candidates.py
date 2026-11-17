"""Kandidaten-Momente finden und auswählen.

1. Signale (kostenlos): Lautstärkespitzen, Aufregungs-Wörter, Sprechdichte, Ausrufe.
2. Grobbewertung der besten Fenster per Gratis-LLM (Gemini/Groq), mehrere Fenster pro Aufruf.
3. Finale Auswahl: Claude (tier "judge"), sonst die Grobbewertung (markiert als vorläufig).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from tools import transcribe as tr
from tools.llm import LLMError, NeedsClaudeSession, complete

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "factory.json").read_text())
HOOKS_MD = ROOT / "docs" / "HOOKS.md"


def signal_windows(t: dict, loud: np.ndarray, win: int, step: int, top: int) -> list[dict]:
    dur = len(loud)
    if dur < win:
        return [{"s": 0.0, "e": float(dur), "signal": 0.0}]
    z = (loud - np.median(loud)) / (loud.std() + 1e-6)
    excite = re.compile(r"\b(" + "|".join(re.escape(w) for w in CFG["excite_words"]) + r")\b", re.I)
    per_sec_words = np.zeros(dur)
    per_sec_excite = np.zeros(dur)
    for w in t["words"]:
        i = min(int(w["s"]), dur - 1)
        per_sec_words[i] += 1
    for sg in t["segments"]:
        i = min(int(sg["s"]), dur - 1)
        per_sec_excite[i] += len(excite.findall(sg["text"])) + sg["text"].count("!") + 2 * sg["text"].count("?!")
    rows = []
    for s in range(0, dur - win + 1, step):
        seg = slice(s, s + win)
        peak = float(np.sort(z[seg])[-5:].mean())          # Spitzen statt Durchschnitt
        density = float(per_sec_words[seg].sum() / win)    # Wörter/s
        exc = float(per_sec_excite[seg].sum())
        score = 1.0 * peak + 0.6 * min(exc, 10) / 3 + 0.4 * min(density, 4)
        if density < 0.8:                                   # kaum Sprache -> selten ein guter Clip
            score -= 2
        rows.append({"s": float(s), "e": float(s + win), "signal": round(score, 3),
                     "peak": round(peak, 2), "excite": exc, "density": round(density, 2)})
    rows.sort(key=lambda r: r["signal"], reverse=True)
    chosen: list[dict] = []
    for r in rows:                                          # nicht überlappend
        if all(r["e"] <= c["s"] or r["s"] >= c["e"] for c in chosen):
            chosen.append(r)
        if len(chosen) >= top:
            break
    return sorted(chosen, key=lambda r: r["s"])


BULK_SYSTEM = """You pick short-form clip moments from a livestream transcript for TikTok/YouTube Shorts.
A good clip: self-contained (no context needed), strong hook in the first 2 seconds (reaction, conflict,
bold claim, question, number), clear payoff at the end, {min_s}-{max_s} seconds long.
Start in the middle of the action, never with a run-up, greeting or a cut-off word.
For each window return candidates (0-2 per window) as JSON:
{{"candidates":[{{"window":<index>,"start":<sec>,"end":<sec>,"score":<1-10>,"hook_type":"reaction|conflict|wait_for_it|question|number|contrast|drama",
"first_line":"<first spoken sentence>","payoff":"<what happens at the end>","hook_text":"<on-screen text, max 8 words, opens a question the clip answers, no lie>",
"title":"<short title>","why":"<one sentence>"}}]}}
Use only timestamps that appear in the window. Score honestly: 8+ only if you would bet on it going viral.
Campaign rules to respect: {rules}"""


def bulk_score(t: dict, windows: list[dict], campaign: dict, min_s: int, max_s: int) -> list[dict]:
    rules = "; ".join((campaign.get("rules") or {}).get("dont") or []) or "none given"
    system = BULK_SYSTEM.format(min_s=min_s, max_s=max_s, rules=rules)
    out = []
    n = CFG["windows_per_llm_call"]
    for i in range(0, len(windows), n):
        batch = windows[i:i + n]
        prompt = "\n\n".join(f"### Window {i + j} ({w['s']:.0f}s-{w['e']:.0f}s)\n" + tr.text_between(t, w["s"] - 10, w["e"] + 10, stamps=True)
                             for j, w in enumerate(batch))
        try:
            res = complete(prompt, system=system, task="clip_candidates", json_mode=True, max_tokens=3000)
        except LLMError as e:
            print(f"  Grobbewertung übersprungen: {e}")
            continue
        for c in res.get("candidates", []) if isinstance(res, dict) else []:
            try:
                c["start"], c["end"], c["score"] = float(c["start"]), float(c["end"]), float(c["score"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append(c)
    return out


def snap(t: dict, start: float, end: float, min_s: int, max_s: int) -> tuple[float, float] | None:
    """Auf Wortgrenzen legen: Start an Wortbeginn, Ende nach Satzende; Länge einhalten."""
    ws = t["words"]
    if not ws:
        return None
    first = min((w for w in ws if w["s"] >= start - 1.0), key=lambda w: abs(w["s"] - start), default=None)
    if not first:
        return None
    s = max(0.0, first["s"] - 0.1)
    cand_ends = [w for w in ws if s + min_s <= w["e"] <= s + max_s]
    if not cand_ends:
        return None
    sentence_ends = [w for w in cand_ends if re.search(r"[.!?]$", w["w"])]
    pool = sentence_ends or cand_ends
    last = min(pool, key=lambda w: abs(w["e"] - end))
    return round(float(s), 2), round(float(last["e"]) + 0.25, 2)


JUDGE_SYSTEM = """You are the final judge for short-form clips. Apply the hook rules below strictly.
Prefer fewer, stronger clips. Return JSON {{"picks":[{{"id":<candidate id>,"score":<1-10>,"start":<sec>,"end":<sec>,
"hook_text":"<max 8 words>","title":"<title>","reason":"<one sentence>"}}]}} with at most {k} picks, best first.
Hook rules:
{hooks}"""


def judge(t: dict, cands: list[dict], k: int) -> tuple[list[dict], str]:
    hooks = HOOKS_MD.read_text()[:6000] if HOOKS_MD.exists() else "Start mid-action; first line must create curiosity."
    listing = "\n\n".join(
        f"### Candidate {i} (bulk score {c['score']}, {c['start']:.1f}-{c['end']:.1f}s, hook type {c.get('hook_type')})\n"
        f"Proposed hook text: {c.get('hook_text')}\n" + tr.text_between(t, c["start"], c["end"], stamps=True)
        for i, c in enumerate(cands))
    try:
        res = complete(listing, system=JUDGE_SYSTEM.format(k=k, hooks=hooks), task="clip_judge",
                       json_mode=True, max_tokens=3000, tier="judge")
        picks = []
        for p in res.get("picks", []):
            c = dict(cands[int(p["id"])])
            c.update({k2: p[k2] for k2 in ("score", "start", "end", "hook_text", "title") if p.get(k2) is not None})
            c["judge_reason"] = p.get("reason")
            picks.append(c)
        return picks, "claude"
    except (NeedsClaudeSession, LLMError, KeyError, IndexError, ValueError):
        return sorted(cands, key=lambda c: c["score"], reverse=True)[:k], "bulk"


def select(t: dict, loud: np.ndarray, campaign: dict, max_clips: int) -> dict:
    fmt = campaign.get("format") or {}
    min_s = int(fmt.get("min_seconds") or CFG["default_min_seconds"])
    max_s = int(fmt.get("max_seconds") or CFG["default_max_seconds"])
    max_s = max(max_s, min_s + 5)
    wins = signal_windows(t, loud, CFG["window_seconds"], CFG["window_step"], CFG["top_windows"])
    cands = bulk_score(t, wins, campaign, min_s, max_s)
    good = []
    for c in cands:
        sn = snap(t, c["start"], c["end"], min_s, max_s)
        if sn and c["score"] >= CFG["min_score"] - 1:
            c["start"], c["end"] = sn
            good.append(c)
    good.sort(key=lambda c: c["score"], reverse=True)
    # nicht überlappend
    dedup: list[dict] = []
    for c in good:
        if all(c["end"] <= d["start"] or c["start"] >= d["end"] for d in dedup):
            dedup.append(c)
    picks, judged_by = judge(t, dedup[: max_clips * 2], max_clips) if dedup else ([], "none")
    final = []
    for p in picks:
        sn = snap(t, p["start"], p["end"], min_s, max_s)
        if sn and float(p["score"]) >= CFG["min_score"]:
            p["start"], p["end"] = sn
            final.append(p)
    return {"windows": wins, "candidates": dedup, "picks": final, "judged_by": judged_by,
            "min_s": min_s, "max_s": max_s}
