"""A local fake of the Anthropic Messages API for development and smoke tests (no real spend).

Run:  uv run python scripts/mock_anthropic.py --port 8788
Then: WASILA_ANTHROPIC_BASE_URL=http://localhost:8788 for uvicorn.

It answers each Wasila prompt with a fixed, plausible reply:
- Ask Wasila → filters derived from simple words in the question (UK/US/Saudi, health, AI,
  angel, email, not contacted);
- drafts → a short warm letter that names the investor;
- AI columns → "Likely: <first tag>" or "Unknown";
- deck suggestions → one shorter title for slide 1.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def answer(body: dict[str, Any]) -> str:
    system = str(body.get("system") or "")
    user = str(body["messages"][0]["content"])
    if system.startswith("Reply with OK"):
        return "OK"
    if "search filters" in system:
        q = user.lower()
        f: dict[str, Any] = {}
        countries = [
            c
            for k, c in (("uk", "United Kingdom"), ("british", "United Kingdom"), ("us ", "United States"),
                         ("america", "United States"), ("saudi", "Saudi Arabia"), ("ksa", "Saudi Arabia"),
                         ("gcc", "GCC"))
            if k in q
        ]
        if countries:
            f["countries"] = sorted(set(countries))
        tags = [t for k, t in (("health", "Health"), (" ai", "AI"), ("mental", "Mental health")) if k in f" {q}"]
        if tags:
            f["tags_any"] = tags
        if "angel" in q:
            f["types"] = ["angel"]
        if "email" in q and "without" not in q:
            f["has_email"] = True
        if "not contacted" in q or "haven't contacted" in q or "not yet contacted" in q:
            f["not_contacted"] = True
        f["explanation"] = "Searched " + ", ".join(
            [*(f.get("countries") or ["all markets"]), *(f.get("tags_any") or []), *(f.get("types") or [])]
        )
        return json.dumps(f)
    if "investor emails" in system:
        data = json.loads(user)
        inv = data.get("investor", {})
        first = str(inv.get("name", "there")).split()[0]
        firm = inv.get("firm") or "your fund"
        att = data.get("attachments") or []
        body_text = (
            f"Dear {first},\n\n"
            f"I'm writing because {firm} backs technical founders early, and I think our work "
            "will interest you.\n\n"
            + (f"I've attached {', '.join(att)}.\n\n" if att else "")
            + "Would you have half an hour for a call next week?\n\nKind regards,"
        )
        return json.dumps({"subject": f"A short introduction for {firm}", "body": body_text})
    if "spreadsheet" in system:
        data = json.loads(user)
        tags = data.get("investor", {}).get("tags") or []
        return f"Likely: {tags[0]}" if tags else "Unknown"
    if "pitch deck" in system:
        data = json.loads(user)
        s = data["slides"][0]
        shape = s["shapes"][0] if s["shapes"] else {"shape": 0}
        return json.dumps(
            {"suggestions": [{"slide": s["slide"], "shape": shape["shape"], "text": "Applied Biosciences", "why": "shorter title"}]}
        )
    return "OK"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        out = json.dumps({"type": "message", "content": [{"type": "text", "text": answer(body)}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args: Any) -> None:
        return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8788)
    port = ap.parse_args().port
    print(f"fake Anthropic on http://localhost:{port}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
