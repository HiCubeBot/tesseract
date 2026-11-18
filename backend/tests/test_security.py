"""Phase 6: Sicherheits-Header und Rate-Limits."""

from fastapi.testclient import TestClient

from tesseract.security import LIMITS, RateLimiter


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" not in r.headers  # nur für HTML


def test_csp_on_html(settings, tmp_path) -> None:
    from tesseract.app import create_app

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>x</title>")
    settings.static_dir = static
    with TestClient(create_app(settings)) as c:
        r = c.get("/")
        csp = r.headers["content-security-policy"]
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        # Einladungsseite behält ihre eigene Referrer-Policy
        assert c.get("/e/abc").headers["referrer-policy"] == "no-referrer"


def test_rate_limit_login(client: TestClient) -> None:
    limit = next(n for p, _, n in LIMITS if p == "/api/auth/login")
    for _ in range(limit):
        r = client.post("/api/auth/login", json={"username": "x", "password": "y"})
        assert r.status_code in (401, 429)
    r = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    # andere Bereiche sind nicht betroffen
    assert client.get("/api/health").status_code == 200


def test_rate_limiter_window() -> None:
    t = [0.0]
    lim = RateLimiter(clock=lambda: t[0])
    assert all(lim.allow(("a", "ip"), 2)[0] for _ in range(2))
    assert lim.allow(("a", "ip"), 2)[0] is False
    assert lim.allow(("a", "andere-ip"), 2)[0] is True
    t[0] = 61
    assert lim.allow(("a", "ip"), 2)[0] is True
