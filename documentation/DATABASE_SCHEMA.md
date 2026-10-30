# Database Schema, Keys and Cardinality

## Primary and foreign keys
Every business table has an immutable primary key. Foreign keys are declared in `database/schema.sql` for all direct parent-child relationships. `StatusEvent` and `AuditLog` use polymorphic `(entity_type, entity_id)` references; these are validated by the service and validator because a conventional SQL FK cannot target multiple tables.

## Cardinality
- Department 1:N Requester; Department 1:N Budget (effective-dated budget allocations).
- Requester 1:N PurchaseRequest; Department 1:N PurchaseRequest; Budget 1:N PurchaseRequest.
- PurchaseRequest 1:N RequestLine; PurchaseRequest 0..1:1 RFQ in the generated baseline.
- RFQ N:M Supplier through RFQSupplier; RFQ 1:N SupplierQuote.
- Supplier 1:N SupplierQuote; SupplierQuote 1:N QuoteLine; RequestLine 1:N QuoteLine.
- PurchaseRequest 0..1:1 PurchaseOrder in the baseline; Supplier 1:N PurchaseOrder.
- PurchaseOrder 1:N PurchaseOrderLine and 1:N Delivery.
- PurchaseOrder 1:N BudgetTransaction.
- PurchaseRequest 1:N Approval; each status transition 1:N StatusEvent; each action 1:N AuditLog.
- PurchaseOrder.rfq_id and awarded_quote_id are optional for single-source POs.
- PurchaseRequest.duplicate_of_request_id and split_group_id are optional exception/reference fields.

## Lifecycle states
- Request: DRAFT -> SUBMITTED -> APPROVED or REJECTED; CANCELLED where applicable.
- RFQ: DRAFT -> ISSUED -> CLOSED -> AWARDED or CANCELLED.
- Quote: RECEIVED -> AWARDED, REJECTED or EXPIRED.
- PO: DRAFT -> ISSUED -> CLOSED or CANCELLED.
- Delivery: PARTIAL -> DELIVERED; inspection may be PENDING, PASSED or FAILED.

## Event history
StatusEvent and AuditLog are append-only records. Service actions insert new events rather than deleting historical decisions. Approval rows preserve the individual approver's decision and timestamp.
