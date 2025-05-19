#!/usr/bin/env python3
"""fetch_dk.py

Pull DraftKings endpoints defined in ``dk-api.yaml`` and save the raw
JSON **directly to Amazon S3** instead of a local ``data/`` folder.

Now supports routing every HTTP request through an **Oxylabs residential
proxy** when the ``OXYLABS_*`` environment variables are present.

---
Project layout (relative to the repo root ``src/``)
```
src/
├── config.yaml          # request settings (headers, sleep windows…)
├── dk-api.yaml          # league → category → subCategory ID map
└── pipeline/
    └── fetch_dk.py      # ← this script
```

S3 destination
--------------
The object key is built from three **environment variables** plus the
slugified league/category/subCategory names:

```
$BucketName/$S3Prefix/$Env/raw/$league/$category/$subcategory/$timestamp.json
```

* ``BucketName`` – **required** (e.g. ``my‑bucket``)
* ``S3Prefix``  – optional (e.g. ``project‑x``); empty → no prefix
* ``Env``       – optional (default ``dev``)

Example URI:
```
s3://my-bucket/project-x/prod/raw/mlb/total-bases-ou/rbis-ou/20250506-160233.json
```

Print statements announce every endpoint hit, object upload, and sleep
interval.

Dependencies
~~~~~~~~~~~~
```bash
pip install requests pyyaml boto3
```
AWS credentials must be available to ``boto3`` via the usual mechanisms
( ``AWS_PROFILE``, environment vars, EC2/IAM role, etc.).
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import boto3
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Paths (script sits in src/pipeline/, so two parents up is src/)
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent
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
    """Return a Requests session pre‑configured with headers, retry, timeout,
    and **optionally** an Oxylabs proxy. If the four ``OXYLABS_*`` environment
    variables (host, port, user, password) are present, all requests are
    routed through the residential gateway using the country code specified in
    ``OXYLABS_COUNTRY`` (defaults to ``US``).
    """

    session = requests.Session()
    session.headers.update(cfg["headers"])

    # -- Optional Oxylabs proxy -------------------------------------------
    proxy_host = os.getenv("OXYLABS_HOST")
    proxy_port = os.getenv("OXYLABS_PORT")
    proxy_user = os.getenv("OXYLABS_USER")
    proxy_password = os.getenv("OXYLABS_PASSWORD")
    proxy_cc = os.getenv("OXYLABS_COUNTRY", "US")

    if all((proxy_host, proxy_port, proxy_user, proxy_password)):
        proxy_entry = (
            f"http://customer-{proxy_user}-cc-{proxy_cc}:"
            f"{proxy_password}@{proxy_host}:{proxy_port}"
        )
        print(f"Proxy entry: {proxy_entry}")
        session.proxies.update({"http": proxy_entry, "https": proxy_entry})
        print("[fetch] Oxylabs proxy enabled →", proxy_entry.split("@")[-1])
    else:
        print("[fetch] Oxylabs proxy **not** configured – going direct")

    # -- Retry & timeout ----------------------------------------------------
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


def utc_stamp() -> str:
    """Return a compact UTC timestamp suitable for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


_slug_regex = re.compile(r"[^0-9a-z]+")
_remove_chars = str.maketrans("", "", "()/-")


def slugify(name: str) -> str:
    """Convert *name* to a lowercase, filesystem‑/URL‑safe slug.

    1. Lower‑case.
    2. Remove parentheses, slashes, hyphens.
    3. Replace any run of non‑alphanumerics with a dash.
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
        sys.exit("config.yaml or dk-api.yaml missing next to fetch_dk.py")

    # ---- S3 settings -------------------------------------------------------
    bucket_name = os.getenv("BUCKET_NAME")
    if not bucket_name:
        sys.exit("Environment variable 'BucketName' is required for S3 upload")

    s3_prefix = os.getenv("S3_PREFIX", "scraper-dk").strip("/")  # may be empty
    env_name = os.getenv("Env", "dev").strip("/")

    def build_key(*parts: str) -> str:
        """Join parts with '/' while skipping empties."""
        return "/".join(p.strip("/") for p in (s3_prefix, env_name, *parts) if p)

    s3 = boto3.client("s3")

    # ---- HTTP settings -----------------------------------------------------
    cfg = load_yaml(CONFIG_PATH)["requests"]
    api_map = load_yaml(API_PATH)

    base_url: str = cfg["baseUrl"].rstrip("/")
    sleep_min: float = cfg.get("sleepSecondsMin", 3)
    sleep_max: float = cfg.get("sleepSecondsMax", 10)

    session = build_session(cfg)

    # Only MLB is defined for now; extend easily for others
    league_name = "mlb"
    sport_cfg = api_map[league_name]
    event_group_id = sport_cfg["eventGroupId"]

    for category_name, cat_data in sport_cfg["categories"].items():
        category_id = cat_data["categoryId"]
        cat_slug = slugify(category_name)

        # Handle both spellings: subCategories vs. subcategories
        subcats_key = next(
            k for k in ("subCategories", "subcategories") if k in cat_data
        )

        for subcat_name, subcat_data in cat_data[subcats_key].items():
            # subcat_data may be int or mapping containing the id
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
                delay = random.uniform(sleep_min, sleep_max)
                print(f"   ⏸ Sleeping {delay:.1f}s...")
                time.sleep(delay)
                continue

            key = build_key(
                "raw",
                league_name,
                cat_slug,
                subcat_slug,
                f"{utc_stamp()}.json",
            )
            print(f"S3 prefix: {s3_prefix}")
            print(f"Key: {key}")

            try:
                s3.put_object(
                    Bucket=bucket_name,
                    Key=key,
                    Body=json.dumps(resp.json()).encode("utf-8"),
                    ContentType="application/json",
                )
                print(f"   ✔ Uploaded to s3://{bucket_name}/{key}")
            except Exception as exc:  # broad except OK for top‑level logging
                print(f"   ! S3 upload failed: {exc}")
                delay = random.uniform(sleep_min, sleep_max)
                print(f"   ⏸ Sleeping {delay:.1f}s...")
                time.sleep(delay)
                continue

            delay = random.uniform(sleep_min, sleep_max)
            print(f"   ⏸ Sleeping {delay:.1f}s...")
            time.sleep(delay)


if __name__ == "__main__":
    main()
