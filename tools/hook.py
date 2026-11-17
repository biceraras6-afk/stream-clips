"""Hook-Spezialisierung (Phase 2b): die ersten 1–3 Sekunden.

Pro Clip 3 Varianten:
  A "original"  – Start wie ausgewählt, Overlay-Text aus der Auswahl
  B "kaltstart" – Start später, direkt am lautesten/aufgeregtesten Satzbeginn (mitten in der Aktion)
  C "teaser"    – Flash-Forward: 0,5–1,5 s des Höhepunkts vorn, dann zurück zum Anfang
Bewertung: Daten (Lautstärke, Bewegung, Gesicht, Sprache ab Sekunde 0, kein Wort-Fragment)
+ Urteil nach docs/HOOKS.md (Claude, sonst Gratis-LLM). Gewinner wird geschnitten,
alle Varianten landen in post.json (für spätere A/B-Tests).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from tools.cut import trimmed_len
from tools.llm import LLMError, NeedsClaudeSession, complete

ROOT = Path(__file__).resolve().parent.parent
HOOKS_MD = ROOT / "docs" / "HOOKS.md"
SENT_END = re.compile(r"[.!?]$")


def _wav_rms(wav: Path, sr_hop: float = 0.1) -> tuple[np.ndarray, float]:
    import wave
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * sr_hop)
    fr = d[: len(d) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1) + 1e-12)), sr_hop


def _sentence_starts(words: list[dict]) -> list[dict]:
    out = []
    for i, w in enumerate(words):
        prev = words[i - 1] if i else None
        if prev is None or SENT_END.search(prev["w"]) or w["s"] - prev["e"] > 0.35:
            out.append(w)
    return out


def variants(words: list[dict], clip: dict, wav: Path, wav_start: float, min_s: int, max_s: int) -> list[dict]:
    """words: Wörter mit absoluten Zeiten; wav: Abschnitts-Audio ab wav_start."""
    rms, hop = _wav_rms(wav)
    def loud(a: float, b: float) -> float:
        i, j = int((a - wav_start) / hop), int((b - wav_start) / hop)
        seg = rms[max(i, 0):max(j, i + 1)]
        return float(seg.mean()) if len(seg) else -60.0

    start, end = clip["start"], clip["end"]
    base = {"overlay": clip.get("hook_text"), "teaser": None}
    vs = [dict(base, name="original", start=start, end=end)]

    # B: Kaltstart – lautester Satzbeginn in den ersten 8 s, Restlänge >= min_s
    starts = [w for w in _sentence_starts([w for w in words if start <= w["s"] <= end])
              if w["s"] <= start + 8 and w["s"] > start + 0.5 and trimmed_len(words, w["s"] - 0.08, end) >= min_s + 0.5]
    if starts:
        best = max(starts, key=lambda w: loud(w["s"], w["s"] + 2))
        vs.append(dict(base, name="kaltstart", start=round(best["s"] - 0.08, 2), end=end))

    # C: Teaser – lautestes 1,2-s-Fenster in den letzten 60 % (Höhepunkt), vorn eingesetzt
    lo = start + (end - start) * 0.4
    best_t, best_v = None, -1e9
    t = lo
    while t + 1.2 <= end:
        v = loud(t, t + 1.2)
        if v > best_v:
            best_t, best_v = t, v
        t += 0.2
    if best_t is not None and best_v > loud(start, end) + 3:   # nur bei echtem Höhepunkt (+3 dB)
        total = trimmed_len(words, start, end) + 1.2
        if total <= max_s + 1:
            vs.append(dict(base, name="teaser", start=start, end=end, teaser=[round(best_t, 2), round(best_t + 1.2, 2)]))
    return vs


def data_score(v: dict, words: list[dict], section: Path, section_start: float, wav: Path) -> dict:
    """Messwerte für Sekunde 0–2 der Variante (0–10)."""
    import cv2
    rms, hop = _wav_rms(wav)
    a = (v["teaser"][0] if v["teaser"] else v["start"]) - section_start
    i, j = int(a / hop), int((a + 2) / hop)
    loud2 = float(rms[max(i, 0):max(j, i + 1)].mean()) if j > i else -60.0
    rel = loud2 - float(np.median(rms))
    w0 = [w for w in words if w["s"] >= (v["teaser"][0] if v["teaser"] else v["start"]) - 0.05]
    first_gap = (w0[0]["s"] - (v["teaser"][0] if v["teaser"] else v["start"])) if w0 else 9.0
    prev = [w for w in words if w["e"] <= v["start"] + 0.05]
    fragment = bool(prev) and not v["teaser"] and v["start"] - prev[-1]["e"] < 0.15 and not SENT_END.search(prev[-1]["w"])
    # Bewegung + Gesicht in den ersten 2 s
    cap = cv2.VideoCapture(str(section))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    diffs, faces, prev_g = [], 0, None
    for k in range(8):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((a + k * 0.25) * fps))
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(fr, (320, 180)), cv2.COLOR_BGR2GRAY)
        if prev_g is not None:
            diffs.append(float(np.abs(g.astype(np.int16) - prev_g).mean()))
        prev_g = g.astype(np.int16)
        faces += int(len(casc.detectMultiScale(g, 1.1, 5, minSize=(16, 16))) > 0)
    cap.release()
    motion = float(np.mean(diffs)) if diffs else 0.0
    score = (min(max(rel + 3, 0), 9) / 9 * 3          # lauter als üblich
             + min(motion, 20) / 20 * 2              # sichtbare Aktion
             + (faces > 0) * 1.5                     # Gesicht/Reaktion im Bild
             + (first_gap < 0.4) * 2                 # sofort Sprache, keine Stille
             + (not fragment) * 1.5)                 # kein abgeschnittenes Wort
    return {"loud_rel_db": round(rel, 1), "motion": round(motion, 1), "face_frames": faces,
            "first_word_gap": round(first_gap, 2), "fragment": fragment, "data_score": round(score, 2)}


JUDGE = """You judge the first 2 seconds of short-form clip variants using these hook rules:
{rules}
Return JSON {{"scores":[{{"name":"<variant>","score":<0-10>,"overlay":"<improved on-screen text, max 8 words, must be true to the clip>","why":"<short>"}}]}}"""


def judge(vs: list[dict], words: list[dict]) -> str:
    rules = HOOKS_MD.read_text()[:5000] if HOOKS_MD.exists() else ""
    def opening(v):
        t0 = v["teaser"][0] if v["teaser"] else v["start"]
        t1 = (v["teaser"][1] if v["teaser"] else v["start"] + 3)
        return " ".join(w["w"] for w in words if t0 - 0.05 <= w["s"] <= t1)
    desc = "\n".join(
        f"- {v['name']}: first words: \"{opening(v)}\" | then: \"{' '.join(w['w'] for w in words if v['start'] <= w['s'] <= v['start'] + 4)}\" "
        f"| overlay: \"{v.get('overlay')}\" | teaser: {'yes' if v['teaser'] else 'no'} | data: {json.dumps(v.get('data'))}"
        for v in vs)
    full = " ".join(w["w"] for w in words if vs[0]["start"] <= w["s"] <= vs[0]["end"])
    prompt = f"Full clip transcript: {full[:2500]}\n\nVariants:\n{desc}"
    for tier in ("judge", "bulk"):
        try:
            res = complete(prompt, system=JUDGE.format(rules=rules), task="hook_judge", json_mode=True,
                           max_tokens=1200, tier=tier)
            for s in res.get("scores", []):
                for v in vs:
                    if v["name"] == s.get("name"):
                        v["llm_score"] = float(s.get("score", 0))
                        if s.get("overlay"):
                            v["overlay_suggestion"] = " ".join(str(s["overlay"]).split()[:8])
                        v["why"] = s.get("why")
            return "claude" if tier == "judge" else "bulk"
        except (NeedsClaudeSession, LLMError, ValueError, TypeError):
            continue
    return "none"


def choose(vs: list[dict], words: list[dict], section: Path, section_start: float, wav: Path) -> tuple[dict, list[dict], str]:
    for v in vs:
        v["data"] = data_score(v, words, section, section_start, wav)
    by = judge(vs, words)
    for v in vs:
        llm = v.get("llm_score")
        v["total"] = round(0.6 * llm + 0.4 * v["data"]["data_score"] if llm is not None else v["data"]["data_score"], 2)
        if v.get("overlay_suggestion"):
            v["overlay"] = v["overlay_suggestion"]
    best = max(vs, key=lambda v: v["total"])
    return best, vs, by


def loop_score(clip_mp4: Path) -> float:
    """Ähnlichkeit letztes/erstes Bild (0–1): hoch = Ende führt sauber in den Anfang zurück."""
    import cv2
    cap = cv2.VideoCapture(str(clip_mp4))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ok1, f1 = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n - 2))
    ok2, f2 = cap.read()
    cap.release()
    if not (ok1 and ok2):
        return 0.0
    h = [cv2.calcHist([cv2.cvtColor(f, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256]) for f in (f1, f2)]
    for x in h:
        cv2.normalize(x, x)
    return round(float(cv2.compareHist(h[0], h[1], cv2.HISTCMP_CORREL)), 3)
