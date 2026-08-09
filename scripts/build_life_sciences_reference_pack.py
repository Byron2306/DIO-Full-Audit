#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


INK = "#18212B"
BLUE = "#2D719B"
GREEN = "#4E8B57"
GOLD = "#D4A23A"
RED = "#A64B3C"
GRID = "#C8CED3"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def title(draw: ImageDraw.ImageDraw, heading: str, subtitle: str) -> None:
    draw.text((75, 58), heading, fill=INK, font=font(38, True))
    draw.text((76, 112), subtitle, fill="#596572", font=font(22))


def frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1565, 965), outline=INK, width=4)
    return image, draw


def finch_asset(path: Path) -> None:
    image, draw = frame()
    title(draw, "SOURCE 1: FINCH BEAK DEPTH AND DROUGHT SELECTION", "Constructed dataset modelled on a natural-selection field investigation")
    headers = ["Group / condition", "Sample size", "Mean beak depth", "Mean hard-seed index"]
    rows = [
        ["Population before drought", "120", "9.4 mm", "3.2"],
        ["Survivors after drought", "44", "10.1 mm", "7.8"],
        ["Offspring next season", "86", "9.9 mm", "5.4"],
    ]
    x0, y0, row_h = 90, 200, 88
    widths = [500, 270, 330, 390]
    x = x0
    for index, item in enumerate(headers):
        draw.rectangle((x, y0, x + widths[index], y0 + row_h), fill="#DDE4EA", outline=INK, width=3)
        draw.text((x + 14, y0 + 28), item, fill=INK, font=font(20, True))
        x += widths[index]
    for row_index, row in enumerate(rows):
        y = y0 + (row_index + 1) * row_h
        x = x0
        for col_index, item in enumerate(row):
            draw.rectangle((x, y, x + widths[col_index], y + row_h), fill="#F7F8F8" if row_index % 2 == 0 else "white", outline=INK, width=2)
            draw.text((x + 14, y + 29), item, fill=INK, font=font(21, col_index == 0))
            x += widths[col_index]

    chart_left, chart_top, chart_right, chart_bottom = 190, 620, 1420, 880
    draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=INK, width=4)
    draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=INK, width=4)
    values = [("Before drought", 9.4, BLUE), ("Survivors", 10.1, RED), ("Offspring", 9.9, GREEN)]
    for tick in range(8, 11):
        y = int(chart_bottom - ((tick - 8) / 3) * (chart_bottom - chart_top))
        draw.line((chart_left, y, chart_right, y), fill=GRID, width=2)
        draw.text((135, y - 13), str(tick), fill=INK, font=font(18))
    for index, (name, value, colour) in enumerate(values):
        x = 330 + index * 360
        height = int(((value - 8) / 3) * (chart_bottom - chart_top))
        draw.rectangle((x, chart_bottom - height, x + 190, chart_bottom), fill=colour, outline=INK, width=3)
        draw.text((x + 66, chart_bottom - height - 35), f"{value:.1f}", fill=INK, font=font(22, True))
        draw.text((x + 15, chart_bottom + 16), name, fill=INK, font=font(20, True))
    draw.text((70, 670), "Mean beak\ndepth (mm)", fill=INK, font=font(20, True))
    image.save(path, quality=95)


def hominin_asset(path: Path) -> None:
    image, draw = frame()
    title(draw, "SOURCE 2: HOMININ EVIDENCE TABLE AND TIMELINE", "Constructed scientific summary; dates and capacities are approximate ranges")
    headers = ["Hominin", "Approximate range", "Cranial capacity", "Selected evidence"]
    rows = [
        ["Australopithecus afarensis", "3.9-2.9 mya", "about 430 cm3", "habitual bipedalism; projecting face"],
        ["Homo habilis", "2.4-1.4 mya", "about 610 cm3", "stone tools; reduced teeth"],
        ["Homo erectus", "1.9-0.11 mya", "about 900 cm3", "long-distance walking; controlled fire"],
        ["Homo sapiens", "0.30 mya-present", "about 1 350 cm3", "chin; complex symbolic culture"],
    ]
    x0, y0, row_h = 75, 195, 92
    widths = [410, 275, 290, 510]
    x = x0
    for index, item in enumerate(headers):
        draw.rectangle((x, y0, x + widths[index], y0 + row_h), fill="#DDE4EA", outline=INK, width=3)
        draw.text((x + 13, y0 + 30), item, fill=INK, font=font(20, True))
        x += widths[index]
    for row_index, row in enumerate(rows):
        y = y0 + (row_index + 1) * row_h
        x = x0
        for col_index, item in enumerate(row):
            draw.rectangle((x, y, x + widths[col_index], y + row_h), fill="#F7F8F8" if row_index % 2 == 0 else "white", outline=INK, width=2)
            draw.text((x + 13, y + 31), item, fill=INK, font=font(19, col_index == 0))
            x += widths[col_index]

    line_y = 790
    x_start, x_end = 170, 1450
    draw.line((x_start, line_y, x_end, line_y), fill=INK, width=6)
    labels = [(4.0, "A. afarensis", GOLD), (2.4, "H. habilis", BLUE), (1.9, "H. erectus", RED), (0.3, "H. sapiens", GREEN)]
    for mya, name, colour in labels:
        x = int(x_end - (mya / 4.0) * (x_end - x_start))
        draw.ellipse((x - 13, line_y - 13, x + 13, line_y + 13), fill=colour, outline=INK, width=2)
        draw.text((x - 60, line_y - 65), name, fill=INK, font=font(18, True))
    for value in range(5):
        x = int(x_end - (value / 4.0) * (x_end - x_start))
        draw.line((x, line_y - 15, x, line_y + 15), fill=INK, width=3)
        draw.text((x - 16, line_y + 28), f"{value}", fill=INK, font=font(18))
    draw.text((620, 870), "MILLIONS OF YEARS AGO", fill=INK, font=font(21, True))
    draw.text((80, 920), "The table does not imply a single straight ladder of progress; hominin lineages overlapped and branched.", fill="#596572", font=font(21))
    image.save(path, quality=95)


def resistance_asset(path: Path) -> None:
    image, draw = frame()
    title(draw, "SOURCE 3: INSECTICIDE-RESISTANCE INVESTIGATION", "Allele R frequency measured across seven generations in equal-sized insect populations")
    left, top, right, bottom = 200, 230, 1450, 825
    draw.line((left, bottom, right, bottom), fill=INK, width=5)
    draw.line((left, top, left, bottom), fill=INK, width=5)
    treated = [0.08, 0.12, 0.20, 0.33, 0.51, 0.68, 0.79]
    control = [0.08, 0.08, 0.09, 0.08, 0.10, 0.09, 0.10]
    for tick in range(0, 11, 2):
        value = tick / 10
        y = int(bottom - value * (bottom - top))
        draw.line((left, y, right, y), fill=GRID, width=2)
        draw.text((135, y - 13), f"{value:.1f}", fill=INK, font=font(18))
    x_step = (right - left) / 6
    for generation in range(7):
        x = int(left + generation * x_step)
        draw.line((x, bottom - 10, x, bottom + 10), fill=INK, width=3)
        draw.text((x - 7, bottom + 20), str(generation), fill=INK, font=font(19))
    for values, colour in [(treated, RED), (control, BLUE)]:
        points = []
        for generation, value in enumerate(values):
            x = int(left + generation * x_step)
            y = int(bottom - value * (bottom - top))
            points.append((x, y))
        draw.line(points, fill=colour, width=7)
        for x, y in points:
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=colour, outline=INK, width=2)
    draw.text((570, 880), "GENERATION", fill=INK, font=font(22, True))
    draw.text((45, 470), "Frequency of\nR allele", fill=INK, font=font(22, True))
    draw.line((1080, 170, 1150, 170), fill=RED, width=7)
    draw.text((1170, 154), "Insecticide-treated", fill=INK, font=font(20))
    draw.line((1080, 205, 1150, 205), fill=BLUE, width=7)
    draw.text((1170, 189), "Untreated control", fill=INK, font=font(20))
    draw.text((80, 930), "Conditions held constant: starting population size, food supply, temperature and breeding time.", fill="#596572", font=font(20))
    image.save(path, quality=95)


def q(number: str, text: str, marks: int, memo: list[str], source: str = "", answer_lines: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"number": number, "question": text, "marks": marks, "memo": memo}
    if source:
        item["source_reference"] = source
    if answer_lines:
        item["answer_lines"] = answer_lines
    return item


def build_pack(out_dir: Path) -> dict[str, Any]:
    assets_dir = out_dir / "source_material"
    assets_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        assets_dir / "source_1_finch_selection_data.png",
        assets_dir / "source_2_hominin_evidence_timeline.png",
        assets_dir / "source_3_resistance_investigation.png",
    ]
    finch_asset(paths[0])
    hominin_asset(paths[1])
    resistance_asset(paths[2])
    return {
        "assessment_title": "Life Sciences Grade 12 Term 3 Evolution Controlled Test",
        "subject": "Life Sciences",
        "grade": 12,
        "phase": "FET",
        "canonical_profile_id": "fet.life_sciences",
        "blueprint": "data_diagram_investigation_assessment",
        "render_shell": "question_paper",
        "language_of_assessment": "English",
        "duration": "1.5 hours",
        "total_marks": 50,
        "source_assets": [
            {"title": "Finch beak depth and drought selection", "source_type": "data_table_and_graph", "png": str(paths[0].resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Hominin evidence table and timeline", "source_type": "scientific_evidence_table", "png": str(paths[1].resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Insecticide-resistance investigation", "source_type": "investigation_graph", "png": str(paths[2].resolve()), "asset_status": "constructed_release_candidate"},
        ],
        "source_embedding": {"generated_visual_policy": "suppress_generated_visuals_when_source_assets_present"},
        "visual_blueprint": {"required_visuals": [{"visual_kind": "data_table"}, {"visual_kind": "axis_diagram"}, {"visual_kind": "investigation_sheet"}]},
        "sections": [
            {
                "title": "QUESTION 1: EVOLUTION CORE CONCEPTS",
                "instructions": "Answer the questions using correct biological terminology.",
                "questions": [
                    q("1.1", "Define biological evolution.", 2, ["A change in the inherited characteristics/allele frequencies of a population over successive generations."]),
                    q("1.2", "Distinguish between a scientific hypothesis and a scientific theory.", 2, ["A hypothesis is a testable proposed explanation.", "A theory is a broad explanation supported by extensive evidence and repeated testing."]),
                    q("1.3", "Explain why genetic variation is necessary for natural selection to occur.", 3, ["Individuals must differ in inherited traits.", "Some variants improve survival/reproduction in a given environment.", "Those alleles are passed on more frequently."]),
                    q("1.4", "State TWO sources of genetic variation in a sexually reproducing population.", 2, ["Any two: mutation; crossing over; independent assortment; random fertilisation."]),
                    q("1.5", "State the role of reproductive isolation in speciation.", 1, ["It prevents gene flow, allowing populations to diverge into separate species."]),
                ],
            },
            {
                "title": "QUESTION 2: NATURAL SELECTION IN FINCHES",
                "instructions": "Use Source 1. Show calculations where required.",
                "stimulus": "Refer to SOURCE 1.",
                "questions": [
                    q("2.1", "Calculate the increase in mean beak depth from the pre-drought population to the survivors.", 2, ["10.1 - 9.4 = 0.7 mm."], "SOURCE 1"),
                    q("2.2", "Describe TWO patterns shown by the table and graph.", 3, ["Survivors had the greatest mean beak depth.", "Offspring retained a greater mean than the pre-drought population.", "Hard-seed availability increased during the drought and then declined."], "SOURCE 1"),
                    q("2.3", "Explain why birds with deeper beaks were more likely to survive the drought.", 3, ["Drought reduced softer seeds and increased the proportion of hard seeds.", "Deeper/stronger beaks could crack hard seeds more effectively.", "Those birds obtained more food and survived/reproduced."], "SOURCE 1"),
                    q("2.4", "Use Source 1 to explain natural selection across the three groups.", 4, ["Variation in beak depth existed before the drought.", "The changed food environment created selection pressure.", "Deeper-beaked birds survived disproportionately.", "Their offspring inherited alleles associated with greater beak depth, shifting the population mean."], "SOURCE 1"),
                    q("2.5", "Suggest ONE additional measurement that would strengthen the investigation and explain why.", 3, ["Examples: individual survival/reproductive success, seed-size distribution, parent-offspring beak measurements, repeated seasons.", "The explanation must show how the measurement tests inheritance, selection pressure or repeatability."], "SOURCE 1"),
                ],
            },
            {
                "title": "QUESTION 3: EVIDENCE FOR HUMAN EVOLUTION",
                "instructions": "Use Source 2. Treat the table as a summary of approximate scientific evidence.",
                "stimulus": "Refer to SOURCE 2.",
                "questions": [
                    q("3.1", "Compare Australopithecus afarensis and Homo erectus using THREE features from Source 2.", 3, ["H. erectus is more recent; has a larger cranial capacity; and shows evidence of long-distance walking/fire, while A. afarensis shows earlier bipedalism and a projecting face."], "SOURCE 2"),
                    q("3.2", "Describe the general trend in cranial capacity shown in Source 2 and state ONE limitation of using cranial capacity alone to judge evolutionary relationships.", 3, ["General increase from about 430 cm3 to about 1 350 cm3.", "Capacity alone does not establish ancestry/intelligence and must be combined with age, anatomy, DNA and other evidence."], "SOURCE 2"),
                    q("3.3", "Explain why the timeline should not be interpreted as a single straight 'ladder of progress'.", 4, ["Evolution branches rather than moving toward a predetermined goal.", "Different hominin species overlapped in time.", "A later species is not automatically a direct descendant of every earlier species.", "Relationships require multiple lines of evidence."], "SOURCE 2"),
                ],
            },
            {
                "title": "QUESTION 4: INSECTICIDE RESISTANCE INVESTIGATION",
                "instructions": "Use Source 3. Show calculations where required.",
                "stimulus": "Refer to SOURCE 3.",
                "questions": [
                    q("4.1", "Identify the independent variable in the investigation.", 1, ["Exposure to insecticide / treatment condition."], "SOURCE 3"),
                    q("4.2", "Describe the trend in frequency of the R allele in the treated population.", 2, ["It increased each generation, from 0.08 to 0.79, with faster increase after generation 2."], "SOURCE 3"),
                    q("4.3", "Calculate the change in R-allele frequency in the treated population from generation 0 to generation 6.", 3, ["0.79 - 0.08 = 0.71, or 71 percentage points."], "SOURCE 3"),
                    q("4.4", "Explain the change in R-allele frequency in terms of natural selection. Do not state that individual insects changed because they needed to.", 5, ["Resistance variation already existed in the starting population.", "Insecticide acted as a selection pressure.", "Susceptible insects died more frequently.", "Resistant insects survived and reproduced.", "The R allele was inherited more often, increasing its frequency over generations."], "SOURCE 3"),
                    q("4.5", "Evaluate the reliability of the investigation and recommend ONE improvement.", 4, ["A control and constant conditions improve reliability.", "One population/run may not represent natural populations.", "Improve by repeating with multiple populations/larger samples and reporting variation/error bars."], "SOURCE 3"),
                ],
            },
        ],
        "rubric": [
            {"criterion": "Question 1: Core concepts", "marks": 10, "descriptor": "Credit accurate biological definitions and causal explanation."},
            {"criterion": "Question 2: Finch selection", "marks": 15, "descriptor": "Credit calculation, data interpretation and natural-selection reasoning."},
            {"criterion": "Question 3: Human-evolution evidence", "marks": 10, "descriptor": "Credit comparison, trend interpretation and evidence-aware reasoning."},
            {"criterion": "Question 4: Resistance investigation", "marks": 15, "descriptor": "Credit variable identification, calculation, selection mechanism and reliability evaluation."},
        ],
        "teacher_review_checklist": [
            "Confirm Grade 12 Term 3 evolution scope and terminology.",
            "Verify all calculations and acceptable biological alternatives.",
            "Confirm that no diagram implies a linear ladder of human evolution.",
            "Approve the paper and memorandum before classroom use.",
        ],
        "generation_backend": "hymark_life_sciences_constructed_data_first",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Grade 12 Term 3 Life Sciences reference pack.")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.out)
    (args.out / "assessment_pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "out": str(args.out), "total_marks": 50}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
