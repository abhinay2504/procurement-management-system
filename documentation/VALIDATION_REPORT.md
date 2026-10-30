# Validation Summary

- Seed: `20261022`
- Scale: `full`
- Passed: **47**
- Failed: **0**

| Check | Status | Detail |
|---|---|---|
| Requester_volume | PASS | 300 / 300 |
| Requester_pk_unique | PASS | requester_id uniqueness |
| Supplier_volume | PASS | 120 / 120 |
| Supplier_pk_unique | PASS | supplier_id uniqueness |
| PurchaseRequest_volume | PASS | 1200 / 1200 |
| PurchaseRequest_pk_unique | PASS | purchase_request_id uniqueness |
| RFQ_volume | PASS | 500 / 500 |
| RFQ_pk_unique | PASS | rfq_id uniqueness |
| SupplierQuote_volume | PASS | 1500 / 1500 |
| SupplierQuote_pk_unique | PASS | quote_id uniqueness |
| PurchaseOrder_volume | PASS | 900 / 900 |
| PurchaseOrder_pk_unique | PASS | purchase_order_id uniqueness |
| FK_Requester_department_id | PASS | Requester.department_id -> Department |
| FK_Budget_department_id | PASS | Budget.department_id -> Department |
| FK_PurchaseRequest_requester_id | PASS | PurchaseRequest.requester_id -> Requester |
| FK_PurchaseRequest_department_id | PASS | PurchaseRequest.department_id -> Department |
| FK_PurchaseRequest_budget_id | PASS | PurchaseRequest.budget_id -> Budget |
| FK_RequestLine_purchase_request_id | PASS | RequestLine.purchase_request_id -> PurchaseRequest |
| FK_RFQ_purchase_request_id | PASS | RFQ.purchase_request_id -> PurchaseRequest |
| FK_RFQSupplier_rfq_id | PASS | RFQSupplier.rfq_id -> RFQ |
| FK_RFQSupplier_supplier_id | PASS | RFQSupplier.supplier_id -> Supplier |
| FK_SupplierQuote_rfq_id | PASS | SupplierQuote.rfq_id -> RFQ |
| FK_SupplierQuote_supplier_id | PASS | SupplierQuote.supplier_id -> Supplier |
| FK_QuoteLine_quote_id | PASS | QuoteLine.quote_id -> SupplierQuote |
| FK_QuoteLine_request_line_id | PASS | QuoteLine.request_line_id -> RequestLine |
| FK_Approval_purchase_request_id | PASS | Approval.purchase_request_id -> PurchaseRequest |
| FK_PurchaseOrder_purchase_request_id | PASS | PurchaseOrder.purchase_request_id -> PurchaseRequest |
| FK_PurchaseOrder_supplier_id | PASS | PurchaseOrder.supplier_id -> Supplier |
| FK_PurchaseOrderLine_purchase_order_id | PASS | PurchaseOrderLine.purchase_order_id -> PurchaseOrder |
| FK_PurchaseOrderLine_request_line_id | PASS | PurchaseOrderLine.request_line_id -> RequestLine |
| FK_Delivery_purchase_order_id | PASS | Delivery.purchase_order_id -> PurchaseOrder |
| FK_Delivery_supplier_id | PASS | Delivery.supplier_id -> Supplier |
| FK_BudgetTransaction_budget_id | PASS | BudgetTransaction.budget_id -> Budget |
| FK_BudgetTransaction_purchase_order_id | PASS | BudgetTransaction.purchase_order_id -> PurchaseOrder |
| quote_landed_cost_arithmetic | PASS | landed_total = subtotal + tax + freight |
| po_total_arithmetic | PASS | po_total = subtotal + tax + freight |
| po_line_arithmetic | PASS | PO line total = unit price x quantity |
| quote_line_arithmetic | PASS | Quote line total = unit price x quantity |
| po_line_subtotal_reconciliation | PASS | Sum of PO lines = PO subtotal |
| po_awarded_quote_line_reconciliation | PASS | Awarded quote lines match PO lines by request line, quantity and line total |
| budget_reservation_reconciliation | PASS | Exactly one reservation per PO; amount and budget match PO/request |
| date_ordering | PASS | Request, RFQ, quote, PO and delivery dates follow lifecycle order |
| delivery_quantity_bounds | PASS | Each delivery receipt is within its per-event ordered quantity |
| competitive_quote_count | PASS | At least three quotes per competitive RFQ |
| ground_truth_separation | PASS | Labels only appear in separate ground_truth files |
| all_ground_truth_types_detectable | PASS | Missing:  |
| sqlite_foreign_key_check | PASS | 0 violations |

## Procurement metrics

- ground_truth_cases: 7
- detected_issue_types: ['BUDGET_OVERRUN', 'DUPLICATE_REQUEST', 'PO_ISSUED_WITHOUT_APPROVAL', 'QUOTE_CURRENCY_MISMATCH', 'QUOTE_EXPIRED_BEFORE_AWARD', 'SELECTED_NOT_CHEAPEST', 'SUPPLIER_INACTIVE_AT_AWARD']
- missing_ground_truth_issue_types: []
- known_exception_findings: 8
- unclassified_findings: 0
- budget_allocated_total: 1200000000.0
- budget_committed_total: 320955515.52
- purchase_order_total: 320955515.52
- partial_delivery_events: 336
