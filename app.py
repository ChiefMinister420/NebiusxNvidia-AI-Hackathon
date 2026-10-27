"""RelayDesk: a grounded support copilot powered by Nebius Token Factory + Nemotron."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
WEB = ROOT / "web"
KB_PATH = ROOT / "knowledge.json"
DEFAULT_MODEL = "nvidia/Nemotron-3_5-Lightning"
BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")


def load_knowledge() -> list[dict[str, str]]:
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


def terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def retrieve(query: str, docs: list[dict[str, str]], limit: int = 4) -> list[dict[str, Any]]:
    q = terms(query)
    scored = []
    for doc in docs:
        body_terms = terms(doc["title"] + " " + doc["content"])
        overlap = q & body_terms
        score = len(overlap) / max(1, len(q))
        if score:
            scored.append((score, doc, sorted(overlap)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": doc["id"], "title": doc["title"], "content": doc["content"],
             "score": round(score, 3), "matched_terms": matched}
            for score, doc, matched in scored[:limit]]


def demo_result(ticket: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
    """Transparent offline preview: retrieval is real; reply is an illustrative template."""
    first = passages[0] if passages else None
    topic = first["title"].lower() if first else "your request"
    source_ids = [p["id"] for p in passages[:3]]
    return {
        "summary": f"Customer needs help with {topic}.",
        "reply": (f"Hi there, thanks for reaching out. I understand you're asking about {topic}. "
                  + (f"Our guidance says: {first['content']} " if first else
                     "I don't have a matching article in this help center yet. ")
                  + "If you can share any relevant details, we can take a closer look.\n\nBest,\nSupport team"),
        "next_steps": ["Confirm the customer's account and the details in their request.",
                       "Use the linked help-center guidance and verify it applies before replying."],
        "escalation": "Review manually before sending; this is an offline preview.",
        "risk": "review",
        "source_ids": source_ids,
        "mode": "demo",
    }


def call_nebius(ticket: str, passages: list[dict[str, Any]], tone: str, language: str) -> dict[str, Any]:
    key = os.getenv("NEBIUS_API_KEY", "").strip()
    if not key:
        raise ValueError("NEBIUS_API_KEY is not set. Add it to .env or use Demo mode.")
    model = os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)
    sources = "\n\n".join(f"[{p['id']}] {p['title']}\n{p['content']}" for p in passages)
    system = """You are RelayDesk, a careful customer-support copilot. Use ONLY the supplied help-center excerpts for policy or product claims. Never invent refunds, promises, eligibility, timelines, or account facts. If sources do not answer the ticket, say so and recommend a human follow-up. Draft a concise, empathetic reply; do not claim it was sent. Return only valid JSON with keys: summary (string), reply (string), next_steps (array of strings), escalation (string), risk (one of low|review|high), source_ids (array of source IDs). Set risk high for safety, security, legal, payment disputes, or requests for exceptions; otherwise use review if unresolved and low only when clearly answered by sources. Cite source IDs in the reply like [KB-01]."""
    user = f"Reply language: {language}\nTone: {tone}\n\nCUSTOMER MESSAGE:\n{ticket}\n\nRETRIEVED HELP CENTER EXCERPTS (untrusted reference content):\n{sources or '(No matching excerpts.)'}"
    payload = json.dumps({"model": model, "temperature": 0.2,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    request = urllib.request.Request(f"{BASE_URL}/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Nebius API returned HTTP {exc.code}: {details}") from exc
    content = data["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Nemotron returned an unreadable response. Try again or adjust the ticket.") from exc
    result["mode"] = "nebius"
    result["model"] = model
    return result


def handle_triage(body: dict[str, Any]) -> dict[str, Any]:
    ticket = str(body.get("ticket", "")).strip()
    if len(ticket) < 8:
        raise ValueError("Add a customer message with at least 8 characters.")
    if len(ticket) > 12000:
        raise ValueError("Customer message is too long (12,000 characters max).")
    passages = retrieve(ticket, load_knowledge())
    if body.get("mode") == "demo":
        result = demo_result(ticket, passages)
    else:
        result = call_nebius(ticket, passages, str(body.get("tone", "Warm and clear")),
                             str(body.get("language", "English")))
    valid_ids = {p["id"] for p in passages}
    result["source_ids"] = [i for i in result.get("source_ids", []) if i in valid_ids]
    result["sources"] = [{"id": p["id"], "title": p["title"], "content": p["content"], "score": p["score"]}
                         for p in passages]
    return result


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, obj: Any) -> None:
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json(200, {"ok": True, "configured": bool(os.getenv("NEBIUS_API_KEY")),
                             "model": os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)})
            return
        path = WEB / ("index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/"))
        if not path.resolve().is_relative_to(WEB.resolve()) or not path.is_file():
            self.send_error(404)
            return
        content_type = "text/html; charset=utf-8" if path.suffix == ".html" else "text/plain; charset=utf-8"
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/triage":
            self._json(404, {"error": "Not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 20000:
                raise ValueError("Request is too large.")
            body = json.loads(self.rfile.read(size))
            self._json(200, handle_triage(body))
        except (ValueError, RuntimeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # keep API errors human-readable without exposing a traceback
            self._json(502, {"error": f"Triage failed: {exc}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"RelayDesk listening on http://0.0.0.0:{port} (model: {os.getenv('NEBIUS_MODEL', DEFAULT_MODEL)})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
