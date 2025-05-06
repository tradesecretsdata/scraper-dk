#!/usr/bin/env python3
"""fetch_dk.py

Loop through DraftKings MLB endpoints defined in ``dk-api.yaml`` and store
the raw JSON.

Project layout expected:

src/
├── config.yaml
├── dk-api.yaml
├── data/                      # auto‑created if missing
└── pipeline/
    └── fetch_dk.py            # ← this file

Naming rules for the output path
--------------------------------
* Every *category* and *sub‑category* name is converted to a **slug**:
  * lower‑cased
  * parentheses, slashes, and hyphens are removed
  * sequences of whitespace are replaced with a single dash
  * all other non‑alphanumeric characters are stripped
  Example: ``"Total Runs (3-Way)" → "total-runs-3way"``
* Each response is written to:

    data/<category‑slug>/<subcat‑slug>/<UTC‑timestamp>.json

* Print statements announce requests, directory creation, saves, and the
  sleep interval.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# fetch_dk.py sits in src/pipeline/, so two parents up is src/
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
CONFIG_PATH: Path = BASE_DIR / "config.yaml"
API_PATH: Path = BASE_DIR / "dk-api.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML into a Python dict."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_session(cfg: Dict[str, Any]) -> requests.Session:
    """Return a Requests session pre‑configured with headers, retry & timeout."""
    session = requests.Session()
    session.headers.update(cfg["headers"])

    retries = Retry(
        total=cfg.get("retriesMax", 3),
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    timeout = cfg.get("timeout", 10)

    # Wrap the original request method so we don't repeat `timeout=` everywhere
    original_request = session.request

    def request_with_timeout(*args, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", timeout)
        return original_request(*args, **kwargs)

    session.request = request_with_timeout  # type: ignore[assignment]
    return session


def ensure_dir(path: Path) -> None:
    """Create *path* (including parents) if it doesn’t already exist."""
    if not path.exists():
        print(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)


def utc_stamp() -> str:
    """Return a compact UTC timestamp suitable for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


_slug_regex = re.compile(r"[^0-9a-z]+")
_remove_chars = str.maketrans("", "", "()/-")


def slugify(name: str) -> str:
    """Return *name* converted to the filesystem‑safe slug rules.

    1. Lower‑case.
    2. Remove parentheses, slashes, and hyphens.
    3. Replace any run of non‑alphanumerics with a single dash.
    4. Strip leading/trailing dashes.
    """
    cleaned = name.lower().translate(_remove_chars)
    cleaned = _slug_regex.sub("-", cleaned).strip("-")
    return cleaned


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def main() -> None:
    if not CONFIG_PATH.exists() or not API_PATH.exists():
        sys.exit("config.yaml or dk-api.yaml missing next to data/ directory")

    cfg = load_yaml(CONFIG_PATH)["requests"]
    api_map = load_yaml(API_PATH)

    ensure_dir(DATA_DIR)

    base_url: str = cfg["baseUrl"].rstrip("/")
    sleep_min: float = cfg.get("sleepSecondsMin", 3)
    sleep_max: float = cfg.get("sleepSecondsMax", 10)

    session = build_session(cfg)

    sport_cfg = api_map["mlb"]
    event_group_id = sport_cfg["eventGroupId"]

    for category_name, cat_data in sport_cfg["categories"].items():
        category_id = cat_data["categoryId"]
        cat_slug = slugify(category_name)

        # Handle both spellings: subCategories vs. subcategories
        subcats_key = next(
            k for k in ("subCategories", "subcategories") if k in cat_data
        )

        for subcat_name, subcat_data in cat_data[subcats_key].items():
            # value may be an int or a mapping containing the id
            if isinstance(subcat_data, dict):
                subcat_id = subcat_data.get("subCategoryId") or subcat_data.get(
                    "subcategoryId"
                )
            else:
                subcat_id = subcat_data

            subcat_slug = slugify(subcat_name)

            url = (
                f"{base_url}/leagues/{event_group_id}/categories/"
                f"{category_id}/subcategories/{subcat_id}"
            )
            print(f"--> GET {url}")

            try:
                resp = session.get(url)
                resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"   ! Request failed: {exc}")
                continue

            dest_dir = DATA_DIR / cat_slug / subcat_slug
            ensure_dir(dest_dir)

            file_path = dest_dir / f"{utc_stamp()}.json"
            with file_path.open("w", encoding="utf-8") as fh:
                json.dump(resp.json(), fh)
            print(f"   ✔ Saved to {file_path}")

            delay = random.uniform(sleep_min, sleep_max)
            print(f"   ⏸ Sleeping {delay:.1f}s...")
            time.sleep(delay)


if __name__ == "__main__":
    main()
