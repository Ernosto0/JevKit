#!/usr/bin/env python3
"""Phase 1: verify JevKit's timeout handling against the real Jev API.

`scripts/verify_jev_api.py` never observed a real timeout -- every call
finished in under a second. This script forces one, at both the transport
layer (`httpx`, directly) and through the public SDK (`DecisionClient`),
so the retry/failure path in `docs/jev-api-notes.md` is backed by a live
observation rather than mocks only.

It does NOT attempt to trigger 429 or 5xx: doing so on purpose means
deliberately exceeding TypeSafe's usage limits, which section 2.3(j) of
the Master Customer Agreement (see "Terms of use" in jev-api-notes.md)
prohibits. Those two remain documented-but-unobserved by policy, not by
oversight.

    python scripts/verify_timeout_behavior.py [--out DIR]

Reads JEV_API_KEY from the environment or .env. Spends a few fractions of
a cent (one real request is allowed to complete during the read-timeout
probe, and two more during the end-to-end SDK probe).
"""

from __future__ import annotations

import argparse
import asyncio
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

PAYLOAD = {
    "state": "Hi, I was charged twice for my subscription this month.",
    "model": MODEL,
    "questions": {"urgent": {"type": "noul", "instructions": "Is this issue urgent?"}},
}


def probe_transport_timeouts(base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    """Force a real `httpx.TimeoutException` two ways: connect and read."""
    results: dict[str, Any] = {}

    with httpx.Client(base_url=base_url, headers=headers, timeout=0.01) as client:
        started = time.perf_counter()
        try:
            client.post(ENDPOINT, json=PAYLOAD)
            results["connect_timeout"] = {"observed": False}
        except httpx.TimeoutException as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            results["connect_timeout"] = {
                "observed": True,
                "exception": type(exc).__name__,
                "elapsed_ms": elapsed,
            }
            print(f"  connect timeout       {type(exc).__name__:16} {elapsed:>8.1f} ms")

    read_timeout = httpx.Timeout(connect=5.0, read=0.1, write=5.0, pool=5.0)
    with httpx.Client(base_url=base_url, headers=headers, timeout=read_timeout) as client:
        started = time.perf_counter()
        try:
            client.post(ENDPOINT, json=PAYLOAD)
            results["read_timeout"] = {"observed": False}
        except httpx.TimeoutException as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            results["read_timeout"] = {
                "observed": True,
                "exception": type(exc).__name__,
                "elapsed_ms": elapsed,
            }
            print(f"  read timeout           {type(exc).__name__:16} {elapsed:>8.1f} ms")

    return results


async def probe_sdk_timeout() -> dict[str, Any]:
    """Drive an unreasonably short `DecisionPolicy.timeout_seconds` through the
    public `DecisionClient`, so the retry loop and typed-error mapping in
    `jevkit.client.engine` run against a live timeout, not a mock."""
    from jevkit import DecisionClient, DecisionPolicy, DecisionTask, Noul

    task = DecisionTask(
        name="phase1-timeout-probe",
        questions={"urgent": Noul(instructions="Is this issue urgent?")},
    )
    policy = DecisionPolicy(primary_provider="jev", timeout_seconds=0.05, max_retries=1)
    client = DecisionClient.from_env(policy=policy)
    async with client:
        result, trace = await client.decide_with_trace(
            state={"message": PAYLOAD["state"]}, task=task
        )

    summary = list(trace.summary())
    for line in summary:
        print(f"    {line}")

    return {
        "execution_status": result.execution_status.value,
        "accepted": result.accepted,
        "trace_summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Jev timeout handling against the live API")
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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "jevkit-phase1-verify",
    }

    print("Transport-level timeouts (raw httpx, bypassing the JevKit adapter):")
    transport = probe_transport_timeouts(base_url, headers)

    print("\nEnd-to-end timeout through DecisionClient (real retry + typed-error mapping):")
    sdk = asyncio.run(probe_sdk_timeout())

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "timeout_probes.json"
    out_file.write_text(
        json.dumps({"transport": transport, "sdk": sdk}, indent=2), encoding="utf-8"
    )
    print(f"\nRaw results -> {out_file}")

    ok = transport["connect_timeout"]["observed"] and transport["read_timeout"]["observed"]
    ok = ok and sdk["execution_status"] == "failed"
    if not ok:
        print("\nExpected a real timeout at every layer; one did not occur.", file=sys.stderr)
        return 1

    print("\nReal timeouts observed and correctly mapped at every layer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
