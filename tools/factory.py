"""Clip-Fabrik: Quelle -> Transkript -> Kandidaten -> Auswahl -> Schnitt -> post.json -> QA.

    python tools/factory.py --campaign <id> [--url <video-oder-kanal>] [--max-clips 8]
    python tools/factory.py --campaign <id> --local-video test.mp4      # Test ohne Download

Läuft in Etappen und ist wiederholbar: vorhandene Zwischenergebnisse in work/ werden genutzt.
Ergebnis: out/clips/<kampagne>/<video>_<n>/ {clip.mp4, post.json, qa.json, render.json}
Nur Quellen, die die Kampagne freigibt (campaign.source.urls + permission_quote).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import campaigns as cm  # noqa: E402
from tools import candidates, cut, hook, media, postmeta, qa, viewer_clips  # noqa: E402
from tools import transcribe as tr  # noqa: E402

CFG = json.loads((ROOT / "config" / "factory.json").read_text())
WORK = ROOT / "work"
OUT = ROOT / "out" / "clips"
SEEN = ROOT / "state" / "processed.json"


def load_campaign(cid: str) -> dict:
    p = ROOT / "campaigns" / f"{cid}.json"
    if not p.exists():
        sys.exit(f"Kampagne {cid} nicht gefunden")
    return json.loads(p.read_text())


def allowed(url: str, campaign: dict) -> bool:
    """URL muss zu einer freigegebenen Quelle der Kampagne gehören (gleicher Kanal/Host-Pfad)."""
    norm = lambda u: re.sub(r"^https?://(www\.|m\.)?", "", u).rstrip("/").lower()  # noqa: E731
    srcs = [norm(u) for u in (campaign.get("source") or {}).get("urls") or []]
    u = norm(url)
    for s in srcs:
        chan = "/".join(s.split("/")[:2])
        if u.startswith(s) or u.startswith(chan):
            return True
    return False


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--url")
    ap.add_argument("--local-video")
    ap.add_argument("--max-clips", type=int, default=CFG["max_clips_per_source"])
    a = ap.parse_args()

    c = load_campaign(a.campaign)
    src = c.get("source") or {}
    if not a.local_video:
        if not src.get("permission_quote"):
            sys.exit("Keine Quellen-Freigabe in der Kampagne – Abbruch.")
        urls = [a.url] if a.url else src.get("urls") or []
        if a.url and not allowed(a.url, c):
            sys.exit(f"{a.url} gehört nicht zu den freigegebenen Quellen der Kampagne.")
        if not urls:
            sys.exit("Kampagne nennt keine Quell-URL.")
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()

    # 1. Quelle bestimmen
    if a.local_video:
        meta = {"id": Path(a.local_video).stem, "title": Path(a.local_video).name,
                "duration": media.video_info(Path(a.local_video))["duration"], "webpage_url": None}
    else:
        meta = None
        for u in urls:
            try:
                meta = media.resolve_source(u, seen)
            except RuntimeError as e:
                log(f"Quelle {u}: {e}")
            if meta:
                break
        if not meta:
            log("Kein neues Video in den freigegebenen Quellen.")
            return 0
        if (meta.get("duration") or 0) > CFG["max_source_hours"] * 3600:
            log(f"Video zu lang ({meta['duration'] / 3600:.1f} h) – übersprungen.")
            return 0
    for _attempt in range(6):
        vid = re.sub(r"[^\w-]", "_", str(meta["id"]))
        work = WORK / c["id"] / vid
        work.mkdir(parents=True, exist_ok=True)
        log(f"Quelle: {meta.get('title')} ({(meta.get('duration') or 0) / 60:.0f} min)")
        # 2. Audio + grobes Transkript
        wav = work / "audio.wav"
        if not wav.exists():
            if a.local_video:
                media.run(["ffmpeg", "-y", "-v", "error", "-i", a.local_video, "-ac", "1", "-ar", "16000", str(wav)])
            else:
                log("Audio laden …")
                media.download_audio(meta["webpage_url"], wav)
        secs = wav.stat().st_size / 32000
        if a.local_video or secs >= 600:
            break
        log(f"Video nur {secs / 60:.1f} min – übersprungen, nächstes")
        seen.add(str(meta["id"]))
        SEEN.parent.mkdir(exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen)))
        meta = None
        for u in urls:
            try:
                meta = media.resolve_source(u, seen)
            except RuntimeError as e:
                log(f"Quelle {u}: {e}")
            if meta:
                break
        if not meta:
            log("Kein weiteres Video.")
            return 0
    tpath = work / "transcript_select.json"
    if not tpath.exists():
        log(f"Transkript ({CFG['whisper_select_model']}) …")
        tr.save(tr.transcribe(wav, CFG["whisper_select_model"], language=c.get("language") or "en"), tpath)
    t = tr.load(tpath)
    log(f"{len(t['words'])} Wörter")

    # 3. Kandidaten + Auswahl
    spath = work / "selection.json"
    if not spath.exists():
        log("Kandidaten bewerten …")
        viewer = viewer_clips.twitch_clips(meta)
        log(f"{len(viewer)} Zuschauer-Clips (Twitch)" if viewer else "keine Zuschauer-Clips (Secrets fehlen oder Kick)")
        sel = candidates.select(t, media.loudness_curve(wav), c, a.max_clips, viewer)
        spath.write_text(json.dumps(sel, indent=1, ensure_ascii=False))
    sel = json.loads(spath.read_text())
    log(f"{len(sel['candidates'])} Kandidaten, {len(sel['picks'])} ausgewählt (Urteil: {sel['judged_by']})")

    # 4. Schnitt, Texte, QA je Clip
    results = []
    for n, clip in enumerate(sel["picks"], 1):
        cdir = OUT / c["id"] / f"{vid}_{n:02d}"
        if (cdir / "qa.json").exists():
            results.append(json.loads((cdir / "qa.json").read_text()) | {"dir": str(cdir)})
            continue
        cdir.mkdir(parents=True, exist_ok=True)
        s0, s1 = max(0.0, clip["start"] - 2), clip["end"] + 2
        section = work / f"section_{n:02d}.mp4"
        log(f"Clip {n}: {clip['start']:.1f}-{clip['end']:.1f}s „{clip.get('title')}“")
        if not section.exists():
            if a.local_video:
                media.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s0}", "-to", f"{s1}", "-i", a.local_video,
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", str(section)])
            else:
                media.download_section(meta["webpage_url"], s0, s1, section, CFG["video_height_max"])
        # genaues Transkript nur für den Abschnitt
        swav = work / f"section_{n:02d}.wav"
        media.run(["ffmpeg", "-y", "-v", "error", "-i", str(section), "-ac", "1", "-ar", "16000", str(swav)])
        ft = tr.transcribe(swav, CFG["whisper_final_model"], language=c.get("language") or "en", offset=s0)
        all_words = ft["words"]
        # Phase 2b: 3 Hook-Varianten, beste nach Daten + HOOKS.md
        vs = hook.variants(all_words, clip, swav, s0, sel["min_s"], sel["max_s"])
        best, vs, hook_by = hook.choose(vs, all_words, section, s0, swav)
        log(f"  Hook: {best['name']} (gesamt {best['total']}) – „{best.get('overlay')}“")
        chosen = dict(clip, start=best["start"], end=best["end"], teaser=best["teaser"], overlay=best.get("overlay"))
        words = tr.words_between(ft, chosen["start"], chosen["end"])
        r = cut.render(section, s0, chosen, all_words, cdir, c.get("disclosure"), c.get("overlays_allowed") is not False)
        r["loop_score"] = hook.loop_score(cdir / "clip.mp4")
        (cdir / "render.json").write_text(json.dumps(r, indent=1))
        text = " ".join(w["w"] for w in words)
        post = postmeta.build(dict(clip, hook_text=best.get("overlay")), text, c)
        post.update({"source_video": meta.get("webpage_url"), "source_start": chosen["start"], "source_end": chosen["end"],
                     "score": clip.get("score"), "hook_type": clip.get("hook_type"), "judged_by": sel["judged_by"],
                     "hook": {"chosen": best["name"], "judged_by": hook_by, "loop_score": r["loop_score"],
                              "variants": [{k: v[k] for k in ("name", "start", "end", "teaser", "overlay", "total", "data")
                                            if k in v} | {"llm_score": v.get("llm_score"), "why": v.get("why")} for v in vs]}})
        postmeta.save(post, cdir / "post.json")
        q = qa.check(cdir, post, c, len(words), len(words), sel["min_s"], sel["max_s"])
        log(f"  QA: {q['status']} " + "; ".join(f"{x['check']}: {x['detail']}" for x in q["checks"] if not x["ok"]))
        results.append(q | {"dir": str(cdir)})
        section.unlink(missing_ok=True)
        swav.unlink(missing_ok=True)

    if not a.local_video:
        SEEN.parent.mkdir(exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen | {str(meta["id"])})))
    ok = sum(r["status"] == "pass" for r in results)
    summary = f"### {c['title']}\nQuelle: {meta.get('title')}\n\n{ok} von {len(results)} Clips bestehen die QA (Urteil: {sel['judged_by']})\n"
    for r in results:
        p = json.loads((Path(r["dir"]) / "post.json").read_text())
        bad = "; ".join(x["check"] for x in r["checks"] if not x["ok"])
        summary += f"- {'✅' if r['status'] == 'pass' else '❌'} {p['title']} (Score {p.get('score')}){' – ' + bad if bad else ''}\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
