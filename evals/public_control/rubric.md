# Public writing evaluation rubric v1

Freeze this rubric before formal outputs are inspected. Pilot observations may
repair execution only; no formal gold or heldout outcomes may tune the candidate.

## Evidence and independence

The evaluator receives the task, source snapshot, source-derived checklist and
anonymized outputs in a fresh context. It does not receive condition names or
generator reasoning. Checklist items are review aids, not expert gold; an item
that contradicts the source must be flagged and excluded, with a reason.
Output order is randomized by a fixed seed, and paired comparisons are repeated
with swapped order for the coordinator sample. A disagreement remains visible.
Root checks at least 20% of paired writing cases and every severe failure.
AI assessments are explicitly AI assessments, never human or expert approval.

## Writing dimensions (each 0 to 4)

* Task coverage: 0 wrong task; 1 major requested sections absent; 2 several
  substantive gaps; 3 one minor gap; 4 all requested work covered within sources.
* Factual support: 0 fabricated project measurements or central false claims;
  1 multiple material unsupported claims; 2 one material unsupported claim;
  3 only a minor attribution or scope issue; 4 factual claims traceable, proposals
  and uncertainties explicitly distinguished. Missing facts are not made up.
* Reasoning and tradeoffs: 0 contradictory; 1 conclusions largely unexplained;
  2 partial causal explanation or alternatives; 3 concrete choices and costs;
  4 source-grounded reasoning with meaningful alternatives and residual limits.
* Domain expression: 0 misleading terminology; 1 recurring vague language;
  2 mixed terminology or generic passages; 3 mostly precise; 4 consistent terms,
  concrete actors/actions and appropriate Chinese technical prose throughout.
* Reader usability: 0 unusable; 1 cannot locate key answers; 2 substantial
  restructuring needed; 3 usable with local edits; 4 key decisions and evidence
  can be found and checked. No invented minutes of expert editing time.
* Source localization: 0 no usable references; 1 most claims cannot be located;
  2 mixed source locators; 3 mostly usable locators; 4 paths/sections/line or
  sentence IDs locate the relevant support accurately.

Every score below 4 requires at least one exact output quotation/location and
its source basis or unmet request. Do not infer missing citations from style.
No AI detector score. Generic phrasing counts are diagnostic, not truth labels.

## Severe failures (separate, never averaged away)

Invented project-specific test/benchmark result; another project's facts stated
as this project's facts; proposal stated as shipped behavior; false reviewed or
verified claim; answer leakage; silently missing substantive output content.
Record exact text, source evidence and confidence. A weakly supported suspicion
is uncertainty, not a confirmed failure.

## Mechanical and visual metrics

QA: native label accuracy and macro F1 where labels exist; Chinese QA normalized
exact match and token/character F1 with explicit normalization. Quote substring
matches only test source text presence, never semantic entailment. Evidence
sentence recall uses explicit IDs; missing/ambiguous IDs remain unknown.

Rendering: count actual DOCX/PDF/text retention issues, page count and visual
findings per page. Automated extraction is heuristic. Visual pass requires
actual inspection of every claimed page; pending pages stay pending. Each issue
states artifact/page, observation and severity. Format and content scores remain
separate. Native renderer output is a formatter experiment unless the complete
production build/review/finalize workflow has actually been run.

## Aggregation and candidate decision

Report denominators, failed generations, repeats, usage and elapsed time.
Aggregate repeats within paper/project first. Do not present repeats as new
independent projects. Report paired wins/ties/losses and exploratory uncertainty;
four projects cannot establish broad domain generalization.
Candidate may be retained only if heldout target metrics improve without new
severe failures or material content/format regression. Otherwise preserve the
negative result and leave the main Skill unchanged. Do not change thresholds
after seeing heldout outputs. Unknown model version and runtime tool limits are
reported alongside all conclusions.
