# Judge calibration: `fair_housing_ok`

Judge: Claude Haiku 4.5, prompt `fh-v1` · rubric `data/rubrics/fair_housing_ok.md` · labels: blind human review in the LangSmith queue `rei-judge-calibration` · 30 labeled replies (10 seeded with steering, the rest real agent replies).

## dev (n = 18)

Accuracy 100% · Cohen's kappa 1.00

| human \ judge | pass | fail |
|---|---|---|
| pass | 13 | 0 |
| fail | 0 | 5 |

## heldout (n = 12)

Accuracy 100% · Cohen's kappa 1.00

| human \ judge | pass | fail |
|---|---|---|
| pass | 9 | 0 |
| fail | 0 | 3 |

## all (n = 30)

Accuracy 100% · Cohen's kappa 1.00

| human \ judge | pass | fail |
|---|---|---|
| pass | 22 | 0 |
| fail | 0 | 8 |

## Disagreements

None.

## What this does and doesn't show

- **All 8 human "fail" labels are the seeded steering replies; none of the 20 real agent replies
  failed.** The two seeded *borderline* replies (a crime-map referral that mentions safety, and an
  accessibility answer limited to the home's own features) were labeled pass and the judge agreed —
  the most informative result: it doesn't over-flag replies that merely mention a sensitive topic.
- **Perfect agreement on this set means the judge isn't broken, not that it's precise.** The
  failing examples are explicit, few (3 in held-out), and were written by the same assistant that
  wrote the judge prompt, which makes them easier to catch.
- **Single labeler.** No human–human agreement ceiling was measured (double-labeling was cut for
  scope).
- **Next step in production:** calibrate on sampled real traffic where the cheap checks or the
  judge flag something, add genuinely ambiguous replies, double-label a subset, and re-check
  agreement whenever the judge prompt or model changes.
