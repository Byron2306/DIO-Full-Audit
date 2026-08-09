#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


INK, BLUE, RED, GREEN, GRID = "#18212B", "#2D719B", "#A64B3C", "#4E8B57", "#C8CED3"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf", size)


def canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1500, 950), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1465, 915), outline=INK, width=4)
    draw.text((70, 55), title, fill=INK, font=font(35, True))
    draw.text((71, 105), subtitle, fill="#596572", font=font(21))
    return image, draw


def geometry_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 1: SIMILAR TRIANGLES", "DE is parallel to BC. The diagram is not drawn to scale.")
    a, b, c = (750, 180), (220, 790), (1280, 790)
    d = (480, 490)
    e = (1020, 490)
    draw.line((a, b, c, a), fill=INK, width=7)
    draw.line((d, e), fill=BLUE, width=8)
    for point, label, offset in [(a, "A", (-15, -55)), (b, "B", (-45, 10)), (c, "C", (18, 10)), (d, "D", (-48, -12)), (e, "E", (18, -12))]:
        draw.ellipse((point[0]-8, point[1]-8, point[0]+8, point[1]+8), fill=RED)
        draw.text((point[0]+offset[0], point[1]+offset[1]), label, fill=INK, font=font(29, True))
    draw.text((495, 340), "AD = 6", fill=INK, font=font(23, True))
    draw.text((315, 645), "DB = 3", fill=INK, font=font(23, True))
    draw.text((875, 340), "AE = 8", fill=INK, font=font(23, True))
    draw.text((1060, 645), "EC = x", fill=INK, font=font(23, True))
    draw.text((580, 510), "DE || BC", fill=BLUE, font=font(26, True))
    draw.text((620, 815), "BC = 12 units", fill=INK, font=font(23, True))
    image.save(path, quality=95)


def statistics_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 2: BIVARIATE DATA", "Study time and test result for six learners")
    left, top, right, bottom = 190, 210, 1400, 770
    draw.line((left, bottom, right, bottom), fill=INK, width=5)
    draw.line((left, top, left, bottom), fill=INK, width=5)
    for yv in range(40, 91, 10):
        y = int(bottom - (yv - 40) / 50 * (bottom - top))
        draw.line((left, y, right, y), fill=GRID, width=2)
        draw.text((130, y - 12), str(yv), fill=INK, font=font(18))
    for xv in range(1, 9):
        x = int(left + (xv - 1) / 7 * (right - left))
        draw.line((x, bottom - 10, x, bottom + 10), fill=INK, width=3)
        draw.text((x - 6, bottom + 20), str(xv), fill=INK, font=font(18))
    xs, ys = [2, 3, 4, 5, 6, 7], [48, 55, 61, 68, 74, 82]
    for xv, yv in zip(xs, ys):
        x = int(left + (xv - 1) / 7 * (right - left))
        y = int(bottom - (yv - 40) / 50 * (bottom - top))
        draw.ellipse((x-11, y-11, x+11, y+11), fill=RED, outline=INK, width=2)
    x1 = int(left + (1 - 1) / 7 * (right - left)); y1 = int(bottom - ((6.66*1+34.7)-40)/50*(bottom-top))
    x2 = int(left + (8 - 1) / 7 * (right - left)); y2 = int(bottom - ((6.66*8+34.7)-40)/50*(bottom-top))
    draw.line((x1, y1, x2, y2), fill=BLUE, width=5)
    draw.text((870, 180), "Least-squares line: y = 6.66x + 34.7", fill=BLUE, font=font(22, True))
    draw.text((560, 840), "STUDY TIME x (hours)", fill=INK, font=font(22, True))
    draw.text((48, 470), "TEST RESULT\ny (%)", fill=INK, font=font(21, True))
    image.save(path, quality=95)


def probability_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 3: QUALITY-CONTROL PROBABILITY TREE", "A component is selected at random from production lines A and B")
    root = (170, 490); a = (600, 280); b = (600, 700)
    ad, an = (1230, 170), (1230, 390)
    bd, bn = (1230, 590), (1230, 810)
    for start, end in [(root,a),(root,b),(a,ad),(a,an),(b,bd),(b,bn)]:
        draw.line((*start,*end), fill=INK, width=6)
    labels = [((330,320),"0.60"),((330,620),"0.40"),((840,190),"0.04"),((840,370),"0.96"),((840,610),"0.07"),((840,790),"0.93")]
    for pos, value in labels: draw.text(pos, value, fill=BLUE, font=font(24, True))
    for pos, value in [(a,"Line A"),(b,"Line B"),(ad,"Defective"),(an,"Not defective"),(bd,"Defective"),(bn,"Not defective")]:
        draw.ellipse((pos[0]-8,pos[1]-8,pos[0]+8,pos[1]+8),fill=RED)
        draw.text((pos[0]+18,pos[1]-18),value,fill=INK,font=font(24,True))
    draw.text((90, 875), "Line selection and defect status form successive events; multiply along a branch and add mutually exclusive branches.", fill="#596572", font=font(20))
    image.save(path, quality=95)


def q(number: str, question: str, marks: int, memo: list[str], source: str = "", lines: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"number": number, "question": question, "marks": marks, "memo": memo}
    if source: item["source_reference"] = source
    if lines: item["answer_lines"] = lines
    return item


def build_pack(out_dir: Path) -> dict[str, Any]:
    asset_dir = out_dir / "source_material"; asset_dir.mkdir(parents=True, exist_ok=True)
    geometry, statistics, probability = asset_dir / "source_1_similar_triangles.png", asset_dir / "source_2_regression.png", asset_dir / "source_3_probability_tree.png"
    geometry_asset(geometry); statistics_asset(statistics); probability_asset(probability)
    return {
        "assessment_title": "Mathematics Grade 12 Term 3 Controlled Test", "subject": "Mathematics", "grade": 12, "phase": "FET",
        "canonical_profile_id": "fet.mathematics", "blueprint": "calculation_proof_data_assessment", "render_shell": "question_paper",
        "language_of_assessment": "English", "duration": "1.5 hours", "total_marks": 50,
        "source_assets": [
            {"title": "Similar triangles", "source_type": "euclidean_geometry_diagram", "png": str(geometry.resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Regression and correlation dataset", "source_type": "scatterplot_and_regression_line", "png": str(statistics.resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Quality-control probability tree", "source_type": "probability_tree", "png": str(probability.resolve()), "asset_status": "constructed_release_candidate"},
        ],
        "source_embedding": {"generated_visual_policy": "suppress_generated_visuals_when_source_assets_present"},
        "visual_blueprint": {"required_visuals": [{"visual_kind": "axis_diagram"}, {"visual_kind": "data_table"}]},
        "sections": [
            {"title": "QUESTION 1: EUCLIDEAN GEOMETRY", "instructions": "Use Source 1. Give reasons for all geometrical statements.", "stimulus": "Refer to SOURCE 1.", "questions": [
                q("1.1", "Prove that triangle ADE is similar to triangle ABC.", 4, ["Angle ADE = angle ABC and angle AED = angle ACB (corresponding angles, DE || BC).", "Angle A is common.", "Therefore triangle ADE is similar to triangle ABC (AAA)."], "SOURCE 1", 4),
                q("1.2", "Hence prove that AD/DB = AE/EC.", 5, ["From similarity, AD/AB = AE/AC.", "AB = AD + DB and AC = AE + EC.", "AD/(AD+DB) = AE/(AE+EC).", "Cross-multiply and cancel AD.AE to obtain AD.EC = AE.DB.", "Therefore AD/DB = AE/EC."], "SOURCE 1", 5),
                q("1.3", "Calculate x, the length of EC.", 3, ["6/3 = 8/x; 6x = 24; x = 4 units."], "SOURCE 1", 3),
                q("1.4", "Calculate the length of DE.", 3, ["DE/BC = AD/AB = 6/9 = 2/3.", "DE = (2/3)(12) = 8 units."], "SOURCE 1", 3),
                q("1.5", "F is the midpoint of AB. A line through F parallel to BC meets AC at G. Prove that G is the midpoint of AC.", 5, ["AF/FB = 1 because F is the midpoint.", "By the proportionality theorem, AF/FB = AG/GC.", "Therefore AG/GC = 1, so AG = GC and G is the midpoint of AC."], "SOURCE 1", 5),
            ]},
            {"title": "QUESTION 2: REGRESSION AND CORRELATION", "instructions": "Use Source 2. Round numerical answers to one decimal place where necessary.", "stimulus": "Refer to SOURCE 2.", "questions": [
                q("2.1", "Identify the dependent variable.", 1, ["Test result y (%)."], "SOURCE 2"),
                q("2.2", "Describe the direction and strength of the correlation.", 2, ["Strong positive correlation."], "SOURCE 2"),
                q("2.3", "Use the regression line to estimate the result for 6.5 hours of study.", 2, ["y = 6.66(6.5) + 34.7 = 78.0%."], "SOURCE 2", 2),
                q("2.4", "Is the estimate in Question 2.3 an interpolation or an extrapolation? Give a reason.", 2, ["Interpolation, because 6.5 lies within the observed range 2 to 7 hours."], "SOURCE 2"),
                q("2.5", "Explain why the strong correlation does not by itself prove that extra study time causes higher marks.", 3, ["Correlation does not prove causation.", "Other variables such as prior knowledge, teaching or sleep may influence both variables.", "A controlled design or further evidence is needed."], "SOURCE 2"),
            ]},
            {"title": "QUESTION 3: COUNTING AND PROBABILITY", "instructions": "Use Source 3 where indicated. Show all probability calculations.", "stimulus": "Refer to SOURCE 3 for Questions 3.1 to 3.4.", "questions": [
                q("3.1", "Verify that the probabilities on each pair of branches sum to 1.", 2, ["0.60 + 0.40 = 1 and 0.04 + 0.96 = 1; 0.07 + 0.93 = 1."], "SOURCE 3"),
                q("3.2", "Calculate the probability that a randomly selected component is defective.", 4, ["P(D) = (0.60)(0.04) + (0.40)(0.07) = 0.024 + 0.028 = 0.052."], "SOURCE 3", 3),
                q("3.3", "Given that a component is defective, calculate the probability that it came from Line B.", 4, ["P(B|D) = P(B and D)/P(D) = 0.028/0.052 = 0.5385 (approximately)."], "SOURCE 3", 3),
                q("3.4", "Determine whether the events 'Line B' and 'defective' are independent. Justify your answer.", 3, ["P(D|B) = 0.07 while P(D) = 0.052.", "They are not equal, so the events are not independent."], "SOURCE 3"),
                q("3.5", "A batch code contains two different letters followed by three digits. Repetition of digits is allowed. How many different codes are possible?", 4, ["26 x 25 x 10 x 10 x 10 = 650 000 codes."], lines=3),
                q("3.6", "Three components are selected independently from a process with defect probability 0.052. Calculate the probability that at least one is defective.", 3, ["1 - P(none defective) = 1 - (0.948)^3 = 0.1480 (approximately)."], lines=3),
            ]},
        ],
        "rubric": [
            {"criterion": "Question 1: Euclidean geometry", "marks": 20, "descriptor": "Similarity proof, proportionality and geometric calculation."},
            {"criterion": "Question 2: Statistics", "marks": 10, "descriptor": "Regression, interpolation and interpretation."},
            {"criterion": "Question 3: Probability", "marks": 20, "descriptor": "Tree probability, conditional probability and counting."},
        ],
        "teacher_review_checklist": ["Verify all calculations and accepted equivalent proof sequences.", "Confirm the 20:10:20 Term 3 topic balance.", "Check diagrams and notation for legibility.", "Approve the paper and memorandum before classroom use."],
        "generation_backend": "hymark_mathematics_constructed_problem_first",
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("out", type=Path); args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.out); (args.out / "assessment_pack.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "out": str(args.out), "total_marks": 50}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
