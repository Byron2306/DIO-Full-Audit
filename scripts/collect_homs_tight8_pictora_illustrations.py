#!/usr/bin/env python3
"""Collect Pictora illustrations and update HOMS source-bank provenance."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from products.pictora_organ import collect

BASE=ROOT/"deliverables"/"homs_tight8_pictora_visual_source_bank_v1"
batch=json.loads((BASE/"pictora_jobs"/"BATCH.json").read_text(encoding="utf-8"))
records=[]
for job in batch["jobs"]:
    output=ROOT/job["output_dir"]
    rec=collect(job["job_id"],output_dir=output,timeout_seconds=1800,poll_interval=2)
    print(json.dumps({"subject_id":job["subject_id"],"state":rec["state"],"artifact_count":len(rec.get("artifacts",[]))}),flush=True)
    if rec.get("state")=="COMPLETE" and rec.get("artifacts"):
        art=rec["artifacts"][0]; img=output/art["path"]
        relative=str(img.relative_to(ROOT))
        records.append({"asset_id":f"pictora_{job['subject_id']}","subject_id":job["subject_id"],"source_type":"photograph_or_image","grade_neutral":True,"title":f"Pictora educational illustration — {job['subject_id'].replace('_',' ').title()}","snippet":f"Original AI-generated educational illustration for {job['subject_id'].replace('_',' ')} source analysis; illustrative imagery only, with no factual labels or measurements embedded.","bank_png":relative,"preferred_png":relative,"asset_status":"pictora_generated_illustration","source_quality_level":"human_visual_review_required","release_gate":"review_required_educator","quality_flags":[],"provenance":{"creator":"DIO Pictora local ComfyUI","job_id":job["job_id"],"image_sha256":art["sha256"],"execution_location":"local_comfyui","remote_processing":False,"prompt_receipt":str((output/"PICTORA_JOB_RECEIPT.json").relative_to(ROOT)),"generated_image":True,"human_visual_review_required":True},"copyright_status":"Generated locally from DIO-authored prompt; model and checkpoint license review required before commercial release"})
bank_path=BASE/"HOMS_TIGHT8_PICTORA_SOURCE_BANK.json"
bank=json.loads(bank_path.read_text(encoding="utf-8")); bank["assets"].extend(records); bank["pictora_illustration_count"]=len(records); bank["pictora_collection_status"]="complete" if len(records)==8 else "partial"; bank_path.write_text(json.dumps(bank,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
composed_path=BASE/"HOMS_COMPOSED_SOURCE_BANK.json"
composed=json.loads(composed_path.read_text(encoding="utf-8")); composed["assets"].extend(records); composed["pictora_illustration_count"]=len(records); composed["pictora_collection_status"]=bank["pictora_collection_status"]; composed_path.write_text(json.dumps(composed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
report={"schema":"dio.homs.tight8_pictora_collection.v1","collected":len(records),"expected":8,"status":bank["pictora_collection_status"],"jobs":batch["jobs"],"human_review_required":True,"commercial_validation":"UNPROVED"}
(BASE/"PICTORA_COLLECTION_REPORT.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
