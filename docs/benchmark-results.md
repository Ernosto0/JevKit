# Benchmark results — Jev, 2026-09-21

Measured numbers from the three datasets shipped in [`examples/`](../examples/). The method
behind them is [`docs/benchmarking.md`](benchmarking.md); read that first if you plan to quote
anything here.

**Raw reports:** [`docs/benchmarks/`](benchmarks/) — one JSON per run, including every
per-example outcome, the full policy, and the run timestamp.

---

## What this page is, and is not

This is a **single-provider report**. It records how Jev behaved on three small, synthetic,
hand-labeled datasets on one day. It is published so the pipeline's output is inspectable, not
to make a case for or against any provider.

It is deliberately **not** a comparison. JevKit ships a reference provider
(`--provider reference`) that can run these same datasets, and the numbers from it are not
published here. That is a legal constraint, not a technical one: TypeSafe's Master Customer
Agreement §2.3(b) prohibits using the Services or their Output to "develop (or facilitate the
development of) a similar or competing product or service," and a public "Jev vs. X" table is
close enough to that line to need a lawyer's answer rather than an engineer's. See "Terms of
use" in [`docs/jev-api-notes.md`](jev-api-notes.md). Reporting one provider's numbers on their
own is the conservative option of the three listed there.

**These numbers do not support a general accuracy claim about Jev.** The datasets total 35
examples across three tasks. At that size a single example moves accuracy by 6–11 points, and
the confidence intervals around every figure below are wide enough to swallow most differences
you might care about. They are synthetic and hand-labeled by one person — they measure agreement
with that person's labels, not correctness in the world.

---

## Setup

| | |
|---|---|
| Provider | `jev` |
| Model | `jev-1.13.0` |
| Run date | 2026-09-21 |
| Policy | timeout 10s, `max_retries` 1, backoff 0.5s, no fallback configured |
| Concurrency | 4 |
| JevKit version | 0.1.0 |

All three runs used the same policy and the same code path the SDK uses. Reproduce with:

```bash
jevkit bench --task examples/support-routing/task.json \
             --dataset examples/support-routing/dataset.jsonl \
             --provider jev --out reports/support-routing.json
```

…and the same for `agent-routing` and `requirement-checks`. This spends real money (fractions of
a cent per run) and needs `JEV_API_KEY` set.

---

## Execution results

Identical across all three datasets, and the least ambiguous thing on this page:

| Dataset | Examples | Coverage | Invalid responses | Fallback rate | p50 latency | p95 latency |
|---|---|---|---|---|---|---|
| support-routing | 15 | 100% | 0% | 0% | 304 ms | 968 ms |
| agent-routing | 11 | 100% | 0% | 0% | 364 ms | 1732 ms |
| requirement-checks | 9 | 100% | 0% | 0% | 323 ms | 989 ms |

Every one of the 35 requests returned an answer that passed schema validation. No retries, no
fallbacks, no parse failures. This is a statement about the **adapter and the API contract**
being sound — it says nothing about whether the answers were right.

`total_cost_usd` and `cost_per_1k_decisions_usd` are `null` in every report. JevKit does not
hardcode provider pricing, because a hardcoded price goes stale silently and a stale cost figure
is worse than no cost figure.

---

## Accuracy and calibration

`acc` = accuracy against the dataset label. `f1` = macro F1. `brier` = Brier score (lower is
better). `ece` = expected calibration error (lower is better). A blank cell means the metric did
not apply, which is not the same as zero.

### support-routing (n=15)

| Question | Type | acc | f1 | brier | ece |
|---|---|---|---|---|---|
| `department` | choice (4 options) | 0.867 | 0.817 | | |
| `urgent` | noul @0.5 | 1.000 | | 0.049 | 0.177 |
| `needs_escalation` | noul @0.5 | 0.933 | | 0.084 | 0.259 |

### agent-routing (n=11)

| Question | Type | acc | f1 | brier | ece |
|---|---|---|---|---|---|
| `route` | choice (4 options) | 0.818 | 0.831 | | |
| `confident_enough_to_act` | noul @0.6 | 0.455 | | 0.290 | 0.428 |

### requirement-checks (n=9)

| Question | Type | acc | brier | ece |
|---|---|---|---|---|
| `passes` | noul @0.5 | 0.778 | 0.162 | 0.187 |
| `unmet_has_title` | noul @0.5 | 0.778 | 0.133 | 0.157 |
| `unmet_has_summary` | noul @0.5 | 0.889 | 0.070 | 0.194 |
| `unmet_cites_sources` | noul @0.5 | 1.000 | 0.006 | 0.070 |
| `unmet_under_word_limit` | noul @0.5 | 0.889 | 0.067 | 0.130 |
| `review_depth` | score (3 levels) | — | — | — |

`review_depth` scored **zero examples**, and that is intended. It asks how much human review an
artifact needs — a judgement call with no ground truth — so the dataset deliberately leaves it
unlabeled and the runner reports nothing rather than inventing a score. See the `methodology`
field in [`examples/requirement-checks/dataset.meta.json`](../examples/requirement-checks/dataset.meta.json).

---

## What stands out

### The classification questions behaved; the meta-judgement question did not

`department` (0.867), `route` (0.818) and the four concrete `unmet_*` checks (0.778–1.000) are
in a band you would expect from a competent classifier on labels this clean. `unmet_cites_sources`
was perfect with a 0.006 Brier score — the model was both right and confident, on the requirement
that is easiest to check by inspection.

`confident_enough_to_act` (0.455) is the outlier, and it is worse than a coin flip. It is worth
being precise about what went wrong, because "the model is bad at this" is only part of it:

- The question asks "is the correct route clear from the task description alone?" — a question
  about the model's own certainty, not about the task.
- Jev's probabilities ran low across the board: mean 0.380 on the 7 examples labeled *clear*,
  mean 0.247 on the 4 labeled *unclear*. The classes separate in the right direction, but weakly,
  and both means sit below the question's 0.6 threshold. So at 0.6 nearly everything reads as
  "not clear", which costs every positive example.
- The 0.428 ECE says the same thing: stated probability and observed correctness are far apart.

That threshold is doing a lot of work. Sweeping it post-hoc on these 11 examples:

| threshold | 0.20 | 0.30 | 0.40 | 0.50 | 0.60 (as shipped) |
|---|---|---|---|---|---|
| accuracy | 0.818 | 0.636 | 0.364 | 0.455 | 0.455 |

**This sweep is not a result.** It is tuned on the same 11 examples it is scored on, which is the
textbook way to manufacture a number. It is here to show that at this sample size the threshold
choice swings accuracy by 45 points — which is the actual finding. The 0.455 in the table above
is the number that stands, because 0.6 is what the shipped task specifies.

The label is also the softest of the three datasets: `dataset.meta.json` states outright that it
encodes the author's routing policy rather than ground truth about the tasks.

### Calibration is the weaker axis

Accuracy is respectable nearly everywhere; ECE ranges 0.070–0.428 and is above 0.15 on five of
the ten scored questions. This matters for anyone planning to gate on `min_confidence`: a
threshold is only as meaningful as the calibration underneath it, and `confident_enough_to_act`
is a worked example of that gate failing while the underlying classification (`route`, 0.818)
held up fine.

### `noul` answers carry no separate confidence

The `confidence` map is empty for every `noul` question in these reports. That is the API's
design, not a gap — for a `noul`, the returned probability **is** the answer. Calibration is
computed from the answer itself.

### Runs are not deterministic

These datasets were run twice on 2026-09-21, before and after a fix to how the runner records
the model identifier. Accuracy and F1 came out identical both times; Brier and ECE moved in the
third decimal (e.g. `urgent` Brier 0.047 → 0.049), and p95 latency moved a lot more (agent-routing
931 ms → 1732 ms, on 11 requests). Treat latency percentiles at this sample size as indicative
only. A single number from a single run of 9–15 examples is not a stable measurement.

---

## Limitations

- **35 examples total**, 9–15 per task. Every figure has a wide interval around it.
- **Synthetic and hand-authored.** No production traffic exists for this project to sample.
  Labels reflect one author's judgement; the datasets say so in their `methodology` fields.
- **One run, one day, one model version.** No variance estimate across runs beyond the
  informal comparison noted above.
- **One provider.** Nothing here establishes that any other provider would do better or worse.
- **Cost unmeasured.** No cost-per-decision figure is reported.
- **`429`/`5xx` paths untested live.** Forcing them means deliberately exceeding the account's
  Usage Limits, which the MCA prohibits. Their handling is mock-tested only.

## What would make these publishable as claims

1. Datasets an order of magnitude larger, with labels from more than one person and an
   inter-annotator agreement figure.
2. Examples drawn from real traffic, or from a licensed public dataset.
3. Multiple runs per configuration, reported with variance.
4. A resolution of the §2.3(b) question, if any comparison is ever to be published.

Until then this page is a record of what the pipeline measured, and nothing more.
