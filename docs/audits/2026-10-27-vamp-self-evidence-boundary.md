# VAMP customer projection: objective declarations are not achievement proof

The customer VAMP projection previously inserted a task from a declared objective and then
linked that **same source statement** to the new task as achievement evidence, with mapping
confidence `1.0`. For example, a packet stating “Objective KPA1 requires two peer-reviewed
articles” created an evidence-to-task link even though no articles were supplied.

This is a source-role error: describing a requirement is not satisfying it. It also makes
source-driven review appear more complete than the underlying customer inputs support.

The projection now retains the declaration in its source/evidence inventory but leaves
`evidence_task` unmapped. Retained rows carry
`UNMAPPED_PENDING_INDEPENDENT_SOURCE_REVIEW` metadata. Actual records may be mapped only by
a separately proven source-to-objective matching step; this change does **not** invent that
matching step or establish any professional performance conclusion.

Regression: `test_customer_objective_statement_cannot_certify_its_own_evidence` failed
before the fix (`1` unsupported mapping instead of `0`) and passed afterward. The existing
customer projection test now asserts that source-declared objectives remain unmapped.

Verification: 84 focused tests passed across VAMP, customer routing, Lingua, funding,
reports and native artifact finishing. The full repository suite remains unverified in
this isolated checkout because broad test collection requires additional BEAST/runtime
environment configuration and dependencies.

No customer rating, publication, external communication, payment or approval authority
was granted by this repair.

## Follow-up: declared requirement quantities

A subsequent regression cycle found that `requires 0 publications` was silently
rewritten into a one-publication minimum. Negative and negated requirements also
fell through to that invented one-item target. Additionally, `requires 1,500 records`
was parsed as `1`, and malformed `1,50` was silently truncated.

VAMP now refuses explicit zero, negative, negated and malformed grouped quantities,
while preserving valid comma-grouped positive quantities in full. The fallback
presence-only review floor remains separately labelled for objective language that
does not declare a parseable count; it is not an authoritative requirement quantity.
All new regressions were observed failing before implementation and passing afterward.
