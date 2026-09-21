# Jev API notes

**Status: VERIFIED AGAINST THE LIVE API.** Roadmap phase 1 record. Last updated 2026-09-21.

Every claim below marked ✅ was observed in a real request/response, not read off a doc page.
Raw pairs: `.jevkit/phase1/jev_api_probes.json` (gitignored), regenerate with
[`scripts/verify_jev_api.py`](../scripts/verify_jev_api.py).

## Source of truth

| | |
|---|---|
| Official docs | <https://docs.typesafe.ai> (index: `/llms.txt`) |
| HTTP reference | <https://docs.typesafe.ai/api.md> |
| API keys | <https://console.typesafe.ai/settings/keys> |
| Model verified against | `jev-1.13.0` (via alias `jev-latest`) |
| Verified on | 2026-09-21 |

## Two different services answer to the name "Jev"

This cost us a day, so it is written down.

| | **TypeSafe AI** — first-party | **jevai.org** |
|---|---|---|
| Keys | <https://console.typesafe.ai/settings/keys> | `jevai.org/agent/keys` |
| Endpoint | `POST api.typesafe.ai/v1/systemone` | `POST www.jevai.org/api/v1/decisions` |
| Response | `{model, answers, usage}` | `{code, message, data: {answers}}` |
| Key prefix seen | `apikey_…` (107 chars) | `jev_…` (36 chars) |

Both accept the same three question primitives and near-identical question bodies, and both
return a working answer — but **their keys are not interchangeable**: a jevai.org key returns
`401 authentication_error` against `api.typesafe.ai` and vice versa. jevai.org wraps Jev behind
its own envelope and preset endpoints (`/tool-guard`, `/model-route`, `/route`, …) and is not
referenced anywhere in TypeSafe's official documentation.

**JevKit targets the first-party TypeSafe API.** It has canonical docs, versioned model IDs,
published pricing and rate limits, and a documented error contract.

## Verified contract

**Endpoint** ✅

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <JEV_API_KEY>
Content-Type: application/json
```

Omitting the header returns `403 "Must supply an API key!"`; a bad key returns
`401 "Cannot authenticate with the server."` The old assumed path `/decisions` returns `404`.

**Request body** ✅

```json
{
  "state": "string | object",
  "model": "jev-latest",
  "questions": {
    "<question_id>": { "type": "noul|choice|score", "instructions": "...", "criteria": ... }
  }
}
```

- `state`, `model` and `questions` are all **required**. Omitting `model` → `422`. ✅
- `state` accepts a plain string *or* a JSON object; both were accepted. ✅
- Mixing all three question types in one request works, answered in one round trip. ✅

**Question types — exactly three** ✅

| Type | `criteria` | Answer fields actually returned |
|---|---|---|
| `noul` | optional `{"true": "...", "false": "..."}` | `type`, `noul` (0–1) — **nothing else** |
| `choice` | map of option → description (max 255) | `type`, `choice`, `confidence`, `probabilities` (map) |
| `score` | ordered array of 2–10 level descriptions | `type`, `score` (unrounded float), `confidence`, `legend`, `probabilities` |

Two corrections to what the published docs imply:

1. **`noul` returns no `confidence` field.** Only `type` and `noul`. The probability *is* the
   answer. Confirmed across three separate probes — do not write code that reads
   `answers[k]["confidence"]` unconditionally.
2. **`score.probabilities` is an object keyed by stringified level index**, not an array:
   `{"0": 0.0, "1": 0.06, "2": 0.0, "3": 0.94}`. `legend` is keyed the same way
   (`{"0": "No impact", …}`). Integer indexing will fail.

**Response body** ✅ — real capture

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "urgent":   {"type": "noul", "noul": 0.91},
    "department": {"type": "choice", "choice": "billing", "confidence": 1.0,
                   "probabilities": {"billing": 1.0, "technical": 0.0,
                                     "account": 0.0, "other": 0.0}},
    "severity": {"type": "score", "score": 2.94, "confidence": 0.94,
                 "legend": {"0": "None", "1": "Minor", "2": "Blocked", "3": "Losing money"},
                 "probabilities": {"0": 0.0, "1": 0.03, "2": 0.0, "3": 0.97}}
  },
  "usage": {"input_tokens": 425, "output_tokens": 75}
}
```

The container is `answers`, not `decisions`, and each value lives under a key **named after the
question type**. There is no generic `value` field.

**Errors** ✅ — the body shape is not uniform

| Status | `detail` shape | Example | Retryable |
|---|---|---|---|
| 400 | **object** | `{"error_type": "api_usage_error", "message": "Unknown model: …"}` | no |
| 401 | object | `{"error_type": "authentication_error", "message": "Cannot authenticate…"}` | no |
| 403 | object | `{"error_type": "authentication_error", "message": "Must supply an API key!"}` | no |
| 404 | string | `"Not Found"` | no |
| 422 | **array** | `[{"type": "missing", "loc": ["body","model"], "msg": "Field required", "input": {…}}]` | no |
| 429 | *(documented)* `retry_after_ms` | not observed | **yes** |
| 5xx / 529 | *(documented)* overloaded | not observed | **yes** |

`422` is FastAPI's validation format — a **list**, and its `input` field **echoes the request
body back**. That matters: `state` may hold personal data, so a 422 body must never be logged
verbatim. An unknown model is `400`, not `422`.

**Limits, pricing, models** (documented, not independently measured)

- Context: 64k tokens/request; 32k for `state` plus the longest single question.
- Rate limits: 250,000 tokens/sec, 1,200 requests/min.
- Pricing: $42 per billion input tokens ($0.042/M). Output free. `usage` is returned per call. ✅
- Models: `jev-1.13.0`; aliases `jev-latest`, `jev-preview`.

**Observed latency** ✅ — one connection, reused

| Probe | Latency |
|---|---|
| First call (incl. TLS handshake) | 884 ms |
| Single `noul` / `choice` / `score` | 271–300 ms |
| Three questions in one request | 416 ms |
| Error responses | ~220 ms |

Three questions in one request cost ~416 ms versus ~850 ms for three sequential calls — batching
questions is roughly 2× cheaper in wall time. The default `JEVKIT_TIMEOUT_SECONDS=10` is
generous; nothing observed came near it.

## Divergences that were fixed

`SCHEMA_VERIFIED` is now `True`. Each row below was a real defect, now corrected in
[`schema.py`](../packages/jevkit/providers/jev/schema.py) /
[`provider.py`](../packages/jevkit/providers/jev/provider.py) /
[`config.py`](../packages/jevkit/config.py) and covered by a test built on a captured payload.

| # | Was | Now |
|---|---|---|
| 1 | `https://api.jev.example/v1` | `https://api.typesafe.ai/v1` |
| 2 | `POST /decisions` | `POST /systemone` |
| 3 | `model` sent only if configured | always sent; defaults to `jev-latest` |
| 4 | `{"options": [...]}` | `criteria`: map for `choice`, list for `score` |
| 5 | kinds `selection`, `scalar`, `rank` emitted | rejected with `TaskDefinitionError` before the call |
| 6 | `Scalar` sent `minimum`/`maximum` | new `Score` question sends a `criteria` list |
| 7 | read `payload["decisions"]` | reads `answers` |
| 8 | expected `{"value": v, "probability": p}` | reads the type-named key; `confidence` for confidence |
| 9 | `legend` unmapped | `Score.levels` mirrors it; `Score.maximum` bounds validation |
| 10 | assumed every answer has `confidence` | `noul` reports none, and contributes none |
| 11 | `Retry-After` header only | reads `retry_after_ms` from the body too, normalized to seconds |
| 12 | `usage` not mapped | parsed into `Usage` on every response |
| 13 | `task.instructions` sent top-level (a 400) | folded into each question's `instructions` |
| 14 | `_safe_detail` dumped the raw body | extracts messages only; never includes the 422 `input` echo |

Already correct, left alone: the status → typed-error mapping in `provider.py`
(401/403 → auth, 429 → rate limit, ≥500 including 529 → retryable).

### Question-type mapping

| JevKit | Jev | Notes |
|---|---|---|
| `Noul` | `noul` | answer is P(yes); no confidence reported |
| `Choice` | `choice` | `options` → `criteria` keys; `descriptions` → criteria values (null allowed) |
| `Score` | `score` | `levels` → `criteria` list; answer is an unrounded position |
| `Selection`, `Scalar`, `Rank` | — | no equivalent; `TaskDefinitionError` at build time |

To express "pick several" against Jev, ask one `Noul` per option — each then carries its own
probability. `examples/requirement-checks` was rewritten this way.

### Behaviours the published docs got wrong

Found by probing, not reading:

- `score.probabilities` and `legend` are **objects keyed by stringified index**, not arrays.
- `noul` answers have **no** `confidence` field.
- A `score` rubric may have **1** level (docs say minimum 2); 11 levels is a `400`.
- A `choice` may have **1** option (docs imply a minimum of 2).
- A top-level `instructions` field is a **`400`**, not ignored.
- `detail` has three shapes: object (400/401/403), array (422), bare string (404, some 400s).
- A question with neither `instructions` nor `criteria` is a `400`.

## Phase 1 checklist

- [x] Locate the current official API documentation and note its version/date.
- [x] Confirm how to obtain credentials and what the auth header looks like.
- [x] Confirm the real base URL and endpoint path.
- [x] Send one minimal real request; record the exact request and response.
- [x] Test each documented question type individually.
- [x] Test whether multiple questions are supported in a single request.
- [x] Record the response schema, including probability field names.
- [x] Record error response bodies for 400, 401, 403, 404 and 422.
- [x] Record observed latency across several calls.
- [x] Record pricing and how usage is reported.
- [x] Note rate limits and quota behavior.
- [x] Record timeout behaviour against a real network condition (not only mocks) — see
      "Timeout behaviour" below; `429`/`5xx` are deliberately not force-triggered (see below).
- [x] Note anything in the terms of use that constrains how JevKit may call it — see
      "Terms of use" below; surfaced one unresolved item (🚩) for a human decision before Phase 3
      benchmark numbers are published.
- [x] Build a small labeled evaluation dataset — this project has no production traffic to draw
      "real" examples from, so per a decision recorded in `progress.md`, the three synthetic
      datasets were expanded instead (18 → 35 rows) with honest `synthetic: true` labeling and
      disclosed methodology, rather than mislabeling invented text as "real."
- [x] Update `schema.py`, set `SCHEMA_VERIFIED = True`, and record the API version here.
- [x] Add tests covering the real response shapes.

**Exit criteria: MET.** `python scripts/verify_jev_api.py` calls Jev and parses documented
responses end to end, exit code 0. `python scripts/verify_timeout_behavior.py` forces a real
timeout at every layer, exit code 0. All three example tasks (35 labeled rows total) run live
through the public SDK and `jevkit bench` with `validation_status=valid` / 100% coverage. The
legal review is done and raised a real flag rather than closing clean (see below). Every Phase 1
checklist item is now closed.

## Timeout behaviour ✅ — real, not mocked

`scripts/verify_jev_api.py` never triggered a timeout; every probe finished in under a second.
[`scripts/verify_timeout_behavior.py`](../scripts/verify_timeout_behavior.py) forces one for
real, at two layers, using an unreasonably short client-side timeout (not by asking Jev to be
slow — that's not something we control):

1. **Transport (`httpx`, bypassing the JevKit adapter).** A 10 ms connect timeout produced a
   real `httpx.ConnectTimeout` in ~157–279 ms (TLS handshake time). A 100 ms read timeout with a
   generous connect budget produced a real `httpx.ReadTimeout` in ~555–690 ms.
2. **End-to-end through the public SDK.** `DecisionClient.decide_with_trace()` with
   `DecisionPolicy(timeout_seconds=0.05, max_retries=1)` produced this real trace:

   ```
   provider_call   {'provider': 'jev', 'attempt': 1}
   failed          {'provider': 'jev', 'attempt': 1, 'error': 'TimeoutError', 'retryable': True}
   retry           {'attempt': 2, 'reason': 'provider_error'}
   provider_call   {'provider': 'jev', 'attempt': 2}
   failed          {'provider': 'jev', 'attempt': 2, 'error': 'TimeoutError', 'retryable': True}
   failed                                                              # exhausted, execution_status=failed
   ```

   The error surfaced to `engine.py` is `TimeoutError` (from `asyncio.wait_for`, which wraps
   `provider.decide()` at the same `policy.timeout_seconds` the httpx client also uses — the two
   timeouts race, and `asyncio.wait_for`'s tends to fire first). It is marked `retryable=True` and
   the policy's retry budget and exponential-ish backoff (`retry_backoff_seconds * attempt`) both
   ran for real, ending in `execution_status=failed` as documented.

Confirmed: `ProviderTimeoutError`/engine-level `TimeoutError` handling is exercised by a real
network condition, at every layer, not only by unit tests against mocks.

**`429` and `5xx` remain deliberately unobserved.** Forcing a `429` means sending enough requests
fast enough to exceed the account's rate limit — i.e. deliberately exceeding a documented "Usage
Limit," which §2.3(j) of the Master Customer Agreement prohibits (see below). Forcing a `5xx` is
not something a client can do at all. Their handling (401/403 → auth, 429 → rate limit with
`retry_after_ms` parsing, ≥500 including 529 → retryable) is written to the docs and covered by
tests built on captured/documented payloads; it has not met a live response, and that is a
deliberate scope boundary, not an oversight.

## Terms of use — reviewed 2026-09-21

<https://docs.typesafe.ai/legal.md> is an index page; the substance is in three linked documents.
**This is a summary for engineering awareness, produced by an LLM reading the pages — not legal
advice.** Anything load-bearing (see the flag below) needs an actual lawyer before v0.1 ships.

Reviewed: [Master Customer Agreement](https://typesafe.ai/legal/mca),
[Data Processing Agreement](https://typesafe.ai/legal/data-processing),
[Privacy Policy index](https://typesafe.ai/legal/privacy-policy).

- 🚩 **§2.3(b) prohibits using the Services or any Output to "develop (or facilitate the
  development of) a similar or competing product or service."** JevKit's Phase 3 goal — a
  benchmark suite that runs the same dataset through Jev *and* a reference/fallback provider and
  compares them — sits close to this line. It is not training on Jev's outputs and it is not
  building a competing model, but "compares Jev against alternatives, in public, in an
  open-source repo" is exactly the shape of thing this clause is written to prevent someone from
  hiding inside. **This needs a human decision before Phase 3 numbers are published**, not an
  engineering one — options include: keep comparative benchmark output private/local-only, seek
  written permission from TypeSafe, or drop head-to-head framing and report each provider's
  numbers separately without a "Jev vs. X" comparison. Not resolved here.
- §2.3(j): must not exceed the account's "Usage Limits." This is why the 429 probe above was
  skipped deliberately.
- §2.1: the license to use the Services is non-sublicensable, restricted to "access and use the
  Services in accordance with applicable documentation." Whether an open-source SDK that lets
  *other* people's accounts call the API through JevKit's code counts as sublicensing "access,"
  or is just... a client library (every SDK is this), isn't answered by the text. JevKit ships no
  API key of its own — every user supplies their own TypeSafe account — which is the usual way
  SDKs stay on the right side of this, but flagging it as unresolved rather than assuming it.
- §16.4: neither party may publicly announce that they've "entered into the Agreement" without
  consent. Doesn't obviously restrict describing JevKit as "a client for the TypeSafe API"
  (nominative use), but is one more reason the existing "Notes on attribution" section's caution
  (no claimed endorsement/affiliation) is the right posture, not overcaution.
- §9.3/§12.2: Services are provided "AS IS," liability capped at fees paid in 12 months or $50.
  This doesn't transfer any obligation onto JevKit itself, but it means JevKit can't promise
  users more reliability than TypeSafe promises JevKit.
- DPA: TypeSafe is a processor for whatever JevKit sends as `state`; retention is "as long as
  necessary," no fixed window. JevKit becomes a *separate* controller for anything it persists
  locally (trace files, `JsonlTraceRecorder`, the eventual Postgres store) — already partly
  covered by "secrets never reach a trace" in the conventions below, but PII in a `state` field
  is a broader category than secrets and isn't specifically handled yet.
- No explicit rate-limit numbers or an automated-access policy beyond "don't exceed your Usage
  Limits" were found in the MCA.

Bottom line for the roadmap: the 🚩 above is the one item that actually blocks Suggested Next
Step #1 ("review terms before publishing benchmark numbers") — the review is now done, and it
surfaced a real open question rather than a clean pass.

## Open questions

- `confidence` semantics: `choice` returned `1.0` on an unambiguous input. Whether it is a
  margin or a calibrated probability is described at <https://docs.typesafe.ai/confidence.md>
  and has not been checked against behaviour.

## Notes on attribution

Jev is developed by TypeSafe AI. JevKit is an independent open-source project and is not an
official client. Do not describe JevKit as endorsed by or affiliated with TypeSafe AI unless an
explicit partnership exists. JevKit's MIT license does not grant any rights to Jev itself;
its access and usage terms are separate and apply to you as the API's user.
