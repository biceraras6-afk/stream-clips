"""post.json je Clip: Titel, Beschreibung, Hashtags, Pflicht-Tags – je Plattform eigene Fassung.

Entwürfe per Gratis-LLM; Pflicht-Tags, Links und Werbe-Hinweis werden immer per Code ergänzt.
"""
from __future__ import annotations

import json
import re

from tools.llm import LLMError, complete

SYSTEM = """Write social captions for a short stream clip. English. No clickbait lies, no emojis spam (max 2).
Return JSON: {"youtube":{"title":"<max 90 chars>","description":"<1-2 sentences>"},
"tiktok":{"caption":"<1 short punchy line>"},"hashtags":["#tag", ...max 4 relevant, lowercase]}
Never name the clipper account. Never claim to be the streamer."""

LIMITS = {"youtube_title": 100, "youtube_desc": 5000, "tiktok": 2200, "instagram": 2200, "x": 280}


def _tags(campaign: dict) -> tuple[list[str], list[str], list[str], str | None]:
    req = [t if t.startswith("@") else "@" + t for t in (campaign.get("required_tags") or [])]
    hs = [t if t.startswith("#") else "#" + t for t in (campaign.get("hashtags") or [])]
    links = list(campaign.get("links") or [])
    return req, hs, links, campaign.get("disclosure")


def build(clip: dict, transcript_text: str, campaign: dict) -> dict:
    req, camp_hs, links, disclosure = _tags(campaign)
    draft = {}
    try:
        draft = complete(f"Streamer: {campaign.get('streamer')}\nClip title idea: {clip.get('title')}\n"
                         f"Hook: {clip.get('hook_text')}\nTranscript:\n{transcript_text[:3000]}",
                         system=SYSTEM, task="post_meta", json_mode=True, max_tokens=800)
    except LLMError as e:
        print(f"  Post-Texte ohne LLM: {e}")
    title = (draft.get("youtube") or {}).get("title") or clip.get("title") or "Stream highlight"
    desc = (draft.get("youtube") or {}).get("description") or ""
    cap = (draft.get("tiktok") or {}).get("caption") or title
    extra = [h.lower() for h in draft.get("hashtags", []) if re.fullmatch(r"#\w{2,30}", h or "")]
    hashtags = list(dict.fromkeys(camp_hs + extra))[:8]
    mention = campaign.get("mention_text")        # z. B. „Live on Kick“ (Briefing-Pflicht)
    must = " ".join(req + ([mention] if mention else []) + hashtags)
    ad = f"{disclosure} " if disclosure else ""
    platforms = {}
    for p in campaign.get("platforms") or []:
        if p == "youtube":
            t = title[: LIMITS["youtube_title"] - 8].rstrip()
            platforms[p] = {"title": f"{t} #shorts" if len(t) < 90 else t,
                            "description": "\n\n".join(x for x in [ad + desc, must, "\n".join(links)] if x.strip())}
        elif p in ("tiktok", "instagram"):
            first = (campaign.get("platform_first_word") or {}).get(p)       # z. B. Instagram: Marken-Tag als erstes Wort
            platforms[p] = {"caption": " ".join(x for x in [first, ad + cap, must, " ".join(links)] if x)[: LIMITS[p]]}
        elif p == "x":
            platforms[p] = {"text": " ".join(x for x in [ad + cap, " ".join(req), " ".join(links)] if x)[: LIMITS["x"]]}
    return {"campaign": campaign["id"], "campaign_url": campaign.get("url"), "title": title,
            "hook_text": clip.get("hook_text"), "required_tags": req, "hashtags": hashtags, "links": links,
            "disclosure": disclosure, "platforms": platforms}


def save(post: dict, path) -> None:
    path.write_text(json.dumps(post, indent=1, ensure_ascii=False))
