"""Tests for frontend/build.sh URL validation and safe config generation."""

import os
import subprocess
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
BUILD_SCRIPT = FRONTEND_DIR / "build.sh"


def _run_build(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("API_BASE_URL", None)
    env.pop("CF_PAGES", None)
    env.update(env_overrides)
    return subprocess.run(
        ["sh", str(BUILD_SCRIPT)],
        cwd=str(FRONTEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_local_dev_build_uses_default_fallback() -> None:
    """Local dev build without API_BASE_URL uses http://127.0.0.1:8000/api/v1."""
    res = _run_build({})
    assert res.returncode == 0
    runtime_cfg = (FRONTEND_DIR / "dist" / "js" / "runtime-config.js").read_text()
    assert 'API_BASE_URL: "http://127.0.0.1:8000/api/v1",' in runtime_cfg
    assert (FRONTEND_DIR / "dist" / "index.html").is_file()
    assert (FRONTEND_DIR / "dist" / "_redirects").is_file()


def test_production_build_with_https_url_succeeds() -> None:
    """Production build (CF_PAGES=1) with HTTPS API URL and path succeeds."""
    res = _run_build(
        {
            "CF_PAGES": "1",
            "API_BASE_URL": "https://college-api.onrender.com/api/v1",
        }
    )
    assert res.returncode == 0
    runtime_cfg = (FRONTEND_DIR / "dist" / "js" / "runtime-config.js").read_text()
    assert 'API_BASE_URL: "https://college-api.onrender.com/api/v1",' in runtime_cfg


def test_production_build_rejects_http_url() -> None:
    """Production build (CF_PAGES=1) rejects non-HTTPS API_BASE_URL."""
    res = _run_build(
        {
            "CF_PAGES": "1",
            "API_BASE_URL": "http://college-api.onrender.com/api/v1",
        }
    )
    assert res.returncode != 0
    assert "https://" in res.stderr


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "not-a-url",
        'https://api.example.com";alert(1);//',
        "https://api.example.com/api v1",
        "javascript:alert(1)",
        "https://user:pass@api.example.com/api/v1",
    ],
)
def test_build_rejects_malicious_and_malformed_urls(bad_url: str) -> None:
    """Build script rejects empty, whitespace, injection, and malformed URLs."""
    res = _run_build({"CF_PAGES": "1", "API_BASE_URL": bad_url})
    assert res.returncode != 0
