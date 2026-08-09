#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_DIR = ROOT / "campaigns" / "phase3" / "homs" / "human_dummy_batch"
MIRROR_ROOT = Path("/home/byron/KnowEdge_Microsoft_Mirror/HOMS/incoming")
JOB_NAME = "HOMS-HUMAN-DUMMY-001_EDU221-short-essay"


RUBRIC = {
    "name": "EDU221 Short Essay Pilot Rubric",
    "total_marks": 30,
    "criteria": [
        {
            "name": "Argument and focus",
            "weight": 10,
            "description": "Clear answer to the prompt, relevant focus, and a coherent line of argument.",
        },
        {
            "name": "Evidence and source use",
            "weight": 10,
            "description": "Uses concrete examples, source details, class concepts, or data to support claims.",
        },
        {
            "name": "Structure and academic communication",
            "weight": 10,
            "description": "Logical organization, readable academic style, and a conclusion that follows from the argument.",
        },
    ],
}


SUBMISSIONS = {
    "S001_maseko_lerato.txt": """Student: S001 Maseko, Lerato

Community gardens can strengthen school food security when they are planned as an educational and social support project. They provide vegetables, but they also create evidence of participation, learning, and household benefit. A useful programme would track learner attendance, crop yield, water use, and feedback from families.

The best argument for gardens is that they connect practical action with learning. Learners can study soil, nutrition, and local inequality while also helping the feeding scheme. The limitation is sustainability. If nobody records roles, costs, and seasonal plans, the garden may become symbolic rather than useful.

Therefore, community gardens are not a complete answer to poverty, but they can be valuable when linked to school records, curriculum activities, and a reliable support structure.""",
    "S002_van-wyk_pieter.txt": """Student: S002 Van Wyk, Pieter

Community gardens are good because food is important. Schools should plant vegetables because learners need food. A garden can teach them responsibility and also make the school look better. Many communities like gardens and they are positive.

I think all schools should do this. It will help everyone because people can eat the food. In conclusion, gardens are good and schools should support them.""",
    "S003_ndlovu_ayanda.txt": """Student: S003 Ndlovu, Ayanda

A school garden may improve food security, but only if the project is measured and managed properly. The strongest design would compare harvest records, learner participation, feeding-scheme demand, and household reports before and after the garden is introduced. Without this evidence, it is difficult to know whether the garden creates real benefit or only a hopeful story.

The educational value is also important. Learners can connect natural science, economics, and citizenship by recording plant growth and discussing why some households experience food insecurity. This turns the garden into a learning site, not only a food source.

However, gardens need water, tools, time, and accountability. A sustainable programme should assign roles, monitor costs, and report results each term. For that reason, a garden is useful as part of a broader support plan, not as a single solution.""",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_batch(job_dir: Path) -> None:
    uploads = job_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (job_dir / "rubric.json").write_text(json.dumps(RUBRIC, indent=2), encoding="utf-8")
    (job_dir / "memo.md").write_text(
        "\n".join(
            [
                "# EDU221 Short Essay Memo",
                "",
                "Prompt: Evaluate whether school community gardens can support food security and learning.",
                "",
                "Expected elements:",
                "- Takes a clear position rather than only praising gardens.",
                "- Discusses evidence such as attendance, yield, costs, household feedback, or term records.",
                "- Recognises limits: water, coordination, sustainability, and accountability.",
                "- Connects the project to learning or curriculum where relevant.",
                "",
                "Boundary: this is a fake, non-sensitive HOMS pilot batch. Educator review remains final.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (job_dir / "intake.json").write_text(
        json.dumps(
            {
                "schema": "knowedge.homs_batch_intake.v1",
                "created_at": utc_now(),
                "marker": "HOMS-HUMAN-DUMMY-001",
                "institution": "Controlled dummy institution",
                "module": "EDU221",
                "assessment": "Short essay pilot",
                "requested_outputs": ["draft feedback", "marks csv", "lecturer review summary", "return zip"],
                "boundary": "Fake/non-sensitive submissions only. Educator approves final marks and feedback.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with (job_dir / "gradebook.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "student_name", "grade", "requires_review"])
        writer.writeheader()
        writer.writerow({"student_id": "S001", "student_name": "Maseko, Lerato", "grade": "", "requires_review": "yes"})
        writer.writerow({"student_id": "S002", "student_name": "Van Wyk, Pieter", "grade": "", "requires_review": "yes"})
        writer.writerow({"student_id": "S003", "student_name": "Ndlovu, Ayanda", "grade": "", "requires_review": "yes"})
    for name, text in SUBMISSIONS.items():
        (uploads / name).write_text(text.strip() + "\n", encoding="utf-8")


def main() -> int:
    source_dir = CAMPAIGN_DIR / JOB_NAME
    mirror_dir = MIRROR_ROOT / JOB_NAME
    for path in (source_dir, mirror_dir):
        if path.exists():
            shutil.rmtree(path)
        write_batch(path)

    receipt = {
        "schema": "knowedge.homs_fake_batch_receipt.v1",
        "created_at": utc_now(),
        "marker": "HOMS-HUMAN-DUMMY-001",
        "source_dir": str(source_dir),
        "mirror_incoming_dir": str(mirror_dir),
        "submissions": len(SUBMISSIONS),
        "rubric_total_marks": RUBRIC["total_marks"],
        "ready_for_runner": True,
    }
    receipt_path = CAMPAIGN_DIR / "HOMS_FAKE_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
