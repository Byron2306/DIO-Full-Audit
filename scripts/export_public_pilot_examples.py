#!/usr/bin/env python3
"""Export twelve explicitly fictional public examples, with canonical DIO covers."""
from __future__ import annotations
import argparse,hashlib,io,json,shutil,sys
from pathlib import Path
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from pypdf import PdfReader,PdfWriter

EVIDENCE=ROOT/'acceptance_runs/68-product-sellability-20261027'
GOLDEN=ROOT/'media/product_asset_packs/homs_corpo_cult_v1/sigils/DIO_EYE_PREMIUM.png'
GOLDEN_SHA='16ab22deea0c4612db21ec9c1387e3ebaac4915af895814562231810d7f8ca96'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def first(folder):return next(folder.glob('*.pdf'))
def paragraph(c,text,x,y,width,size=12,color='#e9e4d8'):
    obj=Paragraph(escape(text),ParagraphStyle('body',fontName='Helvetica',fontSize=size,leading=size*1.55,textColor=HexColor(color)))
    _,height=obj.wrap(width,900);obj.drawOn(c,x,y-height);return y-height-18


def cover(name,scope,boundary):
    data=io.BytesIO();c=canvas.Canvas(data,pagesize=A4);w,h=A4
    c.setFillColor(HexColor('#090b0e'));c.rect(0,0,w,h,fill=1,stroke=0)
    c.drawImage(ImageReader(str(GOLDEN)),w-192,h-180,width=135,height=135,mask='auto',preserveAspectRatio=True,anchor='c')
    c.setFillColor(HexColor('#d6b777'));c.setFont('Helvetica-Bold',12);c.drawString(48,h-65,'DIO WORKFLOWS')
    c.setFillColor(HexColor('#b8ad99'));c.setFont('Helvetica',10);c.drawString(48,h-86,'EXAMPLE OUTPUT  /  REVIEW-LED PROFESSIONAL PILOT')
    y=paragraph(c,name,48,h-215,w-96,29,'#e2c78d')
    y=paragraph(c,scope,48,y-12,w-96,14)
    c.setStrokeColor(HexColor('#765f35'));c.line(48,y-12,w-48,y-12)
    y=paragraph(c,'Illustrative demonstration',48,y-48,w-96,17,'#e2c78d')
    y=paragraph(c,'The following pages use fictional source records prepared for controlled testing. They are examples of the service output, not actual customer results or an independent professional endorsement.',48,y,w-96,12)
    y=paragraph(c,boundary,48,y-5,w-96,12)
    paragraph(c,'A customer engagement starts with your actual source material, an agreed scope, and an identified reviewer. Final interpretation and release remain with the accountable person.',48,y-5,w-96,12)
    c.setFillColor(HexColor('#d6b777'));c.setFont('Helvetica-Bold',11);c.drawString(48,63,'dioworkflows.co.za')
    c.setFillColor(HexColor('#a59e90'));c.setFont('Helvetica',9);c.drawRightString(w-48,63,'Public sample | 27 October 2026')
    c.showPage();c.save();return data.getvalue()


def launch_pdf(path):
    model=json.loads((EVIDENCE/'launch-reviewed/baseline/package_manifest.json').read_text())
    c=canvas.Canvas(str(path),pagesize=A4);w,h=A4
    for asset,copy in zip(model['creative_assets'],model['channel_copy']):
        c.setFillColor(HexColor('#14181e'));c.setFont('Helvetica-Bold',20);c.drawString(44,h-62,copy['channel'].replace('_',' ').title())
        image=EVIDENCE/'launch-reviewed/baseline'/asset['path']
        c.drawImage(ImageReader(str(image)),44,h-405,width=w-88,height=300,preserveAspectRatio=True,anchor='c',mask='auto')
        y=h-440
        for key,value in copy['copy'].items():y=paragraph(c,key.title()+': '+value,44,y,w-88,11,'#20262b')
        paragraph(c,'Fictional workshop example. Draft channel assets; publication, scheduling and spend require the owner.',44,min(y,180),w-88,10,'#586069')
        c.showPage()
    c.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--site-root',type=Path,required=True);args=parser.parse_args()
    site=args.site_root.resolve()
    if sha(GOLDEN)!=GOLDEN_SHA:raise ValueError('canonical golden asset changed')
    root=site/'products/examples';root.mkdir(parents=True,exist_ok=True)
    brand=site/'assets/qualified-pilots';brand.mkdir(parents=True,exist_ok=True);shutil.copyfile(GOLDEN,brand/'dio-golden-eye.png')
    customer=EVIDENCE/'customer-pathways-delivery'
    report=EVIDENCE/'report-pitch/reviewed-final/baseline'
    launch_source=EVIDENCE/'launch-reviewed/LAUNCH_PUBLIC_SOURCE.pdf';launch_pdf(launch_source)
    rows=[
      ('report-pitch-studio','Report & Pitch Studio','report_pitch',first(report/'report'),'A source-linked decision brief, transparent calculations and an editable presentation.','Editorial interpretation, recommendations and publication require review.'),
      ('article-publication','Article Publication','article',first(report/'article'),'An attributed article draft retaining the qualifications in supplied source records.','Editorial review, rights and reference authenticity remain to be confirmed.'),
      ('article-publication-studio','Article Publication Studio','article',first(report/'article'),'A publication-preparation example from the shared article production pathway.','This shares its article capability with Article Publication; it is not a separate expert endorsement.'),
      ('professional-correspondence','Professional Correspondence','correspondence',first(customer/'correspondence/baseline/customer_delivery'),'A specific factual letter requesting the records needed for reconciliation.','The sender approves tone, position and commitments before sending.'),
      ('professional-correspondence-studio','Professional Correspondence Studio','correspondence',first(customer/'correspondence/baseline/customer_delivery'),'An editable correspondence preparation service with source-linked facts.','This Studio uses the shared correspondence capability. Sending remains a separate decision.'),
      ('contract-desk','Contract Desk','contract',first(EVIDENCE/'public-source-contract/customer_delivery'),'A clause register, obligation candidates, dated review calendar and questions for the contract owner. This fictional scenario is reviewed as of 4 December 2026.','This is contract administration preparation. Legal meaning, dates and enforceability require qualified review.'),
      ('finance-readiness','Finance Readiness','finance',first(customer/'readiness/baseline/customer_delivery'),'A requirement-to-evidence review, missing-document requests and transparent financial calculations.','An accountant, lender or responsible reviewer confirms the records and conclusions. No lending decision is made.'),
      ('finance-readiness-studio','Finance Readiness Studio','finance',first(customer/'readiness/unseen/customer_delivery'),'A finance-readiness example showing how changed source amounts change the calculations.','This Studio shares the finance-readiness capability. No affordability, valuation or lending approval is issued.'),
      ('fundingfinder','FundingFinder','funding',first(EVIDENCE/'funding-finder/reviewed/controlled-baseline/report'),'An applicant-specific shortlist with criterion evidence, timing checks and next-document requests.','This example uses a fictional funding programme. Actual current windows and eligibility must be confirmed with the funder.'),
      ('launch-studio','Launch Studio','launch',launch_source,'A source-bound launch kit with channel-specific creatives, copy, a landing page and an owner schedule.','The customer brand in this example is fictional. Claims, rights, destinations, publication and spend need owner review.'),
      ('evidex-evidenceops','Evidex EvidenceOps','evidex',first(customer/'evidex/baseline/customer_delivery'),'A claim-to-record review highlighting a reported quantity discrepancy and the underlying records still needed.','Capturing a statement does not independently verify it. Records, period and population need reconciliation.'),
      ('vamp-performance','VAMP Performance','vamp',first(EVIDENCE/'vamp-quality/customer-release-candidate/customer_delivery'),'A January-June performance evidence review with real objective mapping, candidates and documentary gaps.','This is evidence preparation for a performance conversation. It creates no employee rating, promotion decision or CPD award.'),
    ]
    manifest={'schema':'dio.public_pilot_examples.v1','as_of':'2026-10-27','offer_count':12,'service_group_count':9,
              'independent_professional_signoff_count':0,'commercial_validation':'UNPROVED','sample_type':'FICTIONAL_CONTROLLED_DEMONSTRATION',
              'golden_asset':{'path':'assets/qualified-pilots/dio-golden-eye.png','sha256':GOLDEN_SHA},'offers':[]}
    for slug,name,group,source,scope,boundary in rows:
        target=root/slug;target.mkdir(exist_ok=True)
        writer=PdfWriter()
        for page in PdfReader(io.BytesIO(cover(name,scope,boundary))).pages:writer.add_page(page)
        for page in PdfReader(source).pages:writer.add_page(page)
        writer.add_metadata({'/Title':name+' - illustrative example','/Author':'DIO Workflows','/Subject':'Fictional controlled demonstration; human review required'})
        pdf=target/'sample.pdf'
        with pdf.open('wb') as handle:writer.write(handle)
        text='\n'.join(page.extract_text() or '' for page in PdfReader(pdf).pages)
        for forbidden in ['/home/byron/','/data/byron/','COVENANT_REVIEW','BEGIN PRIVATE KEY','api_keys.json']:
            if forbidden in text:raise ValueError('private material in public sample: '+slug)
        manifest['offers'].append({'slug':slug,'name':name,'service_group':group,'scope':scope,'review_boundary':boundary,
                                  'pdf_path':str(pdf.relative_to(site)),'pdf_sha256':sha(pdf),'bytes':pdf.stat().st_size,'pages':len(writer.pages),
                                  'source_artifact_sha256':sha(source),'qualification':'PROVISIONAL_REVIEW_LED_PILOT','sample_type':'FICTIONAL_CONTROLLED_DEMONSTRATION'})
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'offers':len(rows),'public_root':str(root),'total_pdf_bytes':sum(row['bytes'] for row in manifest['offers'])},indent=2))


if __name__=='__main__':main()
