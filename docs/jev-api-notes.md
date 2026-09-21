# Jev API notes

**Status: UNVERIFIED.** This document is the working record for roadmap phase 1.

Everything JevKit currently assumes about the Jev API is a guess, isolated in one file:
[`packages/jevkit/providers/jev/schema.py`](../../packages/jevkit/providers/jev/schema.py).
Nothing here should be treated as documentation of the real API until the checklist below is
complete and `SCHEMA_VERIFIED` is set to `True`.

## Why this file exists

The plan calls for verifying Jev's contract before implementing against it. Rather than block
all scaffolding on that, the project was built with the unknown part quarantined: the engine,
policies, validation, tracing, benchmarks, CLI, API and dashboard are all independent of the
wire format. Correcting the mapping should touch `schema.py`, `provider.py` and their tests —
nothing else.

## What is currently assumed (and may be wrong)

| Aspect | Current assumption | Verified? |
|---|---|---|
| Base URL | `https://api.jev.example/v1` (placeholder) | ❌ |
| Endpoint | `POST /decisions` | ❌ |
| Auth | `Authorization: Bearer <key>` | ❌ |
| Request body | `{"state": {...}, "questions": {...}, "instructions": "..."}` | ❌ |
| Question payload | `{"type": "<kind>", "options": [...], "instructions": "..."}` | ❌ |
| Question kinds | `choice`, `noul`, `selection`, `scalar`, `rank` | ❌ |
| Response body | `{"decisions": {key: {"value": v, "probability": p}}, "model": "..."}` | ❌ |
| Alternate response | flat `{key: value}` — both are accepted defensively | ❌ |
| Multi-question support | assumed: many questions in one request | ❌ |
| Error bodies | unknown; only status codes are mapped | ❌ |
| Rate limit header | `Retry-After` in seconds | ❌ |
| Usage / cost reporting | not mapped at all | ❌ |

## Phase 1 checklist

- [ ] Locate the current official API documentation and note its version/date.
- [ ] Confirm how to obtain credentials and what the auth header looks like.
- [ ] Confirm the real base URL and endpoint path.
- [ ] Send one minimal real request; record the exact request and response.
- [ ] Test each documented question type individually.
- [ ] Test whether multiple questions are supported in a single request.
- [ ] Record the response schema, including whether probabilities are returned and under what
      field name.
- [ ] Record error response bodies for 400, 401, 429 and 5xx.
- [ ] Record observed latency across several calls.
- [ ] Record pricing and how usage is reported, if at all.
- [ ] Note rate limits and quota behavior.
- [ ] Note anything in the terms of use that constrains how JevKit may call it.
- [ ] Build a small labeled evaluation dataset from a real task.
- [ ] Update `schema.py`, set `SCHEMA_VERIFIED = True`, and record the API version here.
- [ ] Add tests covering the real response shapes.

**Exit criteria:** a repeatable script can call Jev and parse a documented response.

## Findings

_Fill this in as phase 1 proceeds. Record what was observed, not what was expected._

### API version verified against

_Not yet verified._

### Confirmed request format

_Not yet verified._

### Confirmed response format

_Not yet verified._

### Supported question types

_Not yet verified._

### Known limitations and open questions

_Not yet verified._

## Notes on attribution

Jev is developed by TypeSafe AI. JevKit is an independent open-source project and is not an
official client. Do not describe JevKit as endorsed by or affiliated with TypeSafe AI unless an
explicit partnership exists. JevKit's MIT license does not grant any rights to Jev itself;
its access and usage terms are separate and apply to you as the API's user.
