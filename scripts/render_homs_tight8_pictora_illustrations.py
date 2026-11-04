#!/usr/bin/env python3
"""Queue local Pictora educational illustrations for the HOMS Tight 8."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from products.pictora_organ import discover, submit

OUT=ROOT/"deliverables"/"homs_tight8_pictora_visual_source_bank_v1"/"pictora_jobs"
PROMPTS={
"english_language":"Editorial textbook illustration for English language assessment: a welcoming South African school library reading corner, a small diverse group of learners seen from behind choosing books, shelves and reading table, natural daylight, clear focal objects that support inference about audience and purpose, age-appropriate, realistic but gently illustrated, uncluttered, no text, no letters, no logos, no watermark.",
"afrikaans_language":"Editorial textbook illustration for Afrikaans language assessment: a South African community reading garden beside a modest library, a grandmother and child sharing a book under a tree, warm everyday setting, visual clues about intergenerational learning, age-appropriate, realistic illustration, no readable text, no letters, no logos, no watermark.",
"life_orientation":"Age-appropriate South African Life Orientation textbook illustration: a learner choosing between a safe shaded walking route with friends and a risky road crossing, clear non-alarming visual cues, respectful and inclusive, realistic educational illustration, no text, no logos, no watermark.",
"mathematics":"Clean educational still life for a mathematics assessment: colourful wooden blocks, spheres, cylinders and folded paper shapes arranged in a clear repeating pattern on a classroom table, overhead three-quarter view, precise geometry, bright neutral background, no numbers, no text, no logos, no watermark.",
"physical_sciences":"Accurate educational illustration of a simple classroom motion investigation: a small dynamics trolley on an adjustable ramp, measuring tape beside it, stop block and safe lab bench, clear components and believable physical arrangement, textbook editorial style, no labels, no text, no logos, no watermark.",
"life_sciences":"Detailed South African life sciences textbook illustration of a savanna ecosystem: acacia tree, grasses, insects, small birds and antelope with anatomically plausible forms, natural relationships visible, clear light background, no labels, no text, no logos, no watermark.",
"geography":"South African geography textbook landscape illustration from elevated viewpoint: settlement, river bend, cultivated land, road, hill and wetland in one coherent landscape, visible spatial relationships, neutral daylight, educational atlas illustration not a map, no labels, no text, no logos, no watermark.",
"history":"Carefully neutral history source-analysis still life: a museum table with an old handwritten letter with illegible marks, a dated-looking but blank calendar page, a worn metal tool and a family photograph turned away, no specific real historical figure, balanced light, archival educational illustration, no readable words, no logos, no watermark.",
}

def main():
    snap=discover()
    if snap.get("state")!="AVAILABLE": raise RuntimeError("Local Pictora unavailable")
    ckpt="v1-5-pruned-emaonly.safetensors"
    choices=snap.get("model_choices",{})
    if choices.get("checkpoints") and ckpt not in choices["checkpoints"]: ckpt=choices["checkpoints"][0]
    OUT.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for index,(subject,prompt) in enumerate(PROMPTS.items(),start=1):
        out=OUT/subject; out.mkdir(parents=True,exist_ok=True)
        graph={
          "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":ckpt}},
          "2":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["1",1]}},
          "3":{"class_type":"CLIPTextEncode","inputs":{"text":"text, letters, numbers, logo, watermark, distorted anatomy, extra limbs, unsafe, frightening, illegible labels, collage, low resolution, blurry","clip":["1",1]}},
          "4":{"class_type":"EmptyLatentImage","inputs":{"width":640,"height":640,"batch_size":1}},
          "5":{"class_type":"KSampler","inputs":{"model":["1",0],"seed":2026102800+index,"steps":23,"cfg":7.0,"sampler_name":"dpmpp_2m","scheduler":"karras","positive":["2",0],"negative":["3",0],"latent_image":["4",0],"denoise":1.0}},
          "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
          "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":f"HOMS_TIGHT8_{subject}"}},
        }
        receipt=submit(graph,output_dir=out,owner_authorized=True,source_receipts=[{"purpose":"original educational illustration for HOMS visual source bank","subject_id":subject,"prompt":prompt,"checkpoint":ckpt,"seed":2026102800+index,"curriculum_source":"DIO-authored visual brief; no third-party image input","execution_location":"local_comfyui","remote_processing":False}])
        jobs.append({"subject_id":subject,"job_id":receipt["job_id"],"output_dir":str(out.relative_to(ROOT))})
        print(json.dumps(jobs[-1]),flush=True)
    (OUT/"BATCH.json").write_text(json.dumps({"schema":"dio.pictora.homs_tight8_batch.v1","checkpoint":ckpt,"jobs":jobs,"human_review_required":True,"commercial_validation":"UNPROVED"},indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
