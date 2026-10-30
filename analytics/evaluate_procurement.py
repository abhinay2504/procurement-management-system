
#!/usr/bin/env python3
"""Evaluate quote competitiveness, supplier selection and budget utilization from SQLite."""
import argparse, csv, json, sqlite3
from pathlib import Path
from collections import defaultdict

def write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: path.write_text("",encoding="utf-8"); return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def score_quotes(con):
    rfqs=con.execute("SELECT * FROM RFQ").fetchall()
    result=[]
    for rfq in rfqs:
        quotes=con.execute("""SELECT q.*,s.risk_score,s.is_active FROM SupplierQuote q
            JOIN Supplier s ON s.supplier_id=q.supplier_id WHERE q.rfq_id=?""",(rfq["rfq_id"],)).fetchall()
        eligible=[q for q in quotes if q["currency"]==rfq["currency"] and
            q["valid_until"]>=rfq["closing_date"] and q["is_active"]]
        if not eligible: continue
        costs=[float(q["landed_total"]) for q in eligible]
        leads=[int(q["delivery_days"]) for q in eligible]
        risks=[int(q["risk_score"]) for q in eligible]
        def lower_better(v,arr):
            lo,hi=min(arr),max(arr)
            return 100.0 if hi==lo else 100*(hi-v)/(hi-lo)
        ranked=[]
        for q in eligible:
            cs=lower_better(float(q["landed_total"]),costs)
            ds=lower_better(int(q["delivery_days"]),leads)
            rs=lower_better(int(q["risk_score"]),risks)
            score=round(.60*cs+.25*ds+.15*rs,2)
            ranked.append({"rfq_id":rfq["rfq_id"],"quote_id":q["quote_id"],
                "supplier_id":q["supplier_id"],"landed_total":q["landed_total"],
                "delivery_days":q["delivery_days"],"supplier_risk_score":q["risk_score"],
                "cost_score":round(cs,2),"delivery_score":round(ds,2),
                "risk_score":round(rs,2),"weighted_score":score,
                "is_awarded":bool(q["is_selected"]),"award_rationale":q["award_rationale"]})
        ranked.sort(key=lambda x:(-x["weighted_score"],x["landed_total"]))
        for rank,row in enumerate(ranked,1):
            row["rank"]=rank
            result.append(row)
    return result

def budget_metrics(con):
    rows=con.execute("""SELECT b.budget_id,b.department_id,b.fiscal_year,b.currency,b.allocated_amount,
        COALESCE(SUM(bt.amount),0) AS committed
        FROM Budget b LEFT JOIN BudgetTransaction bt ON bt.budget_id=b.budget_id
        GROUP BY b.budget_id,b.department_id,b.fiscal_year,b.currency,b.allocated_amount
        ORDER BY b.budget_id""").fetchall()
    out=[]
    for r in rows:
        alloc=float(r["allocated_amount"]); used=float(r["committed"])
        out.append({"budget_id":r["budget_id"],"department_id":r["department_id"],
            "fiscal_year":r["fiscal_year"],"currency":r["currency"],"allocated":alloc,
            "committed":used,"available":alloc-used,
            "utilization_pct":round(used/alloc*100,2) if alloc else 0,
            "is_over_budget":used>alloc})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",required=True); ap.add_argument("--output",default="analytics_output")
    a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(a.db); con.row_factory=sqlite3.Row
    scores=score_quotes(con); budgets=budget_metrics(con)
    po=con.execute("SELECT COUNT(*) n,COALESCE(SUM(po_total),0) spend FROM PurchaseOrder").fetchone()
    pr=con.execute("SELECT COUNT(*) n FROM PurchaseRequest").fetchone()
    rfq=con.execute("SELECT COUNT(*) n FROM RFQ").fetchone()
    awarded=[x for x in scores if x["is_awarded"]]
    cheapest_awards=0
    unexplained=0
    for rfq_id in {x["rfq_id"] for x in scores}:
        group=[x for x in scores if x["rfq_id"]==rfq_id]
        winner=next((x for x in group if x["is_awarded"]),None)
        if winner:
            cheapest=min(x["landed_total"] for x in group)
            if abs(float(winner["landed_total"])-float(cheapest))<.01: cheapest_awards+=1
            elif not winner["award_rationale"]: unexplained+=1
    budget_alloc=sum(x["allocated"] for x in budgets)
    budget_commit=sum(x["committed"] for x in budgets)
    metrics={"purchase_requests":pr["n"],"rfqs":rfq["n"],"purchase_orders":po["n"],
        "total_po_spend":round(float(po["spend"]),2),"quote_score_rows":len(scores),
        "awarded_quotes_scored":len(awarded),"awards_at_lowest_landed_cost":cheapest_awards,
        "unexplained_non_lowest_awards":unexplained,
        "budget_allocation_total":round(budget_alloc,2),
        "budget_commitment_total":round(budget_commit,2),
        "budget_available_total":round(budget_alloc-budget_commit,2),
        "over_budget_departments":sum(x["is_over_budget"] for x in budgets)}
    write_csv(out/"supplier_quote_scores.csv",scores)
    write_csv(out/"budget_utilization.csv",budgets)
    (out/"procurement_kpis.json").write_text(json.dumps(metrics,indent=2)+"\n")
    con.close(); print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()
