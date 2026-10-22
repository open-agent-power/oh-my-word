# Public writing review rubric v3

This rubric is frozen before v3 review runs. It is an exploratory AI assessment,
not expert approval or an adoption decision.

## Applicability and evidence

Judge the actual task request and its source snapshot. The source-derived
checklist is a review aid, not gold: flag a checklist item that conflicts with
the source and do not penalize an output for it. Apply criteria according to
task kind. A descriptive `technical-report` explains the requested existing
system and does not need new proposals, alternatives, design recommendations,
or a test plan unless requested. A `design-spec` is assessed for the design
choices, tradeoffs, compatibility, and test implications the request asks for.
Clearly marked proposals are not statements of shipped behavior; assess their
source compatibility separately. Do not reward length, caution, extra headings,
or generic warnings by themselves.

The shared generation contract is supplied in the judge prompt. All candidate
responses are carried as JSON. When the JSON is valid, the wrapper, JSON syntax,
field names, renderer-neutral representation, and presence of an envelope are
not style or usability defects. Assess the requested content inside the JSON.
A malformed envelope may be recorded as a mechanical defect only when it
prevents use of the requested content. Never infer visual quality from JSON.

## Six dimensions, each scored from 0 to 4

- **Task coverage:** 0 wrong task; 1 major requested sections absent; 2 several
  substantive gaps; 3 one minor gap; 4 all requested work covered within sources.
- **Factual support:** 0 fabricated project measurements or central false claims;
  1 multiple material unsupported claims; 2 one material unsupported claim;
  3 only a minor attribution or scope issue; 4 factual claims traceable, proposals
  and uncertainties clearly distinguished. Do not invent missing facts.
- **Reasoning and tradeoffs:** 0 contradictory; 1 conclusions largely unexplained;
  2 partial causal explanation or relevant alternatives; 3 concrete choices and
  costs; 4 source-grounded reasoning with meaningful alternatives and residual
  limits, when applicable to the requested task kind.
- **Domain expression:** 0 misleading terminology; 1 recurring vague language;
  2 mixed terminology or generic passages; 3 mostly precise; 4 consistent terms,
  concrete actors/actions, and appropriate Chinese technical prose.
- **Reader usability:** 0 content unusable; 1 key answers cannot be located;
  2 substantial content restructuring needed; 3 usable with local edits; 4 key
  decisions and evidence can be found and checked. Do not score the JSON envelope.
- **Source localization:** 0 no usable references; 1 most claims cannot be located;
  2 mixed source locators; 3 mostly usable locators; 4 paths, sections, lines, or
  sentence IDs accurately locate relevant support.

## Required review contract

Return one JSON object matching the contract included in the prompt. Assess every
candidate exactly once. Include all six dimensions as integer scores from 0 to 4.
Each score below 4 must have at least one `issues` entry with that same dimension,
an exact quotation copied from a decoded string value inside that candidate's
JSON, a non-empty `source_basis`, a non-empty reason, and severity `minor` or
`material`. The source basis must identify source support, contradiction, or a
specific unmet request; do not use a placeholder. Quotation punctuation must be
part of the candidate text. Do not quote the JSON escape spelling for a string.

Record severe failures separately. Each severe failure must quote an exact
candidate string, name the source basis or task contradiction, and explain the
reason. Severe failures include invented project-specific test or benchmark
results, another project's facts presented as this project's facts, proposals
presented as shipped behavior, false claims of review or verification, answer
leakage, and silently missing substantive output. A suspicion without sufficient
evidence belongs in uncertainties, not as a confirmed severe failure.

`preference_order` must contain every candidate ID exactly once, best first.
Use `uncertainties` to preserve evidence limits, checklist conflicts, and
unresolved comparisons. This order is exploratory AI preference only.

## Scope limits

Do not use outside facts or tools. Quote substring checks establish only that
the text appears in the candidate; they do not establish semantic entailment.
Rendering or visual quality is unscored because the judge receives candidate
JSON, not rendered pages. Report unknown model/runtime details and failed reviews
as limits. Only mechanically validated reviews may enter the v3 summary; that
validation cannot establish whether a source interpretation is correct.
