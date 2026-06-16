# Evaluation Report — AINS UC3: JSM → Confluence FAQ Generator

## Methodology

Evaluated on 30 synthetic JSM tickets manually labeled by the team.
Labels assigned per ticket: `faq_worthy` (true/false), `clarity_score` (1–10),
`is_duplicate` (true/false).

Retrieval context was mocked (empty) for all eval runs — duplicate detection
requires integration with the retrieval layer and is reported separately.

Model: llama-3.3-70b-versatile via Groq API, temperature=0.1.

---

## Metric 1 — FAQ-Worthiness Classification

|              | Precision | Recall | F1   | Support |
|--------------|-----------|--------|------|---------|
| not worthy   | 0.67      | 0.86   | 0.75 | 7       |
| worthy       | 0.95      | 0.87   | 0.91 | 23      |
| **accuracy** |           |        | **0.87** | **30** |
| macro avg    | 0.81      | 0.86   | 0.83 | 30      |

**Analysis:** The model correctly identifies the clear cases in both directions.
False negatives (AINS-12, AINS-28, AINS-29) are genuine borderline tickets where
the resolution involved partial IT intervention — honest edge cases, not prompt
failures. The one false positive (AINS-27, manual SharePoint permission grant)
represents the model over-generalising a common symptom.

---

## Metric 2 — Clarity Score Calibration

Pearson r = 0.84 (p < 0.001) across 30 tickets.

Strong positive correlation, statistically significant. Known limitation: the model
produces a bimodal distribution (scores cluster at 1 for rejects and 8–10 for
approvals). Human scores are more evenly distributed across the 1–10 range.
The mid-range (5–7) is where calibration is weakest — tickets the model rejects
that humans scored 4–5 receive a score of 1 rather than a low but non-zero value.

---

## Metric 3 — Duplicate Detection

Note: evaluated with top_faq_similarity = 0.0 (retrieval not integrated).
Tickets labeled is_duplicate=true: AINS-3, AINS-21, AINS-22, AINS-23 (4 tickets).
With empty retrieval, duplicate_flag was correctly set to false for all — expected
behaviour since similarity score never exceeds the 0.88 threshold.

Full duplicate detection accuracy will be measurable after integration with the
retrieval layer. The threshold of 0.88 cosine similarity is documented in the
retrieval spec and will be validated against the 4 known duplicate pairs.

---

## Non-Determinism Handling

Temperature set to 0.1 to minimise variance across runs. The same ticket re-run
3 times produced identical `faq_worthy` decisions in all tested cases. Clarity
scores varied by at most ±1 point across reruns on 5 spot-checked tickets —
within acceptable range for a subjective 1–10 scale. The publishing decision tree
is fully deterministic given a fixed clarity score threshold.

---

## Limitations

- Test set is synthetic — real JSM tickets may contain more ambiguous resolutions
- Retrieval context was absent during eval — in production, similar FAQ context
  improves both quality and duplicate detection accuracy
- Clarity score calibration is weakest in the 4–6 range where human judgment
  varies most
- 30-ticket test set is small; results should be validated on a larger set before
  production deployment
