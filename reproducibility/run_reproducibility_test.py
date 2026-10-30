

"""Regenerate the requested scale twice with the same seed and compare every file hash."""
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

def file_hashes(folder):
    out={}
    for p in sorted(Path(folder).rglob("*")):
        if p.is_file() and p.name!="reproducibility_test.json":
            out[str(p.relative_to(folder))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seed",type=int,default=20261022)
    ap.add_argument("--scale",choices=["starter","full"],default="full")
    ap.add_argument("--generator",default=str(Path(__file__).parents[1]/"generator"/"generate_data.py"))
    ap.add_argument("--output",default=str(Path(__file__).parent/"reproducibility_test.json"))
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="procurement_repro_") as tmp:
        one=Path(tmp)/"run_one"; two=Path(tmp)/"run_two"
        for dest in (one,two):
            cmd=[sys.executable,args.generator,"--seed",str(args.seed),"--scale",args.scale,"--output",str(dest)]
            subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
        h1=file_hashes(one); h2=file_hashes(two)
        keys=sorted(set(h1)|set(h2))
        mismatches=[k for k in keys if h1.get(k)!=h2.get(k)]
        result={"seed":args.seed,"scale":args.scale,"run_1_file_count":len(h1),
            "run_2_file_count":len(h2),"files_identical":not mismatches,
            "mismatch_count":len(mismatches),"mismatched_files":mismatches,
            "run_1_manifest_sha256":hashlib.sha256(json.dumps(h1,sort_keys=True).encode()).hexdigest(),
            "run_2_manifest_sha256":hashlib.sha256(json.dumps(h2,sort_keys=True).encode()).hexdigest(),
            "comparison":"SHA-256 for every generated file, including CSV, JSON, SQLite DB, SQL dump and reports"}
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        Path(args.output).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,indent=2))
        if mismatches: raise SystemExit(2)
if __name__=="__main__": main()
