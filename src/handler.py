"""AWS Lambda entry‑point for the DraftKings fetch job.

The function simply delegates to ``pipeline.fetch.main`` which:
  • builds the endpoints defined in ``dk-api.yaml``
  • downloads each JSON payload
  • uploads the raw data to S3 at the key pattern documented there

Project layout (relative to the repo root ``src/``)::

    src/
    ├── config.yaml
    ├── dk-api.yaml
    ├── handler.py          # ← this file (Lambda handler)
    └── pipeline/
        └── fetch.py

Environment variables required (same as ``fetch.py``):
    BucketName  – S3 bucket to write into (required)
    S3Prefix    – optional path prefix (no leading /)
    Env         – environment name (e.g. dev / prod); default "dev"

Deploy notes
------------
* Package all files under ``src/`` plus third‑party dependencies
  (``requests``, ``boto3``, ``PyYAML``) into the Lambda layer or zip.
* Set the Lambda handler to ``handler.lambda_handler``.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Configure root logging – CloudWatch will capture stdout/stderr automatically
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    force=True,  # override any previous config
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Attempt to import the fetch routine
# ---------------------------------------------------------------------------
try:
    # Normal import when ``pipeline`` is importable as a namespace package.
    from pipeline.fetch import main as fetch_main  # type: ignore
except ModuleNotFoundError:
    # Fallback: add ``src/pipeline`` to sys.path and import the module directly.
    import sys
    from pathlib import Path

    pipeline_path = Path(__file__).resolve().parent / "pipeline"
    sys.path.append(str(pipeline_path))
    try:
        from fetch import main as fetch_main  # type: ignore  # noqa: E401
    except ModuleNotFoundError as exc:  # pragma: no cover – irrecoverable
        logger.error("Failed to import fetch.py: %s", exc)
        raise


def lambda_handler(
    event: Dict[str, Any], context: Any
) -> Dict[str, Any]:  # noqa: ANN401
    """AWS Lambda handler – download DraftKings data and push to S3.

    The *event* payload is ignored for now; all configuration is via
    environment variables and YAML files alongside the code.
    """
    logger.info("Lambda invocation started – fetching DraftKings endpoints …")

    try:
        fetch_main()
        logger.info("Fetch completed successfully.")
        return {"status": "ok"}

    except Exception as exc:  # broad catch to ensure Lambda returns JSON
        logger.error("Fetch failed: %s", exc)
        tb_str = "".join(traceback.format_exception(exc))
        logger.debug(tb_str)
        return {
            "status": "error",
            "error": str(exc),
        }
