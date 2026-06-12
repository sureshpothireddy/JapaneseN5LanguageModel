"""
core/sensei.py — Optional AI conversation tutor ("Sensei").

The structured lessons are the core teacher and work fully offline. This
adds an *optional* live tutor for free conversation, grammar questions and
roleplay. It calls the Anthropic API only if the learner has provided an
API key (stored in settings). With no key, the UI explains how to enable
it — nothing else in the app depends on this.

No API key is ever bundled; the learner supplies their own.
"""

import json
import urllib.request
import urllib.error

SENSEI_SYSTEM = (
    "You are Sensei, a warm, patient Japanese teacher inside a language-"
    "learning app for an English-speaking beginner working toward JLPT N5–N3. "
    "Keep replies short and encouraging. When you use Japanese, always show: "
    "the Japanese, the romaji in parentheses, and the English meaning. "
    "Gently correct mistakes and explain the 'why' simply. Prefer hiragana "
    "over kanji for true beginners. If the learner writes in Japanese, reply "
    "mostly in simple Japanese but keep the romaji + English support. Never "
    "overwhelm: one new idea at a time."
)

MODEL = "claude-sonnet-4-5-20250929"
API_URL = "https://api.anthropic.com/v1/messages"


class Sensei:
    def __init__(self, db):
        self.db = db

    def has_key(self) -> bool:
        return bool(self.db.get_setting("anthropic_api_key", "").strip())

    def reply(self, history: list[dict], user_text: str) -> str:
        """history: [{'role':'user'/'assistant','content':str}, ...]
        Returns the assistant text, or a helpful message on error."""
        key = self.db.get_setting("anthropic_api_key", "").strip()
        if not key:
            return ("(Sensei is offline) Add your Anthropic API key in "
                    "Settings → AI Sensei to chat with a live tutor. The "
                    "lessons and all other features work without it!")
        messages = [{"role": m["role"], "content": m["content"]}
                    for m in history]
        messages.append({"role": "user", "content": user_text})
        payload = json.dumps({
            "model": MODEL,
            "max_tokens": 600,
            "system": SENSEI_SYSTEM,
            "messages": messages,
        }).encode("utf-8")
        req = urllib.request.Request(API_URL, data=payload, method="POST")
        req.add_header("content-type", "application/json")
        req.add_header("x-api-key", key)
        req.add_header("anthropic-version", "2023-06-01")
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = [b.get("text", "") for b in data.get("content", [])
                     if b.get("type") == "text"]
            return "\n".join(p for p in parts if p).strip() or "(no reply)"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return ("That API key was rejected. Double-check it in "
                        "Settings → AI Sensei.")
            return f"Sensei had trouble reaching the server (HTTP {e.code})."
        except urllib.error.URLError:
            return ("Sensei needs an internet connection. Check your network "
                    "and try again.")
        except Exception as e:                       # pragma: no cover
            return f"Sensei error: {e}"
