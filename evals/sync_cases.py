"""Copy query_cases.json to web/assets/ for the chat UI."""

from __future__ import annotations

import shutil

from hindsight_pipeline_2.evals.paths import QUERY_CASES_PATH, QUERY_CASES_STATIC


def sync_query_cases_to_static() -> None:
    QUERY_CASES_STATIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUERY_CASES_PATH, QUERY_CASES_STATIC)


if __name__ == "__main__":
    sync_query_cases_to_static()
    print(f"Synced {QUERY_CASES_PATH} -> {QUERY_CASES_STATIC}")
