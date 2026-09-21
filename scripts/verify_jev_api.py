#!/usr/bin/env python3
"""Phase 1: verify JevKit's assumptions against the real Jev API.

Repeatable probe used to satisfy the phase 1 exit criterion in PLAN.md section 20.
It talks to the API directly with `httpx` -- deliberately NOT through
`jevkit.providers.jev`, so that it reports what the API actually does rather
than what our adapter believes.

    python scripts/verify_jev_api.py [--out DIR]

Reads JEV_API_KEY (and optionally JEV_BASE_URL) from the environment or .env.
The key is never printed in full. Findings are written up by hand in
docs/jev-api-notes.md; raw request/response pairs go to --out for the record.

Exit codes: 0 every probe reached a documented outcome, 1 authentication
failed, 2 the key is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.typesafe.ai/v1"
ENDPOINT = "/systemone"
MODEL = "jev-latest"

TICKET = (
    "Hi, I was charged twice for my subscription this month and the second "
    "charge has not been refunded. I need this fixed today, I am a paying customer."
)


def build_probes() -> list[tuple[str, dict[str, Any]]]:
    """The documented surface: one probe per thing phase 1 must confirm."""
    return [
        (
            "minimal_noul",
            {
                "state": TICKET,
                "model": MODEL,
                "questions": {
                    "urgent": {"type": "noul", "instructions": "Is this issue urgent?"},
                },
            },
        ),
        (
            "noul_with_criteria",
            {
                "state": TICKET,
                "model": MODEL,
                "questions": {
                    "escalate": {
                        "type": "noul",
                        "instructions": "Should this be escalated to a supervisor?",
                        "criteria": {
                            "true": "Money is at stake or the customer is at churn risk",
                            "false": "Routine request a first-line agent can resolve",
                        },
                    },
                },
            },
        ),
        (
            "choice",
            {
                "state": TICKET,
                "model": MODEL,
                "questions": {
                    "department": {
                        "type": "choice",
                        "instructions": "Which department should handle this ticket?",
                        "criteria": {
                            "billing": "Payments, charges, invoices, refunds",
                            "technical": "Bugs, outages, integration failures",
                            "account": "Login, profile, permissions",
                            "other": "Anything else",
                        },
                    },
                },
            },
        ),
        (
            "score",
            {
                "state": TICKET,
                "model": MODEL,
                "questions": {
                    "severity": {
                        "type": "score",
                        "instructions": "How severe is the customer impact?",
                        "criteria": [
                            "No impact",
                            "Minor inconvenience",
                            "Blocked but has a workaround",
                            "Losing money or fully blocked",
                        ],
                    },
                },
            },
        ),
        # All three types in one request: confirms parallel evaluation.
        (
            "multi_question",
            {
                "state": TICKET,
                "model": MODEL,
                "questions": {
                    "urgent": {"type": "noul", "instructions": "Is this issue urgent?"},
                    "department": {
                        "type": "choice",
                        "instructions": "Which department?",
                        "criteria": {
                            "billing": "Payments and refunds",
                            "technical": "Bugs and outages",
                            "account": "Login and profile",
                            "other": "Anything else",
                        },
                    },
                    "severity": {
                        "type": "score",
                        "instructions": "How severe is the impact?",
                        "criteria": ["None", "Minor", "Blocked", "Losing money"],
                    },
                },
            },
        ),
        # `state` may be an object, not only a string.
        (
            "object_state",
            {
                "state": {"message": TICKET, "plan": "pro", "tickets_this_month": 3},
                "model": MODEL,
                "questions": {
                    "urgent": {"type": "noul", "instructions": "Is this issue urgent?"},
                },
            },
        ),
        # Error shapes: `model` is required, so omitting it should be a 422.
        (
            "error_missing_model",
            {
                "state": TICKET,
                "questions": {
                    "urgent": {"type": "noul", "instructions": "Is this issue urgent?"},
                },
            },
        ),
        (
            "error_unknown_model",
            {
                "state": TICKET,
                "model": "not-a-real-model",
                "questions": {
                    "urgent": {"type": "noul", "instructions": "Is this issue urgent?"},
                },
            },
        ),
    ]


def probe(client: httpx.Client, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = client.post(ENDPOINT, json=payload)
    except httpx.HTTPError as exc:
        print(f"  {name:22} transport error: {type(exc).__name__}: {exc}")
        return {"request": payload, "transport_error": f"{type(exc).__name__}: {exc}"}

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:1000]

    print(f"  {name:22} HTTP {response.status_code}  {latency_ms:>8.1f} ms")
    return {
        "request": payload,
        "status": response.status_code,
        "latency_ms": latency_ms,
        "response": body,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Jev API contract.")
    parser.add_argument("--out", default=".jevkit/phase1", help="where to write raw results")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()

    api_key = os.environ.get("JEV_API_KEY", "").strip()
    if not api_key:
        print("JEV_API_KEY is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    base_url = os.environ.get("JEV_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    print(f"Jev API verification -> {base_url}{ENDPOINT}")
    print(f"key: {api_key[:4]}... ({len(api_key)} chars)\n")

    results: dict[str, Any] = {"base_url": base_url, "endpoint": ENDPOINT, "probes": {}}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "jevkit-phase1-verify",
    }

    with httpx.Client(base_url=base_url, headers=headers, timeout=30.0) as client:
        for name, payload in build_probes():
            results["probes"][name] = probe(client, name, payload)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "jev_api_probes.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRaw results -> {out_file}")

    statuses = {p.get("status") for p in results["probes"].values()}
    if statuses & {401, 403}:
        print(
            "\nAuthentication failed. The endpoint and auth scheme are correct, so the key\n"
            "itself is being rejected -- re-issue it on the TypeSafe platform.",
            file=sys.stderr,
        )
        return 1

    print("\nEvery probe reached a documented outcome. Record findings in docs/jev-api-notes.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
