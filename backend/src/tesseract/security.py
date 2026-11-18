"""Phase 6: Sicherheits-Header und Rate-Limits für den Controller.

- Jede Antwort bekommt Schutz-Header; HTML zusätzlich eine strenge Content-Security-Policy
  (alles vom eigenen Server, keine fremden Skripte, Schriften oder Frames).
- Öffentliche Endpunkte (Einladungsseite, Beitritt von Agents, Anmeldung, /metrics) sind pro
  IP begrenzt. Fehlversuche bremsen zusätzlich die vorhandenen Sperren (LoginThrottle).
"""

import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    # Svelte setzt Stile direkt am Element (style="…")
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)
HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]

# (Präfix, nur POST?, Anfragen pro Minute)
LIMITS: list[tuple[str, bool, int]] = [
    ("/api/auth/login", True, 20),
    ("/api/enroll/", False, 60),
    ("/e/", False, 60),
    ("/api/agent/join", False, 30),
    ("/metrics", False, 120),
]
WINDOW = 60.0


class RateLimiter:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, key: tuple[str, str], limit: int) -> tuple[bool, int]:
        now = self.clock()
        q = self.hits[key]
        while q and q[0] <= now - WINDOW:
            q.popleft()
        if len(q) >= limit:
            return False, max(1, int(WINDOW - (now - q[0])) + 1)
        q.append(now)
        # gelegentlich aufräumen, damit der Speicher nicht wächst
        if len(self.hits) > 10_000:
            for k in [k for k, v in self.hits.items() if not v]:
                del self.hits[k]
        return True, 0


class SecurityMiddleware:
    """Reines ASGI – funktioniert auch mit Long-Polling und Streaming-Antworten."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        client = scope.get("client") or ("?", 0)
        for prefix, post_only, limit in LIMITS:
            if path.startswith(prefix) and (not post_only or method == "POST"):
                ok, retry = self.limiter.allow((prefix, client[0]), limit)
                if not ok:
                    await _too_many(send, retry)
                    return
                break

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in HEADERS if k not in present]
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if ctype.startswith(b"text/html") and b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", CSP.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _too_many(send: Send, retry: int) -> None:
    body = '{"detail":"Zu viele Anfragen – bitte kurz warten"}'.encode()
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry).encode()),
                *HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
