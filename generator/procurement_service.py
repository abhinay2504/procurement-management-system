

"""Transactional procurement workflow service backed by the generated SQLite schema."""
from __future__ import annotations
import argparse, sqlite3, json
from datetime import datetime, date
from pathlib import Path

def stamp(value=None):
    if value is None: return datetime.now().replace(microsecond=0).isoformat()
    return value.isoformat() if hasattr(value,"isoformat") else str(value)

def required_roles(amount):
    amount=float(amount)
    if amount < 25000: return ["DEPARTMENT_MANAGER"], "DEPT_ONLY"
    if amount <= 100000: return ["DEPARTMENT_MANAGER","FINANCE"], "DEPT_FINANCE"
    return ["DEPARTMENT_MANAGER","FINANCE","EXECUTIVE"], "DEPT_FINANCE_EXEC"

class ProcurementService:
    def __init__(self, db_path):
        self.db_path=str(db_path)
        self.con=sqlite3.connect(self.db_path)
        self.con.row_factory=sqlite3.Row
        self.con.execute("PRAGMA foreign_keys=ON")

    def close(self): self.con.close()

    def _next(self, table, column, prefix, width=6):
        rows=self.con.execute(f"SELECT {column} FROM {table} WHERE {column} LIKE ?",(prefix+"%",)).fetchall()
        nums=[]
        for row in rows:
            tail=str(row[0]).split("-")[-1]
            if tail.isdigit(): nums.append(int(tail))
        return f"{prefix}{max(nums,default=0)+1:0{width}d}"

    def _event(self, entity_type, entity_id, old, new, actor, reason, now):
        eid=self._next("StatusEvent","event_id","EVT-",7)
        self.con.execute("INSERT INTO StatusEvent VALUES (?,?,?,?,?,?,?,?)",
            (eid,entity_type,entity_id,old,new,now,actor,reason))
        aid=self._next("AuditLog","audit_id","AUD-",7)
        self.con.execute("INSERT INTO AuditLog VALUES (?,?,?,?,?,?,?)",
            (aid,entity_type,entity_id,"STATE_CHANGE",actor,now,reason))

    def create_request(self, requester_id, budget_id, lines, justification, required_by, now=None):
        now=stamp(now); cur=self.con.cursor()
        requester=cur.execute("SELECT department_id FROM Requester WHERE requester_id=? AND is_active=1",(requester_id,)).fetchone()
        budget=cur.execute("SELECT department_id,currency FROM Budget WHERE budget_id=?",(budget_id,)).fetchone()
        if not requester or not budget: raise ValueError("Active requester and valid budget are required")
        if requester["department_id"]!=budget["department_id"]: raise ValueError("Requester and budget departments must match")
        if not lines: raise ValueError("At least one request line is required")
        total=round(sum(float(x["quantity"])*float(x["estimated_unit_price"]) for x in lines),2)
        roles,rule=required_roles(total)
        pr_id=self._next("PurchaseRequest","purchase_request_id","PR-2026-",6)
        cur.execute("""INSERT INTO PurchaseRequest
            (purchase_request_id,requester_id,department_id,budget_id,request_date,required_by_date,
             business_justification,currency,estimated_total,status,duplicate_of_request_id,split_group_id)
             VALUES (?,?,?,?,?,?,?,?,?,'SUBMITTED',NULL,NULL)""",
            (pr_id,requester_id,requester["department_id"],budget_id,now,stamp(required_by),
             justification,budget["currency"],total))
        for i,line in enumerate(lines,1):
            line_id=f"PRL-{pr_id[-6:]}-{i:02d}"
            qty=int(line["quantity"]); unit=float(line["estimated_unit_price"])
            if qty<=0 or unit<0: raise ValueError("Line quantity must be positive and price non-negative")
            cur.execute("""INSERT INTO RequestLine VALUES (?,?,?,?,?,?,?,?,?)""",
                (line_id,pr_id,i,line["item_description"],line["category"],qty,
                 line.get("unit_of_measure","EACH"),unit,round(qty*unit,2)))
        for i,role in enumerate(roles,1):
            cur.execute("INSERT INTO Approval VALUES (?,?,?,?,?,?,?)",
                (f"APR-{pr_id[-6:]}-{i:02d}",pr_id,role,"PENDING",now,rule,"Awaiting decision"))
        self._event("PURCHASE_REQUEST",pr_id,"DRAFT","SUBMITTED",requester_id,"Request submitted",now)
        self.con.commit()
        return {"purchase_request_id":pr_id,"estimated_total":total,"required_approvers":roles,"threshold_rule":rule}

    def decide_approval(self, purchase_request_id, approver_role, decision, comments="", now=None):
        decision=decision.upper()
        if decision not in {"APPROVED","REJECTED"}: raise ValueError("Decision must be APPROVED or REJECTED")
        now=stamp(now); cur=self.con.cursor()
        row=cur.execute("SELECT status FROM PurchaseRequest WHERE purchase_request_id=?",(purchase_request_id,)).fetchone()
        if not row: raise ValueError("Purchase request not found")
        appr=cur.execute("""SELECT approval_id,decision FROM Approval
            WHERE purchase_request_id=? AND approver_role=?""",(purchase_request_id,approver_role)).fetchone()
        if not appr: raise ValueError("Approver role is not required by the approval matrix")
        if appr["decision"]!="PENDING": raise ValueError("Approval has already been decided")
        cur.execute("UPDATE Approval SET decision=?,decision_date=?,comments=? WHERE approval_id=?",
                    (decision,now,comments,appr["approval_id"]))
        if decision=="REJECTED":
            cur.execute("UPDATE PurchaseRequest SET status='REJECTED' WHERE purchase_request_id=?",(purchase_request_id,))
            self._event("PURCHASE_REQUEST",purchase_request_id,row["status"],"REJECTED",approver_role,comments or "Request rejected",now)
        else:
            remaining=cur.execute("""SELECT COUNT(*) FROM Approval
                WHERE purchase_request_id=? AND decision!='APPROVED'""",(purchase_request_id,)).fetchone()[0]
            if remaining==0:
                cur.execute("UPDATE PurchaseRequest SET status='APPROVED' WHERE purchase_request_id=?",(purchase_request_id,))
                self._event("PURCHASE_REQUEST",purchase_request_id,row["status"],"APPROVED",approver_role,"All approval steps completed",now)
        self.con.commit()
        return self.con.execute("SELECT status FROM PurchaseRequest WHERE purchase_request_id=?",(purchase_request_id,)).fetchone()[0]

    def create_rfq(self, purchase_request_id, supplier_ids, closing_date, now=None):
        now=stamp(now); cur=self.con.cursor()
        pr=cur.execute("SELECT status,currency FROM PurchaseRequest WHERE purchase_request_id=?",(purchase_request_id,)).fetchone()
        if not pr or pr["status"]!="APPROVED": raise ValueError("Only fully approved requests can enter competitive RFQ")
        if len(set(supplier_ids))<3: raise ValueError("Competitive RFQ requires at least three distinct suppliers")
        for sid in supplier_ids:
            s=cur.execute("SELECT is_active FROM Supplier WHERE supplier_id=?",(sid,)).fetchone()
            if not s or not s["is_active"]: raise ValueError(f"Supplier {sid} is not active")
        rfq_id=self._next("RFQ","rfq_id","RFQ-2026-",6)
        cur.execute("INSERT INTO RFQ VALUES (?,?,?,?,?,?,?,?)",
            (rfq_id,purchase_request_id,now,stamp(closing_date),pr["currency"],"COMPETITIVE","ISSUED",3))
        for i,sid in enumerate(supplier_ids,1):
            cur.execute("INSERT INTO RFQSupplier VALUES (?,?,?,?,?)",
                (f"RFQS-SVC-{rfq_id[-6:]}-{i:02d}",rfq_id,sid,now,"INVITED"))
        self._event("RFQ",rfq_id,"DRAFT","ISSUED","PROCESS_OWNER","RFQ issued to suppliers",now)
        self.con.commit(); return rfq_id

    def submit_quote(self, rfq_id, supplier_id, line_prices, tax_amount, freight_amount,
                     delivery_days, valid_until, currency="INR", now=None):
        now=stamp(now); cur=self.con.cursor()
        rfq=cur.execute("SELECT currency,closing_date,status FROM RFQ WHERE rfq_id=?",(rfq_id,)).fetchone()
        supplier=cur.execute("SELECT supplier_code,is_active FROM Supplier WHERE supplier_id=?",(supplier_id,)).fetchone()
        if not rfq or not supplier: raise ValueError("RFQ and supplier must exist")
        if not supplier["is_active"]: raise ValueError("Inactive supplier cannot submit a valid quote")
        invitation=cur.execute("SELECT 1 FROM RFQSupplier WHERE rfq_id=? AND supplier_id=?",(rfq_id,supplier_id)).fetchone()
        if not invitation: raise ValueError("Supplier was not invited to this RFQ")
        if int(delivery_days)<=0: raise ValueError("Delivery days must be positive")
        request_id=cur.execute("SELECT purchase_request_id FROM RFQ WHERE rfq_id=?",(rfq_id,)).fetchone()[0]
        req_lines=cur.execute("SELECT request_line_id,quantity FROM RequestLine WHERE purchase_request_id=?",(request_id,)).fetchall()
        if set(line_prices)!= {x["request_line_id"] for x in req_lines}:
            raise ValueError("Quote must price every requested line exactly once")
        subtotal=0.0
        for x in req_lines:
            price=float(line_prices[x["request_line_id"]])
            if price<0: raise ValueError("Unit price cannot be negative")
            subtotal+=price*int(x["quantity"])
        subtotal=round(subtotal,2); tax=float(tax_amount); freight=float(freight_amount)
        if tax<0 or freight<0: raise ValueError("Tax and freight cannot be negative")
        qid=self._next("SupplierQuote","quote_id",f"QUO-{supplier['supplier_code']}-2026-",6)
        cur.execute("""INSERT INTO SupplierQuote VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (qid,rfq_id,supplier_id,now,stamp(valid_until),currency,subtotal,tax,freight,
             round(subtotal+tax+freight,2),int(delivery_days),"RECEIVED","",0))
        for i,x in enumerate(req_lines,1):
            unit=float(line_prices[x["request_line_id"]])
            cur.execute("INSERT INTO QuoteLine VALUES (?,?,?,?,?,?)",
                (f"QL-SVC-{qid[-6:]}-{i:02d}",qid,x["request_line_id"],x["quantity"],unit,
                 round(unit*int(x["quantity"]),2)))
        cur.execute("UPDATE RFQSupplier SET response_status='RESPONDED' WHERE rfq_id=? AND supplier_id=?",
                    (rfq_id,supplier_id))
        self.con.commit(); return qid

    def compare_quotes(self, rfq_id, award_time=None):
        now=stamp(award_time); cur=self.con.cursor()
        rfq=cur.execute("SELECT currency,closing_date FROM RFQ WHERE rfq_id=?",(rfq_id,)).fetchone()
        if not rfq: raise ValueError("RFQ not found")
        qs=cur.execute("""SELECT q.*,s.risk_score,s.is_active FROM SupplierQuote q
            JOIN Supplier s ON s.supplier_id=q.supplier_id WHERE q.rfq_id=?""",(rfq_id,)).fetchall()
        eligible=[q for q in qs if q["currency"]==rfq["currency"] and q["valid_until"]>=now
                  and q["is_active"] and q["status"]=="RECEIVED"]
        if not eligible: return []
        costs=[float(q["landed_total"]) for q in eligible]
        leads=[int(q["delivery_days"]) for q in eligible]
        risks=[int(q["risk_score"]) for q in eligible]
        def norm(v, values, lower=True):
            lo,hi=min(values),max(values)
            if hi==lo: return 100.0
            score=100*(hi-v)/(hi-lo)
            return score if lower else 100-score
        out=[]
        for q in eligible:
            cost_score=norm(float(q["landed_total"]),costs)
            delivery_score=norm(int(q["delivery_days"]),leads)
            risk_score=norm(int(q["risk_score"]),risks)
            total=round(.60*cost_score+.25*delivery_score+.15*risk_score,2)
            out.append({"quote_id":q["quote_id"],"supplier_id":q["supplier_id"],
                "landed_total":q["landed_total"],"delivery_days":q["delivery_days"],
                "supplier_risk_score":q["risk_score"],"cost_score":round(cost_score,2),
                "delivery_score":round(delivery_score,2),"risk_score":round(risk_score,2),
                "weighted_score":total})
        return sorted(out,key=lambda x:(-x["weighted_score"],x["landed_total"]))

    def award_quote(self, rfq_id, quote_id, rationale="", now=None):
        now=stamp(now); cur=self.con.cursor()
        rfq=cur.execute("SELECT * FROM RFQ WHERE rfq_id=?",(rfq_id,)).fetchone()
        q=cur.execute("SELECT * FROM SupplierQuote WHERE quote_id=? AND rfq_id=?",(quote_id,rfq_id)).fetchone()
        if not rfq or not q: raise ValueError("RFQ/quote relationship is invalid")
        pr=cur.execute("SELECT * FROM PurchaseRequest WHERE purchase_request_id=?",(rfq["purchase_request_id"],)).fetchone()
        if pr["status"]!="APPROVED": raise ValueError("Purchase request is not fully approved")
        pending=cur.execute("SELECT COUNT(*) FROM Approval WHERE purchase_request_id=? AND decision!='APPROVED'",
                            (pr["purchase_request_id"],)).fetchone()[0]
        if pending: raise ValueError("All approval steps must be approved before award")
        count=cur.execute("""SELECT COUNT(*) FROM SupplierQuote q
            JOIN Supplier s ON s.supplier_id=q.supplier_id
            WHERE q.rfq_id=? AND q.status IN ('RECEIVED','AWARDED')
              AND q.currency=? AND q.valid_until>=? AND s.is_active=1""",
            (rfq_id,rfq["currency"],now)).fetchone()[0]
        if rfq["sourcing_type"]=="COMPETITIVE" and count<3:
            raise ValueError("Competitive award requires at least three valid, active, currency-matched quotes")
        if q["currency"]!=rfq["currency"]: raise ValueError("Quote currency does not match RFQ")
        if q["valid_until"]<now: raise ValueError("Quote expired before award")
        supplier=cur.execute("SELECT is_active FROM Supplier WHERE supplier_id=?",(q["supplier_id"],)).fetchone()
        if not supplier["is_active"]: raise ValueError("Supplier is inactive")
        comparison=self.compare_quotes(rfq_id,now)
        cheapest=cur.execute("""SELECT MIN(q.landed_total) FROM SupplierQuote q
            JOIN Supplier s ON s.supplier_id=q.supplier_id
            WHERE q.rfq_id=? AND q.currency=? AND q.valid_until>=? AND s.is_active=1""",
            (rfq_id,rfq["currency"],now)).fetchone()[0]
        if cheapest is not None and float(q["landed_total"])>float(cheapest)+.01 and not rationale.strip():
            raise ValueError("Non-cheapest award requires a documented rationale")

        budget=cur.execute("SELECT b.* FROM Budget b WHERE b.budget_id=?",(pr["budget_id"],)).fetchone()
        reserved=cur.execute("SELECT COALESCE(SUM(amount),0) FROM BudgetTransaction WHERE budget_id=?",
                             (pr["budget_id"],)).fetchone()[0]
        total=float(q["landed_total"])
        if reserved+total>float(budget["allocated_amount"]):
            raise ValueError("Insufficient budget: award would exceed available allocation")
        po_id=self._next("PurchaseOrder","purchase_order_id","PO-2026-",6)
        cur.execute("""INSERT INTO PurchaseOrder VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (po_id,pr["purchase_request_id"],q["supplier_id"],rfq_id,quote_id,now,q["currency"],
             q["subtotal"],q["tax_amount"],q["freight_amount"],q["landed_total"],"APPROVED","ISSUED",
             rationale,"NET_30"))
        qlines=cur.execute("SELECT * FROM QuoteLine WHERE quote_id=?",(quote_id,)).fetchall()
        for i,ql in enumerate(qlines,1):
            reqline=cur.execute("SELECT item_description FROM RequestLine WHERE request_line_id=?",
                                (ql["request_line_id"],)).fetchone()
            cur.execute("INSERT INTO PurchaseOrderLine VALUES (?,?,?,?,?,?,?)",
                (f"POL-SVC-{po_id[-6:]}-{i:02d}",po_id,ql["request_line_id"],reqline["item_description"],
                 ql["quantity"],ql["unit_price"],ql["line_total"]))
        bt=self._next("BudgetTransaction","budget_transaction_id","BT-",6)
        cur.execute("INSERT INTO BudgetTransaction VALUES (?,?,?,?,?,?,?)",
            (bt,pr["budget_id"],po_id,"RESERVATION",total,q["currency"],now))
        cur.execute("UPDATE SupplierQuote SET status=CASE WHEN quote_id=? THEN 'AWARDED' ELSE 'REJECTED' END, is_selected=CASE WHEN quote_id=? THEN 1 ELSE 0 END WHERE rfq_id=?",
                    (quote_id,quote_id,rfq_id))
        cur.execute("UPDATE RFQ SET status='AWARDED' WHERE rfq_id=?",(rfq_id,))
        self._event("PURCHASE_ORDER",po_id,"DRAFT","ISSUED","PROCESS_OWNER",
                    "PO generated from approved awarded quote",now)
        self.con.commit()
        return {"purchase_order_id":po_id,"po_total":total,"supplier_id":q["supplier_id"],
                "quote_id":quote_id,"budget_reserved":total,"supplier_comparison":comparison}

    def create_single_source_po(self, purchase_request_id, supplier_id, unit_prices,
                                rationale, tax_amount=0, freight_amount=0, now=None):
        """Create a controlled quote-less PO for an approved single-source exception."""
        now=stamp(now); cur=self.con.cursor()
        pr=cur.execute("SELECT * FROM PurchaseRequest WHERE purchase_request_id=?",
                       (purchase_request_id,)).fetchone()
        supplier=cur.execute("SELECT * FROM Supplier WHERE supplier_id=?",(supplier_id,)).fetchone()
        if not pr or pr["status"]!="APPROVED": raise ValueError("Single-source request must be fully approved")
        if not supplier or not supplier["is_active"]: raise ValueError("Supplier must be active")
        if not rationale or not rationale.strip(): raise ValueError("Single-source exception requires documented rationale")
        lines=cur.execute("SELECT * FROM RequestLine WHERE purchase_request_id=?",
                          (purchase_request_id,)).fetchall()
        if set(unit_prices)!={x["request_line_id"] for x in lines}:
            raise ValueError("A price is required for every request line")
        subtotal=round(sum(float(unit_prices[x["request_line_id"]])*int(x["quantity"]) for x in lines),2)
        tax=float(tax_amount); freight=float(freight_amount)
        if tax<0 or freight<0: raise ValueError("Tax and freight cannot be negative")
        total=round(subtotal+tax+freight,2)
        budget=cur.execute("SELECT * FROM Budget WHERE budget_id=?",(pr["budget_id"],)).fetchone()
        reserved=cur.execute("SELECT COALESCE(SUM(amount),0) FROM BudgetTransaction WHERE budget_id=?",
                             (pr["budget_id"],)).fetchone()[0]
        if float(reserved)+total>float(budget["allocated_amount"]):
            raise ValueError("Insufficient budget for single-source commitment")
        po_id=self._next("PurchaseOrder","purchase_order_id","PO-2026-",6)
        cur.execute("""INSERT INTO PurchaseOrder VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (po_id,purchase_request_id,supplier_id,None,None,now,pr["currency"],subtotal,tax,freight,
             total,"APPROVED","ISSUED",rationale,"NET_30"))
        for i,line in enumerate(lines,1):
            unit=float(unit_prices[line["request_line_id"]])
            cur.execute("INSERT INTO PurchaseOrderLine VALUES (?,?,?,?,?,?,?)",
                (f"POL-SVC-{po_id[-6:]}-{i:02d}",po_id,line["request_line_id"],
                 line["item_description"],line["quantity"],unit,round(unit*int(line["quantity"]),2)))
        bt=self._next("BudgetTransaction","budget_transaction_id","BT-",6)
        cur.execute("INSERT INTO BudgetTransaction VALUES (?,?,?,?,?,?,?)",
            (bt,pr["budget_id"],po_id,"RESERVATION",total,pr["currency"],now))
        self._event("PURCHASE_ORDER",po_id,"DRAFT","ISSUED","PROCESS_OWNER",
                    "Approved single-source PO: "+rationale,now)
        self.con.commit()
        return {"purchase_order_id":po_id,"po_total":total,"supplier_id":supplier_id,
                "sourcing_type":"SINGLE_SOURCE","rationale":rationale}

    def record_delivery(self, purchase_order_id, quantity_received, now=None, inspection="PASSED"):
        now=stamp(now); cur=self.con.cursor()
        po=cur.execute("SELECT supplier_id,status FROM PurchaseOrder WHERE purchase_order_id=?",
                       (purchase_order_id,)).fetchone()
        if not po or po["status"] not in ("ISSUED","CLOSED"): raise ValueError("PO must be issued")
        ordered=cur.execute("SELECT COALESCE(SUM(quantity_ordered),0) FROM PurchaseOrderLine WHERE purchase_order_id=?",
                            (purchase_order_id,)).fetchone()[0]
        received=cur.execute("SELECT COALESCE(SUM(quantity_received),0) FROM Delivery WHERE purchase_order_id=?",
                             (purchase_order_id,)).fetchone()[0]
        qty=int(quantity_received)
        if qty<=0 or received+qty>ordered: raise ValueError("Delivery quantity exceeds outstanding ordered quantity")
        seq=cur.execute("SELECT COUNT(*) FROM Delivery WHERE purchase_order_id=?",(purchase_order_id,)).fetchone()[0]+1
        did=f"DEL-{purchase_order_id}-{seq:02d}"
        status="DELIVERED" if received+qty==ordered else "PARTIAL"
        cur.execute("INSERT INTO Delivery VALUES (?,?,?,?,?,?,?,?,?)",
            (did,purchase_order_id,po["supplier_id"],now,ordered,qty,status,inspection,
             "" if status=="DELIVERED" else "PARTIAL_DELIVERY"))
        if status=="DELIVERED":
            self._event("PURCHASE_ORDER",purchase_order_id,"ISSUED","CLOSED","OPERATIONS_ANALYST",
                        "All ordered quantities received",now)
            cur.execute("UPDATE PurchaseOrder SET status='CLOSED' WHERE purchase_order_id=?",(purchase_order_id,))
        self.con.commit()
        return {"delivery_id":did,"delivery_status":status,"outstanding_quantity":ordered-received-qty}

    def budget_summary(self, budget_id):
        row=self.con.execute("SELECT * FROM Budget WHERE budget_id=?",(budget_id,)).fetchone()
        if not row: raise ValueError("Budget not found")
        reserved=self.con.execute("SELECT COALESCE(SUM(amount),0) FROM BudgetTransaction WHERE budget_id=?",
                                   (budget_id,)).fetchone()[0]
        allocated=float(row["allocated_amount"])
        return {"budget_id":budget_id,"allocated":allocated,"reserved":float(reserved),
                "available":allocated-float(reserved),"utilization_pct":round(float(reserved)/allocated*100,2)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",required=True)
    p.add_argument("--budget-id")
    a=p.parse_args()
    svc=ProcurementService(a.db)
    try:
        if a.budget_id: print(json.dumps(svc.budget_summary(a.budget_id),indent=2))
        else: print("ProcurementService ready. Use its methods from Python; pass --budget-id for a budget summary.")
    finally: svc.close()
if __name__=="__main__": main()
