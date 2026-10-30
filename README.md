# Procurement Management System

End-to-end synthetic procurement workflow and evaluation project. Includes deterministic full/starter dataset generation, relational SQLite persistence, approval and sourcing service, quote scoring, budget controls, delivery events, exception detection, analytics and SHA-256 reproducibility tests.

## Quick start

Python 3.10+; standard library only.

```bash
# Generate the exact requested full dataset
python generator/generate_data.py --seed 20261022 --scale full --output generated_full

# Generate a smaller starter dataset using the same generation logic
python generator/generate_data.py --seed 20261022 --scale starter --output generated_starter

# Validate a generated SQLite database
python generator/validate_data.py --db generated_full/database/procurement.db

# Run supplier quote scoring, budget utilization and procurement KPIs
python analytics/evaluate_procurement.py --db generated_full/database/procurement.db --output generated_full/analytics

# Rebuild the full dataset twice and compare SHA-256 for every output file
python reproducibility/run_reproducibility_test.py --seed 20261022 --scale full

# Run the transactional end-to-end service integration test
python tests/test_end_to_end_service.py --db generated_full/database/procurement.db
```

## Baseline full volume

| Entity | Rows |
|---|---:|
| Requester | 300 |
| Supplier | 120 |
| PurchaseRequest | 1,200 |
| RFQ | 500 |
| SupplierQuote | 1,500 |
| PurchaseOrder | 900 |

Supporting entities include 12 departments, 12 budgets, request lines, RFQ-supplier bridge rows, quote lines, approvals, PO lines, deliveries, budget transactions, status events and audit logs.

## Included capabilities

1. **Parameterized data regeneration:** `--scale starter|full`, `--seed`, `--output`.
2. **Reproducibility:** full two-run SHA-256 comparison of CSV, JSON, SQLite, SQL dump and reports.
3. **Transactional workflow service:** create request, threshold approvals, RFQ, supplier quotes, quote comparison, award, PO generation, single-source exception, delivery receipt and budget summary.
4. **Supplier evaluation:** landed-cost, delivery and supplier-risk scoring (60/25/15 weighted score).
5. **Budget controls:** reservations calculated from PO commitments; new service awards are blocked when budget is insufficient.
6. **Ground truth:** seven labelled anomalies in separate CSV/JSON files; labels are not included in feature tables.
7. **Auditability:** status transitions and audit actions are appended as records.

## ID conventions

- `PR-2026-000001`
- `RFQ-2026-000001`
- `QUO-S001-2026-000001`
- `PO-2026-000001`
- `DEL-PO-2026-000001-01`

## Folder structure

- `data/master`, `data/transactions`, `data/events`, `data/ground_truth`, `data/json`
- `database/schema.sql`, `database/procurement.db`, `database/seed_data.sql`
- `generator/generate_data.py`, `generator/validate_data.py`, `generator/procurement_service.py`
- `analytics/evaluate_procurement.py`
- `documentation/` data dictionary, rules, relationships, evaluation metrics and validation report
- `reproducibility/` manifest, per-file checksums, and two-run comparison
- `tests/test_end_to_end_service.py`

## Synthetic provenance

All names, emails, supplier identities, amounts and transactions are synthetic. Emails use `example.test`. No public or private external dataset was used, so there are no third-party licensing or redistribution dependencies.

## Design notes

The packaged full dataset deliberately contains the seven requested negative scenarios so the exception detector can be evaluated. The operational service, by contrast, blocks invalid new actions such as awarding an expired quote, issuing a PO before approval, selecting a non-cheapest quote without rationale, or committing beyond available budget.

## Verified completion snapshot

See `documentation/COMPLETION_RESULTS.md` for the final run. The full build passed 47 generator checks and 21 SQL checks; the two-run reproducibility test compared 45 generated files with zero SHA-256 mismatches. The service integration test passed for both competitive and single-source procurement paths and confirmed that an over-budget award is blocked.
