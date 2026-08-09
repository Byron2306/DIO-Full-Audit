#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


INK = "#18212B"
BLUE = "#2D719B"
RED = "#A64B3C"
GREEN = "#4E8B57"
GRID = "#C8CED3"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def canvas(heading: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1565, 965), outline=INK, width=4)
    draw.text((75, 55), heading, fill=INK, font=font(36, True))
    draw.text((76, 108), subtitle, fill="#596572", font=font(21))
    return image, draw


def battery_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 1: INTERNAL RESISTANCE INVESTIGATION", "Terminal potential difference measured while current is varied")
    # Scientifically coherent circuit: ammeter and variable resistor in series; voltmeter across battery terminals.
    draw.line((120, 265, 340, 265), fill=INK, width=7)
    draw.line((340, 225, 340, 305), fill=INK, width=5)
    draw.line((370, 240, 370, 290), fill=INK, width=9)
    draw.line((370, 265, 555, 265), fill=INK, width=7)
    draw.ellipse((555, 215, 655, 315), outline=INK, width=6)
    draw.text((584, 239), "A", fill=INK, font=font(32, True))
    draw.line((655, 265, 810, 265), fill=INK, width=7)
    draw.rectangle((810, 230, 1080, 300), outline=INK, width=5)
    draw.line((850, 330, 1040, 200), fill=RED, width=6)
    draw.polygon([(1040, 200), (1011, 211), (1029, 231)], fill=RED)
    draw.text((850, 242), "VARIABLE RESISTOR", fill=INK, font=font(19, True))
    draw.line((1080, 265, 1350, 265, 1350, 430, 120, 430, 120, 265), fill=INK, width=7)
    draw.line((340, 305, 340, 510, 555, 510), fill=BLUE, width=5)
    draw.ellipse((555, 460, 655, 560), outline=BLUE, width=6)
    draw.text((583, 485), "V", fill=BLUE, font=font(32, True))
    draw.line((655, 510, 655, 430), fill=BLUE, width=5)
    draw.text((220, 180), "1.50 V CELL", fill=INK, font=font(22, True))

    headers = ["Current I (A)", "0.20", "0.40", "0.60", "0.80", "1.00"]
    values = ["Terminal voltage V (V)", "1.40", "1.30", "1.20", "1.10", "1.00"]
    x0, y0, h = 105, 655, 90
    widths = [410, 205, 205, 205, 205, 205]
    for row_i, row in enumerate([headers, values]):
        x = x0
        for col_i, value in enumerate(row):
            draw.rectangle((x, y0 + row_i * h, x + widths[col_i], y0 + (row_i + 1) * h), fill="#DDE4EA" if row_i == 0 else "white", outline=INK, width=3)
            draw.text((x + 14, y0 + row_i * h + 31), value, fill=INK, font=font(20, col_i == 0))
            x += widths[col_i]
    draw.text((105, 875), "Relationship: Vterminal = emf - Ir. Read emf from the intercept and internal resistance from the magnitude of the gradient.", fill="#596572", font=font(19))
    image.save(path, quality=95)


def photoelectric_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 2: PHOTOELECTRIC-EFFECT DATA", "Maximum kinetic energy of emitted electrons versus incident-light frequency")
    left, top, right, bottom = 210, 210, 1450, 800
    draw.line((left, bottom, right, bottom), fill=INK, width=5)
    draw.line((left, top, left, bottom), fill=INK, width=5)
    for tick in range(0, 6):
        value = tick * 0.5
        y = int(bottom - value / 2.5 * (bottom - top))
        draw.line((left, y, right, y), fill=GRID, width=2)
        draw.text((125, y - 13), f"{value:.1f}", fill=INK, font=font(18))
    for f in range(5, 10):
        x = int(left + (f - 5) / 4 * (right - left))
        draw.line((x, bottom - 10, x, bottom + 10), fill=INK, width=3)
        draw.text((x - 10, bottom + 22), str(f), fill=INK, font=font(18))
    frequencies = [5.5, 6.0, 7.0, 8.0, 9.0]
    energies = [0.0, 0.331, 0.994, 1.657, 2.320]
    points = []
    for frequency, energy in zip(frequencies, energies):
        x = int(left + (frequency - 5) / 4 * (right - left))
        y = int(bottom - energy / 2.5 * (bottom - top))
        points.append((x, y))
    draw.line(points, fill=RED, width=7)
    for x, y in points:
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=RED, outline=INK, width=2)
    draw.text((550, 880), "FREQUENCY (x 10^14 Hz)", fill=INK, font=font(22, True))
    draw.text((45, 465), "Maximum KE\n(x 10^-19 J)", fill=INK, font=font(21, True))
    draw.text((830, 170), "Cut-off frequency f0 = 5.5 x 10^14 Hz", fill=INK, font=font(21, True))
    draw.text((80, 930), "Use h = 6.63 x 10^-34 J.s and KEmax = hf - W0.", fill="#596572", font=font(21))
    image.save(path, quality=95)


def cell_asset(path: Path) -> None:
    image, draw = canvas("SOURCE 3: STANDARD ZINC-COPPER GALVANIC CELL", "Standard conditions: 25 degrees C; solutions 1 mol.dm^-3")
    draw.rectangle((120, 270, 640, 760), outline=INK, width=5)
    draw.rectangle((960, 270, 1480, 760), outline=INK, width=5)
    draw.rectangle((122, 460, 638, 758), fill="#DCECF2", outline=INK, width=2)
    draw.rectangle((962, 460, 1478, 758), fill="#DDEDDC", outline=INK, width=2)
    draw.rectangle((290, 220, 380, 680), fill="#B8BDC2", outline=INK, width=4)
    draw.rectangle((1210, 220, 1300, 680), fill="#B87333", outline=INK, width=4)
    draw.text((285, 180), "Zn(s)", fill=INK, font=font(25, True))
    draw.text((1205, 180), "Cu(s)", fill=INK, font=font(25, True))
    draw.text((220, 700), "Zn2+(aq)", fill=INK, font=font(24, True))
    draw.text((1110, 700), "Cu2+(aq)", fill=INK, font=font(24, True))
    draw.line((335, 220, 335, 135, 1255, 135, 1255, 220), fill=INK, width=6)
    draw.polygon([(760, 135), (720, 115), (720, 155)], fill=RED)
    draw.text((660, 80), "electron flow", fill=RED, font=font(22, True))
    draw.arc((500, 330, 1100, 620), start=180, end=360, fill=BLUE, width=28)
    draw.text((650, 555), "KNO3 SALT BRIDGE", fill=BLUE, font=font(23, True))
    draw.rectangle((190, 820, 1410, 910), fill="#F2F4F5", outline=INK, width=3)
    draw.text((220, 847), "E degrees (Zn2+/Zn) = -0.76 V     E degrees (Cu2+/Cu) = +0.34 V     E degrees cell = E cathode - E anode", fill=INK, font=font(21, True))
    image.save(path, quality=95)


def q(number: str, text: str, marks: int, memo: list[str], source: str = "", answer_lines: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"number": number, "question": text, "marks": marks, "memo": memo}
    if source:
        item["source_reference"] = source
    if answer_lines:
        item["answer_lines"] = answer_lines
    return item


def build_pack(out_dir: Path) -> dict[str, Any]:
    assets = out_dir / "source_material"
    assets.mkdir(parents=True, exist_ok=True)
    battery = assets / "source_1_internal_resistance.png"
    photoelectric = assets / "source_2_photoelectric_graph.png"
    cell = assets / "source_3_galvanic_cell.png"
    battery_asset(battery)
    photoelectric_asset(photoelectric)
    cell_asset(cell)
    return {
        "assessment_title": "Physical Sciences Grade 12 Term 3 Controlled Test",
        "subject": "Physical Sciences", "grade": 12, "phase": "FET", "canonical_profile_id": "fet.physical_sciences",
        "blueprint": "data_diagram_practical_investigation", "render_shell": "question_paper", "language_of_assessment": "English",
        "duration": "1.5 hours", "total_marks": 50,
        "source_assets": [
            {"title": "Internal resistance investigation", "source_type": "circuit_diagram_and_data_table", "png": str(battery.resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Photoelectric-effect graph", "source_type": "quantitative_graph", "png": str(photoelectric.resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Zinc-copper galvanic cell", "source_type": "labelled_cell_diagram_and_data", "png": str(cell.resolve()), "asset_status": "constructed_release_candidate"},
        ],
        "source_embedding": {"generated_visual_policy": "suppress_generated_visuals_when_source_assets_present"},
        "visual_blueprint": {"required_visuals": [{"visual_kind": "data_table"}, {"visual_kind": "axis_diagram"}, {"visual_kind": "investigation_sheet"}]},
        "sections": [
            {"title": "QUESTION 1: INTERNAL RESISTANCE", "instructions": "Use Source 1. Show formulae, substitutions and units.", "stimulus": "Refer to SOURCE 1.", "questions": [
                q("1.1", "Distinguish between the emf of a cell and its terminal potential difference.", 2, ["Emf is energy supplied per coulomb/open-circuit potential difference.", "Terminal potential difference is energy transferred per coulomb in the external circuit and decreases under load."], "SOURCE 1"),
                q("1.2", "Identify the independent variable, the dependent variable and ONE controlled variable in this investigation.", 3, ["Independent: current, varied with the variable resistor.", "Dependent: terminal voltage.", "Controlled: same cell/temperature/circuit components."], "SOURCE 1"),
                q("1.3", "Describe the relationship between terminal voltage and current shown by the data.", 2, ["Terminal voltage decreases linearly as current increases."], "SOURCE 1"),
                q("1.4", "Use the data and V = emf - Ir to determine the emf and internal resistance of the cell.", 5, ["Gradient = (1.00 - 1.40)/(1.00 - 0.20) = -0.50 V.A^-1.", "r = 0.50 ohm.", "Using any point, emf = V + Ir = 1.50 V."], "SOURCE 1", 4),
                q("1.5", "Calculate the terminal voltage and the potential difference across the internal resistance when the current is 0.70 A.", 4, ["V = 1.50 - (0.70)(0.50) = 1.15 V.", "Vinternal = Ir = 0.35 V."], "SOURCE 1", 3),
                q("1.6", "Explain why the switch should be opened between readings.", 2, ["To limit heating/discharge of the cell, which would change internal resistance/emf and reduce validity."], "SOURCE 1"),
            ]},
            {"title": "QUESTION 2: PHOTOELECTRIC EFFECT", "instructions": "Use Source 2 and the supplied constant h = 6.63 x 10^-34 J.s.", "stimulus": "Refer to SOURCE 2.", "questions": [
                q("2.1", "Define the work function of a metal.", 2, ["The minimum energy needed to remove an electron from the metal surface."], "SOURCE 2"),
                q("2.2", "Calculate the work function of the metal.", 4, ["W0 = hf0 = (6.63 x 10^-34)(5.5 x 10^14) = 3.65 x 10^-19 J."], "SOURCE 2", 3),
                q("2.3", "Calculate the maximum kinetic energy of emitted electrons when the frequency is 8.0 x 10^14 Hz.", 4, ["KEmax = h(f - f0) = (6.63 x 10^-34)(2.5 x 10^14) = 1.66 x 10^-19 J."], "SOURCE 2", 3),
                q("2.4", "State the effect of increasing light intensity when the frequency is above f0, and explain what happens when the frequency is below f0.", 3, ["Above f0, more electrons are emitted per second but KEmax is unchanged.", "Below f0, no electrons are emitted regardless of intensity."], "SOURCE 2"),
                q("2.5", "State why the photoelectric effect supports the particle model of light.", 2, ["Energy is transferred in discrete photons with energy hf; one photon transfers energy to one electron."], "SOURCE 2"),
            ]},
            {"title": "QUESTION 3: GALVANIC CELLS", "instructions": "Use Source 3. Standard conditions apply.", "stimulus": "Refer to SOURCE 3.", "questions": [
                q("3.1", "Identify the anode and the cathode.", 2, ["Anode: Zn; cathode: Cu."], "SOURCE 3"),
                q("3.2", "State the direction of electron flow in the external circuit.", 2, ["From the zinc electrode to the copper electrode."], "SOURCE 3"),
                q("3.3", "Write the oxidation and reduction half-reactions.", 4, ["Zn(s) -> Zn2+(aq) + 2e-.", "Cu2+(aq) + 2e- -> Cu(s)."], "SOURCE 3", 3),
                q("3.4", "Write the overall cell reaction.", 2, ["Zn(s) + Cu2+(aq) -> Zn2+(aq) + Cu(s)."], "SOURCE 3"),
                q("3.5", "Calculate the standard emf of the cell and state whether the reaction is spontaneous.", 3, ["Ecell = 0.34 - (-0.76) = +1.10 V.", "Positive Ecell means the reaction is spontaneous under standard conditions."], "SOURCE 3", 3),
                q("3.6", "Explain the function of the salt bridge.", 2, ["It permits ion movement, maintains electrical neutrality and completes the circuit without mixing the half-cell solutions directly."], "SOURCE 3"),
                q("3.7", "State how the cell potential changes as Zn2+ concentration increases and Cu2+ concentration decreases while the cell discharges.", 2, ["The cell potential decreases and approaches zero at equilibrium."], "SOURCE 3"),
            ]},
        ],
        "rubric": [
            {"criterion": "Question 1: Internal resistance", "marks": 18, "descriptor": "Concepts, variables, data relationship and circuit calculations."},
            {"criterion": "Question 2: Photoelectric effect", "marks": 15, "descriptor": "Definitions, quantitative reasoning and photon model."},
            {"criterion": "Question 3: Galvanic cells", "marks": 17, "descriptor": "Cell interpretation, redox equations, emf and ion movement."},
        ],
        "teacher_review_checklist": ["Verify all formulae, substitutions, signs and units.", "Confirm Grade 12 Term 3 CAPS scope.", "Check every diagram label and data value.", "Approve the paper and memorandum before classroom use."],
        "generation_backend": "hymark_physical_sciences_constructed_source_first",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.out)
    (args.out / "assessment_pack.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "out": str(args.out), "total_marks": 50}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
