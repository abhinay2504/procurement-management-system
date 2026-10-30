# Procurement Evaluation Metrics

The analytics evaluator exports one row per eligible quote and one row per budget.

- **Landed cost:** supplier subtotal + tax + freight.
- **Quote score:** 60% normalized landed-cost score + 25% normalized delivery score + 15% normalized supplier-risk score.
- **Lowest-cost award rate:** awards where selected landed cost equals the minimum eligible landed cost / competitive awards evaluated.
- **Unexplained non-lowest awards:** selected quote exceeds minimum eligible landed cost and award rationale is blank.
- **PO spend:** sum of PurchaseOrder.po_total.
- **Budget commitment:** sum of BudgetTransaction.amount for current reservation/commitment events.
- **Available budget:** allocated budget - committed reservation amount.
- **Budget utilization:** committed / allocated x 100.
- **Over-budget budgets:** budget rows where committed amount exceeds allocation.
- **Partial delivery events:** number of Delivery rows whose delivery_status is PARTIAL.

Known anomalies are compared with `ground_truth.csv` only after evaluation; the ground-truth file must not be joined into model input features.
