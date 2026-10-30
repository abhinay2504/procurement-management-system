# Completion and Verification Results

Fixed seed: `20261022`; full scale.

## Completed deliverables
- Parameterized generator for `starter` and `full` scales.
- Full relational SQLite database and SQL seed dump.
- Transactional approval, RFQ, quote, award, PO, budget and delivery service.
- Single-source exception workflow with mandatory rationale.
- Quote scoring: landed cost 60%, delivery 25%, supplier risk 15%.
- Budget reservation and over-budget prevention in the service.
- Separate seven-case ground-truth dataset.
- Supplier and budget analytics exports.

## Verification
- Generator validation: **47 passed, 0 failed**.
- SQL validation: **21 passed, 0 failed**.
- Two-run full regeneration: **45 files compared, 0 checksum mismatches**.
- End-to-end integration test: **PASS**. Covers approval gate, competitive RFQ, three supplier quotes, weighted comparison, quote award, PO line creation, delivery closure, budget reservation, single-source exception and rejection of a new over-budget commitment.
- Starter-scale generation: **47 passed, 0 failed**.

## Full-scale evaluation snapshot
- Purchase requests: 1,200.
- RFQs: 500.
- Supplier quotes: 1,500.
- Purchase orders: 900.
- PO spend / budget reservations: INR 320,955,515.52.
- Total budget allocation: INR 1,200,000,000.00.
- Aggregate available budget: INR 879,044,484.48.
- One departmental budget is intentionally overrun by the labelled test PO.
- 497 of 498 eligible scored awards use the lowest eligible landed cost; one deliberately injected non-cheapest award lacks rationale.
- All seven ground-truth issue types are detected by the rule evaluator.

The intentionally invalid baseline cases remain in the dataset for exception-detection evaluation. The transactional service blocks the corresponding invalid new actions.
