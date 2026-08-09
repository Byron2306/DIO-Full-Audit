#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


INK = "#18212B"
BLUE = "#246B9B"
GREEN = "#4E8B57"
GOLD = "#D8A436"
RED = "#A64B3C"
WATER = "#5BA8C9"
LIGHT = "#F4F6F5"
GRID = "#C8CED3"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def dashed_line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], fill: str, width: int = 7) -> None:
    for start, end in zip(points, points[1:]):
        x1, y1 = start
        x2, y2 = end
        length = max(abs(x2 - x1), abs(y2 - y1))
        steps = max(1, length // 20)
        for index in range(steps):
            if index % 2 == 0:
                a = index / steps
                b = min(1, (index + 1) / steps)
                draw.line((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b), fill=fill, width=width)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str = INK, size: int = 25, bold: bool = True) -> None:
    draw.text(xy, text, fill=fill, font=font(size, bold))


def map_asset(path: Path) -> None:
    image = Image.new("RGB", (1600, 1050), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1565, 1015), outline=INK, width=4)
    label(draw, (75, 60), "SOURCE 1: MBALI ECONOMIC DEVELOPMENT CORRIDOR", size=38)
    draw.text((76, 112), "Constructed Grade 12 Geography map | Each grid square represents 10 km x 10 km", fill="#596572", font=font(22))

    left, top, right, bottom = 105, 190, 1215, 900
    draw.rectangle((left, top, right, bottom), fill="#F8FAF8", outline=INK, width=4)
    cols, rows = 8, 5
    cell_w, cell_h = (right - left) / cols, (bottom - top) / rows
    for col in range(1, cols):
        x = int(left + col * cell_w)
        draw.line((x, top, x, bottom), fill=GRID, width=2)
    for row in range(1, rows):
        y = int(top + row * cell_h)
        draw.line((left, y, right, y), fill=GRID, width=2)
    for col, letter in enumerate("ABCDEFGH"):
        draw.text((int(left + col * cell_w + 8), top + 5), letter, fill="#6B737B", font=font(18, True))
    for row in range(rows):
        draw.text((left + 8, int(top + row * cell_h + 30)), str(row + 1), fill="#6B737B", font=font(18, True))

    coast_x = 1120
    draw.polygon([(coast_x, top), (right, top), (right, bottom), (1080, bottom), (1100, 760), (1070, 620), (1125, 460)], fill="#DCEFF5")
    draw.line([(coast_x, top), (1125, 460), (1070, 620), (1100, 760), (1080, bottom)], fill=WATER, width=6)
    label(draw, (1125, 795), "INDIAN\nOCEAN", fill=BLUE, size=22)

    river = [(250, 210), (330, 330), (500, 410), (625, 535), (760, 610), (910, 720), (1085, 800)]
    draw.line(river, fill=WATER, width=12)
    draw.text((520, 455), "Mbali River", fill=BLUE, font=font(22, True))

    agri = (225, 240, 500, 435)
    draw.rectangle(agri, fill="#DCEAD8", outline=GREEN, width=4)
    for y in range(265, 425, 26):
        draw.line((245, y, 480, y), fill="#8CB27F", width=3)
    label(draw, (255, 320), "IRRIGATED\nAGRICULTURE", fill=GREEN, size=23)

    mine = (245, 590)
    draw.ellipse((mine[0] - 48, mine[1] - 48, mine[0] + 48, mine[1] + 48), fill="#F2CD72", outline=INK, width=4)
    label(draw, (190, 650), "COAL MINE", size=22)

    junction = (650, 600)
    draw.ellipse((junction[0] - 16, junction[1] - 16, junction[0] + 16, junction[1] + 16), fill=INK)
    label(draw, (575, 625), "KWEZI JUNCTION", size=21)

    industry = (775, 510, 955, 650)
    draw.rectangle(industry, fill="#ECD8D3", outline=RED, width=5)
    label(draw, (800, 548), "MBALI\nINDUSTRIAL\nZONE", fill=RED, size=21)

    port = (1055, 570)
    draw.rectangle((port[0] - 42, port[1] - 42, port[0] + 42, port[1] + 42), fill="#D9E2EA", outline=INK, width=4)
    draw.line((port[0], port[1] - 30, port[0], port[1] + 24), fill=INK, width=5)
    draw.arc((port[0] - 24, port[1] - 5, port[0] + 24, port[1] + 35), 0, 180, fill=INK, width=5)
    label(draw, (985, 625), "PORT DUMA", size=22)

    rail = [mine, junction, (860, 580), port]
    dashed_line(draw, rail, "#565F68", width=9)
    road = [(170, 750), (420, 680), junction, (830, 420), (1030, 350)]
    draw.line(road, fill=RED, width=9)
    draw.line(road, fill="white", width=3)
    label(draw, (690, 360), "NATIONAL ROAD", fill=RED, size=20)

    draw.line((1310, 260, 1310, 185), fill=INK, width=7)
    draw.polygon([(1310, 160), (1288, 200), (1332, 200)], fill=INK)
    label(draw, (1296, 270), "N", size=24)

    legend_x, legend_y = 1250, 360
    draw.rectangle((1235, 340, 1525, 690), fill="white", outline=INK, width=3)
    label(draw, (1260, 365), "LEGEND", size=25)
    entries = [
        (GOLD, "Coal mine", "circle"),
        (GREEN, "Irrigated agriculture", "box"),
        (RED, "Industrial zone", "box"),
        (RED, "National road", "line"),
        ("#565F68", "Railway", "dash"),
        (WATER, "River / coast", "line"),
    ]
    for index, (colour, text, kind) in enumerate(entries):
        y = legend_y + 55 + index * 43
        if kind == "circle":
            draw.ellipse((1260, y, 1284, y + 24), fill=colour, outline=INK)
        elif kind == "box":
            draw.rectangle((1260, y, 1286, y + 24), fill=colour, outline=INK)
        elif kind == "dash":
            dashed_line(draw, [(1260, y + 12), (1290, y + 12)], colour, width=6)
        else:
            draw.line((1260, y + 12, 1290, y + 12), fill=colour, width=7)
        draw.text((1305, y - 2), text, fill=INK, font=font(19))

    draw.line((1250, 760, 1450, 760), fill=INK, width=8)
    for x in [1250, 1350, 1450]:
        draw.line((x, 748, x, 772), fill=INK, width=4)
    draw.text((1240, 780), "0", fill=INK, font=font(18))
    draw.text((1332, 780), "10", fill=INK, font=font(18))
    draw.text((1425, 780), "20 km", fill=INK, font=font(18))
    draw.text((110, 935), "Map convention: one grid interval equals 10 km. Calculate straight-line grid distances from feature centres.", fill="#596572", font=font(20))
    image.save(path, quality=95)


def data_asset(path: Path) -> None:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1565, 965), outline=INK, width=4)
    label(draw, (75, 65), "SOURCE 2: MBALI CORRIDOR ECONOMIC DATA", size=38)
    draw.text((76, 118), "Constructed dataset for geographical interpretation and calculation", fill="#596572", font=font(22))

    headers = ["Sector", "2021 output", "2025 output", "2025 jobs", "Main constraint"]
    rows = [
        ["Mining", "2.8 Mt", "3.6 Mt", "3 200", "Water use"],
        ["Manufacturing", "R1.1 bn", "R1.8 bn", "5 200", "Power cost"],
        ["Agriculture", "420 000 t", "510 000 t", "7 400", "Drought risk"],
        ["Port logistics", "2.8 Mt cargo", "4.6 Mt cargo", "1 800", "Road congestion"],
    ]
    x0, y0, table_w, row_h = 85, 205, 1430, 82
    widths = [260, 250, 250, 230, 440]
    x = x0
    for index, header in enumerate(headers):
        draw.rectangle((x, y0, x + widths[index], y0 + row_h), fill="#DDE4EA", outline=INK, width=3)
        draw.text((x + 15, y0 + 25), header, fill=INK, font=font(21, True))
        x += widths[index]
    for row_index, row in enumerate(rows):
        y = y0 + (row_index + 1) * row_h
        x = x0
        for col_index, value in enumerate(row):
            fill = "#F7F8F8" if row_index % 2 == 0 else "white"
            draw.rectangle((x, y, x + widths[col_index], y + row_h), fill=fill, outline=INK, width=2)
            draw.text((x + 15, y + 26), value, fill=INK, font=font(21, col_index == 0))
            x += widths[col_index]

    chart_left, chart_top, chart_right, chart_bottom = 160, 650, 1450, 885
    draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=INK, width=4)
    draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=INK, width=4)
    values = [(2021, 2.8), (2022, 3.1), (2023, 3.5), (2024, 4.0), (2025, 4.6)]
    max_value = 5.0
    bar_w = 120
    gap = 100
    for index, (year, value) in enumerate(values):
        x = chart_left + 90 + index * (bar_w + gap)
        h = int((value / max_value) * (chart_bottom - chart_top - 25))
        draw.rectangle((x, chart_bottom - h, x + bar_w, chart_bottom), fill=BLUE, outline=INK, width=2)
        draw.text((x + 34, chart_bottom + 15), str(year), fill=INK, font=font(19))
        draw.text((x + 34, chart_bottom - h - 35), f"{value:.1f}", fill=INK, font=font(20, True))
    draw.text((75, 690), "Port cargo\n(million tonnes)", fill=INK, font=font(20, True))
    draw.text((1370, 905), "YEAR", fill=INK, font=font(20, True))
    image.save(path, quality=95)


def q(number: str, text: str, marks: int, memo: list[str], source: str, answer_lines: int | None = None) -> dict[str, Any]:
    item = {"number": number, "source_reference": source, "question": text, "marks": marks, "memo": memo}
    if answer_lines:
        item["answer_lines"] = answer_lines
    return item


def build_pack(out_dir: Path) -> dict[str, Any]:
    assets_dir = out_dir / "source_material"
    assets_dir.mkdir(parents=True, exist_ok=True)
    map_path = assets_dir / "source_1_mbali_economic_corridor_map.png"
    data_path = assets_dir / "source_2_mbali_corridor_data.png"
    map_asset(map_path)
    data_asset(data_path)
    source_3 = {
        "label": "SOURCE 3",
        "type": "constructed case-study extract",
        "title": "Planning the Mbali Development Corridor",
        "provenance": "Constructed CAPS-aligned economic-geography case study for educator review.",
        "date": "Planning scenario",
        "content": (
            "The Mbali corridor authority plans to expand mineral processing near Kwezi Junction and move more freight by rail to Port Duma. "
            "Supporters argue that beneficiation will increase the value of raw coal before export, create manufacturing employment and stimulate "
            "local services. Farmers welcome improved transport but are concerned that industry and mining may compete with irrigation for water from "
            "the Mbali River. The port municipality expects higher revenue, yet road congestion and informal settlement growth are already placing pressure "
            "on housing, waste collection and public transport. The plan proposes solar generation for the industrial zone, a freight-rail upgrade, water "
            "recycling at processing plants and a protected buffer along the river. Critics question whether the new jobs will be accessible to local workers "
            "without a parallel skills programme."
        ),
        "context": "A fictional regional planning case used with Sources 1 and 2.",
    }
    return {
        "assessment_title": "Geography Grade 12 Term 3 Economic Geography Controlled Test",
        "subject": "Geography",
        "grade": 12,
        "phase": "FET",
        "canonical_profile_id": "fet.geography",
        "blueprint": "source_based_plus_extended_response",
        "render_shell": "question_paper",
        "language_of_assessment": "English",
        "duration": "1.5 hours",
        "total_marks": 50,
        "source_assets": [
            {"title": "Mbali Economic Development Corridor map", "source_type": "map_extract", "png": str(map_path.resolve()), "asset_status": "constructed_release_candidate"},
            {"title": "Mbali Corridor economic data", "source_type": "data_table", "png": str(data_path.resolve()), "asset_status": "constructed_release_candidate"},
        ],
        "source_embedding": {"generated_visual_policy": "suppress_generated_visuals_when_source_assets_present"},
        "evidence_cards": [source_3],
        "visual_blueprint": {"required_visuals": [{"visual_kind": "map_extract"}, {"visual_kind": "data_table"}]},
        "sections": [
            {
                "title": "QUESTION 1: MAP AND SPATIAL INTERPRETATION",
                "instructions": "Use Source 1. Show calculations where required.",
                "stimulus": "Refer to SOURCE 1.",
                "questions": [
                    q("1.1", "State the general direction of Port Duma from the coal mine.", 1, ["East / east-north-east."], "SOURCE 1"),
                    q("1.2", "Using the grid scale, calculate the approximate straight-line distance from the coal mine to the Mbali Industrial Zone. Show your calculation.", 2, ["Approximately four grid intervals x 10 km = 40 km. Accept 35-45 km with method."], "SOURCE 1"),
                    q("1.3", "Identify TWO location factors visible on the map that favour industry at the Mbali Industrial Zone. Explain the value of each factor.", 4, ["Any two explained: railway access; national-road access; proximity to Port Duma; proximity to Kwezi Junction/labour and services; access to the river; proximity to raw material from the mine."], "SOURCE 1"),
                    q("1.4", "Explain how the transport network creates a development corridor between the coal mine, the industrial zone and Port Duma.", 4, ["Rail and road connect extraction, processing and export nodes.", "The corridor reduces transfer time/cost and supports flows of goods, labour and services."], "SOURCE 1"),
                    q("1.5", "Explain TWO economic linkages that could develop between irrigated agriculture and the industrial/port nodes.", 4, ["Processing and packaging of agricultural products in the industrial zone.", "Export of produce through Port Duma.", "Supply of food to workers and urban markets.", "Transport, storage or cold-chain services."], "SOURCE 1"),
                    q("1.6", "Assess ONE environmental risk shown by the location pattern and recommend a practical management response.", 5, ["Risk may include river pollution, competition for water, mine runoff, habitat loss or port/coastal pollution.", "Response must match the risk, such as water recycling, treatment, monitoring, buffer zones or rehabilitation.", "Award for map evidence, explanation and justified response."], "SOURCE 1"),
                ],
            },
            {
                "title": "QUESTION 2: ECONOMIC DATA INTERPRETATION",
                "instructions": "Use Source 2 and show all calculations.",
                "stimulus": "Refer to SOURCE 2.",
                "questions": [
                    q("2.1", "Which sector provided the most jobs in 2025?", 1, ["Agriculture: 7 400 jobs."], "SOURCE 2"),
                    q("2.2", "Calculate the percentage increase in port cargo from 2021 to 2025. Use: change / original x 100.", 3, ["(4.6 - 2.8) / 2.8 x 100 = 64.3% (approximately).", "Award method marks."], "SOURCE 2"),
                    q("2.3", "Compare the contribution of mining and manufacturing to the corridor economy using TWO data-based observations.", 4, ["Mining output rose from 2.8 Mt to 3.6 Mt and supported 3 200 jobs.", "Manufacturing value rose from R1.1 bn to R1.8 bn and supported 5 200 jobs.", "Manufacturing had more jobs; both sectors grew."], "SOURCE 2"),
                    q("2.4", "Explain how growth in port cargo could produce a multiplier effect in the corridor.", 3, ["More cargo increases demand for transport, storage and port services.", "New income/jobs raise local spending and stimulate secondary businesses."], "SOURCE 2"),
                    q("2.5", "Evaluate TWO limitations of Source 2 when judging whether corridor development is socially and environmentally sustainable.", 4, ["The dataset gives no wage quality, inequality or local-employment detail.", "It gives constraints but no measured pollution, water-use or emissions data.", "Only selected years/sectors are shown and informal activity is excluded."], "SOURCE 2"),
                ],
            },
            {
                "title": "QUESTION 3: INTEGRATED ECONOMIC-GEOGRAPHY RESPONSE",
                "instructions": "Use Sources 1, 2 and 3 in your response.",
                "stimulus": "Refer to SOURCE 1, SOURCE 2 and SOURCE 3.",
                "questions": [
                    q("3.1", "Explain how beneficiation and improved freight rail could strengthen the Mbali corridor. Use at least TWO sources.", 5, ["Beneficiation adds value before export and supports manufacturing jobs.", "Rail connects mine, industry and port while reducing road pressure and transport costs.", "Credit explicit evidence from at least two sources."], "SOURCE 1, SOURCE 2 and SOURCE 3"),
                    q("3.2", "Write a geographical paragraph evaluating whether the proposed corridor expansion is likely to be sustainable. Reach a supported judgement.", 10, ["Economic benefits: output growth, jobs, export access, linkages and multiplier effects.", "Social concerns: skills access, housing, services and uneven benefit distribution.", "Environmental concerns: river water, pollution and land-use pressure.", "Evaluate proposed rail, solar, recycling and buffer measures.", "Award for integrated source use, geographic reasoning and a substantiated judgement."], "SOURCE 1, SOURCE 2 and SOURCE 3", answer_lines=6),
                ],
            },
        ],
        "rubric": [
            {"criterion": "Question 1: Map and spatial interpretation", "marks": 20, "descriptor": "Credit map reading, calculation, spatial explanation and justified management response."},
            {"criterion": "Question 2: Economic data interpretation", "marks": 15, "descriptor": "Credit accurate data use, calculation, comparison and evaluation."},
            {"criterion": "Question 3: Integrated response", "marks": 15, "descriptor": "Credit cross-source synthesis, economic-geography reasoning and supported judgement."},
        ],
        "teacher_review_checklist": [
            "Confirm Grade 12 Term 3 economic-geography scope and terminology.",
            "Verify every map distance and data calculation.",
            "Confirm that all source labels remain attached to their questions.",
            "Approve the paper and memorandum before classroom use.",
        ],
        "generation_backend": "hymark_geography_constructed_cartographic_source_first",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Grade 12 Term 3 Geography reference pack.")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.out)
    (args.out / "assessment_pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "out": str(args.out), "total_marks": 50}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
