"""Query probe — live HTTP check of the running Hey Kivi API.

A *probe* here means: read ``cases/query_cases.json``, POST each message to
``/chat`` (same path the chat UI uses), and save reply + trace + metrics to
``artifacts/reports/query_probe_<timestamp>.json``.

Unlike pytest (stub memory) or ``corpus_runner`` (in-process agent), probe
requires Docker + a restored snapshot/import and exercises the full FastAPI
stack::

    python -m hindsight_pipeline_2.evals.cli.query_probe --base-url http://localhost:8002
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

from hindsight_pipeline_2.evals.paths import CORPUS_REPORTS_DIR, QUERY_CASES_PATH
from hindsight_pipeline_2.evals.runners.expect import load_cases

CASES_PATH = QUERY_CASES_PATH
REPORT_DIR = CORPUS_REPORTS_DIR


def post_chat(base_url: str, user_id: str, message: str) -> dict[str, Any]:
    payload = json.dumps({"message": message, "user_id": user_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_probe(
    *,
    base_url: str,
    user_id: str,
    cases_path: Path,
    report_dir: Path,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            data = post_chat(base_url, user_id, case["message"])
            results.append(
                {
                    "id": case["id"],
                    "message": case["message"],
                    "reply": data.get("reply"),
                    "trace": data.get("trace"),
                    "metrics": data.get("metrics"),
                    "ok": True,
                }
            )
        except urllib.error.URLError as exc:
            results.append(
                {
                    "id": case["id"],
                    "message": case["message"],
                    "ok": False,
                    "error": str(exc),
                }
            )
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_url": base_url,
        "user_id": user_id,
        "total": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S+00-00")
    out = report_dir / f"query_probe_{stamp}.json"
    latest = report_dir / "query_probe.latest.json"
    body = json.dumps(report, indent=2, default=str)
    out.write_text(body, encoding="utf-8")
    latest.write_text(body, encoding="utf-8")
    report["report_path"] = str(out)
    report["latest_path"] = str(latest)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe /chat with query_cases.json")
    parser.add_argument("--base-url", default="http://localhost:8002")
    parser.add_argument("--user-id", default="golden_goose_eval_user")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args(argv)
    report = run_probe(
        base_url=args.base_url,
        user_id=args.user_id.strip(),
        cases_path=args.cases,
        report_dir=args.report_dir,
    )
    print(json.dumps({"report_path": report["report_path"], "ok": report["ok"], "failed": report["failed"]}, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
