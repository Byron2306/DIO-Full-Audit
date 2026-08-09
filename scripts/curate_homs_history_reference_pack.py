#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOURCE_CARDS = [
    {
        "label": "SOURCE 1A",
        "type": "constructed political statement",
        "title": "Opening statement at a multiparty negotiation forum, 1991",
        "provenance": "Constructed synthesis based on themes documented in the CODESA negotiation process; not a verbatim quotation.",
        "date": "1991",
        "content": (
            "Delegates from political organisations and administrations have gathered after decades of conflict and exclusion. "
            "Although they represent different traditions, they share two immediate purposes: ending apartheid and creating a "
            "democratic state based on the will of the people. The path to negotiations has involved repression, protest and loss "
            "of life. A negotiated settlement is presented as the only workable route forward. The statement warns that political "
            "violence and groups opposed to majority rule may derail the process. It nevertheless commits the forum to a unitary, "
            "non-racial and non-sexist South Africa, a justiciable Bill of Rights, and a constitution that protects human dignity. "
            "Delegates are urged to negotiate in good faith because millions of South Africans depend on a peaceful settlement."
        ),
        "context": "A constructed negotiation-era statement for source analysis.",
    },
    {
        "label": "SOURCE 1B",
        "type": "constructed contemporary observation",
        "title": "Election observer's field note, Soweto, 27 April 1994",
        "provenance": "Constructed eyewitness-style record based on widely documented features of South Africa's first democratic election.",
        "date": "27 April 1994",
        "content": (
            "Before sunrise, a long queue had formed outside the polling station. Most voters were Black South Africans who had "
            "never previously been permitted to vote in a national election. Elderly voters waited beside young adults, while some "
            "parents carried children and identity documents. IEC officials directed the queue and explained the ballot procedure. "
            "Despite the long wait, the atmosphere remained patient and celebratory. Several voters described the act of placing a "
            "ballot in the box as proof that citizenship now included them. The note records only one polling station and therefore "
            "cannot represent every experience of the election, but it captures the determination visible at that location."
        ),
        "context": "A constructed observation record with an explicit limitation.",
    },
    {
        "label": "SOURCE 1C",
        "type": "constructed retrospective account",
        "title": "A former negotiation delegate reflects on the road to the 1994 election",
        "provenance": "Constructed retrospective account for classroom analysis; the speaker is fictional and the passage is not taken from a memoir.",
        "date": "Written retrospectively",
        "content": (
            "The April 1994 election fulfilled a goal that many South Africans had pursued for decades: equal political citizenship. "
            "The negotiations were repeatedly threatened by mistrust and violence. The assassination of Chris Hani in April 1993 "
            "created a real danger that anger would overwhelm the talks, but it also increased pressure on political leaders to set "
            "an election date and prevent further conflict. Compromise was unavoidable. The liberation movements accepted a phased "
            "transition and a Government of National Unity, while the outgoing government accepted majority rule and a binding Bill "
            "of Rights. Looking back, the delegate describes the election as both a victory over apartheid and the product of difficult "
            "concessions. Because the account was written after the successful election, its hopeful tone may understate divisions that "
            "remained unresolved."
        ),
        "context": "A constructed retrospective source that learners can evaluate for perspective and hindsight.",
    },
    {
        "label": "SOURCE 2A",
        "type": "constructed policy statement",
        "title": "Soviet foreign-policy statement reflecting the 'new thinking' of 1988",
        "provenance": "Constructed paraphrase of themes associated with Gorbachev's 1988 United Nations address; not a verbatim quotation.",
        "date": "1988",
        "content": (
            "International relations can no longer depend on the threat or use of force. Every nation must be allowed to choose its "
            "own political path without external coercion. The Soviet Union will retain its own values, but it should not impose them "
            "on other states. Foreign policy must become less ideological, and disputes should be addressed through cooperation and "
            "negotiation. This approach implies that Soviet military power will no longer automatically preserve communist governments "
            "in Eastern Europe."
        ),
        "context": "A constructed policy source illustrating Gorbachev's shift away from coercive control.",
    },
    {
        "label": "SOURCE 2B",
        "type": "constructed contemporary editorial",
        "title": "Editorial response to the opening of the Berlin Wall, November 1989",
        "provenance": "Constructed newspaper-style commentary for classroom analysis; not reproduced from a published editorial.",
        "date": "November 1989",
        "content": (
            "Crowds crossing the Berlin Wall have done more than open a border. They have exposed the weakening of Soviet influence "
            "throughout Eastern Europe. Moscow did not send tanks to preserve the East German government, as it had used force against "
            "earlier challenges in the region. Popular pressure, reform movements and the Soviet policy of non-intervention have combined "
            "to make the old division of Europe unsustainable. The celebration in Berlin is therefore also a warning to every government "
            "that relies on outside power rather than public consent."
        ),
        "context": "A constructed editorial interpretation written from the perspective of November 1989.",
    },
    {
        "label": "SOURCE 2C",
        "type": "constructed secondary interpretation",
        "title": "Interpreting the end of the Cold War and its significance for South Africa",
        "provenance": "Constructed secondary synthesis for educator review; not a quotation from a published historian.",
        "date": "Contemporary synthesis",
        "content": (
            "Gorbachev's reforms were intended to renew the Soviet system, yet glasnost and perestroika widened criticism and weakened "
            "central control. In Poland, Solidarity demonstrated the organisational strength of popular resistance, while economic "
            "stagnation limited Moscow's ability to sustain its allies. The revolutions of 1989 and the collapse of the Soviet Union "
            "therefore resulted from both reform from above and pressure from below. For South Africa, the decline of superpower rivalry "
            "weakened the apartheid government's claim that racial rule was necessary to resist communism. It also reduced external "
            "support for armed conflict in the region and created a more favourable climate for negotiations, although internal mass "
            "resistance and economic pressure remained essential causes of political change."
        ),
        "context": "A constructed interpretation that presents multiple causes and avoids a single-factor explanation.",
    },
    {
        "label": "SOURCE 3A",
        "type": "constructed testimony summary",
        "title": "Summary of a survivor's testimony to the Truth and Reconciliation Commission",
        "provenance": "Constructed composite based on recurring forms of TRC testimony; no words are attributed to a real witness.",
        "date": "TRC hearing period, 1996-1998",
        "content": (
            "A survivor describes being detained without trial during the 1980s and assaulted while officials demanded information "
            "about local activists. The testimony identifies the place of detention, the methods used and the lasting effect on the "
            "survivor's family. Speaking publicly is described as painful but necessary because the abuse had previously been denied. "
            "The survivor wants official acknowledgement and information about who authorised the operation. The account provides a "
            "personal perspective and detailed memory, but trauma, elapsed time and the survivor's limited access to official records "
            "must be considered when historians corroborate particular details."
        ),
        "context": "A constructed composite testimony for evaluating value and limitation.",
    },
    {
        "label": "SOURCE 3B",
        "type": "constructed historian's interpretation",
        "title": "A historian assesses the TRC as evidence and as a process of reconciliation",
        "provenance": "Constructed secondary interpretation for classroom use; not a quotation from a published historian.",
        "date": "Contemporary synthesis",
        "content": (
            "The TRC created an unusually large public archive of testimony about apartheid-era violations and made experiences that "
            "had been excluded from official records visible. Its hearings helped some families obtain acknowledgement and allowed "
            "historians to compare personal accounts with institutional documents. Yet the archive is incomplete. Not every victim "
            "testified, perpetrators seeking amnesty had incentives to shape their accounts, and the focus on gross human-rights "
            "violations could obscure the everyday structural effects of apartheid. The TRC therefore remains indispensable evidence, "
            "but it cannot by itself provide a complete history or prove that reconciliation was achieved equally for all communities."
        ),
        "context": "A constructed balanced interpretation of the TRC's historical value and limits.",
    },
]


def question(number: str, source: str, text: str, marks: int, memo: list[str]) -> dict[str, Any]:
    return {"number": number, "source_reference": source, "question": text, "marks": marks, "memo": memo}


def build_pack(exam_set: dict[str, Any]) -> dict[str, Any]:
    essay = exam_set["first_opportunity"]["essay_question"]
    sections = [
        {
            "title": "QUESTION 1: THE COMING OF DEMOCRACY IN SOUTH AFRICA",
            "instructions": "Use Sources 1A to 1C and your own knowledge where required.",
            "stimulus": "Refer to SOURCE 1A, SOURCE 1B and SOURCE 1C.",
            "questions": [
                question("1.1", "SOURCE 1A", "According to Source 1A, state TWO purposes that brought delegates to the negotiation forum.", 2, ["To end apartheid.", "To create a democratic state based on the will of the people."]),
                question("1.2", "SOURCE 1B", "Identify THREE details in Source 1B that show the inclusive and determined character of the election.", 3, ["Any three: first-time Black voters; elderly and young voters together; parents with children; voters carrying identity documents; patient queues; celebratory atmosphere; voters describing inclusion as citizens."]),
                question("1.3", "SOURCE 1C", "Explain why the assassination of Chris Hani was both a threat to and a catalyst for the negotiation process.", 3, ["It threatened to intensify anger and political violence.", "It increased pressure on leaders to prevent conflict.", "It accelerated agreement on an election date."]),
                question("1.4", "SOURCE 1A and SOURCE 1C", "Explain how Source 1C supports Source 1A's warning that negotiations faced serious difficulties.", 4, ["Source 1A warns that violence and opponents of majority rule could derail negotiations.", "Source 1C identifies mistrust, violence and Hani's assassination as actual threats.", "Together they show that negotiations occurred under sustained pressure and could have collapsed."]),
                question("1.5", "SOURCE 1B", "Evaluate the usefulness of Source 1B for a historian studying public participation on 27 April 1994.", 4, ["Useful because it is framed as a contemporary field note and records concrete behaviour at a polling station.", "It captures first-time participation, patience and voters' stated sense of citizenship.", "Limited because it covers one Soweto polling station and cannot represent every region or political experience."]),
                question("1.6", "SOURCE 1C", "Explain TWO ways in which hindsight may influence the perspective in Source 1C.", 4, ["The successful election may encourage a hopeful interpretation of earlier events.", "The writer may emphasise compromise and understate unresolved divisions.", "Retrospective memory selects events that fit the known outcome."]),
                question("1.7", "SOURCE 1A, SOURCE 1B and SOURCE 1C", "Using all three sources and your own knowledge, assess the extent to which the 1994 election resulted from political compromise.", 5, ["A supported judgement is required.", "Compromise included acceptance of majority rule, constitutional protection, a phased transition and the Government of National Unity.", "Mass participation gave the settlement democratic legitimacy.", "Violence, pressure from civil society and the risk of breakdown also shaped the outcome."]),
            ],
        },
        {
            "title": "QUESTION 2: THE END OF THE COLD WAR AND A NEW WORLD ORDER",
            "instructions": "Use Sources 2A to 2C and your own knowledge where required.",
            "stimulus": "Refer to SOURCE 2A, SOURCE 2B and SOURCE 2C.",
            "questions": [
                question("2.1", "SOURCE 2A", "State TWO principles of the Soviet 'new thinking' described in Source 2A.", 2, ["States should be free to choose their political path.", "Force or coercion should not determine international relations.", "Ideology should not be imposed on other states."]),
                question("2.2", "SOURCE 2B", "What does Source 2B identify as the significance of Moscow's decision not to send tanks to East Germany?", 2, ["It showed that the Soviet Union would no longer preserve Eastern European communist governments by force.", "It exposed the decline of Soviet influence."]),
                question("2.3", "SOURCE 2C", "State TWO consequences of the end of superpower rivalry for South Africa.", 2, ["It weakened the apartheid government's anti-communist justification.", "It reduced external support for regional conflict.", "It created a more favourable climate for negotiations."]),
                question("2.4", "SOURCE 2A", "Explain how Source 2A reflects a change in Soviet foreign policy.", 3, ["It rejects force and imposed ideology.", "It recognises freedom of political choice.", "This differs from earlier Soviet intervention to preserve communist rule in Eastern Europe."]),
                question("2.5", "SOURCE 2B", "Explain why the opening of the Berlin Wall represented more than a change to one national border.", 3, ["It symbolised the collapse of division in Europe.", "It demonstrated the weakness of Soviet-backed governments.", "It showed the combined effect of popular pressure and Soviet non-intervention."]),
                question("2.6", "SOURCE 2C", "Evaluate the reliability of Source 2C as an explanation of the end of the Cold War.", 4, ["It is reliable as a balanced constructed synthesis because it identifies reform, popular resistance and economic weakness.", "It avoids treating Gorbachev as the only cause.", "It remains a secondary interpretation and its claims should be checked against primary evidence."]),
                question("2.7", "SOURCE 2A and SOURCE 2B", "Compare how Sources 2A and 2B explain the decline of Soviet control in Eastern Europe.", 4, ["Source 2A emphasises policy change from above: non-coercion and freedom of choice.", "Source 2B combines Soviet non-intervention with popular pressure from below.", "Both identify reduced Soviet willingness to use force as decisive."]),
                question("2.8", "SOURCE 2A, SOURCE 2B and SOURCE 2C", "Using all three sources and your own knowledge, assess the extent to which Gorbachev's reforms caused the end of the Cold War.", 5, ["A supported judgement is required.", "Reforms and non-intervention weakened Soviet control.", "Solidarity and other popular movements challenged communist governments.", "Economic stagnation and wider structural pressures must also be considered."]),
            ],
        },
        {
            "title": "QUESTION 3: THE TRUTH AND RECONCILIATION COMMISSION",
            "instructions": "Use Sources 3A and 3B to conduct a historical enquiry into testimony, evidence and reconciliation.",
            "stimulus": "Refer to SOURCE 3A and SOURCE 3B.",
            "questions": [
                question("3.1", "SOURCE 3A", "State TWO reasons why the survivor considered public testimony necessary.", 2, ["To obtain official acknowledgement of abuse that had been denied.", "To discover who authorised the operation.", "To place the experience on public record."]),
                question("3.2", "SOURCE 3A", "Explain what Source 3A reveals about both the value and the difficulty of survivor testimony.", 4, ["It provides personal detail, identifies methods of abuse and records lasting effects.", "Testifying can restore acknowledgement.", "Trauma and elapsed time may affect memory, so details require corroboration."]),
                question("3.3", "SOURCE 3A and SOURCE 3B", "Compare the views of Sources 3A and 3B on the historical value of testimony.", 4, ["Source 3A demonstrates the detailed personal evidence testimony can provide.", "Source 3B values the public archive but stresses that it is incomplete.", "Both support using testimony while recognising the need for corroboration and context."]),
                question("3.4", "SOURCE 3B", "Evaluate the usefulness and limitations of Source 3B for a historian assessing the TRC.", 5, ["Useful because it explains acknowledgement, archive creation and comparison with institutional records.", "It identifies missing testimony, incentives affecting amnesty accounts and the narrow focus on gross violations.", "As a constructed secondary synthesis, it should be tested against hearings, reports and other scholarship."]),
                question("3.5", "SOURCE 3A and SOURCE 3B", "Write a historical paragraph assessing the extent to which the TRC produced both truth and reconciliation.", 10, ["Award for a clear judgement supported by both sources.", "Truth: public testimony, acknowledgement, archive creation and comparison with records.", "Limitations: incomplete participation, shaped perpetrator accounts and underrepresentation of structural apartheid.", "Reconciliation: some acknowledgement and public recognition, but unequal outcomes mean reconciliation was incomplete.", "Credit coherent evidence use, historical reasoning and a substantiated conclusion."]),
            ],
        },
        {
            "title": "QUESTION 4: EXTENDED WRITING",
            "instructions": "Write a well-structured historical essay with a clear line of argument and relevant evidence.",
            "stimulus": str(essay.get("context") or ""),
            "questions": [
                question("4.1", "CAPS TERM 3 CONTENT", str(essay.get("question") or ""), 50, [
                    "A defensible thesis that addresses 'to what extent'.",
                    "Gorbachev's glasnost, perestroika and non-intervention policy.",
                    "The role of Solidarity, the 1989 revolutions and the Berlin Wall.",
                    "Soviet economic and political weakness and the collapse of the USSR.",
                    "Consequences for South Africa alongside internal resistance, sanctions and negotiation pressure.",
                    "A balanced conclusion that weighs global and South African causes.",
                ]),
            ],
        },
    ]
    return {
        "assessment_title": "Grade 12 History Term 3 Controlled Examination",
        "subject": "History",
        "grade": 12,
        "phase": "FET",
        "canonical_profile_id": "fet.history",
        "blueprint": "source_based_exam",
        "render_shell": "question_paper",
        "language_of_assessment": "English",
        "duration": "3 hours",
        "total_marks": 125,
        "evidence_cards": SOURCE_CARDS,
        "source_embedding": {"generated_visual_policy": "suppress_generated_visuals_when_evidence_cards_present"},
        "visual_blueprint": {"required_visuals": []},
        "sections": sections,
        "rubric": [
            {"criterion": "Question 1: Democracy source enquiry", "marks": 25, "descriptor": "Mark each response against its source-specific memorandum points."},
            {"criterion": "Question 2: Cold War source enquiry", "marks": 25, "descriptor": "Credit accurate evidence use, comparison, evaluation and supported judgement."},
            {"criterion": "Question 3: TRC historical enquiry", "marks": 25, "descriptor": "Credit corroboration, value-and-limitation reasoning and a supported historical paragraph."},
            {"criterion": "Question 4: Historical essay", "marks": 50, "descriptor": "Apply the CAPS-style holistic judgement to argument, evidence, structure and conclusion."},
        ],
        "teacher_review_checklist": [
            "Confirm the constructed-source labels remain visible and no passage is presented as a verbatim historical quotation.",
            "Verify factual scope against Grade 12 CAPS Term 3 content.",
            "Confirm acceptable alternatives and cognitive demand in the memorandum.",
            "Approve the final paper and memorandum before classroom use.",
        ],
        "generation_backend": "hymark_history_curated_source_first",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the curated Grade 12 Term 3 History reference pack.")
    parser.add_argument("exam_set", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    exam_set = json.loads(args.exam_set.read_text(encoding="utf-8"))
    pack = build_pack(exam_set)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "out": str(args.out), "total_marks": pack["total_marks"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
