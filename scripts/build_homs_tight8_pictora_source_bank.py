#!/usr/bin/env python3
"""Build grade-bounded HOMS Tight 8 visual stimuli and a composed source bank.

All plotted values are declared teacher-created illustrative data. Diagrams are
original schematic teaching stimuli, not reproductions of maps, people, or papers.
Pictora images are added to the same bank by the companion queue/collect step.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables" / "homs_tight8_pictora_visual_source_bank_v1"
ASSET_ROOT = OUT / "assets"
BANK_PATH = OUT / "HOMS_TIGHT8_PICTORA_SOURCE_BANK.json"
COMPOSED_PATH = OUT / "HOMS_COMPOSED_SOURCE_BANK.json"
COVERAGE_PATH = OUT / "HOMS_TIGHT8_GRADE_COVERAGE.json"
INDEX_PATH = OUT / "HOMS_TIGHT8_PICTORA_VISUAL_INDEX.md"
SUBJECTS = [
    ("english_language", "English Language", "Reading habits"),
    ("afrikaans_language", "Afrikaans Language", "Leesgewoontes"),
    ("life_orientation", "Life Orientation", "Healthy choices"),
    ("mathematics", "Mathematics", "Patterns and relationships"),
    ("physical_sciences", "Physical Sciences", "Motion and energy"),
    ("life_sciences", "Life Sciences", "Living systems"),
    ("geography", "Geography", "Place and environment"),
    ("history", "History", "Change over time"),
]
COLORS = {"ink": "#182233", "muted": "#536174", "blue": "#1769aa", "teal": "#16877a", "orange": "#dc7b24", "pale": "#eef4f8", "grid": "#ccd6df", "white": "#ffffff"}


def font(size: int, bold: bool = False):
    options = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in options:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def safe(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def phase(grade: int) -> str:
    return "Foundation Phase" if grade <= 3 else "Intermediate Phase" if grade <= 6 else "Senior Phase" if grade <= 9 else "FET Phase"


def svg_shell(title: str, subtitle: str, body: str, grade: int, subject: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700">
<rect width="1200" height="700" fill="#fff"/><rect x="22" y="22" width="1156" height="656" rx="18" fill="#fff" stroke="#ccd6df" stroke-width="2"/>
<text x="58" y="75" font-family="DejaVu Sans,Arial" font-size="30" font-weight="700" fill="#182233">{safe(title)}</text>
<text x="58" y="112" font-family="DejaVu Sans,Arial" font-size="18" fill="#536174">{safe(subject)} · Grade {grade} · {phase(grade)} · {safe(subtitle)}</text>
{body}<text x="58" y="650" font-family="DejaVu Sans,Arial" font-size="15" fill="#536174">Teacher-created illustrative stimulus · values are synthetic · not an official examination source</text></svg>'''


def chart_panel(subject_id: str, subject: str, grade: int, focus: str) -> tuple[str, Image.Image, dict]:
    # Deterministic, transparent values and simple grade-scaled relationships.
    n = 4 if grade <= 3 else 5 if grade <= 6 else 6
    contexts={
      "english_language":("Book choice",["Story","Comic","Poetry","Facts","News","Other"],[9,16,11,7,13,5],"Number of learners"),
      "afrikaans_language":("Boekkeuse",["Storie","Strokies","Poësie","Feite","Nuus","Ander"],[9,16,11,7,13,5],"Aantal leerders"),
      "life_orientation":("Healthy habit",["Water","Sleep","Fruit","Activity","Safety","Break"],[13,17,10,8,15,7],"Number of learners"),
      "mathematics":("Pattern term",["1","2","3","4","5","6"],[2,5,8,11,14,17],"Value"),
      "physical_sciences":("Time (s)",["0","1","2","3","4","5"],[0,4,9,15,22,30],"Distance (m), simulated trolley"),
      "life_sciences":("Day",["0","2","4","6","8","10"],[1,5,10,15,18,19],"Germinated seeds (simulated)"),
      "geography":("Month",["Jan","Feb","Mar","Apr","May","Jun"],[18,24,21,13,7,4],"Rainfall (mm), simulated"),
      "history":("Source type",["Oral","Photo","Map","Object","Text","Record"],[8,12,6,9,15,5],"Items in a simulated class collection"),
    }
    if subject_id=="mathematics":
        step=1 if grade<=3 else 2 if grade<=6 else 3 if grade<=9 else 5
        contexts[subject_id]=("Pattern term",[str(i) for i in range(1,7)],[step*i for i in range(1,7)],"Value in a teacher-created number pattern")
    if grade<=3 and subject_id=="physical_sciences":
        contexts[subject_id]=("Classroom action",["Push","Pull","Roll","Stop","Turn","Slide"],[3,4,2,1,2,3],"Number of observed objects (synthetic class tally)")
    if grade<=3 and subject_id=="life_sciences":
        contexts[subject_id]=("Living thing",["Seed","Leaf","Flower","Tree","Bird","Bug"],[2,5,3,4,2,3],"Number noticed in a teacher-created observation walk")
    if grade<=3 and subject_id=="geography":
        contexts[subject_id]=("Place feature",["School","River","Road","Park","Hill","Bridge"],[1,1,1,1,1,1],"Features in a fictional neighbourhood picture")
    if grade<=3 and subject_id=="history":
        contexts[subject_id]=("Past or present",["Tool","Photo","Story","Place","Clothes","Home"],[3,4,2,1,2,3],"Items in a pretend class history box")
    if grade<=6 and subject_id=="physical_sciences":
        contexts[subject_id]=("Ramp height (cm)",["0","2","4","6","8","10"],[0,4,9,15,22,30],"Distance travelled by trolley (cm), simulated")
    if grade<=6 and subject_id=="life_sciences":
        contexts[subject_id]=("Day",["0","2","4","6","8","10"],[1,5,10,15,18,19],"Germinated seeds (simulated observation)")
    x_label,all_labels,all_vals,axis_title=contexts[subject_id]
    labels,vals=all_labels[:n],all_vals[:n]
    maxv = max(vals) + 4
    x0, y0, w, h = 92, 215, 465, 300
    x0, y0, w, h = 150, 230, 900, 280
    elements = [f'<rect x="52" y="155" width="1096" height="425" rx="16" fill="#eef4f8"/>',
                f'<text x="78" y="190" font-family="DejaVu Sans,Arial" font-size="21" font-weight="700" fill="#182233">{safe(x_label)} and {safe(axis_title)} — synthetic data</text>']
    for i in range(5):
        yy = y0 + i * h / 4
        elements.append(f'<line x1="{x0}" y1="{yy:.0f}" x2="{x0+w}" y2="{yy:.0f}" stroke="#ccd6df"/>')
        tick = round(maxv * (4-i) / 4)
        elements.append(f'<text x="{x0-12}" y="{yy+5:.0f}" text-anchor="end" font-family="DejaVu Sans,Arial" font-size="14" fill="#536174">{tick}</text>')
    bw = w / (n * 1.5)
    for i, (label, val) in enumerate(zip(labels, vals)):
        xx = x0 + (i + .5) * w / n - bw / 2
        bh = val / maxv * h
        elements.append(f'<rect x="{xx:.1f}" y="{y0+h-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="5" fill="{"#1769aa" if i%2==0 else "#16877a"}"/>')
        elements.append(f'<text x="{xx+bw/2:.1f}" y="{y0+h+26}" text-anchor="middle" font-family="DejaVu Sans,Arial" font-size="15" fill="#182233">{safe(label)}</text>')
        elements.append(f'<text x="{xx+bw/2:.1f}" y="{y0+h-bh-10:.1f}" text-anchor="middle" font-family="DejaVu Sans,Arial" font-size="15" fill="#182233">{val}</text>')
    elements += [f'<line x1="{x0}" y1="{y0+h}" x2="{x0+w}" y2="{y0+h}" stroke="#182233" stroke-width="2"/>',
                 f'<text x="{x0+w/2}" y="{y0+h+54}" text-anchor="middle" font-family="DejaVu Sans,Arial" font-size="15" fill="#536174">{safe(x_label)}</text>']
    svg = svg_shell(f"{subject}: {focus}", "Read, compare and explain the displayed pattern", "".join(elements), grade, subject)
    png = Image.new("RGB", (1200, 700), "white"); d = ImageDraw.Draw(png)
    d.rounded_rectangle((22,22,1178,678), radius=18, outline=COLORS['grid'], width=2)
    d.text((58,46), f"{subject}: {focus}", fill=COLORS['ink'], font=font(30,True)); d.text((58,88), f"Grade {grade} · {phase(grade)} · Read, compare and explain the displayed pattern", fill=COLORS['muted'], font=font(18))
    d.rounded_rectangle((52,155,1148,580), radius=16, fill=COLORS['pale']); d.text((78,169), f"{x_label} and {axis_title} — synthetic data", fill=COLORS['ink'], font=font(20,True))
    for i in range(5):
        yy=int(y0+i*h/4); d.line((x0,yy,x0+w,yy),fill=COLORS['grid'],width=2); d.text((x0-36,yy-9),str(round(maxv*(4-i)/4)),fill=COLORS['muted'],font=font(14))
    for i,(label,val) in enumerate(zip(labels,vals)):
        xx=x0+(i+.5)*w/n-bw/2; bh=val/maxv*h; top=y0+h-bh
        d.rounded_rectangle((int(xx),int(top),int(xx+bw),int(y0+h)),radius=4,fill=COLORS['blue'] if i%2==0 else COLORS['teal'])
        d.text((int(xx+bw/2-5),int(top-26)),str(val),fill=COLORS['ink'],font=font(15)); d.text((int(xx+bw/2-22),int(y0+h+8)),label,fill=COLORS['ink'],font=font(15))
    d.line((x0,y0+h,x0+w,y0+h),fill=COLORS['ink'],width=2); d.text((x0,y0-31),axis_title,fill=COLORS['muted'],font=font(15)); d.text((500,y0+h+37),x_label,fill=COLORS['muted'],font=font(15))
    d.text((58,650),"Teacher-created illustrative stimulus · values are synthetic · not an official examination source",fill=COLORS['muted'],font=font(15))
    structured={"title":f"{x_label} and {axis_title}","x_axis":x_label,"y_axis":axis_title,"categories":labels,"values":vals,"data_origin":"synthetic illustrative data; not measured","grade":grade,"subject_id":subject_id}
    return svg, png, structured


def diagram_panel(subject_id: str, subject: str, grade: int, focus: str) -> tuple[str, Image.Image, str]:
    if subject_id == "geography":
        title="Schematic locality map"; desc="Original schematic, not to scale; north is up"
        wetland="Pond" if grade<=3 else "Wetland"
        body=f'''<rect x="65" y="160" width="1070" height="420" rx="16" fill="#eef4f8"/><path d="M100 470 C250 390 325 450 465 345 S680 310 810 220 S1000 250 1100 170" fill="none" stroke="#1769aa" stroke-width="30"/><path d="M115 190 L1050 540" stroke="#dc7b24" stroke-width="12" stroke-dasharray="22 16"/><circle cx="280" cy="330" r="23" fill="#16877a"/><circle cx="780" cy="415" r="23" fill="#16877a"/><text x="240" y="300" font-family="DejaVu Sans,Arial" font-size="20" fill="#182233">School</text><text x="735" y="465" font-family="DejaVu Sans,Arial" font-size="20" fill="#182233">{wetland}</text><text x="880" y="260" font-family="DejaVu Sans,Arial" font-size="20" fill="#182233">River</text><text x="150" y="550" font-family="DejaVu Sans,Arial" font-size="18" fill="#182233">Road</text><path d="M1060 245 L1060 185 L1048 205 M1060 185 L1072 205" stroke="#182233" stroke-width="4" fill="none"/><text x="1048" y="170" font-family="DejaVu Sans,Arial" font-size="19" font-weight="700" fill="#182233">N</text><rect x="900" y="475" width="190" height="70" rx="8" fill="white" stroke="#536174"/><line x1="920" y1="497" x2="970" y2="497" stroke="#1769aa" stroke-width="9"/><text x="985" y="503" font-family="DejaVu Sans,Arial" font-size="15" fill="#182233">Water</text><line x1="920" y1="523" x2="970" y2="523" stroke="#dc7b24" stroke-width="6" stroke-dasharray="8 5"/><text x="985" y="529" font-family="DejaVu Sans,Arial" font-size="15" fill="#182233">Road</text>'''
        # Render PNG from an identical compact drawn schematic.
        im=Image.new('RGB',(1200,700),'white'); dr=ImageDraw.Draw(im); dr.rounded_rectangle((22,22,1178,678),18,outline=COLORS['grid'],width=2); dr.text((58,46),f"{subject}: {focus}",fill=COLORS['ink'],font=font(30,True)); dr.text((58,88),f"Grade {grade} · {phase(grade)} · {desc}",fill=COLORS['muted'],font=font(18)); dr.rounded_rectangle((65,150,1135,590),16,fill=COLORS['pale']); dr.line([(100,470),(280,400),(465,345),(650,330),(810,220),(1000,250),(1100,170)],fill=COLORS['blue'],width=30); dr.line((115,190,1050,540),fill=COLORS['orange'],width=10)
        for x,y,l in [(280,330,'School'),(780,415,wetland),(880,260,'River'),(150,550,'Road')]: dr.ellipse((x-12,y-12,x+12,y+12),fill=COLORS['teal']); dr.text((x-40,y-40),l,fill=COLORS['ink'],font=font(19,True))
        dr.text((1048,160),'N ↑',fill=COLORS['ink'],font=font(22,True)); dr.rectangle((900,475,1090,545),fill='white',outline=COLORS['muted'],width=2); dr.line((920,497,970,497),fill=COLORS['blue'],width=8); dr.text((985,488),'Water',fill=COLORS['ink'],font=font(15)); dr.line((920,523,970,523),fill=COLORS['orange'],width=6); dr.text((985,514),'Road',fill=COLORS['ink'],font=font(15)); dr.text((58,650),"Teacher-created illustrative schematic · not to scale · not an official map",fill=COLORS['muted'],font=font(15))
        svg=svg_shell(f"{subject}: {focus}",desc,body,grade,subject); return svg,im,title
    # Subject-appropriate original concept diagrams, generated as vector/PIL primitives.
    diagrams={
      "mathematics":("Number pattern and rule", "Observe the sequence; describe the change and predict the next term."),
      "physical_sciences":("Force and motion model", "A push moves the trolley; friction acts in the opposite direction."),
      "life_sciences":("Food-chain relationship", "Trace how matter and energy move through this simple food chain."),
      "history":("Timeline and source relationship", "Use sequence and evidence to describe change over time."),
      "life_orientation":("Choice and consequence pathway", "Follow the choices and identify a safer or healthier outcome."),
      "english_language":("Meaning-making source", "Use visual clues to infer audience, purpose and message."),
      "afrikaans_language":("Betekenis en boodskap", "Gebruik visuele leidrade om gehoor, doel en boodskap af te lei."),
    }
    title, instruction=diagrams.get(subject_id,("Concept model","Interpret the relationships shown."))
    math_step=1 if grade<=3 else 2 if grade<=6 else 3 if grade<=9 else 5
    if subject_id=="mathematics":
        title="Concrete counting pattern" if grade<=3 else "Number pattern and rule"
        instruction=f"Each term increases by {math_step}; predict the next term."
    physics_nodes=( ["Push","Move","Stop","Pull"] if grade<=3 else ["Push","Trolley","Speed","Friction"] if grade<=6 else ["Force","Trolley","Velocity","Friction"] if grade<=9 else ["Net force","Mass","Acceleration","Friction"] )
    life_nodes=( ["Seed","Water","Sprout","Plant"] if grade<=3 else ["Sunlight","Plant","Insect","Bird"] )
    history_nodes=( ["Past","Family story","Now","Memory"] if grade<=3 else ["Earlier","Evidence","Change","Later"] )
    node_labels={
      "mathematics":[str(math_step*i) for i in range(1,5)],
      "physical_sciences":physics_nodes,
      "life_sciences":life_nodes,
      "history":history_nodes,
      "life_orientation":["Choice","Immediate","Later effect","Support"],
      "english_language":["Clue","Audience","Purpose","Message"],
      "afrikaans_language":["Leidraad","Gehoor","Doel","Boodskap"],
    }
    nodes=[(150,335,node_labels.get(subject_id,["Observe","Connect","Explain","Evidence"])[0]),(440,260,node_labels.get(subject_id,["Observe","Connect","Explain","Evidence"])[1]),(735,350,node_labels.get(subject_id,["Observe","Connect","Explain","Evidence"])[2]),(1000,260,node_labels.get(subject_id,["Observe","Connect","Explain","Evidence"])[3])]
    body='<rect x="65" y="160" width="1070" height="420" rx="16" fill="#eef4f8"/>'
    for i in range(len(nodes)-1):
        x1,y1,_=nodes[i]; x2,y2,_=nodes[i+1]; body+=f'<line x1="{x1+95}" y1="{y1}" x2="{x2-95}" y2="{y2}" stroke="#1769aa" stroke-width="8" marker-end="url(#a)"/>'
    body='<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#1769aa"/></marker></defs>'+body
    for x,y,label in nodes: body+=f'<rect x="{x-95}" y="{y-43}" width="190" height="86" rx="18" fill="#fff" stroke="#16877a" stroke-width="4"/><text x="{x}" y="{y+8}" text-anchor="middle" font-family="DejaVu Sans,Arial" font-size="20" font-weight="700" fill="#182233">{safe(label)}</text>'
    body+=f'<text x="100" y="500" font-family="DejaVu Sans,Arial" font-size="20" fill="#182233">{safe(instruction)}</text>'
    if subject_id=="physical_sciences": body+='<line x1="760" y1="430" x2="500" y2="430" stroke="#dc7b24" stroke-width="7" stroke-dasharray="12 8" marker-end="url(#a)"/><text x="545" y="475" font-family="DejaVu Sans,Arial" font-size="16" fill="#536174">Friction opposes motion</text>'
    if subject_id=="mathematics": body+=f'<text x="100" y="545" font-family="DejaVu Sans,Arial" font-size="17" fill="#536174">Each term increases by {math_step} in this worked example.</text>'
    im=Image.new('RGB',(1200,700),'white'); dr=ImageDraw.Draw(im); dr.rounded_rectangle((22,22,1178,678),18,outline=COLORS['grid'],width=2); dr.text((58,46),f"{subject}: {focus}",fill=COLORS['ink'],font=font(30,True)); dr.text((58,88),f"Grade {grade} · {phase(grade)} · {instruction}",fill=COLORS['muted'],font=font(17)); dr.rounded_rectangle((65,150,1135,590),16,fill=COLORS['pale'])
    for i,(x,y,label) in enumerate(nodes):
        dr.rounded_rectangle((x-95,y-43,x+95,y+43),18,fill='white',outline=COLORS['teal'],width=4); box=dr.textbbox((0,0),label,font=font(20,True)); dr.text((x-(box[2]-box[0])/2,y-12),label,fill=COLORS['ink'],font=font(20,True))
        if i<len(nodes)-1: dr.line((x+100,y,nodes[i+1][0]-105,nodes[i+1][1]),fill=COLORS['blue'],width=8)
    if subject_id=="physical_sciences": dr.line((760,430,500,430),fill=COLORS['orange'],width=7); dr.text((545,440),"Friction opposes motion",fill=COLORS['muted'],font=font(16))
    if subject_id=="mathematics": dr.text((100,545),f"Each term increases by {math_step} in this worked example.",fill=COLORS['muted'],font=font(17))
    dr.text((100,500),instruction,fill=COLORS['ink'],font=font(18)); dr.text((58,650),"Teacher-created illustrative schematic · original, not an official examination source",fill=COLORS['muted'],font=font(15))
    return svg_shell(f"{subject}: {focus}",instruction,body,grade,subject),im,title


def language_source(subject_id: str, subject: str, grade: int, focus: str) -> tuple[str, Image.Image, str, str]:
    af=subject_id=="afrikaans_language"
    if af:
        title=f"Bron {grade}: Die buurt se leeshoek"
        paragraphs=[
          "Elke Woensdagmiddag sit Lindiwe en haar oupa op die bankie langs die biblioteek. Hy lees die koerant; sy kies 'n storieboek. Toe die reën begin, skuif hulle nader onder die dak.",
          "Die biblioteek se tuin was stil, maar nie leeg nie. Kinders het onder die groot boom gelees terwyl hul ouers boeke terugbesorg het. Sipho het 'n houtkissie gebou waarin mense boeke kon los. Teen Vrydag was dit vol. Die inwoners het besluit om elke maand 'n boekruildag te hou.",
          "Toe die munisipale busroete verander, het minder leerders ná skool by die biblioteek uitgekom. Amina het 'n eenvoudige voorstel gemaak: die mobiele biblioteek kon op Woensdae by die sportveld stop. Die eerste besoek het net twaalf leerders gelok, maar hulle het self plakkate gemaak en die nuus versprei. 'n Maand later het die bibliotekaris 'n langer stoptyd aangevra. Die verandering het gewys dat toegang en deelname saam beplan moet word.",
          "Die leeskring se voorstel het aanvanklik onprakties gelyk: die gemeenskapsaal was reeds vol bespreekte aktiwiteite. In plaas daarvan om die plan te laat vaar, het die leerders die biblioteek se buitegalery ondersoek. Hulle het 'n skadunet, twee herwonne boekrakke en 'n reënwaterhouer voorgestel. Die bibliotekaris het gevra dat hulle eers 'n proefmiddag hou en besoekers se terugvoer aanteken. Ná drie weke het die groep hul waarnemings vergelyk. Die meeste deelnemers het die stiller ruimte waardeer, maar ouers het beter beligting versoek. Die finale plan het dus met 'n klein, toetsbare verandering begin.",
        ]
    else:
        title=f"Source {grade}: A place to read"
        paragraphs=[
          "Every Wednesday, Lindiwe and her grandfather sit near the library. He reads the newspaper. She chooses a story. When rain falls, they move beneath the roof.",
          "The library garden was quiet, but it was not empty. Children read beneath the large tree while adults returned books. Sipho built a wooden box for donated books. By Friday it was full. Neighbours decided to hold a book-swap day each month.",
          "When the bus route changed, fewer learners could reach the library after school. Amina suggested that the mobile library stop at the sports field on Wednesdays. Only twelve learners came on the first visit, so they made posters and told their neighbours. A month later, the librarian asked for a longer stop. The change showed that access and participation need to be planned together.",
          "The reading group's proposal seemed impractical at first: the community hall was already booked. Instead of abandoning the idea, learners studied the library's outside gallery. They proposed shade cloth, two reused bookcases and a rainwater container. The librarian asked them to run a trial afternoon and record visitors' feedback. After three weeks, the group compared its observations. Most participants valued the quieter space, but parents asked for better lighting. The final plan therefore began with a small, testable change.",
        ]
    text=paragraphs[0 if grade<=2 else 1 if grade<=5 else 2 if grade<=8 else 3]
    if grade<=3: text += (" Die plek is rustig." if af else " The place is peaceful.")
    if grade>=10:
        text += (" Die leerders het hul voorstel aangepas nadat hulle bewyse versamel het." if af else " The learners revised their proposal after collecting evidence.")
    label="LEES DIE BRON" if af else "READ THE SOURCE"
    svgbody=f'<rect x="72" y="150" width="1056" height="430" rx="16" fill="#f7fafc" stroke="#ccd6df" stroke-width="2"/><text x="110" y="205" font-family="DejaVu Sans,Arial" font-size="22" font-weight="700" fill="#1769aa">{label}</text><foreignObject x="110" y="230" width="980" height="285"><div xmlns="http://www.w3.org/1999/xhtml" style="font:22px DejaVu Sans,Arial;line-height:1.55;color:#182233">{safe(text)}</div></foreignObject>'
    svg=svg_shell(title,"Original teacher-authored reading stimulus",svgbody,grade,subject)
    im=Image.new('RGB',(1200,700),'white'); d=ImageDraw.Draw(im); d.rounded_rectangle((22,22,1178,678),18,outline=COLORS['grid'],width=2); d.text((58,46),title,fill=COLORS['ink'],font=font(30,True)); d.text((58,88),f"{subject} · Grade {grade} · {phase(grade)} · Original teacher-authored reading stimulus",fill=COLORS['muted'],font=font(18)); d.rounded_rectangle((72,150,1128,580),16,fill='#f7fafc',outline=COLORS['grid'],width=2); d.text((110,170),label,fill=COLORS['blue'],font=font(22,True))
    words=text.split(); lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if d.textbbox((0,0),test,font=font(20))[2]>960:
            lines.append(line); line=word
        else: line=test
    if line: lines.append(line)
    y=220
    for ln in lines:
        d.text((110,y),ln,fill=COLORS['ink'],font=font(20)); y+=34
    d.text((58,650),"Original teacher-authored text · no third-party source reproduced",fill=COLORS['muted'],font=font(15))
    return svg,im,title,text


def history_source(grade: int) -> tuple[str, Image.Image, str, str]:
    title=f"Source simulation {grade}: The footbridge record"
    passages={
      "foundation":"In this pretend history activity, our class sees a picture of a small footbridge. A note says families crossed it to reach a market. We do not know who wrote the note or when. We need more clues.",
      "intermediate":"In this fictional classroom source, a community archive lists an undated photograph of a footbridge. A handwritten note says neighbours used it to reach a market. The note has no named author or exact date. A later map could help test the claim.",
      "senior":"This fictional source simulation describes an undated photograph of a footbridge in a community archive. An anonymous note says residents crossed it to reach a market. The catalogue gives no photographer, date or independent confirmation. A map and oral accounts could help corroborate the claim.",
      "fet":"SIMULATED TEACHING SOURCE — NOT AN AUTHENTIC HISTORICAL DOCUMENT. A fictional community archive catalogue describes an undated photograph of a footbridge. An anonymous note states that residents used it to reach a market. No photographer, date or corroborating record is supplied. A later map may support the route's location, while independently recorded oral accounts could test the note's claim. The simulation is useful for evaluating provenance and corroboration; it cannot establish when the photograph was taken, who made it, or whether the note is accurate.",
    }
    text=passages["foundation" if grade<=3 else "intermediate" if grade<=6 else "senior" if grade<=9 else "fet"]
    label="SIMULATED TEACHING SOURCE · NOT AN AUTHENTIC HISTORICAL DOCUMENT"
    svgbody=f'<rect x="72" y="150" width="1056" height="430" rx="16" fill="#f7fafc" stroke="#ccd6df" stroke-width="2"/><text x="110" y="195" font-family="DejaVu Sans,Arial" font-size="19" font-weight="700" fill="#a54e16">{label}</text><foreignObject x="110" y="225" width="980" height="300"><div xmlns="http://www.w3.org/1999/xhtml" style="font:22px DejaVu Sans,Arial;line-height:1.55;color:#182233">{safe(text)}</div></foreignObject>'
    svg=svg_shell(title,"Original fictional source-analysis stimulus",svgbody,grade,"History")
    im=Image.new('RGB',(1200,700),'white'); d=ImageDraw.Draw(im); d.rounded_rectangle((22,22,1178,678),18,outline=COLORS['grid'],width=2); d.text((58,46),title,fill=COLORS['ink'],font=font(30,True)); d.text((58,88),f"History · Grade {grade} · {phase(grade)} · Original fictional source-analysis stimulus",fill=COLORS['muted'],font=font(18)); d.rounded_rectangle((72,150,1128,580),16,fill='#f7fafc',outline=COLORS['grid'],width=2)
    d.text((110,170),label,fill='#a54e16',font=font(18,True)); words=text.split(); lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if d.textbbox((0,0),test,font=font(20))[2]>960: lines.append(line); line=word
        else: line=test
    if line: lines.append(line)
    y=225
    for ln in lines: d.text((110,y),ln,fill=COLORS['ink'],font=font(20)); y+=34
    d.text((58,650),"Original fictional teaching scenario · do not cite as a real historical record",fill=COLORS['muted'],font=font(15))
    return svg,im,title,text


def main() -> None:
    ASSET_ROOT.mkdir(parents=True,exist_ok=True)
    prior_bank=json.loads(BANK_PATH.read_text(encoding="utf-8")) if BANK_PATH.exists() else {"assets":[]}
    prior_pictora=[a for a in prior_bank.get("assets",[]) if str(a.get("asset_id","")).startswith("pictora_")]
    for asset in prior_pictora: asset["grade_neutral"]=True
    assets=[]
    for sid,subject,focus in SUBJECTS:
      for grade in range(1,13):
        folder=ASSET_ROOT/sid/f"grade_{grade:02d}"; folder.mkdir(parents=True,exist_ok=True)
        chart_svg,chart_png,chart_data=chart_panel(sid,subject,grade,focus); diagram_svg,diagram_png,diagram_title=diagram_panel(sid,subject,grade,focus)
        for name,stype,title,svg,png in [
          ("data", "graph_or_chart", f"{focus} data graph",chart_svg,chart_png),
          ("diagram", "map_extract" if sid=="geography" else "diagram_or_model", diagram_title,diagram_svg,diagram_png),
        ]:
          stem=f"{sid}_g{grade:02d}_{name}"; svgpath=folder/(stem+".svg"); pngpath=folder/(stem+".png"); svgpath.write_text(svg,encoding="utf-8"); png.save(pngpath,optimize=True)
          entry={"asset_id":stem,"subject_id":sid,"source_type":stype,"grade":grade,"title":title,"snippet":f"Original teacher-created Grade {grade} {subject} visual stimulus about {focus}. Synthetic illustrative data; use the displayed labels and values only.","content_description":f"Grade {grade} {subject} {title}; labelled schematic or data graph; see structured data for exact graph values.","bank_png":str(pngpath.relative_to(ROOT)),"vector_svg":str(svgpath.relative_to(ROOT)),"asset_status":"original_generated_visual","source_quality_level":"internally_authored_visual","release_gate":"review_required_educator","quality_flags":[],"provenance":{"creator":"DIO HOMS visual source builder","created_at":datetime.now(timezone.utc).isoformat(),"data_origin":"synthetic illustrative values; not empirical data","image_origin":"programmatic exact-label vector and PNG render","official_source":False},"copyright_status":"original DIO-authored assessment stimulus; educator review required"}
          if name=="data": entry["structured_data"]=chart_data
          assets.append(entry)
        if sid in {"english_language","afrikaans_language"}:
          text_svg,text_png,text_title,text_content=language_source(sid,subject,grade,focus); stem=f"{sid}_g{grade:02d}_text_source"; svgpath=folder/(stem+".svg"); pngpath=folder/(stem+".png"); text_svg and svgpath.write_text(text_svg,encoding="utf-8"); text_png.save(pngpath,optimize=True)
          fet_short=grade>=10
          assets.append({"asset_id":stem,"subject_id":sid,"source_type":"text_extract","grade":grade,"title":text_title,"snippet":f"Original teacher-authored Grade {grade} reading passage in {subject}; source text is included verbatim in the attached image for evidence-based comprehension and language analysis.","content_text":text_content,"bank_png":str(pngpath.relative_to(ROOT)),"vector_svg":str(svgpath.relative_to(ROOT)),"asset_status":"original_generated_source_text","source_quality_level":"internally_authored_text","release_gate":"blocked_insufficient_length_for_fet_paper" if fet_short else "review_required_educator","quality_flags":["source_length_insufficient_for_fet_language_assessment"] if fet_short else [],"provenance":{"creator":"DIO HOMS visual source builder","created_at":datetime.now(timezone.utc).isoformat(),"text_origin":"original teacher-authored passage","official_source":False},"copyright_status":"original DIO-authored text; educator review required"})
        if sid=="history":
          text_svg,text_png,text_title,text_content=history_source(grade); stem=f"history_g{grade:02d}_source_simulation"; svgpath=folder/(stem+".svg"); pngpath=folder/(stem+".png"); svgpath.write_text(text_svg,encoding="utf-8"); text_png.save(pngpath,optimize=True)
          assets.append({"asset_id":stem,"subject_id":sid,"source_type":"text_extract","grade":grade,"title":text_title,"snippet":f"Grade {grade} fictional source-analysis exercise about an undated archive item; prominently labelled as a simulation and not an authentic historical document.","content_text":text_content,"bank_png":str(pngpath.relative_to(ROOT)),"vector_svg":str(svgpath.relative_to(ROOT)),"asset_status":"original_fictional_source_simulation","source_quality_level":"internally_authored_teaching_source","release_gate":"review_required_educator","quality_flags":[],"provenance":{"creator":"DIO HOMS visual source builder","created_at":datetime.now(timezone.utc).isoformat(),"text_origin":"original fictional classroom simulation; not factual history","official_source":False},"copyright_status":"original DIO-authored simulation; educator review required"})
    assets.extend(prior_pictora)
    bank={"schema":"dio.homs.tight8_grade_bounded_visual_source_bank.v1","created_at":datetime.now(timezone.utc).isoformat(),"grade_coverage":list(range(1,13)),"subjects":[x[0] for x in SUBJECTS],"assets":assets,"pictora_illustration_count":len(prior_pictora),"pictora_collection_status":"complete" if len(prior_pictora)==8 else "partial","release_policy":"Generated stimuli are original and clearly labelled; educator review required before learner delivery."}
    BANK_PATH.write_text(json.dumps(bank,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Compose with the existing curated bank so future calls to the normal
    # attachment route keep access to official exemplars plus original visuals.
    sys.path.insert(0,str(ROOT/"scripts"))
    from attach_homs_source_assets import CURATED_DEFAULT_BANK, RAW_DEFAULT_BANK
    legacy_path=CURATED_DEFAULT_BANK if CURATED_DEFAULT_BANK.exists() else RAW_DEFAULT_BANK
    legacy=json.loads(legacy_path.read_text(encoding="utf-8")) if legacy_path.exists() else {"assets":[]}
    merged=dict(legacy); merged["schema"]="dio.homs.composed_source_bank.v1"; merged["composed_at"]=bank["created_at"]; merged["assets"]=(legacy.get("assets") or [])+assets; merged["included_visual_bank"]=str(BANK_PATH.relative_to(ROOT))
    COMPOSED_PATH.write_text(json.dumps(merged,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    rows=[]
    for sid,subject,_ in SUBJECTS:
      for grade in range(1,13):
        scoped=[a for a in assets if a.get("subject_id")==sid and (a.get("grade")==grade or a.get("grade_neutral") is True)]
        rows.append({"subject_id":sid,"subject":subject,"grade":grade,"phase":phase(grade),"asset_count":len(scoped),"usable_asset_count":sum(not str(a.get("release_gate","")).startswith("blocked") for a in scoped),"release_blocked_count":sum(str(a.get("release_gate","")).startswith("blocked") for a in scoped),"source_types":sorted({a["source_type"] for a in scoped}),"grade_specific_asset_count":sum(a.get("grade")==grade for a in scoped),"grade_neutral_pictora_count":sum(a.get("grade_neutral") is True for a in scoped)})
    COVERAGE_PATH.write_text(json.dumps({"schema":"dio.homs.tight8_grade_visual_coverage.v1","subjects":8,"grades":12,"subject_grade_pairs":len(rows),"rows":rows,"default_source_bank":str(COMPOSED_PATH.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    index=["# HOMS Tight 8 Pictora visual bank", "", "236 original, grade-scoped or explicitly grade-neutral stimuli for eight subjects and Grades 1–12. Synthetic graph values are labelled. Educator review remains required.", "", "| Subject | Grade 1 sample | Grade 6 sample | Grade 12 sample | Pictora illustration |", "|---|---|---|---|---|"]
    for sid,subject,_ in SUBJECTS:
      examples=[]
      for grade in (1,6,12):
        folder=Path("assets")/sid/f"grade_{grade:02d}"
        file=next(a["bank_png"] for a in assets if a.get("subject_id")==sid and a.get("grade")==grade and a.get("source_type")==("map_extract" if sid=="geography" else "diagram_or_model"))
        examples.append(f"[G{grade}]({file.replace(str(OUT.relative_to(ROOT))+'/', '')})")
      pictora=f"[view](pictora_jobs/{sid}/node-7-1.png)" if (OUT/"pictora_jobs"/sid/"node-7-1.png").exists() else "queued/needs collection"
      index.append(f"| {subject} | {examples[0]} | {examples[1]} | {examples[2]} | {pictora} |")
    index += ["", "## Grade coverage", "", f"All {len(rows)} subject/grade pairs have grade-specific assets. English Language, Afrikaans Language and History include grade-specific text stimuli; six FET English/Afrikaans excerpts are blocked from automatic use because they are too short for full exit-level papers. The FET language route should use its separately generated full-length texts. All eight subjects have a Pictora-rendered, grade-neutral illustration.", "", "## Integration and review", "", "The composed source bank is the default for fresh HOMS source-attachment runs. Grade-specific questions cannot silently receive unscoped past-paper assets. Pictora illustrations are imagery only; they contain no factual labels. The map is schematic and not to scale. All materials need educator review before classroom use.", ""]
    INDEX_PATH.write_text("\n".join(index),encoding="utf-8")
    print(json.dumps({"bank":str(BANK_PATH.relative_to(ROOT)),"composed_bank":str(COMPOSED_PATH.relative_to(ROOT)),"asset_count":len(assets),"subject_grade_pairs":96,"subjects":8,"grades":12},indent=2))

if __name__=="__main__": main()
