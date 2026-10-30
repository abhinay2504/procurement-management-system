
#!/usr/bin/env python3
"""Deterministic end-to-end synthetic procurement data generator.

Examples:
  python generator/generate_data.py --seed 20261022 --scale starter --output generated_starter
  python generator/generate_data.py --seed 20261022 --scale full --output generated_full
"""
from __future__ import annotations
import argparse, csv, hashlib, json, random, sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from collections import defaultdict

SEED_DEFAULT = 20261022
START = date(2026, 1, 1)
COUNTS = {
    "starter": {"requesters":30, "suppliers":12, "requests":120, "rfqs":50, "quotes_per_rfq":3, "pos":90},
    "full": {"requesters":300, "suppliers":120, "requests":1200, "rfqs":500, "quotes_per_rfq":3, "pos":900},
}
DEPARTMENTS = ["IT","Finance","Human Resources","Operations","Marketing","Sales",
               "Research","Legal","Facilities","Customer Support","Security","Procurement"]
ITEMS = [
    ("Laptop","IT_HARDWARE",65000), ("Monitor","IT_HARDWARE",18000),
    ("Software License","SOFTWARE",24000), ("Office Chair","OFFICE_SUPPLIES",9500),
    ("Network Switch","NETWORKING",42000), ("Consulting Service","PROFESSIONAL_SERVICES",85000),
    ("Printer","IT_HARDWARE",28000), ("Maintenance Service","FACILITIES",35000),
    ("Keyboard","IT_HARDWARE",1800), ("Cloud Subscription","SOFTWARE",55000),
]

def iso(day, hour=10):
    return f"{day.isoformat()}T{hour:02d}:00:00"

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8"); return
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def write_json(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str)+"\n", encoding="utf-8")

def make_data(seed, scale):
    rng=random.Random(seed)
    n=COUNTS[scale]
    departments=[]
    for i,name in enumerate(DEPARTMENTS,1):
        departments.append({"department_id":f"DEPT-{i:03d}","department_name":name,
            "cost_center":f"CC-{1000+i}","is_active":True,
            "effective_from":"2026-01-01","effective_to":""})
    requesters=[]
    for i in range(1,n["requesters"]+1):
        dept=departments[(i-1)%len(departments)]
        requesters.append({"requester_id":f"REQ-{i:04d}","full_name":f"Employee {i:03d}",
            "email":f"employee{i:03d}@example.test","department_id":dept["department_id"],
            "role":"BUSINESS_REQUESTER","is_active":True,"effective_from":"2026-01-01","effective_to":""})
    budgets=[]
    for i,d in enumerate(departments,1):
        budgets.append({"budget_id":f"BUD-{i:03d}-2026","department_id":d["department_id"],
            "fiscal_year":2026,"currency":"INR","allocated_amount":100000000.00,
            "effective_from":"2026-01-01","effective_to":"2026-12-31"})
    suppliers=[]
    for i in range(1,n["suppliers"]+1):
        inactive = i in {17,44,88} and n["suppliers"]>=88
        high = i in {9,31,72,105} and n["suppliers"]>=105
        suppliers.append({"supplier_id":f"SUP-{i:03d}","supplier_code":f"S{i:03d}",
            "supplier_name":f"Supplier {i:03d} Pvt Ltd","country":"India","currency":"INR",
            "is_active":not inactive,"risk_flag":"HIGH" if high else ("MEDIUM" if i%7==0 else "LOW"),
            "risk_score":85 if high else (55 if i%7==0 else 20),
            "effective_from":"2025-01-01","effective_to":""})
    requests=[]; request_lines=[]; approvals=[]; status_events=[]; audit_logs=[]
    budget_by_dept={b["department_id"]:b for b in budgets}
    for i in range(1,n["requests"]+1):
        requester=requesters[(i-1)%len(requesters)]
        dept_id=requester["department_id"]
        item,cat,unit=rng.choice(ITEMS); qty=rng.randint(1,8)
        created=START+timedelta(days=rng.randint(0,220))
        est=round(unit*qty*rng.uniform(.93,1.10),2)
        duplicate_of=""
        split_group=""
        if i in (120,121) and n["requests"]>=121:
            item,cat,qty,est,created="Laptop","IT_HARDWARE",2,130000.00,START+timedelta(days=23)
            requester=requesters[119 % len(requesters)]; dept_id=requester["department_id"]
            if i==121: duplicate_of="PR-2026-000120"
        if i in (40,41) and n["requests"]>=41:

            item,cat,qty,est="Monitor","IT_HARDWARE",1,18000.00
            requester=requesters[39 % len(requesters)]; dept_id=requester["department_id"]
            split_group="SPLIT-2026-0001"
            created=START+timedelta(days=35+(i-40))
        if i==122 and n["requests"]>=122:
            est=950000.00
        threshold="DEPT_ONLY" if est<25000 else ("DEPT_FINANCE" if est<=100000 else "DEPT_FINANCE_EXEC")
        roles=["DEPARTMENT_MANAGER"] if threshold=="DEPT_ONLY" else (
            ["DEPARTMENT_MANAGER","FINANCE"] if threshold=="DEPT_FINANCE" else
            ["DEPARTMENT_MANAGER","FINANCE","EXECUTIVE"])
        request_status="APPROVED" if i<=min(900,n["pos"]) else ("REJECTED" if i%9==0 else "SUBMITTED")
        if i==6 and n["pos"]>=6:
            request_status="SUBMITTED"
        if i==122 and n["requests"]>=122:
            request_status="APPROVED"
        pr_id=f"PR-2026-{i:06d}"
        requests.append({"purchase_request_id":pr_id,"requester_id":requester["requester_id"],
            "department_id":dept_id,"budget_id":budget_by_dept[dept_id]["budget_id"],
            "request_date":iso(created,9),"required_by_date":(created+timedelta(days=30)).isoformat(),
            "business_justification":f"Operational requirement for {item.lower()}",
            "currency":"INR","estimated_total":est,"status":request_status,
            "duplicate_of_request_id":duplicate_of,"split_group_id":split_group})
        line_count=2 if i%17==0 else 1
        remaining=est
        for ln in range(1,line_count+1):
            line_item, line_cat, line_unit=(item,cat,unit) if ln==1 else rng.choice(ITEMS)
            line_qty=qty if ln==1 else rng.randint(1,3)
            if line_count==1:
                line_total=round(est,2)
            elif ln==1:
                line_total=round(est*.65,2)
            else:
                line_total=round(est-sum(float(z["estimated_line_total"]) for z in request_lines if z["purchase_request_id"]==pr_id),2)
            request_lines.append({"request_line_id":f"PRL-{i:06d}-{ln:02d}","purchase_request_id":pr_id,
                "line_number":ln,"item_description":line_item,"category":line_cat,"quantity":line_qty,
                "unit_of_measure":"EACH","estimated_unit_price":line_total/line_qty,
                "estimated_line_total":line_total})
        for j,role in enumerate(roles,1):
            decision="APPROVED" if i<=min(900,n["pos"]) else ("REJECTED" if request_status=="REJECTED" else "PENDING")
            if i==6: decision="PENDING"
            approvals.append({"approval_id":f"APR-{i:06d}-{j:02d}","purchase_request_id":pr_id,
                "approver_role":role,"decision":decision,"decision_date":iso(created+timedelta(days=j),11),
                "threshold_rule":threshold,"comments":"Reviewed against configured approval matrix"})
        status_events.append({"event_id":f"EVT-PR-{i:06d}-01","entity_type":"PURCHASE_REQUEST",
            "entity_id":pr_id,"from_status":"DRAFT","to_status":request_status,
            "event_time":iso(created+timedelta(days=1),12),"actor_role":"PROCESS_OWNER",
            "reason":"Submission and approval workflow evaluation"})
        audit_logs.append({"audit_id":f"AUD-{i:07d}","entity_type":"PURCHASE_REQUEST",
            "entity_id":pr_id,"action":"CREATE","actor_id":requester["requester_id"],
            "event_time":iso(created,9),"details":"Synthetic purchase request created"})

    rfqs=[]; rfq_suppliers=[]; quotes=[]; quote_lines=[]
    rfq_request_indices=list(range(1,min(n["rfqs"],n["requests"])+1))
    for i,req_idx in enumerate(rfq_request_indices,1):
        pr=requests[req_idx-1]; rfq_id=f"RFQ-2026-{i:06d}"
        issue_day=max(START+timedelta(days=30+(i%150)),
                      date.fromisoformat(pr["request_date"][:10])+timedelta(days=1))
        rfqs.append({"rfq_id":rfq_id,"purchase_request_id":pr["purchase_request_id"],
            "issue_date":iso(issue_day,10),"closing_date":iso(issue_day+timedelta(days=14),17),
            "currency":"INR","sourcing_type":"COMPETITIVE","status":"AWARDED","minimum_quote_count":3})

        selected_suppliers=rng.sample(suppliers,3)
        if i==4 and len(suppliers)>=17:
            selected_suppliers=[suppliers[16]]+[x for x in selected_suppliers if x["supplier_id"]!="SUP-017"][:2]
        line_set=[x for x in request_lines if x["purchase_request_id"]==pr["purchase_request_id"]]
        for j,sup in enumerate(selected_suppliers,1):
            rfq_suppliers.append({"rfq_supplier_id":f"RFQS-{i:04d}-{j:02d}","rfq_id":rfq_id,
                "supplier_id":sup["supplier_id"],"invited_at":iso(issue_day,10),"response_status":"RESPONDED"})
            subtotal=round(sum(float(x["estimated_line_total"]) for x in line_set)*rng.uniform(.88,1.15),2)
            tax=round(subtotal*.18,2); freight=round(subtotal*rng.uniform(.005,.03),2)
            lead=rng.randint(5,35); valid=issue_day+timedelta(days=21)
            currency="USD" if i==7 and j==3 else "INR"
            if i==2 and j==1: valid=issue_day+timedelta(days=5)
            qid=f"QUO-{sup['supplier_code']}-2026-{((i-1)*3+j):06d}"
            quotes.append({"quote_id":qid,"rfq_id":rfq_id,"supplier_id":sup["supplier_id"],
                "quote_date":iso(issue_day+timedelta(days=2),14),"valid_until":iso(valid,23),
                "currency":currency,"subtotal":subtotal,"tax_amount":tax,"freight_amount":freight,
                "landed_total":round(subtotal+tax+freight,2),"delivery_days":lead,
                "status":"RECEIVED","award_rationale":"","is_selected":False})
            for ln,x in enumerate(line_set,1):
                qline_total=round(float(x["estimated_line_total"])*subtotal/
                    max(1,sum(float(y["estimated_line_total"]) for y in line_set)),2)
                if ln==len(line_set):
                    prior=sum(float(z["line_total"]) for z in quote_lines if z["quote_id"]==qid)
                    qline_total=round(subtotal-prior,2)
                quote_lines.append({"quote_line_id":f"QL-{i:04d}-{j:02d}-{ln:02d}","quote_id":qid,
                    "request_line_id":x["request_line_id"],"quantity":x["quantity"],
                    "unit_price":qline_total/x["quantity"],"line_total":qline_total})

        group=[q for q in quotes if q["rfq_id"]==rfq_id]
        eligible=[q for q in group if q["currency"]=="INR" and q["valid_until"]>=iso(issue_day+timedelta(days=15),0)
                  and next(s for s in suppliers if s["supplier_id"]==q["supplier_id"])["is_active"]]
        if not eligible: eligible=group
        eligible.sort(key=lambda q:(q["landed_total"],q["delivery_days"],q["supplier_id"]))
        selected=eligible[0]
        if i==3 and len(eligible)>1:
            selected=eligible[-1]
            selected["award_rationale"]=""
        if i==2:

            selected=group[0]
        if i==4 and len(suppliers)>=17:
            selected=next(q for q in group if q["supplier_id"]=="SUP-017")
            selected["award_rationale"]="Emergency continuity override; inactive supplier approval required"
        selected["is_selected"]=True; selected["status"]="AWARDED"
        for q in group:
            if q is not selected and q["valid_until"]<iso(issue_day+timedelta(days=15),0):
                q["status"]="EXPIRED"
            elif q is not selected:
                q["status"]="REJECTED"

    pos=[]; po_lines=[]; deliveries=[]; budget_transactions=[]

    for i in range(1,min(n["pos"],n["requests"])+1):
        pr=requests[i-1]; po_id=f"PO-2026-{i:06d}"
        rfq_id=""; quote_id=""; supplier_id=""; rationale=""
        subtotal=tax=freight=0.0
        if i<=n["rfqs"]:
            rfq_id=f"RFQ-2026-{i:06d}"
            selected=next(q for q in quotes if q["rfq_id"]==rfq_id and q["is_selected"])
            quote_id=selected["quote_id"]; supplier_id=selected["supplier_id"]
            subtotal=float(selected["subtotal"]); tax=float(selected["tax_amount"]); freight=float(selected["freight_amount"])
            rationale=selected["award_rationale"]
        else:
            active_suppliers=[x for x in suppliers if x["is_active"]]
            sup=active_suppliers[(i*7)%len(active_suppliers)]
            supplier_id=sup["supplier_id"]
            subtotal=round(float(pr["estimated_total"])*rng.uniform(.90,1.08),2)
            tax=round(subtotal*.18,2); freight=round(subtotal*.015,2)
            rationale="Approved single-source exception: compatibility and continuity requirement"
        approval_status="APPROVED"
        if i==6:
            approval_status="NOT_APPROVED"
            rationale="Injected control failure: PO issued while required approvals remain pending"
        if i==122 and n["pos"]>=122:

            subtotal=150000000.00; tax=0.0; freight=0.0
            rationale="Budget overrun test case; commitment exceeds approved departmental allocation"
            quote_id=""; rfq_id=""
        total=round(subtotal+tax+freight,2)
        po_day=max(START+timedelta(days=160+(i%70)),
                   date.fromisoformat(pr["request_date"][:10])+timedelta(days=10))
        if rfq_id:
            close_day=date.fromisoformat(next(x for x in rfqs if x["rfq_id"]==rfq_id)["closing_date"][:10])
            po_day=max(po_day,close_day+timedelta(days=1))
        po_date=iso(po_day,15)
        pos.append({"purchase_order_id":po_id,"purchase_request_id":pr["purchase_request_id"],
            "supplier_id":supplier_id,"rfq_id":rfq_id,"awarded_quote_id":quote_id,
            "po_date":po_date,"currency":"INR","subtotal":subtotal,"tax_amount":tax,
            "freight_amount":freight,"po_total":total,"approval_status":approval_status,
            "status":"ISSUED","award_rationale":rationale,"payment_terms":"NET_30"})
        pr_lines=[x for x in request_lines if x["purchase_request_id"]==pr["purchase_request_id"]]
        if quote_id:
            source_lines=[x for x in quote_lines if x["quote_id"]==quote_id]
            line_map={x["request_line_id"]:x for x in source_lines}
            for k,x in enumerate(pr_lines,1):
                ql=line_map[x["request_line_id"]]
                line_amount=float(ql["line_total"])
                po_lines.append({"po_line_id":f"POL-{i:06d}-{k:02d}","purchase_order_id":po_id,
                    "request_line_id":x["request_line_id"],"description":x["item_description"],
                    "quantity_ordered":int(ql["quantity"]),"unit_price":float(ql["unit_price"]),
                    "line_total":line_amount})
        else:
            line_weights=[float(x["estimated_line_total"]) for x in pr_lines]
            denominator=sum(line_weights) or 1
            allocated=0.0
            for k,x in enumerate(pr_lines,1):
                line_amount=round(subtotal*line_weights[k-1]/denominator,2)
                if k==len(pr_lines): line_amount=round(subtotal-allocated,2)
                allocated+=line_amount
                po_lines.append({"po_line_id":f"POL-{i:06d}-{k:02d}","purchase_order_id":po_id,
                    "request_line_id":x["request_line_id"],"description":x["item_description"],
                    "quantity_ordered":x["quantity"],"unit_price":line_amount/x["quantity"],
                    "line_total":line_amount})
        budget_transactions.append({"budget_transaction_id":f"BT-{i:06d}","budget_id":pr["budget_id"],
            "purchase_order_id":po_id,"transaction_type":"RESERVATION","amount":total,
            "currency":"INR","transaction_date":po_date})
        for dno in (1,2) if i%5==0 else (1,):
            qty=pr_lines[0]["quantity"]
            received=max(1,qty//2) if i%5==0 and dno==1 else (qty-max(1,qty//2) if i%5==0 else qty)
            delivery_id=f"DEL-{po_id}-{dno:02d}"
            deliveries.append({"delivery_id":delivery_id,"purchase_order_id":po_id,
                "supplier_id":supplier_id,"delivery_date":iso(po_day+timedelta(days=10+dno),13),
                "quantity_ordered":qty,"quantity_received":received,
                "delivery_status":"PARTIAL" if received<qty else "DELIVERED",
                "inspection_status":"PENDING" if received<qty else "PASSED",
                "delivery_exception_reason":"PARTIAL_DELIVERY" if received<qty else ""})
        status_events.append({"event_id":f"EVT-PO-{i:06d}-01","entity_type":"PURCHASE_ORDER",
            "entity_id":po_id,"from_status":"DRAFT","to_status":"ISSUED",
            "event_time":po_date,"actor_role":"PROCESS_OWNER","reason":"PO issue event"})
        audit_logs.append({"audit_id":f"AUD-{n['requests']+i:07d}","entity_type":"PURCHASE_ORDER",
            "entity_id":po_id,"action":"ISSUE","actor_id":"SYSTEM-PROCUREMENT",
            "event_time":po_date,"details":"PO issuance recorded"})

    gt=[]
    def label(case, entity_type, entity_id, issue, severity, expected, rule):
        gt.append({"case_id":f"GT-{case:03d}","entity_type":entity_type,"entity_id":entity_id,
            "issue_type":issue,"severity":severity,"expected_label":expected,"rule":rule})
    if n["pos"]>=6:
        label(1,"PURCHASE_ORDER","PO-2026-000006","PO_ISSUED_WITHOUT_APPROVAL","CRITICAL","CONTROL_FAILURE",
              "A PO cannot be ISSUED unless all approval steps are APPROVED")
    if n["rfqs"]>=2:
        q=next(q for q in quotes if q["rfq_id"]=="RFQ-2026-000002" and q["is_selected"])
        label(2,"SUPPLIER_QUOTE",q["quote_id"],"QUOTE_EXPIRED_BEFORE_AWARD","HIGH","INVALID_AWARD",
              "Award date must be on or before quote valid_until")
    if n["rfqs"]>=3:
        q=next(q for q in quotes if q["rfq_id"]=="RFQ-2026-000003" and q["is_selected"])
        label(3,"SUPPLIER_QUOTE",q["quote_id"],"SELECTED_NOT_CHEAPEST","MEDIUM","RATIONALE_REQUIRED",
              "Selected quote must be cheapest or have a documented decision rationale")
    if n["rfqs"]>=4 and n["suppliers"]>=17:
        label(4,"SUPPLIER","SUP-017","SUPPLIER_INACTIVE_AT_AWARD","HIGH","SUPPLIER_STATUS_EXCEPTION",
              "Supplier must be active at award date unless an approved exception exists")
    if n["pos"]>=122:
        label(5,"PURCHASE_ORDER","PO-2026-000122","BUDGET_OVERRUN","HIGH","OVER_BUDGET",
              "Cumulative reservations must not exceed budget allocation")
    if n["requests"]>=121:
        label(6,"PURCHASE_REQUEST","PR-2026-000121","DUPLICATE_REQUEST","MEDIUM","DUPLICATE",
              "Duplicate requester/item/category/quantity/date fingerprint")
    if n["rfqs"]>=7:
        q=next(q for q in quotes if q["rfq_id"]=="RFQ-2026-000007" and q["currency"]=="USD")
        label(7,"SUPPLIER_QUOTE",q["quote_id"],"QUOTE_CURRENCY_MISMATCH","HIGH","CURRENCY_MISMATCH",
              "Quote currency must match RFQ currency or have an explicit FX conversion")

    tables={
      "Department":departments,"Requester":requesters,"Budget":budgets,"Supplier":suppliers,
      "PurchaseRequest":requests,"RequestLine":request_lines,"RFQ":rfqs,"RFQSupplier":rfq_suppliers,
      "SupplierQuote":quotes,"QuoteLine":quote_lines,"Approval":approvals,"PurchaseOrder":pos,
      "PurchaseOrderLine":po_lines,"Delivery":deliveries,"BudgetTransaction":budget_transactions,
      "StatusEvent":status_events,"AuditLog":audit_logs
    }
    return tables,gt

def create_sqlite(db_path, tables):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists(): db_path.unlink()
    con=sqlite3.connect(db_path); con.execute("PRAGMA foreign_keys=ON")
    ddl=[
      "CREATE TABLE Department(department_id TEXT PRIMARY KEY, department_name TEXT UNIQUE NOT NULL, cost_center TEXT UNIQUE NOT NULL, is_active INTEGER NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT)",
      "CREATE TABLE Requester(requester_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, department_id TEXT NOT NULL REFERENCES Department, role TEXT NOT NULL, is_active INTEGER NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT)",
      "CREATE TABLE Budget(budget_id TEXT PRIMARY KEY, department_id TEXT NOT NULL REFERENCES Department, fiscal_year INTEGER NOT NULL, currency TEXT NOT NULL, allocated_amount REAL NOT NULL CHECK(allocated_amount>0), effective_from TEXT NOT NULL, effective_to TEXT NOT NULL)",
      "CREATE TABLE Supplier(supplier_id TEXT PRIMARY KEY, supplier_code TEXT UNIQUE NOT NULL, supplier_name TEXT NOT NULL, country TEXT NOT NULL, currency TEXT NOT NULL, is_active INTEGER NOT NULL, risk_flag TEXT NOT NULL CHECK(risk_flag IN ('LOW','MEDIUM','HIGH')), risk_score INTEGER NOT NULL CHECK(risk_score BETWEEN 0 AND 100), effective_from TEXT NOT NULL, effective_to TEXT)",
      "CREATE TABLE PurchaseRequest(purchase_request_id TEXT PRIMARY KEY, requester_id TEXT NOT NULL REFERENCES Requester, department_id TEXT NOT NULL REFERENCES Department, budget_id TEXT NOT NULL REFERENCES Budget, request_date TEXT NOT NULL, required_by_date TEXT NOT NULL, business_justification TEXT NOT NULL, currency TEXT NOT NULL, estimated_total REAL NOT NULL, status TEXT NOT NULL, duplicate_of_request_id TEXT REFERENCES PurchaseRequest, split_group_id TEXT)",
      "CREATE TABLE RequestLine(request_line_id TEXT PRIMARY KEY, purchase_request_id TEXT NOT NULL REFERENCES PurchaseRequest, line_number INTEGER NOT NULL, item_description TEXT NOT NULL, category TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), unit_of_measure TEXT NOT NULL, estimated_unit_price REAL NOT NULL, estimated_line_total REAL NOT NULL, UNIQUE(purchase_request_id,line_number))",
      "CREATE TABLE RFQ(rfq_id TEXT PRIMARY KEY, purchase_request_id TEXT UNIQUE NOT NULL REFERENCES PurchaseRequest, issue_date TEXT NOT NULL, closing_date TEXT NOT NULL, currency TEXT NOT NULL, sourcing_type TEXT NOT NULL, status TEXT NOT NULL, minimum_quote_count INTEGER NOT NULL)",
      "CREATE TABLE RFQSupplier(rfq_supplier_id TEXT PRIMARY KEY, rfq_id TEXT NOT NULL REFERENCES RFQ, supplier_id TEXT NOT NULL REFERENCES Supplier, invited_at TEXT NOT NULL, response_status TEXT NOT NULL, UNIQUE(rfq_id,supplier_id))",
      "CREATE TABLE SupplierQuote(quote_id TEXT PRIMARY KEY, rfq_id TEXT NOT NULL REFERENCES RFQ, supplier_id TEXT NOT NULL REFERENCES Supplier, quote_date TEXT NOT NULL, valid_until TEXT NOT NULL, currency TEXT NOT NULL, subtotal REAL NOT NULL, tax_amount REAL NOT NULL, freight_amount REAL NOT NULL, landed_total REAL NOT NULL, delivery_days INTEGER NOT NULL, status TEXT NOT NULL, award_rationale TEXT, is_selected INTEGER NOT NULL)",
      "CREATE TABLE QuoteLine(quote_line_id TEXT PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES SupplierQuote, request_line_id TEXT NOT NULL REFERENCES RequestLine, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL)",
      "CREATE TABLE Approval(approval_id TEXT PRIMARY KEY, purchase_request_id TEXT NOT NULL REFERENCES PurchaseRequest, approver_role TEXT NOT NULL, decision TEXT NOT NULL, decision_date TEXT NOT NULL, threshold_rule TEXT NOT NULL, comments TEXT)",
      "CREATE TABLE PurchaseOrder(purchase_order_id TEXT PRIMARY KEY, purchase_request_id TEXT UNIQUE NOT NULL REFERENCES PurchaseRequest, supplier_id TEXT NOT NULL REFERENCES Supplier, rfq_id TEXT REFERENCES RFQ, awarded_quote_id TEXT REFERENCES SupplierQuote, po_date TEXT NOT NULL, currency TEXT NOT NULL, subtotal REAL NOT NULL, tax_amount REAL NOT NULL, freight_amount REAL NOT NULL, po_total REAL NOT NULL, approval_status TEXT NOT NULL, status TEXT NOT NULL, award_rationale TEXT, payment_terms TEXT)",
      "CREATE TABLE PurchaseOrderLine(po_line_id TEXT PRIMARY KEY, purchase_order_id TEXT NOT NULL REFERENCES PurchaseOrder, request_line_id TEXT NOT NULL REFERENCES RequestLine, description TEXT NOT NULL, quantity_ordered INTEGER NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL)",
      "CREATE TABLE Delivery(delivery_id TEXT PRIMARY KEY, purchase_order_id TEXT NOT NULL REFERENCES PurchaseOrder, supplier_id TEXT NOT NULL REFERENCES Supplier, delivery_date TEXT NOT NULL, quantity_ordered INTEGER NOT NULL, quantity_received INTEGER NOT NULL, delivery_status TEXT NOT NULL, inspection_status TEXT NOT NULL, delivery_exception_reason TEXT)",
      "CREATE TABLE BudgetTransaction(budget_transaction_id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES Budget, purchase_order_id TEXT NOT NULL REFERENCES PurchaseOrder, transaction_type TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, transaction_date TEXT NOT NULL)",
      "CREATE TABLE StatusEvent(event_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, event_time TEXT NOT NULL, actor_role TEXT NOT NULL, reason TEXT)",
      "CREATE TABLE AuditLog(audit_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, action TEXT NOT NULL, actor_id TEXT NOT NULL, event_time TEXT NOT NULL, details TEXT)"
    ]
    for sql in ddl: con.execute(sql)
    for table in ["Department","Requester","Budget","Supplier","PurchaseRequest","RequestLine","RFQ","RFQSupplier","SupplierQuote","QuoteLine","Approval","PurchaseOrder","PurchaseOrderLine","Delivery","BudgetTransaction","StatusEvent","AuditLog"]:
        rows=tables[table]
        if not rows: continue
        cols=list(rows[0]); sql=f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
        vals=[]
        for row in rows:
            vals.append(tuple(None if v=="" else (int(v) if isinstance(v,bool) else v) for v in row.values()))
        try:
            con.executemany(sql,vals)
        except Exception as exc:
            raise RuntimeError(f"Insert failed for {table}: {exc}") from exc
    con.commit()
    fk=con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    if fk: raise RuntimeError(f"SQLite FK violations: {fk[:5]}")
    return ddl

def evaluate(tables, gt):
    idx={k:{r[list(r)[0]]:r for r in v} for k,v in tables.items() if v}
    reqs=tables["PurchaseRequest"]; approvals=tables["Approval"]; pos=tables["PurchaseOrder"]
    quotes=tables["SupplierQuote"]; suppliers={s["supplier_id"]:s for s in tables["Supplier"]}
    budgets={b["budget_id"]:b for b in tables["Budget"]}
    budget_used=defaultdict(float)
    for bt in tables["BudgetTransaction"]: budget_used[bt["budget_id"]]+=float(bt["amount"])
    issues=[]
    def issue(code, entity, entity_id, detail, expected=False):
        issues.append({"rule_id":code,"entity_type":entity,"entity_id":entity_id,
                       "detail":detail,"is_known_injected_exception":expected})
    gt_pairs={(g["entity_type"],g["entity_id"]):g["issue_type"] for g in gt}

    for pr in reqs:
        amount=float(pr["estimated_total"])
        expected=["DEPARTMENT_MANAGER"] if amount<25000 else (
            ["DEPARTMENT_MANAGER","FINANCE"] if amount<=100000 else
            ["DEPARTMENT_MANAGER","FINANCE","EXECUTIVE"])
        actual=[a for a in approvals if a["purchase_request_id"]==pr["purchase_request_id"]]
        for role in expected:
            if not any(a["approver_role"]==role and a["decision"]=="APPROVED" for a in actual):
                if pr["status"]=="APPROVED":
                    issue("APPROVAL_REQUIRED","PURCHASE_REQUEST",pr["purchase_request_id"],
                          f"Missing approved step {role}",("PURCHASE_REQUEST",pr["purchase_request_id"]) in gt_pairs)

    for q in quotes:
        rfq=next(x for x in tables["RFQ"] if x["rfq_id"]==q["rfq_id"])
        if q["currency"]!=rfq["currency"]:
            issue("CURRENCY_MISMATCH","SUPPLIER_QUOTE",q["quote_id"],"Quote currency differs from RFQ",
                  ("SUPPLIER_QUOTE",q["quote_id"]) in gt_pairs)
        if q["is_selected"]:
            if q["valid_until"] < rfq["closing_date"]:
                issue("QUOTE_EXPIRED","SUPPLIER_QUOTE",q["quote_id"],"Selected quote expired before RFQ close",
                      ("SUPPLIER_QUOTE",q["quote_id"]) in gt_pairs)
            if not suppliers[q["supplier_id"]]["is_active"]:
                issue("INACTIVE_SUPPLIER","SUPPLIER",q["supplier_id"],"Selected supplier inactive",
                      ("SUPPLIER",q["supplier_id"]) in gt_pairs)
            award_eligible=[x for x in quotes if x["rfq_id"]==q["rfq_id"]
                and x["currency"]==rfq["currency"] and x["valid_until"]>=rfq["closing_date"]
                and suppliers[x["supplier_id"]]["is_active"]]
            if q in award_eligible:
                cheapest=min((float(x["landed_total"]) for x in award_eligible),default=float(q["landed_total"]))
                if float(q["landed_total"])>cheapest+.01 and not q["award_rationale"]:
                    issue("AWARD_RATIONALE","SUPPLIER_QUOTE",q["quote_id"],"Non-cheapest eligible award lacks rationale",
                          ("SUPPLIER_QUOTE",q["quote_id"]) in gt_pairs)

    for po in pos:
        if po["status"]=="ISSUED" and po["approval_status"]!="APPROVED":
            issue("PO_WITHOUT_APPROVAL","PURCHASE_ORDER",po["purchase_order_id"],"Issued PO is not approved",
                  ("PURCHASE_ORDER",po["purchase_order_id"]) in gt_pairs)
        if po["awarded_quote_id"]:
            q=next(x for x in quotes if x["quote_id"]==po["awarded_quote_id"])
            if abs(float(po["po_total"])-float(q["landed_total"]))>.02:
                issue("PO_QUOTE_TOTAL","PURCHASE_ORDER",po["purchase_order_id"],"PO total differs from awarded quote landed total",
                      ("PURCHASE_ORDER",po["purchase_order_id"]) in gt_pairs)
        if not suppliers[po["supplier_id"]]["is_active"]:
            issue("PO_INACTIVE_SUPPLIER","PURCHASE_ORDER",po["purchase_order_id"],"PO supplier inactive",
                  ("SUPPLIER",po["supplier_id"]) in gt_pairs)

    for budget_id,spent in budget_used.items():
        allocation=float(budgets[budget_id]["allocated_amount"])
        if spent>allocation:
            related=[x for x in tables["BudgetTransaction"] if x["budget_id"]==budget_id]
            for bt in related:
                po_id=bt["purchase_order_id"]
                if ("PURCHASE_ORDER",po_id) in gt_pairs:
                    issue("BUDGET_OVERRUN","PURCHASE_ORDER",po_id,
                          f"Budget {budget_id}: {spent:.2f} committed > {allocation:.2f} allocated",True)
                    break
            else:
                issue("BUDGET_OVERRUN","BUDGET",budget_id,
                      f"{spent:.2f} committed > {allocation:.2f} allocated",False)

    seen={}
    for pr in reqs:
        lines=[x for x in tables["RequestLine"] if x["purchase_request_id"]==pr["purchase_request_id"]]
        for line in lines:
            key=(pr["requester_id"],line["item_description"],line["category"],line["quantity"],pr["request_date"][:10])
            if key in seen and seen[key] != pr["purchase_request_id"]:
                issue("DUPLICATE_REQUEST","PURCHASE_REQUEST",pr["purchase_request_id"],
                      f"Duplicate fingerprint of {seen[key]}",("PURCHASE_REQUEST",pr["purchase_request_id"]) in gt_pairs)
            else:
                seen[key]=pr["purchase_request_id"]

    for po in pos:
        ds=[d for d in tables["Delivery"] if d["purchase_order_id"]==po["purchase_order_id"]]
        if ds:
            ordered=max(d["quantity_ordered"] for d in ds)
            received=sum(d["quantity_received"] for d in ds)
            if received>ordered:
                issue("DELIVERY_OVER_RECEIPT","PURCHASE_ORDER",po["purchase_order_id"],
                      "Cumulative receipts exceed ordered quantity",False)
    expected_types={g["issue_type"] for g in gt}
    detected_types=set()
    for x in issues:
        code=x["rule_id"]
        mapping={"PO_WITHOUT_APPROVAL":"PO_ISSUED_WITHOUT_APPROVAL","QUOTE_EXPIRED":"QUOTE_EXPIRED_BEFORE_AWARD",
                 "AWARD_RATIONALE":"SELECTED_NOT_CHEAPEST","INACTIVE_SUPPLIER":"SUPPLIER_INACTIVE_AT_AWARD",
                 "PO_INACTIVE_SUPPLIER":"SUPPLIER_INACTIVE_AT_AWARD","BUDGET_OVERRUN":"BUDGET_OVERRUN",
                 "DUPLICATE_REQUEST":"DUPLICATE_REQUEST","CURRENCY_MISMATCH":"QUOTE_CURRENCY_MISMATCH"}
        if code in mapping: detected_types.add(mapping[code])
    missing=sorted(expected_types-detected_types)
    unexpected=[x for x in issues if not x["is_known_injected_exception"]]
    return issues, {"ground_truth_cases":len(gt),"detected_issue_types":sorted(detected_types),
        "missing_ground_truth_issue_types":missing,"known_exception_findings":sum(x["is_known_injected_exception"] for x in issues),
        "unclassified_findings":len(unexpected),"budget_allocated_total":sum(float(b["allocated_amount"]) for b in tables["Budget"]),
        "budget_committed_total":sum(float(x["amount"]) for x in tables["BudgetTransaction"]),
        "purchase_order_total":sum(float(x["po_total"]) for x in pos),
        "partial_delivery_events":sum(1 for d in tables["Delivery"] if d["delivery_status"]=="PARTIAL")}

def validate(tables, gt, scale):
    checks=[]
    def add(name, ok, detail): checks.append({"check":name,"status":"PASS" if ok else "FAIL","detail":detail})
    expected=COUNTS[scale]
    for table,key,count in [("Requester","requester_id",expected["requesters"]),
        ("Supplier","supplier_id",expected["suppliers"]),("PurchaseRequest","purchase_request_id",expected["requests"]),
        ("RFQ","rfq_id",expected["rfqs"]),("SupplierQuote","quote_id",expected["rfqs"]*expected["quotes_per_rfq"]),
        ("PurchaseOrder","purchase_order_id",expected["pos"])]:
        rows=tables[table]
        add(f"{table}_volume",len(rows)==count,f"{len(rows)} / {count}")
        add(f"{table}_pk_unique",len({r[key] for r in rows})==len(rows),f"{key} uniqueness")

    keys={t:{r[list(r)[0]] for r in rows} for t,rows in tables.items() if rows}
    fk_specs=[("Requester","department_id","Department"),("Budget","department_id","Department"),
      ("PurchaseRequest","requester_id","Requester"),("PurchaseRequest","department_id","Department"),
      ("PurchaseRequest","budget_id","Budget"),("RequestLine","purchase_request_id","PurchaseRequest"),
      ("RFQ","purchase_request_id","PurchaseRequest"),("RFQSupplier","rfq_id","RFQ"),
      ("RFQSupplier","supplier_id","Supplier"),("SupplierQuote","rfq_id","RFQ"),
      ("SupplierQuote","supplier_id","Supplier"),("QuoteLine","quote_id","SupplierQuote"),
      ("QuoteLine","request_line_id","RequestLine"),("Approval","purchase_request_id","PurchaseRequest"),
      ("PurchaseOrder","purchase_request_id","PurchaseRequest"),("PurchaseOrder","supplier_id","Supplier"),
      ("PurchaseOrderLine","purchase_order_id","PurchaseOrder"),("PurchaseOrderLine","request_line_id","RequestLine"),
      ("Delivery","purchase_order_id","PurchaseOrder"),("Delivery","supplier_id","Supplier"),
      ("BudgetTransaction","budget_id","Budget"),("BudgetTransaction","purchase_order_id","PurchaseOrder")]
    for child,col,parent in fk_specs:
        ok=all(r[col] in keys[parent] for r in tables[child])
        add(f"FK_{child}_{col}",ok,f"{child}.{col} -> {parent}")
    for q in tables["SupplierQuote"]:
        add_ok=abs(float(q["landed_total"])-sum(float(q[k]) for k in ("subtotal","tax_amount","freight_amount")))<.02
        if not add_ok: break
    else: add_ok=True
    add("quote_landed_cost_arithmetic",add_ok,"landed_total = subtotal + tax + freight")
    po_ok=all(abs(float(p["po_total"])-sum(float(p[k]) for k in ("subtotal","tax_amount","freight_amount")))<.02 for p in tables["PurchaseOrder"])
    add("po_total_arithmetic",po_ok,"po_total = subtotal + tax + freight")
    po_line_ok=all(abs(float(x["line_total"])-float(x["unit_price"])*int(x["quantity_ordered"]))<.02 for x in tables["PurchaseOrderLine"])
    add("po_line_arithmetic",po_line_ok,"PO line total = unit price x quantity")
    quote_line_ok=all(abs(float(x["line_total"])-float(x["unit_price"])*int(x["quantity"]))<.02 for x in tables["QuoteLine"])
    add("quote_line_arithmetic",quote_line_ok,"Quote line total = unit price x quantity")
    po_subtotal_ok=True
    for po in tables["PurchaseOrder"]:
        line_sum=sum(float(x["line_total"]) for x in tables["PurchaseOrderLine"] if x["purchase_order_id"]==po["purchase_order_id"])
        if abs(line_sum-float(po["subtotal"]))>.02: po_subtotal_ok=False; break
    add("po_line_subtotal_reconciliation",po_subtotal_ok,"Sum of PO lines = PO subtotal")
    po_quote_ok=True
    for po in tables["PurchaseOrder"]:
        if po["awarded_quote_id"]:
            qmap={x["request_line_id"]:x for x in tables["QuoteLine"] if x["quote_id"]==po["awarded_quote_id"]}
            pmap={x["request_line_id"]:x for x in tables["PurchaseOrderLine"] if x["purchase_order_id"]==po["purchase_order_id"]}
            if set(qmap)!=set(pmap) or any(abs(float(qmap[k]["line_total"])-float(pmap[k]["line_total"]))>.02
                or int(qmap[k]["quantity"])!=int(pmap[k]["quantity_ordered"]) for k in qmap):
                po_quote_ok=False; break
    add("po_awarded_quote_line_reconciliation",po_quote_ok,"Awarded quote lines match PO lines by request line, quantity and line total")
    budget_ok=True
    for po in tables["PurchaseOrder"]:
        bt=[x for x in tables["BudgetTransaction"] if x["purchase_order_id"]==po["purchase_order_id"] and x["transaction_type"]=="RESERVATION"]
        pr=next(x for x in tables["PurchaseRequest"] if x["purchase_request_id"]==po["purchase_request_id"])
        if len(bt)!=1 or abs(float(bt[0]["amount"])-float(po["po_total"]))>.02 or bt[0]["budget_id"]!=pr["budget_id"]:
            budget_ok=False; break
    add("budget_reservation_reconciliation",budget_ok,"Exactly one reservation per PO; amount and budget match PO/request")
    date_ok=all(r["required_by_date"]>=r["request_date"][:10] for r in tables["PurchaseRequest"])
    date_ok=date_ok and all(x["closing_date"]>x["issue_date"] for x in tables["RFQ"])
    date_ok=date_ok and all(q["valid_until"]>=q["quote_date"] for q in tables["SupplierQuote"])
    date_ok=date_ok and all(p["po_date"]>=next(r for r in tables["PurchaseRequest"] if r["purchase_request_id"]==p["purchase_request_id"])["request_date"] for p in tables["PurchaseOrder"])
    date_ok=date_ok and all(d["delivery_date"]>=next(p for p in tables["PurchaseOrder"] if p["purchase_order_id"]==d["purchase_order_id"])["po_date"] for d in tables["Delivery"])
    add("date_ordering",date_ok,"Request, RFQ, quote, PO and delivery dates follow lifecycle order")
    delivery_quantity_bounds_placeholder = None
    add("delivery_quantity_bounds",all(0<=int(d["quantity_received"])<=int(d["quantity_ordered"]) for d in tables["Delivery"]),
        "Each delivery receipt is within its per-event ordered quantity")
    add("competitive_quote_count",all(sum(1 for q in tables["SupplierQuote"] if q["rfq_id"]==r["rfq_id"])>=3 for r in tables["RFQ"]),
        "At least three quotes per competitive RFQ")
    add("ground_truth_separation",all("issue_type" not in r for t in tables.values() for r in t),
        "Labels only appear in separate ground_truth files")
    issues,metrics=evaluate(tables,gt)
    add("all_ground_truth_types_detectable",not metrics["missing_ground_truth_issue_types"],
        "Missing: "+", ".join(metrics["missing_ground_truth_issue_types"]))
    return checks,issues,metrics

def run(seed, scale, output):
    tables,gt=make_data(seed,scale)
    out=Path(output)
    if out.exists():
        import shutil; shutil.rmtree(out)
    for t,rows in tables.items():
        folder="master" if t in ("Department","Requester","Budget","Supplier") else (
            "events" if t in ("BudgetTransaction","StatusEvent","AuditLog") else "transactions")
        write_csv(out/"data"/folder/(t.lower()+".csv"),rows)
        write_json(out/"data"/"json"/(t.lower()+".json"),rows)
    write_csv(out/"data"/"ground_truth"/"ground_truth.csv",gt)
    write_json(out/"data"/"ground_truth"/"ground_truth.json",gt)
    ddl=create_sqlite(out/"database"/"procurement.db",tables)
    (out/"database"/"schema.sql").write_text("PRAGMA foreign_keys=ON;\n"+"\n".join(x+";" for x in ddl)+"\n",encoding="utf-8")
    con=sqlite3.connect(out/"database"/"procurement.db")
    with (out/"database"/"seed_data.sql").open("w",encoding="utf-8") as f:
        for line in con.iterdump(): f.write(line+"\n")
    fk=con.execute("PRAGMA foreign_key_check").fetchall(); con.close()
    checks,issues,metrics=validate(tables,gt,scale)
    checks.append({"check":"sqlite_foreign_key_check","status":"PASS" if not fk else "FAIL","detail":f"{len(fk)} violations"})
    write_csv(out/"documentation"/"business_rule_findings.csv",issues)
    write_json(out/"documentation"/"business_rule_findings.json",issues)
    report={"seed":seed,"scale":scale,"checks":checks,"passed":sum(x["status"]=="PASS" for x in checks),
            "failed":sum(x["status"]=="FAIL" for x in checks),"metrics":metrics}
    (out/"documentation"/"validation_summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    md="# Validation Summary\n\n"
    md+=f"- Seed: `{seed}`\n- Scale: `{scale}`\n- Passed: **{report['passed']}**\n- Failed: **{report['failed']}**\n\n"
    md+="| Check | Status | Detail |\n|---|---|---|\n"
    md+="".join(f"| {x['check']} | {x['status']} | {x['detail']} |\n" for x in checks)
    md+="\n## Procurement metrics\n\n"+ "\n".join(f"- {k}: {v}" for k,v in metrics.items())+"\n"
    (out/"documentation"/"VALIDATION_REPORT.md").write_text(md,encoding="utf-8")
    (out/"reproducibility").mkdir(parents=True, exist_ok=True)
    manifest={"project":"Synthetic Procurement Management System","seed":seed,"scale":scale,
        "generated_date":"2026-10-30","provenance":"Fully synthetic; no external data",
        "row_counts":{k:len(v) for k,v in tables.items()},"ground_truth_cases":len(gt)}
    (out/"reproducibility"/"source_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")

    checksums={}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="checksums.json":
            checksums[str(p.relative_to(out))]=hashlib.sha256(p.read_bytes()).hexdigest()
    (out/"reproducibility"/"checksums.json").write_text(json.dumps(checksums,indent=2,sort_keys=True)+"\n")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed",type=int,default=SEED_DEFAULT)
    p.add_argument("--scale",choices=COUNTS,default="full")
    p.add_argument("--output",default="generated")
    a=p.parse_args()
    report=run(a.seed,a.scale,a.output)
    print(json.dumps({"output":a.output,"seed":a.seed,"scale":a.scale,
        "passed":report["passed"],"failed":report["failed"],"metrics":report["metrics"]},indent=2))
    if report["failed"]: raise SystemExit(2)
if __name__=="__main__": main()
