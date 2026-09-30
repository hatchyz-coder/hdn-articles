# Decision Log — LHub Daily Recovery Contract (2026-09-30)

## Incident
The Daily Guarantee contract is one LHub publication per JST calendar day. The recovery workflow still targeted two Drive publications and could dispatch the Daily Drive workflow up to six times. On 2026-09-29 and 2026-09-30 this amplified failed generation attempts without creating a valid publication.

## Decision
- The scheduled four Daily Drive slots remain the primary retry mechanism.
- The 10:00 JST recovery workflow uses the same lightweight repository preflight as Daily Drive.
- If today's LHub publication already exists, recovery exits before dependency setup, API, reserve, tests/build, PR, or deploy.
- If today's publication is missing, recovery dispatches Daily Drive exactly once.
- No second same-day publication target is introduced.

## Boundaries
This change does not alter article content, Fact Gate rules, reserve content/state, provider credentials, deployment, customer data, or production data. The separate Groq 413 remediation remains owned by existing PR #115 and is not duplicated here.

## Verification
The regression test asserts use of the canonical preflight, absence of the stale two-per-day target, exactly one dispatch command, and the lightweight already-published path.
