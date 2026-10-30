
#!/usr/bin/env python3
"""Integration smoke test for create -> approve -> RFQ -> quote -> award -> delivery."""
import argparse, shutil, tempfile, json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "generator"))
from procurement_service import ProcurementService

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--db",required=True); a=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="procurement_service_test_") as tmp:
        db=Path(tmp)/"service_test.db"; shutil.copy2(a.db,db)
        svc=ProcurementService(db)
        try:
            pr=svc.create_request("REQ-0001","BUD-001-2026",
                [{"item_description":"Test workstation","category":"IT_HARDWARE",
                  "quantity":2,"estimated_unit_price":20000}],
                "Integration test request","2026-12-15","2026-10-30T09:00:00")
            pr_id=pr["purchase_request_id"]
            try:
                svc.create_rfq(pr_id,["SUP-001","SUP-002","SUP-003"],"2026-11-15T17:00:00","2026-10-30T09:30:00")
                raise AssertionError("Unapproved request was incorrectly allowed into RFQ")
            except ValueError:
                pass
            svc.decide_approval(pr_id,"DEPARTMENT_MANAGER","APPROVED","Department approved","2026-10-30T10:00:00")
            state=svc.decide_approval(pr_id,"FINANCE","APPROVED","Finance approved","2026-10-30T11:00:00")
            assert state=="APPROVED",state
            rfq=svc.create_rfq(pr_id,["SUP-001","SUP-002","SUP-003"],"2026-11-15T17:00:00","2026-10-30T12:00:00")
            line=svc.con.execute("SELECT request_line_id FROM RequestLine WHERE purchase_request_id=?",(pr_id,)).fetchone()[0]
            quotes=[]
            for sid,unit in [("SUP-001",20000),("SUP-002",21000),("SUP-003",19000)]:
                quotes.append(svc.submit_quote(rfq,sid,{line:unit},6840,400,10,
                    "2026-12-01T23:00:00","INR","2026-10-30T13:00:00"))
            comparison=svc.compare_quotes(rfq,"2026-10-30T14:00:00")
            winner=next(x for x in comparison if x["quote_id"]==quotes[2])
            award=svc.award_quote(rfq,quotes[2],"Lowest landed cost with acceptable delivery","2026-10-30T14:30:00")
            delivery=svc.record_delivery(award["purchase_order_id"],2,"2026-11-05T12:00:00")
            budget=svc.budget_summary("BUD-001-2026")
            assert award["po_total"]==45240.0,award
            assert delivery["delivery_status"]=="DELIVERED",delivery
            assert delivery["outstanding_quantity"]==0
            assert budget["reserved"]>0
            # Exercise the documented single-source exception path on a separate approved request.
            pr2=svc.create_request("REQ-0003","BUD-003-2026",
                [{"item_description":"Specialized adapter","category":"IT_HARDWARE",
                  "quantity":1,"estimated_unit_price":10000}],
                "Compatibility-only single source","2026-12-20","2026-10-30T15:00:00")
            svc.decide_approval(pr2["purchase_request_id"],"DEPARTMENT_MANAGER","APPROVED",
                                "Department approved","2026-10-30T15:10:00")
            line2=svc.con.execute("SELECT request_line_id FROM RequestLine WHERE purchase_request_id=?",
                                  (pr2["purchase_request_id"],)).fetchone()[0]
            single=svc.create_single_source_po(pr2["purchase_request_id"],"SUP-004",
                {line2:10000},"OEM compatibility; no equivalent approved alternative",0,150,
                "2026-10-30T15:20:00")
            assert single["sourcing_type"]=="SINGLE_SOURCE"
            # The synthetic over-budget department must reject a new commitment.
            pr3=svc.create_request("REQ-0002","BUD-002-2026",
                [{"item_description":"Low-cost accessory","category":"IT_HARDWARE",
                  "quantity":1,"estimated_unit_price":1000}],
                "Budget guard integration test","2026-12-20","2026-10-30T16:00:00")
            svc.decide_approval(pr3["purchase_request_id"],"DEPARTMENT_MANAGER","APPROVED",
                                "Department approved","2026-10-30T16:10:00")
            line3=svc.con.execute("SELECT request_line_id FROM RequestLine WHERE purchase_request_id=?",
                                  (pr3["purchase_request_id"],)).fetchone()[0]
            budget_blocked=False
            try:
                svc.create_single_source_po(pr3["purchase_request_id"],"SUP-005",
                    {line3:1000},"Approved emergency exception",0,0,"2026-10-30T16:20:00")
            except ValueError as exc:
                budget_blocked="Insufficient budget" in str(exc)
            assert budget_blocked, "Over-budget single-source PO was not blocked"
            result={"status":"PASS","request_id":pr_id,"rfq_id":rfq,
                "awarded_quote":quotes[2],"purchase_order_id":award["purchase_order_id"],
                "po_total":award["po_total"],"delivery":delivery,
                "budget_after_reservation":budget,"supplier_comparison":comparison,
                "single_source_exception":single,"over_budget_award_blocked":budget_blocked}
            print(json.dumps(result,indent=2))
        finally: svc.close()
if __name__=="__main__": main()
