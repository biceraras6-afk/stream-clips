"""Transkript mit Wortzeiten (faster-whisper, CPU int8)."""
from __future__ import annotations

import json
from pathlib import Path

_MODELS: dict[str, object] = {}


def _model(name: str):
    if name not in _MODELS:
        from faster_whisper import WhisperModel
        _MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODELS[name]


def _read_wav(path: Path):
    """16-kHz-Mono-WAV als float32 (umgeht PyAV-Versionsprobleme)."""
    import wave

    import numpy as np
    with wave.open(str(path)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "WAV muss 16 kHz mono sein"
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def transcribe(audio: Path, model: str = "base.en", language: str = "en", offset: float = 0.0) -> dict:
    """-> {"words": [{w, s, e, p}], "segments": [{s, e, text}]}  (Zeiten + offset)."""
    segs, info = _model(model).transcribe(_read_wav(audio), language=language, word_timestamps=True,
                                          vad_filter=True, beam_size=1 if model.startswith(("tiny", "base")) else 5)
    words, segments = [], []
    for sg in segs:
        segments.append({"s": round(sg.start + offset, 2), "e": round(sg.end + offset, 2), "text": sg.text.strip()})
        for w in sg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start + offset, 2), "e": round(w.end + offset, 2),
                          "p": round(w.probability, 2)})
    return {"language": info.language, "duration": info.duration, "words": words, "segments": segments}


def save(t: dict, path: Path) -> None:
    path.write_text(json.dumps(t, ensure_ascii=False))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def words_between(t: dict, s: float, e: float) -> list[dict]:
    return [w for w in t["words"] if w["s"] >= s - 0.05 and w["e"] <= e + 0.05]


def text_between(t: dict, s: float, e: float, stamps: bool = False) -> str:
    if not stamps:
        return " ".join(w["w"] for w in words_between(t, s, e))
    return "\n".join(f"[{sg['s']:.1f}] {sg['text']}" for sg in t["segments"] if sg["e"] > s and sg["s"] < e)
