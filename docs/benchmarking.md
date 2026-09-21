# Benchmarking

Benchmarking is the part of JevKit most easily turned into marketing. These rules exist to
stop that.

## The core commitment

> JevKit reports what it measured, under a stated methodology, on a stated dataset.
> It does not claim that Jev — or any provider — is better in general.

## Workflow

1. Define a task with an explicit output schema.
2. Prepare a labeled dataset and document how the labels were made.
3. Run the task over the dataset with provider A.
4. Run the **same** task over the **same** dataset with provider B, under the **same** policy.
5. Compare.
6. Publish the methodology alongside any number.

```bash
jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl \
             --provider jev --out reports/jev.json

jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl \
             --provider reference --out reports/reference.json
```

## Metrics

| Metric | What it tells you | When it applies |
|---|---|---|
| Accuracy | Overall correctness | Labeled categorical or thresholded binary answers |
| Precision / Recall / F1 | The shape of the errors, per label | Classification tasks |
| Brier score | Quality of probabilistic predictions (lower is better) | `Noul` questions with boolean labels |
| Calibration error | Whether stated confidence matches observed correctness | Probabilistic answers |
| p50 / p95 latency | Typical and tail response time | Always, when latency was recorded |
| Cost per 1,000 decisions | Estimated spend under recorded pricing | When the provider reports cost |
| Invalid response rate | How often output failed schema validation | Always |
| Fallback rate | How often escalation to another provider happened | When a fallback is configured |
| Coverage | Share of inputs that produced an accepted result | Always |

### Absent is not zero

Every metric function returns `None` when it does not apply, and the report and dashboard
render that as a dash. A run that could not compute calibration error shows an em dash, never
`0.000`. This is deliberate: a zero that means "not measured" is a false claim.

### Invalid answers lower coverage, not accuracy

An answer that fails schema validation is excluded from scoring and counted in
`invalid_response_rate` and `coverage`. Scoring it as "wrong" would conflate two different
failure modes: a model that answers incorrectly and a model that answers unusably.

## Accuracy is not the whole picture

A model can be accurate and badly calibrated — confidently wrong on the cases it gets wrong.
If you plan to gate on `min_confidence`, calibration error matters more to you than accuracy
does, because a poorly calibrated confidence score makes the gate meaningless.

Conversely, a well-calibrated model with mediocre accuracy can be more useful than an
overconfident accurate one, because you can route its uncertain cases to review.

## Reproducibility requirements

Every `BenchmarkReport` records:

- task ref (`name@version`)
- dataset ref (`name@version`)
- provider and model identifier
- the full policy used
- run timestamp
- per-example outcomes

Two reports are comparable only if the first four match.

## Dataset requirements

Every dataset carries a `methodology` describing:

- how labels were produced, and by whom
- whether examples are synthetic or sampled from real traffic
- where labels are ambiguous
- what the dataset does **not** support concluding

`tests/unit/test_examples.py` enforces that every shipped dataset has a methodology and that
its labels are valid answers to its task.

## About the shipped datasets

The datasets in `examples/` are **synthetic, hand-authored, and tiny** — 9 to 15 examples each,
35 in total. They exist to make the pipeline runnable end to end and to give the metrics code
something real to compute.

They are not large or representative enough to support any claim about a provider's accuracy.

Measured numbers from them are published in
[`docs/benchmark-results.md`](benchmark-results.md), as a **record of what the pipeline
measured** — single-provider, fully caveated, with the raw per-example reports alongside. That
is the only form in which numbers from these datasets may be published. Quoting a figure from
that page as a claim about a provider's accuracy — in a README, a release note, or a comparison
— is exactly what the page says it does not support.

## Before publishing any number

- [ ] Both providers ran the same dataset version and the same task version.
- [ ] Both ran under the same policy, with the same timeout and retry limits.
- [ ] The model identifier and run date are recorded.
- [ ] The dataset's methodology is published with the result.
- [ ] Dataset size and composition are stated.
- [ ] Known limitations and ambiguous labels are disclosed.
- [ ] Demo and illustrative numbers are clearly separated from measured ones.
- [ ] The claim being made is scoped to the task that was measured.

## The reference provider

`--provider reference` (`packages/jevkit/providers/reference/`) calls an OpenAI-compatible Chat
Completions API using JSON-schema structured outputs. It is not assumed to be more accurate than
Jev, and it supports the full provider-agnostic question vocabulary (`Noul`, `Choice`, `Score`,
`Selection`, `Scalar`, `Rank`), unlike the Jev adapter, which only implements the three types Jev
documents. Set `JEVKIT_FALLBACK_PROVIDER=reference` and `JEVKIT_FALLBACK_API_KEY` to use it; see
`.env.example`. It has been verified against a mocked transport, not a live account — nothing in
this repo has spent against it.

**Running `jevkit bench --provider reference` next to `jevkit bench --provider jev` on the same
dataset does not by itself clear this benchmark for publishing.** The "Terms of use" section of
[`docs/jev-api-notes.md`](jev-api-notes.md) flags an open item (Master Customer Agreement
§2.3(b), which bears on any public "Jev vs. X" comparison) that still applies to whatever numbers
this produces. Run it, inspect it, keep it private — do not publish a head-to-head number from it
without resolving that first.

## Things not to say

- "Jev is more accurate." — Accurate at what, on which data, against what?
- "Jev is cheaper." — Under what pricing, at what volume, on what date?
- "99% accuracy." — On eight synthetic examples, this is noise.
- "Benchmarked against GPT-4." — Which version, which settings, which prompt?
