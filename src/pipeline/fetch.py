#!/usr/bin/env python3
"""Download DraftKings endpoints and *return* the JSON instead of uploading.

Print statements were added to:
  • log each successful GET with its category / sub-category
  • announce the delay before sleeping
"""
from __future__ import annotations

import os
import random
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
API_PATH = BASE_DIR / "dk-api.yaml"


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _slugify(s: str) -> str:
    s = s.lower()
    s = s.replace("&", "and").replace("'", "")
    # collapse O/U abbreviation
    s = re.sub(r"\bo\s*/\s*u\b", "ou", s, flags=re.I)
    # replace separators with space
    s = re.sub(r"[\/\-]", " ", s)
    # collapse whitespace, then underscore-join
    s = re.sub(r"\s+", " ", s).strip().replace(" ", "_")
    # strip any stray chars
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def _build_session(cfg: Mapping[str, Any]) -> requests.Session:
    sess = requests.Session()
    sess.headers.update(cfg["headers"])

    retries = Retry(
        total=cfg.get("retriesMax", 3),
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    sess.mount("https://", HTTPAdapter(max_retries=retries))

    # Optional Oxylabs proxy
    if os.getenv("OXYLABS_USERNAME") and os.getenv("OXYLABS_PASSWORD"):
        host = os.getenv("OXYLABS_HOST", "pr.oxylabs.io")
        port = os.getenv("OXYLABS_PORT", "7777")
        proxy = f"http://{os.environ['OXYLABS_USERNAME']}:{os.environ['OXYLABS_PASSWORD']}@{host}:{port}"
        sess.proxies = {"http": proxy, "https": proxy}

    return sess


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_main() -> Dict[str, Dict[str, Any]]:
    """Return every sub-category payload as a dict keyed ``cat/subcat``."""
    if not CONFIG_PATH.exists() or not API_PATH.exists():
        sys.exit("❌ config.yaml or dk-api.yaml missing – abort")

    cfg = _load_yaml(CONFIG_PATH)["requests"]
    api_map = _load_yaml(API_PATH)
    base_url: str = cfg["baseUrl"].rstrip("/")

    sleep_min = cfg.get("sleepSecondsMin", 3)
    sleep_max = cfg.get("sleepSecondsMax", 10)

    sess = _build_session(cfg)

    league_name = "mlb"
    if league_name not in api_map:
        raise KeyError(f"{league_name!r} not found in dk-api.yaml")

    payloads: dict[str, dict[str, Any]] = {}
    # Track endpoints that failed (HTTP error) or returned an empty payload
    failed_endpoints: list[str] = []
    league = api_map[league_name]
    event_group_id = league["eventGroupId"]

    for category_name, cat_data in league["categories"].items():
        category_id = cat_data["categoryId"]
        cat_slug = _slugify(category_name)

        subcats_key = next(
            k for k in ("subCategories", "subcategories") if k in cat_data
        )

        for subcat_name, subcat_data in cat_data[subcats_key].items():
            subcat_id = (
                subcat_data.get("subCategoryId")
                if isinstance(subcat_data, dict)
                else subcat_data
            )
            subcat_slug = _slugify(subcat_name)

            url = (
                f"{base_url}/leagues/{event_group_id}/categories/"
                f"{category_id}/subcategories/{subcat_id}"
            )

            delay = random.uniform(sleep_min, sleep_max)

            try:
                r = sess.get(url)
                r.raise_for_status()

                data = r.json()

                # Determine if the payload contains usable data. We treat it as
                # *empty* when none of the common DraftKings keys are present
                # or all of them are empty sequences.
                has_selections = bool(data.get("selections"))
                has_events = bool(data.get("events"))
                has_markets = bool(data.get("markets"))

                if not (has_selections or has_events or has_markets):
                    # 200 OK, but nothing to work with → mark as failed
                    print(f"❌ 200 OK – empty payload: {category_name} / {subcat_name}")
                    failed_endpoints.append(f"{category_name} / {subcat_name} (empty)")
                else:
                    print(f"✅ GET OK: {category_name} / {subcat_name}")

                # Store payload regardless so downstream steps keep the full map
                payloads[f"{cat_slug}/{subcat_slug}"] = data

            except requests.RequestException as exc:
                print(f"❌ Request failed: {category_name} / {subcat_name} – {exc}")
                failed_endpoints.append(f"{category_name} / {subcat_name} (HTTP error)")
                print(f"sleeping for {delay:.1f} seconds")
                time.sleep(delay)
                continue

            print(f"sleeping for {delay:.1f} seconds")
            time.sleep(delay)

    # ------------------------------------------------------------------
    # Final summary of any failures / empty responses
    # ------------------------------------------------------------------
    if failed_endpoints:
        print("\n❌ Summary – endpoints with errors or no data:")
        for ep in failed_endpoints:
            print(f"   ❌ {ep}")
    else:
        print("\n✅ All endpoints returned data.")

    return payloads
