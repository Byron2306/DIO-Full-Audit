"""Capture and render the three current Services SETA 2026/27 funding windows."""
from __future__ import annotations
import csv
import hashlib
import html
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
OUT = BASE / "FUNDINGFINDER_SERVICESETA_THREE_WINDOW_REVIEW_20261102_V2"

PAGES = [
    {"id": "DG03", "window": "2026/27-DG-03", "title": "Discretionary Grant Funding Window 2026/27", "url": "https://serviceseta.org.za/discretionary-grant-funding-window-2026-27-now-open/",
     "quotes": ["Reference: 2026/27-DG-03", "Applicants may apply for a maximum of two learning programmes.", "The application link and submission instructions will be published on this page shortly.", "Closing deadline: 6 November 2026"]},
    {"id": "SP04", "window": "SP2026/27-04", "title": "Strategic Projects Funding Window 2026/27", "url": "https://serviceseta.org.za/strategic-projects-funding-window-2026-27-now-open/",
     "quotes": ["Reference: SP2026/27-04", "Applications are open to legally registered South African NGOs, NPOs, NPCs, community-based organisations and community trusts.", "Details of the application platform and submission process will be published on this page shortly.", "Closing date: 6 November 2026."]},
    {"id": "SP01", "window": "SP2026/27-01", "title": "Strategic Partnership Funding Window 2026/27 for Public Entities", "url": "https://serviceseta.org.za/strategic-partnership-funding-window-2026-27-now-open-for-public-entities/",
     "quotes": ["public institutions, including national and provincial government, municipalities, TVET colleges, CET colleges and public entities", "Details of the application platform and submission process will be published on this page shortly.", "Closing date: 6 November 2026."]},
    {"id": "WITHDRAWN", "window": "DG2026/27-02 and SP2026/27-03", "title": "Notice: withdrawal of previous funding windows", "url": "https://serviceseta.org.za/notice-withdrawal-of-funding-windows-2/",
     "quotes": ["Regular Discretionary Grant Funding Window: DG2026/27-02", "Special Projects Funding Window: SP2026/27-03", "Applications will not automatically transfer to any future funding window."]},
]
DOCUMENTS = [
    {"id": "DG03_ADVERT", "window_id": "DG03", "title": "DG-03 advert", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Grant_Advert_2026_27.pdf", "kind": "pdf"},
    {"id": "DG03_ANNEXURE_A", "window_id": "DG03", "title": "DG-03 Annexure A priority list", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/DG_Annexure_A_2026_27.pdf", "kind": "pdf"},
    {"id": "DG03_EVALUATION", "window_id": "DG03", "title": "DG-03 evaluation criteria", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Evaluation-Criteria-DG-3-16-Oct-2026.pdf", "kind": "pdf"},
    {"id": "SP04_ADVERT", "window_id": "SP04", "title": "SP-04 Strategic Projects advert", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/03_Advert_Strategic_Projects_SP2026_27_04-Final_AA-Inputs-23-October.pdf", "kind": "pdf"},
    {"id": "SP04_APPLICATION", "window_id": "SP04", "title": "SP-04 application summary form", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/05_Strategic_Projects_Application_Form_SP2026_27_04.docx", "kind": "docx"},
    {"id": "SP04_PLAN_BUDGET", "window_id": "SP04", "title": "Learning Programme Project Plan and Budget Template", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Generic_Learning-Programme_Project-Plan-and-Budget-Template-_2026.pdf", "kind": "pdf"},
    {"id": "SP04_EVALUATION", "window_id": "SP04", "title": "SP-04 Strategic Projects evaluation criteria", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Strategic-Evaluation-Criteria.pdf", "kind": "pdf"},
    {"id": "SP01_ADVERT", "window_id": "SP01", "title": "SP-01 Public Institutions advert", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Public_Entities_Grant_Advert_SP2026_27_01.pdf", "kind": "pdf"},
    {"id": "SP01_APPLICATION", "window_id": "SP01", "title": "SP-01 Public Institutions application form", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Public_Entities_Application_Form_SP2026_27_01.docx", "kind": "docx"},
    {"id": "SP01_EVALUATION", "window_id": "SP01", "title": "SP-01 Public Institutions evaluation criteria", "url": "https://servicessetawebsite.blob.core.windows.net/wordpresslivesite/2026/10/Public_Entities_Evaluation_Criteria_SP2026_27_01.pdf", "kind": "pdf"},
]

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}: self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def fetch(url: str) -> tuple[bytes, dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "DIO-FundingFinder evidence refresh/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
        return raw, {"http_status": response.status, "final_url": response.url,
                     "content_type": response.headers.get("Content-Type", ""),
                     "last_modified": response.headers.get("Last-Modified"),
                     "etag": response.headers.get("ETag")}

def main() -> None:
    if OUT.exists() and any(OUT.iterdir()): raise FileExistsError(f"Refusing to overwrite captured evidence: {OUT}")
    pages_dir, docs_dir, text_dir = OUT / "pages", OUT / "documents", OUT / "extracted_text"
    for directory in (pages_dir, docs_dir, text_dir): directory.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    page_rows=[]
    for row in PAGES:
        raw, meta = fetch(row["url"])
        path = pages_dir / f"{row['id']}.html"; path.write_bytes(raw)
        parser=Text(); parser.feed(raw.decode("utf-8", errors="replace")); plain=clean(" ".join(parser.parts))
        text_path=text_dir / f"{row['id']}.txt"; text_path.write_text(plain+"\n", encoding="utf-8")
        absent=[quote for quote in row["quotes"] if quote not in plain]
        if absent: raise ValueError(f"Official page quote did not match captured bytes ({row['id']}): {absent}")
        page_rows.append({**row,"captured_path":str(path.relative_to(OUT)),"sha256":sha(raw),"bytes":len(raw),
                          "extracted_text_path":str(text_path.relative_to(OUT)),"extracted_text_sha256":sha(text_path.read_bytes()),
                          "quotes":row["quotes"],"retrieved_at":fetched_at,**meta})
    doc_rows=[]
    for row in DOCUMENTS:
        raw, meta = fetch(row["url"])
        suffix=".pdf" if row["kind"]=="pdf" else ".docx"
        path=docs_dir/f"{row['id']}{suffix}"; path.write_bytes(raw)
        if row["kind"]=="pdf":
            text_path=text_dir/f"{row['id']}.txt"
            subprocess.run(["pdftotext","-layout",str(path),str(text_path)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            extracted=text_path.read_text(encoding="utf-8",errors="replace")
            row_text={"path":str(text_path.relative_to(OUT)),"sha256":sha(text_path.read_bytes()),"has_text":bool(extracted.strip())}
        else: row_text={"path":None,"sha256":None,"has_text":None}
        doc_rows.append({**row,"captured_path":str(path.relative_to(OUT)),"sha256":sha(raw),"bytes":len(raw),
                         "extracted_text":row_text,"retrieved_at":fetched_at,**meta})
    sp04_text=(OUT/next(x["extracted_text"]["path"] for x in doc_rows if x["id"]=="SP04_EVALUATION")).read_text(encoding="utf-8",errors="replace")
    sp01_text=(OUT/next(x["extracted_text"]["path"] for x in doc_rows if x["id"]=="SP01_EVALUATION")).read_text(encoding="utf-8",errors="replace")
    criteria_observations={}
    for key,body,expected_ref in [("SP04",sp04_text,"SP2026/27-04"),("SP01",sp01_text,"SP2026/27-01")]:
        pending=bool(re.search(r"submitted to the Accounting Authority for approval",body,re.I))
        headers=re.findall(r"Evaluation Criteria\s+(SP\d{4}/\d{2}-\d{2})",body,re.I)
        refs=re.findall(r"Reference\s+(SP\d{4}/\d{2}-\d{2})",body,re.I)
        criteria_observations[key]={"expected_window_reference":expected_ref,"approval_pending_language_found":pending,
                                    "running_header_references":sorted(set(headers)),"body_references":sorted(set(refs)),
                                    "reference_mismatch":any(ref!=expected_ref for ref in headers+refs),
                                    "state":"CONFLICT_REQUIRES_FUNDER_CONFIRMATION" if pending or any(ref!=expected_ref for ref in headers+refs) else "REVIEW_REQUIRED"}
    manifest={"schema":"dio.fundingfinder.serviceseta.three_window_review.v1","product":"FundingFinder",
              "retrieved_at_utc":fetched_at,"as_of_date":"2026-11-02","official_page_count":len(page_rows),
              "official_document_count":len(doc_rows),"pages":page_rows,"documents":doc_rows,
              "windows":[
                {"id":"DG03","reference":"2026/27-DG-03","title":"Discretionary Grants","applicant_class":"Eligible employers, sectoral associations, professional bodies, trade unions and federations, and accredited Skills Development Providers within Services SETA scope","programme_types":["learnerships","apprenticeships","Recognition of Prior Learning","Adult Education and Training","skills programmes","candidacy"],"maximum_programmes_per_application":2,"priority_source":"Annexure A","closing_date":"2026-11-06","closing_time":"NOT_STATED_ON_CURRENT_PAGE","submission_instructions":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","application_link":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","match_state":"REQUIRES_APPLICANT_AND_PROGRAMME_EVIDENCE"},
                {"id":"SP04","reference":"SP2026/27-04","title":"Strategic Projects for Non-profit Organisations","applicant_class":"Legally registered South African NGOs, NPOs, NPCs, community-based organisations and community trusts operating on a non-profit basis","focus_areas":["rural and township development and revitalisation","youth and women empowerment","inclusion of persons with disabilities","support to military veterans and their dependants","enterprise development and self-employment","job creation and local economic development"],"proposal_limit":"5 A4 pages","required_documents":["application summary form","project proposal","project implementation template","budget template","proof of legal registration","signed POPI declaration Form 1C","signed Declaration of Interest Form 1A","authorised representatives’ identification certified within three months"],"closing_date":"2026-11-06","closing_time":"NOT_STATED_ON_CURRENT_PAGE","submission_instructions":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","application_link":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","evaluation_criteria_state":criteria_observations["SP04"]["state"],"match_state":"REQUIRES_APPLICANT_AND_PROJECT_EVIDENCE"},
                {"id":"SP01","reference":"SP2026/27-01","title":"Strategic Partnership for Public Institutions","applicant_class":"Public institutions: national and provincial government, municipalities, TVET colleges, CET colleges and public entities across the three spheres of government","focus_areas":["rural and township development and revitalisation","youth and women empowerment","enterprise development and self-employment","job creation and local economic development"],"proposal_limit":"5 A4 pages","required_documents":["Public Institutions Application Summary Form","project implementation template","budget template","project proposal","signed Declaration of Interest","signed Declaration of Authorised Person","signed POPI Declaration","authorised representatives’ identification certified within three months"],"other_funding_disclosure_required":True,"closing_date":"2026-11-06","closing_time":"NOT_STATED_ON_CURRENT_PAGE","submission_instructions":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","application_link":"NOT_YET_PUBLISHED_ON_CURRENT_PAGE","evaluation_criteria_state":criteria_observations["SP01"]["state"],"match_state":"REQUIRES_APPLICANT_AND_PROJECT_EVIDENCE"}],
              "withdrawal_controls":{"withdrawn_references":["DG2026/27-02","SP2026/27-03"],"prior_applications_transfer_automatically":False,"new_application_required":True},
              "evaluation_criteria_observations":criteria_observations,
              "product_boundaries":{"synthetic_applicant_only":True,"eligibility_certified":False,"award_probability_scored":False,"application_submitted":False,"external_release_authorized":False,
                                    "technical_scoring_enabled_for_SP04_or_SP01":False,"reason":"Current official information states submission instructions are pending; linked strategic criteria PDFs include approval-status and reference-label inconsistencies."}}
    (OUT/"THREE_WINDOW_REVIEW.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Blank review register makes the current source and applicant gaps actionable without implying a decision.
    fields=["window_id","review_item","evidence_required","source_page","source_page_sha256","applicant_record","reviewer","decision","rationale","follow_up"]
    with (OUT/"APPLICANT_WINDOW_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        items={"DG03":["legal entity and Services SETA scope","learning programme and provider eligibility","Annexure A priority alignment","complete current advert, policy and unit-cost conditions","portal URL and submission instructions","signed declarations and current supporting records"],
               "SP04":["legal non-profit status","focus-area and need evidence","required application, proposal, plan and budget templates","current approval and reference of evaluation criteria","portal URL and submission instructions","signed declarations, registration and current IDs"],
               "SP01":["public-institution applicant category","focus-area and service-impact evidence","required application, proposal, plan and budget templates","current approval and reference of evaluation criteria","portal URL and submission instructions","other funding and duplication disclosures","signed declarations and current IDs"]}
        for window_id,checks in items.items():
            page=next(x for x in page_rows if x["id"]==window_id)
            for check in checks:
                writer.writerow({"window_id":window_id,"review_item":check,"evidence_required":"Reviewer to obtain/verify against current official source and applicant record","source_page":page["url"],"source_page_sha256":page["sha256"],"applicant_record":"","reviewer":"","decision":"","rationale":"","follow_up":""})
    cards=[]
    for window in manifest["windows"]:
        docs=[d for d in doc_rows if d["window_id"]==window["id"]]
        links="".join(f'<li><a href="{html.escape(d["captured_path"],quote=True)}">{html.escape(d["title"])}</a> · <a href="{html.escape(d["url"],quote=True)}">official URL</a><code>SHA-256 {d["sha256"]}</code></li>' for d in docs)
        requirements="".join(f"<li>{html.escape(x)}</li>" for x in window.get("required_documents",[]))
        criteria=""
        if window["id"] in {"SP04","SP01"}:
            ob=criteria_observations[window["id"]]
            criteria=f'<p class="alert"><strong>Evaluation-criteria document conflict:</strong> the linked PDF has pending-approval language and/or a reference label inconsistent with {html.escape(window["reference"])}. FundingFinder does not score this route. Obtain confirmation of the current approved criteria from Services SETA.</p>'
        cards.append(f'''<article class="window"><p class="eyebrow">{html.escape(window['id'])}</p><h2>{html.escape(window['reference'])} · {html.escape(window['title']) if 'title' in window else ''}</h2><p><strong>Applicant category:</strong> {html.escape(window['applicant_class'])}</p><p><strong>Closing date:</strong> 6 November 2026; closing time is not stated on the current official page.</p><p><strong>Submission route:</strong> {html.escape(window['submission_instructions'])}. The official page says the application link and instructions are forthcoming.</p>{f'<p><strong>Maximum programmes:</strong> {window["maximum_programmes_per_application"]}</p>' if 'maximum_programmes_per_application' in window else ''}{f'<p><strong>Focus areas:</strong> {html.escape("; ".join(window["focus_areas"]))}</p>' if window.get('focus_areas') else ''}{f'<p><strong>Proposal limit:</strong> {html.escape(window["proposal_limit"])}</p>' if window.get('proposal_limit') else ''}{f'<ul>{requirements}</ul>' if requirements else ''}{criteria}<p class="hold"><strong>FundingFinder match state:</strong> {html.escape(window['match_state'].replace('_',' ').lower())}. Applicant and programme records are required before further screening.</p><details><summary>Captured official documents ({len(docs)})</summary><ul>{links}</ul></details></article>''')
    page_html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FundingFinder · Services SETA 2026/27 windows</title><style>
:root{{--ink:#172c2a;--muted:#52635f;--line:#cad4cf;--paper:#f2f4f0;--panel:#fff;--green:#174c45;--gold:#bd8740;--red:#813c2f}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05}}h2{{font-size:1.4rem;line-height:1.25}}a{{color:#075e70;overflow-wrap:anywhere}}a:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-weight:800;color:var(--muted);font-size:.78rem}}.banner{{background:#fff5df;border-left:5px solid var(--gold);padding:1rem 1.2rem;margin:1rem 0}}.alert{{background:#fff0ed;border-left:4px solid var(--red);padding:.8rem 1rem}}.hold{{color:#553d21}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:1rem}}.window{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1.1rem;box-shadow:0 4px 16px #172c2a0a}}.window p{{line-height:1.5}}li{{margin:.35rem 0}}code{{display:block;font-size:.72rem;overflow-wrap:anywhere;color:var(--muted)}}details{{border-top:1px solid var(--line);padding:.6rem 0}}summary{{cursor:pointer;font-weight:750}}footer{{margin:2rem 0;color:var(--muted);font-size:.9rem}}</style></head><body><main><p class="eyebrow">FundingFinder · official-source review</p><h1>Services SETA funding windows · 2026/27</h1><p>Captured {html.escape(fetched_at)}. Three open funding paths are shown separately by applicant category. Deadlines and published instructions come from current official pages and attached documents; the synthetic applicant has not been screened in.</p><div class="banner"><strong>Submission hold:</strong> all three current official pages state 6 November 2026 as the closing date and say application links or platform instructions will be published later. The pages do not state a closing time. Confirm the live channel and current deadline directly with Services SETA before preparing a submission.</div><p><strong>Withdrawal warning:</strong> DG2026/27-02 and SP2026/27-03 were withdrawn. The official withdrawal notice says prior applications do not automatically transfer; interested applicants must submit new applications in a replacement window.</p><div class="grid">{''.join(cards)}</div><h2>Current source register</h2><ul>{''.join(f'<li><a href="{html.escape(p["captured_path"],quote=True)}">{html.escape(p["title"])}</a> · <a href="{html.escape(p["url"],quote=True)}">official page</a><code>SHA-256 {p["sha256"]}</code></li>' for p in page_rows)}</ul><p><a href="APPLICANT_WINDOW_REVIEW.csv">Download the blank applicant-window review worksheet</a> · <a href="THREE_WINDOW_REVIEW.json">Download source-bound window data</a></p><footer>FundingFinder does not certify eligibility, score strategic applications, guarantee funding, or submit applications. Verify applicant evidence, full current rules, approved evaluation criteria and submission instructions with Services SETA.</footer></main></body></html>'''
    (OUT/"FUNDINGFINDER_SERVICESETA_WINDOWS.html").write_text(page_html,encoding="utf-8")
    outputs=[]
    for path in [OUT/"FUNDINGFINDER_SERVICESETA_WINDOWS.html",OUT/"THREE_WINDOW_REVIEW.json",OUT/"APPLICANT_WINDOW_REVIEW.csv"]:
        outputs.append({"path":str(path.relative_to(ROOT)),"sha256":sha(path.read_bytes()),"bytes":path.stat().st_size})
    manifest.update({"customer_review_page":outputs[0],"review_data_path":str((OUT/"THREE_WINDOW_REVIEW.json").relative_to(ROOT)),
                     "blank_applicant_review_worksheet":outputs[2],"generated_at_utc":fetched_at})
    data_path=OUT/"THREE_WINDOW_REVIEW.json"
    data_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    receipt_outputs=[]
    for path in [OUT/"FUNDINGFINDER_SERVICESETA_WINDOWS.html",data_path,OUT/"APPLICANT_WINDOW_REVIEW.csv"]:
        receipt_outputs.append({"path":str(path.relative_to(ROOT)),"sha256":sha(path.read_bytes()),"bytes":path.stat().st_size})
    receipt={"schema":"dio.fundingfinder.serviceseta.three_window_review_receipt.v1","generated_at_utc":fetched_at,
             "source_page_sha256s":{row["id"]:row["sha256"] for row in page_rows},
             "source_document_sha256s":{row["id"]:row["sha256"] for row in doc_rows},"outputs":receipt_outputs,
             "window_count":3,"withdrawal_controls_verified":True,"criteria_status_conflicts":criteria_observations,
             "eligibility_certified":False,"award_probability_scored":False,"application_submitted":False,"external_release_authorized":False}
    (OUT/"THREE_WINDOW_REVIEW_RECEIPT.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"output_dir":str(OUT.relative_to(ROOT)),"windows":len(manifest["windows"]),"official_pages":len(page_rows),"official_documents":len(doc_rows),"criteria_conflicts":criteria_observations,"application_link_published":False,"eligibility_certified":False},indent=2))

if __name__ == "__main__": main()
