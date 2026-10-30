

"""Validate FK integrity, exact volumes, reconciliation and lifecycle consistency."""
import argparse, sqlite3, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="database/procurement.db")
    ap.add_argument("--report",default="")
    a=ap.parse_args()
    con=sqlite3.connect(a.db); con.row_factory=sqlite3.Row
    checks=[]
    def add(name,ok,detail): checks.append({"check":name,"status":"PASS" if ok else "FAIL","detail":detail})
    fk=con.execute("PRAGMA foreign_key_check").fetchall()
    add("foreign_key_integrity",not fk,f"{len(fk)} FK violations")
    targets={"Requester":300,"Supplier":120,"PurchaseRequest":1200,"RFQ":500,"SupplierQuote":1500,"PurchaseOrder":900}
    for table,count in targets.items():
        actual=con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        add(f"{table}_volume",actual==count,f"{actual} / {count}")
    dup=con.execute("SELECT COUNT(*) FROM (SELECT purchase_request_id,line_number FROM RequestLine GROUP BY 1,2 HAVING COUNT(*)>1)").fetchone()[0]
    add("request_line_uniqueness",dup==0,f"{dup} duplicate request-line keys")
    for label,query in [
      ("quote_landed_total","SELECT COUNT(*) FROM SupplierQuote WHERE ABS(landed_total-(subtotal+tax_amount+freight_amount))>0.02"),
      ("po_total","SELECT COUNT(*) FROM PurchaseOrder WHERE ABS(po_total-(subtotal+tax_amount+freight_amount))>0.02"),
      ("po_line_total","SELECT COUNT(*) FROM PurchaseOrderLine WHERE ABS(line_total-(unit_price*quantity_ordered))>0.02"),
      ("quote_line_total","SELECT COUNT(*) FROM QuoteLine WHERE ABS(line_total-(unit_price*quantity))>0.02"),
      ("competitive_quote_coverage","SELECT COUNT(*) FROM RFQ r WHERE (SELECT COUNT(*) FROM SupplierQuote q WHERE q.rfq_id=r.rfq_id)<3"),
      ("delivery_bounds","SELECT COUNT(*) FROM Delivery WHERE quantity_received<0 OR quantity_received>quantity_ordered"),
      ("budget_over_reservation_count","""SELECT COUNT(*) FROM PurchaseOrder p WHERE
          (SELECT COUNT(*) FROM BudgetTransaction b WHERE b.purchase_order_id=p.purchase_order_id
           AND b.transaction_type='RESERVATION' AND ABS(b.amount-p.po_total)<0.02)=0"""),
      ("po_quote_line_mismatch","""SELECT COUNT(*) FROM PurchaseOrder p WHERE p.awarded_quote_id IS NOT NULL AND
          (SELECT COUNT(*) FROM QuoteLine q WHERE q.quote_id=p.awarded_quote_id) !=
          (SELECT COUNT(*) FROM PurchaseOrderLine l WHERE l.purchase_order_id=p.purchase_order_id)"""),
      ("request_po_date_order","""SELECT COUNT(*) FROM PurchaseOrder p JOIN PurchaseRequest r
          ON r.purchase_request_id=p.purchase_request_id WHERE p.po_date<r.request_date"""),
      ("delivery_po_date_order","""SELECT COUNT(*) FROM Delivery d JOIN PurchaseOrder p
          ON p.purchase_order_id=d.purchase_order_id WHERE d.delivery_date<p.po_date"""),
      ("rfq_request_date_order","""SELECT COUNT(*) FROM RFQ f JOIN PurchaseRequest r
          ON r.purchase_request_id=f.purchase_request_id WHERE f.issue_date<r.request_date""")
    ]:
        count=con.execute(query).fetchone()[0]
        add(label,count==0,f"{count} violations")
    po_quote_value=con.execute("""SELECT COUNT(*) FROM PurchaseOrder p
      JOIN QuoteLine q ON q.quote_id=p.awarded_quote_id
      LEFT JOIN PurchaseOrderLine l ON l.purchase_order_id=p.purchase_order_id AND l.request_line_id=q.request_line_id
      WHERE l.po_line_id IS NULL OR ABS(l.line_total-q.line_total)>0.02 OR l.quantity_ordered!=q.quantity""").fetchone()[0]
    add("po_awarded_quote_line_value",po_quote_value==0,f"{po_quote_value} mismatched awarded quote lines")
    budget_mismatch=con.execute("""SELECT COUNT(*) FROM BudgetTransaction bt
      JOIN PurchaseOrder p ON p.purchase_order_id=bt.purchase_order_id
      JOIN PurchaseRequest r ON r.purchase_request_id=p.purchase_request_id
      WHERE bt.transaction_type='RESERVATION' AND
        (bt.budget_id!=r.budget_id OR ABS(bt.amount-p.po_total)>0.02)""").fetchone()[0]
    add("budget_reservation_reconciliation",budget_mismatch==0,f"{budget_mismatch} reservation mismatches")
    con.close()
    result={"passed":sum(x["status"]=="PASS" for x in checks),
            "failed":sum(x["status"]=="FAIL" for x in checks),"checks":checks}
    print(json.dumps(result,indent=2))
    if a.report: Path(a.report).write_text(json.dumps(result,indent=2)+"\n")
    if result["failed"]: raise SystemExit(2)
if __name__=="__main__": main()
