"""Doc / config drift guard — fail loudly when the docs stop matching the code.

Run via ``make check-docs`` (also wired into ``make check``). Two cheap, deterministic
checks that turn "keep the docs in sync" from a hope into an assertion:

1. **Env-var parity** — every environment variable the code reads (``os.environ[...]``
   / ``os.environ.get(...)``, plus ``*_ENV = "..."`` constants) must be present in
   ``.env.example``. This is exactly the drift that shipped once already
   (``BLOB_STORAGE_*`` / ``CF_AI_MODEL_*`` were missing).

2. **Forbidden drift markers** — a short, high-precision list of strings that should
   never appear in any Markdown doc because they name a stack we do not use
   (e.g. ``anthropic_client``, ``r2_client``). The patterns are deliberately specific
   so legitimate guidance ("MinIO, NOT R2") and citations ("Anthropic's eval paper")
   do not trip them.

Exit code 0 = clean, 1 = drift found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# os.environ["X"] / os.environ.get("X", ...) — var names may contain digits (CF_D1_...).
_ENV_READ = re.compile(r"""os\.environ(?:\.get)?\s*[(\[]\s*["']([A-Z][A-Z0-9_]*)["']""")
# Indirect reads via a constant, e.g. AUDIT_HMAC_KEY_ENV = "AUDIT_HMAC_KEY".
_ENV_CONST = re.compile(r"""_ENV\s*[:=][^"'\n]*["']([A-Z][A-Z0-9_]*)["']""")

# High-precision drift markers: regex -> why it is wrong. Keep these unambiguous so
# they never match legitimate "NOT R2" guidance or research citations.
_FORBIDDEN: dict[str, str] = {
    r"anthropic_client": "all LLM calls go through cf_ai_client (CF Workers AI), not Anthropic",
    r"r2_client": "blob storage is MinIO (minio_client) — R2 was skipped",
    r"python -m sentinel\.": "no `sentinel.` module namespace (src-layout: from <pkg> import ...)",
    r"[Cc]laude-as-judge": "the LLM judge is CF Workers AI Llama, not Claude",
}

_SKIP_DIRS = (".venv", ".git", "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache")


def _iter_files(suffix: str) -> list[Path]:
    """Return repo files with ``suffix``, skipping vendored / cache dirs."""
    return [
        path
        for path in ROOT.rglob(f"*{suffix}")
        if not any(part in _SKIP_DIRS for part in path.parts)
    ]


def code_env_vars() -> set[str]:
    """Every env var the application code reads (packages/, excluding tests)."""
    found: set[str] = set()
    for py in _iter_files(".py"):
        if "tests" in py.parts or "packages" not in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        found.update(_ENV_READ.findall(text))
        found.update(_ENV_CONST.findall(text))
    return found


def env_example_keys() -> set[str]:
    """Keys defined in ``.env.example`` (``KEY=...`` lines, ignoring comments)."""
    keys: set[str] = set()
    for raw in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def check_env_parity(errors: list[str]) -> None:
    """Append an error for every code-read env var missing from ``.env.example``."""
    missing = sorted(code_env_vars() - env_example_keys())
    if missing:
        errors.append(f".env.example is missing vars the code reads: {', '.join(missing)}")


def check_forbidden_markers(errors: list[str]) -> None:
    """Append an error for every forbidden drift marker found in a Markdown doc."""
    for md in _iter_files(".md"):
        text = md.read_text(encoding="utf-8")
        for pattern, why in _FORBIDDEN.items():
            if re.search(pattern, text):
                rel = md.relative_to(ROOT)
                errors.append(f"{rel}: contains '{pattern}' — {why}")


def main() -> int:
    """Run both checks and report. Returns a process exit code."""
    errors: list[str] = []
    check_env_parity(errors)
    check_forbidden_markers(errors)

    if errors:
        print("✗ check-docs FAILED — docs/config drifted from the code:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("✓ check-docs passed: .env.example matches the code; no drift markers in docs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
