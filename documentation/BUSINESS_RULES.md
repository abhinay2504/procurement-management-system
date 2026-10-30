# Procurement Business Rules

## Approval matrix
- Estimated request total < INR 25,000: Department Manager.
- INR 25,000 through INR 100,000 inclusive: Department Manager + Finance.
- Above INR 100,000: Department Manager + Finance + Executive.
- A request is APPROVED only after every required approval is APPROVED. Rejection stops the workflow.

## Sourcing and quote comparison
- Competitive RFQs invite at least three distinct active suppliers.
- Competitive awards require at least three valid, active, currency-matched quotes.
- Landed cost = subtotal + tax + freight.
- Quote currency must match RFQ currency; no implicit FX conversion is allowed.
- Expired quotes and inactive suppliers are excluded from eligible award comparison.
- Evaluation score weights: landed cost 60%, delivery time 25%, supplier risk 15%. Each criterion is normalized within the eligible RFQ quote set; lower cost, fewer delivery days and lower risk score are better.
- Selecting a quote above the lowest eligible landed cost requires a documented rationale.
- Award decisions store the selected quote and rationale; rejected quotes remain in history.

## Purchase order and budget
- POs are created only from fully approved requests.
- Quote-backed PO subtotal, tax, freight and total reconcile to the awarded quote and quote lines.
- Single-source PO requires active supplier, approved request and written exception rationale.
- Budget availability = allocated amount - reservations - actual commitments + releases, as represented by BudgetTransaction rows. The service blocks new awards that exceed available allocation.
- Known injected over-budget PO is retained as a labelled test case in the baseline dataset.

## Delivery
- Delivery records are append-only. Each event records ordered and received quantity.
- Cumulative receipts may not exceed ordered quantities.
- Partial deliveries remain open with outstanding quantity; complete receipt closes the PO in the service.

## Exceptions and ground truth
The seven deliberate negative scenarios are PO without approval, expired quote award, unexplained non-cheapest award, inactive supplier award, budget overrun, duplicate request and quote currency mismatch. Labels are held only in `data/ground_truth/`; they are not copied into model feature tables.
