#!/usr/bin/env python3
"""snapshot_funnel.py — capture the current outreach funnel + slash-usage baseline.

Usage:
    python scripts/snapshot_funnel.py [--days 30] [--out docs/baseline_2026_05_01.json]

Reads directly from the auth Postgres (DATABASE_URL env var) and writes a JSON
snapshot.  Run once before the workspace refactor to establish the "before" numbers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Allow running from the repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))


def _fetch_funnel(days: int) -> dict:
    from auth_db import transaction

    with transaction() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM outreach_log
            WHERE created_at >= NOW() - (%s || ' days')::INTERVAL
            GROUP BY status
            """,
            (str(days),),
        )
        rows = cur.fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = int(r["cnt"])

    draft_count = counts.get("draft", 0)
    sent_count = counts.get("sent", 0)
    replied_count = counts.get("replied", 0) + counts.get("meeting", 0)
    signed_count = counts.get("cda_signed", 0) + counts.get("ts_signed", 0)
    dropped_count = counts.get("passed", 0) + counts.get("dead", 0)

    def _rate(n: int, d: int) -> float:
        return round(n / d, 4) if d else 0.0

    return {
        "draft_count": draft_count,
        "sent_count": sent_count,
        "replied_count": replied_count,
        "signed_count": signed_count,
        "dropped_count": dropped_count,
        "draft_to_sent_rate": _rate(sent_count, draft_count + sent_count),
        "sent_to_replied_rate": _rate(replied_count, sent_count),
        "replied_to_signed_rate": _rate(signed_count, replied_count),
        "window_days": days,
    }


def _fetch_slash_usage(days: int) -> list[dict]:
    from auth_db import transaction

    with transaction() as cur:
        cur.execute(
            """
            SELECT slug, COUNT(*) AS cnt
            FROM report_history
            WHERE created_at >= NOW() - (%s || ' days')::INTERVAL
            GROUP BY slug
            ORDER BY cnt DESC
            """,
            (str(days),),
        )
        rows = cur.fetchall()

    return [{"slug": r["slug"], "count": int(r["cnt"])} for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot outreach funnel baseline")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "..", "docs", "baseline_2026_05_01.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to DB… (window: {args.days} days)")
    funnel = _fetch_funnel(args.days)
    slash = _fetch_slash_usage(args.days)

    snapshot = {
        "snapshot_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": args.days,
        "funnel": funnel,
        "slash_usage": slash,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Baseline snapshot written to {out_path}")
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
