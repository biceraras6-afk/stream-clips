"""Schnitt: 9:16 mit Gesichts-Tracking, Pausen kürzen, wortgenaue Untertitel, Hook-Text, −14 LUFS."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from tools import media

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "factory.json").read_text())


# ---------- Gesicht / Layout ----------

def analyze_faces(video: Path, per_second: float = 2.0) -> list[dict]:
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(fps / per_second))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out, i = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (640, int(640 * h / w)))
                gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
                faces = casc.detectMultiScale(gray, 1.1, 6, minSize=(24, 24))
                sc = w / 640
                if len(faces):
                    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                    out.append({"t": i / fps, "x": x * sc / w, "y": y * sc / h, "w": fw * sc / w, "h": fh * sc / h})
                else:
                    out.append({"t": i / fps})
        i += 1
    cap.release()
    return out


def choose_layout(info: dict, faces: list[dict]) -> dict:
    W, H = info["w"], info["h"]
    if W / H <= 0.65:
        return {"type": "native"}
    hits = [f for f in faces if "x" in f]
    ratio = len(hits) / max(1, len(faces))
    if hits:
        cx = float(np.median([f["x"] + f["w"] / 2 for f in hits]))
        cy = float(np.median([f["y"] + f["h"] / 2 for f in hits]))
        area = float(np.median([f["w"] * f["h"] for f in hits]))
        spread = float(np.std([f["x"] + f["w"] / 2 for f in hits]))
        fw = float(np.median([f["w"] for f in hits]))
    else:
        cx, cy, area, spread, fw = 0.5, 0.5, 0.0, 1.0, 0.0
    # Kleine, ruhige Facecam in einer Ecke + Gameplay -> geteiltes Bild
    corner = (cx < 0.3 or cx > 0.7) or (cy < 0.3 or cy > 0.7)
    if ratio >= 0.4 and area < 0.04 and spread < 0.05 and corner:
        return {"type": "split", "cx": cx, "cy": cy, "fw": fw}
    # Kein starker Crop (wirkt unscharf): ganzes Bild + unscharfer Hintergrund, max. fit_zoom-facher Ausschnitt
    return {"type": "fit", "cx": cx if ratio >= 0.3 else 0.5, "zoom": CFG.get("layout", {}).get("fit_zoom", 1.3)}


def layout_filter(lay: dict, info: dict) -> str:
    OW, OH = CFG["output"]["width"], CFG["output"]["height"]
    W, H = info["w"], info["h"]
    if lay["type"] == "native":
        return f"scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH}"
    if lay["type"] == "fit":
        z = max(1.0, lay.get("zoom", 1.0))
        cw, ch = int(W / z) // 2 * 2, int(H / z) // 2 * 2
        x = int(min(max(lay["cx"] * W - cw / 2, 0), W - cw))
        y = (H - ch) // 2
        fh = int(OW * ch / cw) // 2 * 2
        return (f"split=2[bg][fg];[bg]scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH},"
                f"boxblur=30:5,eq=brightness=-0.08[b];[fg]crop={cw}:{ch}:{x}:{y},scale={OW}:{fh}:flags=lanczos[f];"
                f"[b][f]overlay=0:(H-h)/2")
    if lay["type"] == "crop":
        cw = int(H * OW / OH) // 2 * 2
        x = int(min(max(lay["cx"] * W - cw / 2, 0), W - cw))
        return f"crop={cw}:{H}:{x}:0,scale={OW}:{OH}"
    # split: oben Facecam (40 %), unten Gameplay (60 %)
    top_h = int(OH * 0.4) // 2 * 2
    bot_h = OH - top_h
    fw_px = max(lay["fw"] * W * 2.6, W * 0.12)
    fh_px = fw_px * top_h / OW
    fx = min(max(lay["cx"] * W - fw_px / 2, 0), W - fw_px)
    fy = min(max(lay["cy"] * H - fh_px / 2, 0), H - fh_px)
    gw = int(H * OW / bot_h) // 2 * 2
    gx = (W - gw) // 2
    return (f"split=2[cam][game];[cam]crop={int(fw_px)}:{int(fh_px)}:{int(fx)}:{int(fy)},scale={OW}:{top_h}[c];"
            f"[game]crop={gw}:{H}:{gx}:0,scale={OW}:{bot_h}[g];[c][g]vstack=inputs=2")


# ---------- Pausen kürzen ----------

def keep_segments(words: list[dict], start: float, end: float) -> list[tuple[float, float]]:
    """Zeitbereiche (relativ zum Clipstart), Pausen > silence_gap auf silence_keep gekürzt."""
    gap, keep = CFG["silence_gap"], CFG["silence_keep"]
    segs: list[list[float]] = []
    cur = [0.0, None]
    prev_end = 0.0
    for w in words:
        ws, we = w["s"] - start, w["e"] - start
        if ws - prev_end > gap and cur[1] is not None:
            cur[1] = prev_end + keep
            segs.append(cur)
            cur = [max(ws - keep, cur[1]), None]
        cur[1] = we
        prev_end = we
    cur[1] = min(end - start, (cur[1] or 0) + 0.35)
    segs.append(cur)
    return [(round(a, 3), round(b, 3)) for a, b in segs if b - a > 0.05]


def trimmed_len(words: list[dict], start: float, end: float) -> float:
    """Länge nach dem Kürzen der Pausen."""
    ws = [w for w in words if start - 0.05 <= w["s"] and w["e"] <= end + 0.05]
    return sum(b - a for a, b in keep_segments(ws, start, end)) if ws else end - start


def remap(t: float, segs: list[tuple[float, float]]) -> float:
    acc = 0.0
    for a, b in segs:
        if t < a:
            return acc
        if t <= b:
            return acc + (t - a)
        acc += b - a
    return acc


# ---------- Untertitel (ASS) ----------

def _ass_time(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def build_ass(words: list[dict], start: float, segs, hook_text: str | None, disclosure: str | None,
              brand: bool = False, total: float = 0.0) -> str:
    """segs: Bereiche relativ zu `start`, in Ausgabereihenfolge (ein Teaser darf vorn stehen)."""
    sc, hk = CFG["subtitles"], CFG["hook"]
    OW, OH = CFG["output"]["width"], CFG["output"]["height"]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {OW}", f"PlayResY: {OH}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{sc['font']},{sc['size']},{sc['color']},&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,"
        f"{sc['outline']},2,2,60,60,{int(OH * (1 - sc['y_ratio']))},1",
        f"Style: Hook,{sc['font']},{hk['size']},&H00000000,&H000000FF,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,"
        f"18,0,8,90,90,{int(OH * hk['y_ratio'])},1",
        f"Style: HookB,{sc['font']},84,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,8,70,70,110,1",
        f"Style: Ad,{sc['font']},44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,7,50,50,60,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    out_off = 0.0
    for a, b in segs:
        seg_words = [w for w in words if a - 0.02 <= w["s"] - start < b]
        groups: list[list[dict]] = []
        for w in seg_words:
            if (not groups or len(groups[-1]) >= sc["words_per_line"]
                    or re.search(r"[.!?,]$", groups[-1][-1]["w"]) or w["s"] - groups[-1][-1]["e"] > 0.3):
                groups.append([])
            groups[-1].append(w)
        for g in groups:
            for i, w in enumerate(g):
                t0 = out_off + max(0.0, w["s"] - start - a)
                nxt = g[i + 1]["s"] if i + 1 < len(g) else w["e"]
                t1 = out_off + min(b - a, nxt - start - a)
                if t1 - t0 < 0.05:
                    t1 = t0 + 0.05
                txt = " ".join(
                    (f"{{\\c{sc['highlight']}}}{_esc(x['w']).upper()}{{\\c{sc['color']}}}" if j == i else _esc(x["w"]).upper())
                    for j, x in enumerate(g))
                lines.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},Cap,,0,0,0,,{txt}")
        out_off += b - a
    if hook_text:
        hook = " ".join(hook_text.split()[: hk["max_words"]]).upper()
        if brand:   # Überschrift im oberen Balken, ganze Videodauer (wie im Beispiel der Marke)
            lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(max(total, hk['seconds']))},HookB,,0,0,0,,{_esc(hook)}")
        else:
            lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(hk['seconds'])},Hook,,0,0,0,,{_esc(hook)}")
    if disclosure:
        lines.append(f"Dialogue: 2,{_ass_time(0)},{_ass_time(3.0)},Ad,,0,0,0,,{_esc(disclosure)}")
    return "\n".join(lines) + "\n"


# ---------- Marken-Layout (Kampagnen mit Pflicht-Wasserzeichen) ----------

def prepare_watermark(src: Path, dst: Path) -> Path:
    """Wasserzeichen laden, auf den sichtbaren Inhalt zuschneiden (transparenter Rand weg), als PNG mit Alpha ablegen."""
    import cv2
    img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim < 3 or img.shape[2] < 4:
        raise RuntimeError("Wasserzeichen nicht lesbar oder ohne Transparenz")
    ys, xs = np.where(img[:, :, 3] > 8)
    pad = 6
    y0, y1, x0, x1 = max(ys.min() - pad, 0), ys.max() + pad, max(xs.min() - pad, 0), xs.max() + pad
    cv2.imwrite(str(dst), img[y0:y1, x0:x1])
    return dst


# ---------- Rendern ----------

def render(section: Path, section_start: float, clip: dict, words: list[dict], out_dir: Path,
           disclosure: str | None, overlays_allowed: bool = True, brand: dict | None = None) -> dict:
    """section: heruntergeladener Abschnitt ab `section_start` (absolute Zeit).
    clip: {start, end, overlay|hook_text, teaser: [a, b] | None} (absolute Zeiten)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    info = media.video_info(section)
    faces = analyze_faces(section)
    lay = choose_layout(info, faces)
    start, end = clip["start"], clip["end"]
    off = start - section_start                                  # Clipstart im Abschnitt
    segs = keep_segments([w for w in words if start <= w["s"] <= end], start, end)
    if clip.get("teaser"):
        ta, tb = clip["teaser"]
        segs = [(round(ta - start, 3), round(tb - start, 3))] + segs
    overlay = (clip.get("overlay") or clip.get("hook_text")) if overlays_allowed else None
    total_len = sum(b - a for a, b in segs)
    ass = build_ass(words, start, segs, overlay, disclosure, brand=bool(brand), total=total_len)
    (out_dir / "subs.ass").write_text(ass)
    parts, labels = [], []
    for i, (a, b) in enumerate(segs):
        parts.append(f"[0:v]trim={off + a:.3f}:{off + b:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={off + a:.3f}:{off + b:.3f},asetpts=PTS-STARTPTS[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    o = CFG["output"]
    fps = min(o.get("fps_max", 60), round(info["fps"])) if info["fps"] >= 24 else 30
    OW, OH = o["width"], o["height"]
    extra_in: list[str] = []
    if brand:   # oben Überschrift-Balken, Mitte Video, unten Balken mit Wasserzeichen (Beispiel der Marke)
        top, box_h, wm_w = brand.get("top", 428), brand.get("box_h", 1200), brand.get("wm_width", 960)
        lay = {"type": "brand", "top": top, "box_h": box_h}
        wm_y = top + box_h + (OH - top - box_h - int(wm_w * brand["wm_ratio"])) // 2
        fc = ("".join(parts) + "".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];"
              f"[vc]scale={OW}:{box_h}:force_original_aspect_ratio=increase,crop={OW}:{box_h},"
              f"pad={OW}:{OH}:0:{top}:black[vb];[1:v]scale={wm_w}:-1[wm];"
              f"[vb][wm]overlay=(W-w)/2:{wm_y}:shortest=1,fps={fps},ass={out_dir / 'subs.ass'}[vo]")
        extra_in = ["-loop", "1", "-i", str(brand["watermark"])]
    else:
        fc = ("".join(parts) + "".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];"
              f"[vc]{layout_filter(lay, info)},fps={fps},ass={out_dir / 'subs.ass'}[vo]")
    raw = out_dir / "raw.mp4"
    media.run(["ffmpeg", "-y", "-v", "error", "-i", str(section), *extra_in, "-filter_complex", fc, "-map", "[vo]", "-map", "[ac]",
               "-c:v", "libx264", "-preset", o.get("preset", "medium"), "-crf", str(o["crf"]), "-pix_fmt", "yuv420p",
               "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", str(raw)])
    final = out_dir / "clip.mp4"
    lo = CFG["loudness"]
    media.normalize_audio(raw, final, lo["target"], lo["true_peak"])
    raw.unlink()
    try:
        br = int(media.probe(section)["format"].get("bit_rate") or 0) // 1000
    except Exception:  # noqa: BLE001
        br = 0
    meta = {"source": {"w": info["w"], "h": info["h"], "fps": round(info["fps"], 1), "kbps": br}, "out_fps": fps, "layout": lay, "segments": segs, "source_start": start, "source_end": end, "teaser": clip.get("teaser"),
            "overlay": overlay, "duration": round(sum(b - a for a, b in segs), 2),
            "face_hit_ratio": round(sum("x" in f for f in faces) / max(1, len(faces)), 2)}
    (out_dir / "render.json").write_text(json.dumps(meta, indent=1))
    return meta
