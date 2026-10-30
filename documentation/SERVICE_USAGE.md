# Procurement Service Usage

`generator/procurement_service.py` exposes a transactional `ProcurementService` class. Every successful business action commits its database transaction and appends status/audit records.

```python
from generator.procurement_service import ProcurementService

service = ProcurementService("database/procurement.db")
try:
    request = service.create_request(
        requester_id="REQ-0001",
        budget_id="BUD-001-2026",
        lines=[{
            "item_description": "Workstation",
            "category": "IT_HARDWARE",
            "quantity": 2,
            "estimated_unit_price": 20000
        }],
        justification="New engineering workstation",
        required_by="2026-12-15"
    )
    pr_id = request["purchase_request_id"]

    service.decide_approval(pr_id, "DEPARTMENT_MANAGER", "APPROVED")
    service.decide_approval(pr_id, "FINANCE", "APPROVED")

    rfq_id = service.create_rfq(
        pr_id, ["SUP-001", "SUP-002", "SUP-003"], "2026-12-01"
    )

    # Submit one price per RequestLine.request_line_id.
    # Compare quotes, then award the selected eligible quote.
    comparison = service.compare_quotes(rfq_id)
    print(comparison)
finally:
    service.close()
```

## Service safeguards
- The approval matrix is generated from estimated request value.
- RFQ creation is blocked until the request is fully approved.
- Competitive RFQs require at least three distinct active suppliers.
- Awarding requires three valid active quotes with matching currency.
- Expired quotes and inactive suppliers cannot be awarded.
- A selected quote above the lowest eligible landed cost requires written rationale.
- PO line values are copied from the awarded quote lines.
- Budget reservations are checked before PO creation; an over-budget award is rejected.
- Single-source POs require a fully approved request, active supplier and written exception rationale.
- Delivery receipts cannot exceed outstanding ordered quantity.
- State changes and audit actions are appended to history.

The integration test exercises the full competitive path, approval gate, quote comparison, award, PO generation, delivery closure, budget reservation and single-source exception.
