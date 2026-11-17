"""Gemeinsamer LLM-Aufruf mit Fallback (Gemini -> Groq -> Claude).

- Nur offizielle APIs, Schlüssel aus Umgebungsvariablen (GitHub-Secrets).
- Hält konfigurierte Gratis-Limits ein (rpm/rpd aus config/llm.json).
- Protokolliert jeden Aufruf in state/llm_usage.jsonl (nicht im Repo; in Actions als Cache/Artefakt).

Nutzung:
    from tools.llm import complete
    data = complete(prompt, system="...", task="campaign_intake", json_mode=True)
    # tier="judge" -> nur Claude (finale Hook-Auswahl)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "llm.json").read_text())
USAGE = ROOT / "state" / "llm_usage.jsonl"


class LLMError(Exception):
    pass


class NeedsClaudeSession(LLMError):
    """Kein Claude-API-Schlüssel: Urteil muss in der geplanten Claude-Sitzung fallen."""


def _post(url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read()[:300]!r}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(str(e)) from None


# ---------- Anbieter ----------

def _gemini(model, system, prompt, json_mode, max_tokens):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    r = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        body,
    )
    text = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    u = r.get("usageMetadata", {})
    return text, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


def _groq(model, system, prompt, json_mode, max_tokens):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.4}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        body,
    )
    u = r.get("usage", {})
    return r["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def _claude(model, system, prompt, json_mode, max_tokens):
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    r = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        body,
    )
    text = "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text")
    u = r.get("usage", {})
    return text, u.get("input_tokens", 0), u.get("output_tokens", 0)


FUNCS = {"gemini": _gemini, "groq": _groq, "claude": _claude}


# ---------- Limits & Protokoll ----------

def _records(provider: str) -> list[dict]:
    if not USAGE.exists():
        return []
    out = []
    for line in USAGE.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("provider") == provider:
            out.append(rec)
    return out


def _wait_for_slot(provider: str, pc: dict) -> bool:
    """False, wenn das Tageslimit erreicht ist; wartet sonst ggf. auf das Minutenlimit."""
    now = time.time()
    recs = _records(provider)
    day_start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    if sum(1 for r in recs if r["ts"] >= day_start) >= pc["rpd"]:
        return False
    last_min = sorted(r["ts"] for r in recs if r["ts"] > now - 60)
    if len(last_min) >= pc["rpm"]:
        time.sleep(max(0.0, 60 - (now - last_min[-pc["rpm"]])) + 1)
    return True


def _log(provider, model, task, ok, tin=0, tout=0, err=""):
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "provider": provider, "model": model, "task": task, "ok": ok,
           "in": tin, "out": tout}
    if err:
        rec["err"] = err[:200]
    with USAGE.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def complete(prompt: str, system: str = "", task: str = "misc", json_mode: bool = False,
             max_tokens: int = 2048, tier: str = "bulk", providers: list[str] | None = None):
    order = providers or CFG["tiers"][tier]
    errors = []
    for p in order:
        pc = CFG["providers"][p]
        if not os.environ.get(pc["key_env"]):
            errors.append(f"{p}: kein Schlüssel")
            continue
        if not _wait_for_slot(p, pc):
            errors.append(f"{p}: Tageslimit")
            continue
        try:
            text, tin, tout = FUNCS[p](pc["model"], system, prompt, json_mode, max_tokens)
            result = _parse_json(text) if json_mode else text
        except (LLMError, KeyError, IndexError, json.JSONDecodeError) as e:
            _log(p, pc["model"], task, False, err=str(e))
            errors.append(f"{p}: {e}")
            continue
        _log(p, pc["model"], task, True, tin, tout)
        return result
    if order == ["claude"] and "claude: kein Schlüssel" in errors:
        raise NeedsClaudeSession("Urteil in der geplanten Claude-Sitzung treffen")
    raise LLMError("alle Anbieter fehlgeschlagen: " + "; ".join(errors))


def usage_summary() -> dict:
    """Aufrufe/Tokens je Anbieter heute (UTC)."""
    day_start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    out = {}
    for p in CFG["providers"]:
        recs = [r for r in _records(p) if r["ts"] >= day_start]
        out[p] = {"calls": len(recs), "failed": sum(not r["ok"] for r in recs),
                  "tokens": sum(r.get("in", 0) + r.get("out", 0) for r in recs)}
    return out


if __name__ == "__main__":
    print(json.dumps(usage_summary(), indent=2))
