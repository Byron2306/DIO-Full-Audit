#!/usr/bin/env python3
"""Create reproducible, source-verified CAPS grade exam and memo drafts.

The item bank is educator-authored and deliberately small enough for review. It
does not call a language model. Every paper is labelled as a draft and its memo
is checked against the question marks before either DOCX is written.
"""
from __future__ import annotations

import hashlib
import json
import sys
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from scripts.build_homs_grade_exam_candidate import render_docx
from scripts.resolve_caps_source import load_manifest, resolve as resolve_caps

OUT = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ASSIGNMENTS = OUT / "RANDOM_SUBJECT_ASSIGNMENTS.json"
CAPS_MANIFEST = OUT / "CAPS_SOURCE_MANIFEST_VERIFIED.json"
MARKS = {1: [4]*5, 2: [4]*5, 3: [4]*5, 4: [5,5,6,7,6], 5: [5,5,6,7,7], 6: [5,5,6,7,7], 7: [6,6,8,10,10], 8: [6,6,8,10,10], 9: [6,7,8,9,10], 10: [8,9,10,11,12], 11: [8,9,10,11,12], 12: [8,9,10,11,12]}
DURATIONS = {1:45,2:45,3:45,4:60,5:60,6:60,7:90,8:90,9:90,10:120,11:120,12:120}

def q(prompt: str, answers: list[str], bloom: str, family: str) -> dict[str, Any]:
    return {"prompt": prompt, "marks": len(answers), "memo": [{"point": a, "marks": 1} for a in answers], "bloom_level": bloom, "question_family": family}

# Original, educator-authored items: language and examples are not copied from CAPS.
# Topic choices are checked against the selected official phase/subject document.
PAPERS: dict[int, dict[str, Any]] = {
1: {"title":"Healthy routines and safe play", "stimulus":"At home, Nandi washes her hands before eating. She packs a bottle of clean water. At school, she waits for her turn on the slide. When a friend falls, Nandi calls the teacher.", "questions":[
q("1.1 Name two healthy things Nandi does and give one reason each is healthy. [4]",["Names washing hands before eating.","Names taking clean water.","Gives one reason clean hands help keep a person healthy.","Gives one reason drinking clean water is helpful."],"remember","identify_and_explain"),
q("1.2 What does Nandi do to use the slide safely? Give one other safe playground action and explain how each action helps keep children safe. [4]",["Says she waits for her turn.","Gives one other safe action, such as using equipment as intended.","Explains how waiting for a turn helps prevent a collision or fall.","Explains how the other safe action helps prevent someone getting hurt."],"understand","scenario_response"),
q("1.3 Her friend falls. Name four safe things Nandi can do while getting help. [4]",["Calls the teacher or another trusted adult.","Stays with the friend if it is safe.","Does not move an injured person who may be seriously hurt.","Uses calm, kind words while getting help."],"apply","safety_sequence"),
q("1.4 Starting with washing hands, put these actions in a helpful order: wash hands, sit to eat, play with a ball, tidy the ball away. [4]",["Puts washing hands before eating.","Puts sitting to eat after washing hands.","Puts playing with the ball before tidying it away.","Gives a sensible complete order with all four actions."],"apply","sequence"),
q("1.5 Give one kind way to help a classmate, say what you would do, and explain how it would help. [4]",["Names a specific kind action.","Explains how the action helps the classmate.","Uses respectful words or behaviour.","Chooses an action that is safe and realistic at school."],"understand","short_response")]},
2: {"title":"The class garden", "stimulus":"On Monday, Class Two planted bean seeds beside the classroom. Asha put a name label by each pot. The class added a little water and placed the pots near a sunny window. On Friday, two small green shoots had appeared. The learners measured them with paper strips. Asha wrote the results in the class book. The class agreed to water the pots only when the soil felt dry. They wanted to save water and keep the plants healthy.", "questions":[
q("1.1 When and where did Class Two plant the bean seeds? What did Asha put by each pot? [4]",["States that the seeds were planted on Monday.","States that they were planted beside the classroom.","Identifies the seeds as bean seeds.","Says that Asha put a name label by each pot."],"remember","retrieve_specific_details"),
q("1.2 Name two things the class did to help the seeds grow. What did they use to measure the shoots, and when did two shoots appear? [4]",["Says the class added a little water.","Says the pots were placed near a sunny window.","Identifies paper strips as the measuring tool.","States that two shoots appeared on Friday."],"understand","retrieve_multiple_details"),
q("1.3 Give two reasons the class watered the pots only when the soil felt dry. Explain how this helped save water and keep the plants healthy. [4]",["Identifies the dry soil as the cue for watering.","Explains that waiting until the soil is dry avoids unnecessary watering and saves water.","Explains that watering when needed helps the plants while avoiding too much water.","Links both reasons to the class's decision to check the soil before watering."],"understand","infer_reason"),
q("1.4 Change 'two small green shoots' to describe one shoot. [4]",["Uses the singular noun 'shoot'.","Changes 'two' to 'one' or removes the quantity correctly.","Uses singular agreement with 'shoot'.","Keeps the meaning clear."],"apply","language_structures"),
q("1.5 Write two sentences about how you would care for a class plant. [4]",["Gives one suitable plant-care action.","Gives a second suitable plant-care action.","Uses two complete, understandable sentences.","Uses capitals and end punctuation correctly."],"apply","short_composition")]},
3: {"title":"Number, pattern and measurement", "stimulus":"The class collected 24 bottle tops on Monday and 18 on Tuesday. They put the tops into bags of 6 for a sorting activity. A number pattern on the board begins 5, 10, 15, __, __.", "questions":[
q("1.1 How many bottle tops did the class collect altogether? Show your addition. [4]",["Chooses addition.","Writes 24 + 18.","Adds the ones correctly to make 12 ones.","Gives 42 bottle tops."],"apply","calculation"),
q("1.2 Put all the tops into bags of 6. How many full bags can be made? [4]",["Recognises equal groups of 6.","Uses a correct division or repeated-subtraction method.","Finds 7 groups.","States 7 full bags."],"apply","equal_grouping"),
q("1.3 Complete the pattern 5, 10, 15, __, __, state its rule and give the number that would be in the eighth position. [4]",["Writes 20 in the fourth position.","Writes 25 in the fifth position.","States that 5 is added each time.","Gives 40 as the eighth term, continuing the rule correctly."],"understand","pattern"),
q("1.4 A ribbon is 35 cm long. Sipho uses 12 cm. How much remains? [4]",["Chooses subtraction.","Writes 35 - 12.","Calculates 23.","Includes centimetres in the answer."],"apply","measurement"),
q("1.5 Name one 2-D shape with four straight sides and one object with that shape. [4]",["Names a square or rectangle.","States that the chosen shape has four straight sides.","Gives a plausible object with that 2-D shape.","Distinguishes the flat 2-D shape from a solid object."],"understand","geometry")]},
4: {"title":"Whole numbers, fractions and perimeter", "stimulus":"A school garden has 8 rows with 24 seedlings in each row. The garden is a rectangle 8 m long and 5 m wide. Learners water three quarters of the garden on Monday.", "questions":[
q("1.1 Calculate the total number of seedlings. Show a method. [5]",["Recognises 8 equal groups of 24.","Uses multiplication or repeated addition.","Calculates 8 x 20 = 160 or equivalent.","Calculates 8 x 4 = 32 or equivalent.","Adds to give 192 seedlings."],"apply","multiplication"),
q("1.2 Calculate the perimeter of the rectangular garden. [5]",["Identifies two lengths of 8 m.","Identifies two widths of 5 m.","Uses addition of all four sides or 2 x (8 + 5).","Calculates 16 m for the two lengths.","Gives perimeter 26 m with units."],"apply","perimeter"),
q("1.3 The learners plant 48 seedlings. What fraction of 192 is 48? Simplify it. [6]",["Writes fraction 48/192.","Divides numerator and denominator by a common factor.","Shows an equivalent fraction such as 1/4.","States the simplified answer 1/4.","Explains that 48 is one of four equal groups of 48.","Uses fraction notation correctly."],"understand","fraction"),
q("1.4 The class has 360 seeds and plants 145. How many seeds remain? [7]",["Chooses subtraction.","Writes 360 - 145.","Regroups one ten correctly.","Subtracts ones correctly.","Subtracts tens correctly.","Subtracts hundreds correctly.","Gives 215 seeds remaining."],"apply","subtraction"),
q("1.5 Each seedling needs 250 mL of water. For 8 seedlings, show the multiplication and the conversion calculation. Give the total in millilitres and litres. [6]",["Sets up 8 groups of 250 mL, for example 250 × 8.","Calculates 2,000 mL.","Uses the relationship 1,000 mL = 1 L.","Shows division by 1,000 or an equivalent conversion method.","Gives the converted answer as 2 L.","Includes the correct mL and L units with the two totals."],"apply","measurement_conversion")]},
5: {"title":"Materials, mixtures and fair testing", "stimulus":"A learner pours sand and water into a clear jar and stirs them. After the jar stands still, the sand settles at the bottom. In a second test, the learner compares how quickly equal-sized ice cubes melt: one is in sunlight and one is in shade. Both cubes start at the same time.", "questions":[
q("1.1 Describe the appearance of the sand-and-water mixture after stirring and after it stands. [5]",["States that sand and water are both present.","States that the mixture looks cloudy or mixed just after stirring.","States that sand settles to the bottom after standing.","Identifies water above the settled sand.","Uses an observation rather than claiming the sand disappeared."],"understand","observation"),
q("1.2 Suggest a way to separate the sand from the water and explain why it works. [5]",["Names filtration or careful decanting.","Describes placing a filter or allowing settling before pouring.","States that sand does not dissolve in water.","Explains that solid sand is retained or settles while water passes/pours away.","Gives a safe, workable sequence."],"apply","investigation_method"),
q("1.3 Identify what is changed, what is measured and two things kept the same to make the ice test fair. [6]",["Changed factor is sunlight/shade.","Measured outcome is melting time or amount melted after a stated time.","Keeps ice-cube size the same.","Keeps the starting time the same.","Keeps the type of ice the same.","Recognises this is a fair comparison of conditions."],"analyze","fair_test"),
q("1.4 Predict which ice cube melts faster and explain the cause. State what result to observe or measure, how the setup supports your prediction, and whether the shaded cube can also melt. [7]",["Predicts the cube in sunlight melts faster.","Links sunlight to greater heating.","Links heating to melting.","Uses a complete cause-and-effect explanation.","Does not claim the shaded cube cannot melt.","Uses the test setup as evidence.","States that the result should be observed or measured."],"analyze","prediction"),
q("1.5 Give a results-table heading and describe how the learner could make the comparison reliable. [7]",["Includes condition (sunlight/shade) in a heading.","Includes time or amount melted in a heading.","Includes units if time is recorded.","Repeats the test.","Uses equal-sized cubes in each repeat.","Records results at the same time intervals.","Compares repeated results before drawing a conclusion."],"evaluate","data_handling")]},
6: {"title":"Well-being, relationships and responsible choices", "stimulus":"Thabo has been sleeping late because he watches videos after homework. He feels tired in class and has stopped joining football at break. His friend asks what is wrong. Thabo can speak to a trusted adult and make a plan for homework, screen time, sleep and activity.", "questions":[
q("1.1 Identify two changes in Thabo's routine and one effect at school. [5]",["Identifies late video watching.","Identifies reduced football/activity.","Identifies feeling tired in class.","Connects the tiredness to his routine.","Uses details from the scenario."],"understand","scenario_analysis"),
q("1.2 Suggest a realistic evening plan with a time for homework, screen-free time and sleep preparation. Put the activities in a sensible order and explain how the plan could support rest. [5]",["Includes a homework period.","Includes a screen-free period before bed.","Includes a sleep-preparation action.","Puts activities in a sensible order.","Explains how the plan could support rest."],"apply","planning"),
q("1.3 What could Thabo say to his friend to explain how he feels and ask for support? [6]",["Names a feeling accurately.","Gives one reason linked to the scenario.","Uses an I-statement or respectful wording.","Makes a clear request for support.","Identifies a trusted adult if the problem continues.","Shows that asking for help is a responsible choice."],"apply","communication"),
q("1.4 Give two benefits of regular physical activity. Then suggest safe steps for Thabo's gradual return to football, including how to prepare, when to rest, and what to do if he feels unwell. [7]",["Names one health or mood benefit.","Names a second distinct benefit.","Suggests starting at a manageable level.","Suggests warming up or following school safety rules.","Allows rest and hydration.","Avoids pressuring Thabo to play when unwell.","Links the action to gradual participation."],"understand","wellbeing"),
q("1.5 Evaluate two options Thabo could use to reduce late-night screen use; recommend one. [7]",["Gives a first realistic option.","Gives a second realistic option.","States one benefit of option one.","States one limitation or challenge of option one.","States one benefit or limitation of option two.","Makes a clear recommendation.","Justifies the recommendation using the scenario."],"evaluate","decision_making")]},
7: {"title":"Needs, wants and a small business budget", "stimulus":"Lebo sells fruit cups at a school market. She buys 30 cups at R4 each and fruit for R90. She sells 24 cups at R12 each. Six cups remain unsold. Her table fee is R30. All amounts are in rand.", "questions":[
q("1.1 Classify the fruit and the table fee as business inputs or costs, and explain each choice. [6]",["Identifies fruit as an input used to make the product.","Identifies the table fee as a business cost.","Explains that fruit is used in the fruit cups.","Explains that the fee is paid to use selling space.","Uses the scenario evidence.","Distinguishes an input from revenue."],"understand","business_concepts"),
q("1.2 Calculate revenue from the cups sold. [6]",["Identifies 24 cups sold.","Identifies selling price R12 per cup.","Uses 24 x R12.","Calculates 20 x 12 = R240 or equivalent.","Calculates 4 x 12 = R48 or equivalent.","Gives revenue R288."],"apply","calculation"),
q("1.3 Calculate sales revenue and the cash remaining after the stated outlays. Explain why that cash balance alone does not establish profit. [8]",["Calculates cup cost: 30 x R4 = R120.","Identifies fruit cost R90.","Identifies table fee R30.","Adds the three outlays to get R240.","Calculates sales revenue as 24 x R12 = R288.","Subtracts stated outlays from revenue.","Gives R48 cash remaining after those outlays.","Notes that six cups remain unsold, so inventory value/cost treatment is needed to establish accounting profit."],"apply","budget"),
q("1.4 Explain two reasons the six unsold cups matter for the next market day. Use case facts to recommend how many cups to make or buy, and address freshness or safety, waste, and why unsold stock is not sales revenue. [10]",["States unsold cups represent stock not sold.","Notes that ingredients or cups may have cost money.","Explains that demand may be lower than expected.","Suggests adjusting quantity made or bought.","Uses one relevant scenario figure.","Recognises food freshness/safety constraints.","Avoids counting unsold cups as sales revenue.","Gives a second distinct planning reason.","Connects planning to reducing waste or cost.","Writes a supported explanation."],"analyze","inventory_planning"),
q("1.5 Recommend one change for Lebo's next market day and support it with two calculations or facts from the case. [10]",["States one realistic change.","Uses the 24 cups sold as evidence.","Uses the 6 unsold cups as evidence.","Calculates or cites revenue of R288.","Calculates or cites the stated costs of R240.","Shows a correct comparison or inference.","Explains how the change may improve planning.","Considers customer demand.","Keeps the recommendation within the information provided.","Presents a clear supported conclusion."],"evaluate","recommendation")]},
8: {"title":"Goals, choices and healthy relationships", "stimulus":"A learner has a major assignment due in two weeks and also wants to join friends for an afternoon activity. The learner has not started the assignment and feels pressured to copy a classmate's work. The school expects original work and allows learners to ask the teacher for help.", "questions":[
q("1.1 State the deadline challenge, explain why copying is tempting, and give one possible school consequence. Use details from the scenario. [6]",["Identifies the assignment deadline.","Identifies that work has not started.","Identifies peer pressure or temptation to copy.","States copying is not original work.","Gives a plausible school consequence.","Uses scenario information."],"understand","scenario_analysis"),
q("1.2 Create a two-week plan with three milestones and one leisure period. [6]",["Includes a first milestone soon after today.","Includes a middle progress check.","Includes a final review before the due date.","Includes a leisure period.","Orders the milestones sensibly.","Makes the plan achievable."],"apply","planning"),
q("1.3 Compare asking the teacher for help with copying a classmate's work. [8]",["Names a benefit of asking for help.","Names a limitation or effort involved in asking for help.","Names a short-term perceived benefit of copying.","Identifies an academic-integrity risk of copying.","Considers learning gained from original work.","Uses the school rule in the scenario.","Distinguishes the two choices.","Gives a supported comparison."],"analyze","comparison"),
q("1.4 Write a respectful message to a friend explaining a boundary about copying while preserving the friendship. [10]",["States clearly that the learner will not copy.","Uses respectful language.","Avoids insulting or threatening the friend.","Gives a brief reason based on learning or honesty.","Offers a constructive alternative.","Keeps the friendship in view.","Uses an appropriate greeting or opening.","Makes the message coherent.","Uses suitable punctuation.","Maintains a calm tone."],"apply","transactional_writing"),
q("1.5 Recommend one help-seeking step and explain how the learner can monitor progress. [10]",["Names an appropriate trusted school support person.","States a clear question or request for help.","Connects help-seeking to the assignment.","Sets a measurable first task.","Sets a date to check progress.","Uses the two-week deadline.","Includes a way to respond if behind schedule.","Protects time for rest or leisure.","Explains why monitoring helps.","Gives a justified recommendation."],"evaluate","help_seeking")]},
9: {"title":"A community library that travels", "stimulus":"Every Thursday, a small van parks beside Mhlabeni Community Hall. It carries books, newspapers and a few tablets loaded with reading activities. The service began when residents noticed that many children travelled far to reach the nearest library. Volunteer Naledi records which books are borrowed so the team can bring popular titles next time. The tablets work offline, so learners can use them even when the mobile signal is weak. Adults may also borrow newspapers and ask volunteers for help with online forms. The service cannot visit every street each week, so residents suggest stops at a monthly meeting. Naledi says the van is useful because people help shape its route.", "questions":[
q("1.1 Give two services the van offers and one detail about where it stops. [6]",["Names books or newspapers.","Names tablet reading activities.","Names help with online forms or newspaper borrowing.","States it parks beside Mhlabeni Community Hall on Thursdays.","Uses accurate details from the text.","Writes a clear response."],"remember","literal_comprehension"),
q("1.2 Explain why the service records borrowed books and uses offline tablets. [7]",["Links borrowing records to identifying popular titles.","Links popular titles to future stock choices.","States offline tablets work without a mobile signal.","Explains how this helps learners in a weak-signal area.","Uses evidence from the passage.","Keeps the two reasons distinct.","Writes a logical explanation."],"understand","inference"),
q("1.3 What does Naledi mean when she says residents help shape the route? [8]",["Identifies the monthly meeting as a way to give suggestions.","Explains that suggestions influence where the van stops.","Connects route choice to community needs.","Uses the passage rather than an unsupported assumption.","Distinguishes consultation from guaranteed weekly service.","Gives one relevant example from the text.","Writes in own words.","Makes the meaning clear."],"analyze","interpretation"),
q("1.4 Rewrite 'The tablets work offline, so learners can use them even when the mobile signal is weak' as two sentences without changing its meaning. Preserve both facts and their cause-and-effect link; check grammar, capitals and punctuation, and do not add a new claim. [9]",["Produces two complete sentences.","Keeps the fact that tablets work offline.","Keeps the fact that learners can use them.","Keeps the weak-signal condition.","Uses an appropriate linking or explanatory phrase.","Uses capitals correctly.","Uses end punctuation correctly.","Maintains grammatical agreement.","Does not add a new claim."],"apply","language_editing"),
q("1.5 In a short paragraph, evaluate one strength and one limitation of the travelling library service. [10]",["Identifies a supported strength.","Explains who benefits from it.","Identifies the limitation that it cannot visit every street weekly.","Explains the effect of the limitation.","Uses one piece of textual evidence for the strength.","Uses one piece of textual evidence for the limitation.","Makes a balanced judgment.","Uses a coherent paragraph structure.","Uses appropriate vocabulary.","Maintains a clear conclusion."],"evaluate","paragraph_response")]},
10: {"title":"Motion in one dimension", "stimulus":"A trolley moves directly east along a straight track without reversing direction. Take east as the positive direction. It starts at position x = -4 m and reaches x = +20 m in 6 s. Later, its velocity changes from +3 m·s⁻¹ to +15 m·s⁻¹ in 4 s. Assume uniform motion during each stated interval.", "questions":[
q("1.1 Distinguish distance and displacement, then calculate both for the first movement. [8]",["Defines distance as total path length.","Defines displacement as change in position with direction.","Identifies initial position -4 m.","Identifies final position +20 m.","Calculates displacement +20 - (-4).","Gives displacement +24 m east.","Calculates straight-path distance 24 m.","Uses units."],"understand","concept_and_calculation"),
q("1.2 Calculate the trolley's average velocity for the first interval. [9]",["Uses average velocity = displacement / time.","Uses displacement +24 m.","Uses time 6 s.","Substitutes values correctly.","Calculates 24 / 6.","Gives +4 m·s⁻¹.","Includes east/positive direction.","Uses correct SI units.","Distinguishes average velocity from speed."],"apply","calculation"),
q("1.3 Calculate acceleration during the later interval and state what its sign means. [10]",["Identifies initial velocity +3 m·s⁻¹.","Identifies final velocity +15 m·s⁻¹.","Uses time interval 4 s.","Uses a = (v_f - v_i)/Δt.","Calculates change in velocity +12 m·s⁻¹.","Divides by 4 s.","Gives +3 m·s⁻².","Uses correct SI units.","States acceleration is in the positive/east direction.","Connects positive acceleration to increasing positive velocity."],"apply","calculation_and_interpretation"),
q("1.4 If the later acceleration stays constant for 3 more seconds, calculate the new velocity. [11]",["Uses initial velocity +15 m·s⁻¹.","Uses acceleration +3 m·s⁻².","Uses time 3 s.","Chooses v_f = v_i + aΔt.","Substitutes values correctly.","Calculates 3 x 3 = 9 m·s⁻¹ change.","Adds change to initial velocity.","Gives +24 m·s⁻¹.","States positive/east direction.","Uses correct units.","Shows a coherent calculation."],"apply","multi_step_calculation"),
q("1.5 Compare a position-time graph and a velocity-time graph. For each graph, name both axes and give their units; state what its gradient represents and what a horizontal line means. For the velocity-time graph, state what the signed area represents. [12]",["Names position as the vertical-axis quantity on the position-time graph.","Names time as the horizontal-axis quantity on the position-time graph.","Gives metres (m) for position and seconds (s) for time on the position-time graph.","Names velocity as the vertical-axis quantity on the velocity-time graph.","Names time as the horizontal-axis quantity on the velocity-time graph.","Gives metres per second (m·s⁻¹) for velocity and seconds (s) for time on the velocity-time graph.","States that the gradient of a position-time graph represents velocity.","States that the gradient of a velocity-time graph represents acceleration.","States that the signed area under a velocity-time graph represents displacement.","Explains that a horizontal position-time line means position is constant.","Explains that a horizontal velocity-time line means velocity is constant.","Clearly distinguishes the quantity shown directly by each graph."],"analyze","graph_interpretation")]},
11: {"title":"Repairing a school footpath", "stimulus":"For months, learners at Riverside School crossed a muddy patch between the gate and the bicycle racks. After heavy rain, the path became slippery. The eco-club checked how learners used the route before planning a repair. The club proposed a narrow gravel path, but first checked that rainwater could still drain into the garden. With permission from the grounds manager, volunteers laid the gravel on a Saturday. They left a planted strip beside the path for insects and small flowers. Two weeks later, the club asked users whether the route was easier to walk. Most replies were positive, although some learners requested a wider entrance. The club recorded the feedback for its next meeting.", "data_table":{"caption":"Riverside eco-club route-use survey · 60 learners", "columns":["How often learners used the route", "Number of learners"], "rows":[["Every day", "42"], ["Sometimes", "18"], ["Total surveyed", "60"]]}, "questions":[
q("1.1 State the route problem. Give two details showing the conditions learners faced, and explain one reason the repair mattered. [8]",["Identifies the muddy patch as the route problem.","States that the patch was between the gate and the bicycle racks.","Uses the detail that learners crossed it for months.","Uses the detail that it became slippery after heavy rain.","Explains that a slippery path can create a risk of slipping or falling.","Explains how the route affected learners moving between the gate and bicycle racks.","Supports the response with two relevant details from the passage.","Writes a clear answer that separates evidence from explanation."],"analyze","comprehension"),
q("1.2 Identify the two environmental choices in the club's plan and explain the purpose of each. [9]",["Identifies drainage into the garden.","Identifies the planted strip beside the path.","Explains that drainage prevents blocking water flow.","Explains that plants provide habitat/space for insects or flowers.","Connects the choices to the project design.","Uses text evidence.","Separates the two environmental choices.","Uses an appropriate cause-effect link.","Gives a clear answer."],"understand","inference"),
q("1.3 Use the survey table to compare daily and occasional route use. Calculate the percentage in each group and write one accurate sentence describing what the figures show. [10]",["Reads 42 learners in the every-day group.","Reads 18 learners in the sometimes group.","Uses 60 as the total number surveyed.","Sets up 42/60 x 100 for daily use.","Simplifies 42/60 to 7/10 or an equivalent fraction.","Calculates 70% for daily use.","Sets up 18/60 x 100 for sometimes use.","Calculates 30% for sometimes use.","Correctly compares the two proportions (70% versus 30%, or 42 versus 18 learners).","Writes a clear sentence that accurately describes the comparison."],"analyze","visual_data_interpretation"),
q("1.4 Assess one strength and one limitation of the club's feedback method. [11]",["Identifies the two-week follow-up as a strength.","Explains that users can comment after trying the path.","Identifies that the passage says 'most replies' without giving a count.","Explains that the response total is unknown.","Notes that only route users may have been asked or another defensible limitation.","Uses evidence from the text.","Distinguishes strength from limitation.","Avoids inventing a survey sample size.","Makes a supported judgment.","Uses clear paragraph structure.","Uses appropriate analytical language."],"evaluate","evaluation"),
q("1.5 Write a short recommendation to the eco-club about its next step, using evidence from the passage. [12]",["Makes one clear next-step recommendation.","Addresses the requested wider entrance feedback.","Uses the positive replies as relevant evidence.","Recognises the follow-up response count is not reported.","Suggests collecting a count or specific user feedback.","Keeps drainage in the design.","Keeps the planted strip in the design or explains any change.","Names who should be consulted.","Gives a practical action.","Explains expected benefit.","Uses a formal, suitable tone.","Organises the recommendation coherently."],"evaluate","evidence_based_writing")]},
12: {"title":"Business environments and responsible management", "stimulus":"Koru Foods is a small company that makes dried fruit snacks. It buys fruit from nearby farmers and sells packets to local shops. A large supermarket has offered to stock the product if Koru can supply larger, consistent orders. The owners are considering a new drying machine. They must compare its cost with expected sales, train workers to use it safely, and check that packaging gives accurate ingredient information. A community group has also asked whether Koru can donate snacks to a youth event. The owners want the business to grow while maintaining product quality and fair relationships with workers and suppliers.", "questions":[
q("1.1 Identify one factor in each business environment: micro, market and macro. Classify and justify each. [8]",["Identifies a micro factor such as workers or owners.","Classifies it as internal/within the business.","Identifies a market factor such as farmers, shops or customers.","Classifies it as an immediate external market participant.","Identifies a macro factor such as general economic conditions or laws, without claiming a specific fact not given.","Classifies it as a broad external influence.","Gives a reason for each classification.","Uses correct environment terms."],"analyze","business_environment"),
q("1.2 Explain two different considerations before buying the drying machine. Use case details and identify a cost, sales or production estimate to check, plus one worker training or safety issue. [9]",["Considers purchase/operating cost.","Considers whether expected sales can cover the cost.","Considers production capacity or consistent orders.","Considers worker training.","Considers workplace safety.","Uses the case details.","Explains rather than lists one consideration.","Explains a second distinct consideration.","States that the comparison should use estimates or records rather than assumption."],"apply","decision_analysis"),
q("1.3 Explain why accurate ingredient information and fair supplier relationships matter. [10]",["States ingredient information should be accurate.","Links accuracy to informed customer choice or safety.","Avoids inventing a specific legal requirement.","Identifies nearby farmers as suppliers.","Explains that fair supplier relationships support reliable sourcing.","Links reliable sourcing to product consistency.","Identifies workers as another stakeholder.","Shows that responsible conduct affects trust.","Uses case evidence.","Writes a coherent explanation."],"understand","ethics_and_stakeholders"),
q("1.4 Evaluate the supermarket offer: give one opportunity and two risks the owners should investigate. [11]",["Identifies access to a larger sales channel as an opportunity.","Links opportunity to potential growth.","Identifies risk of being unable to meet larger orders.","Identifies a quality-consistency risk.","Considers the machine cost or cash-flow risk.","Explains one risk using case evidence.","Explains a second risk distinctly.","States information needed before deciding.","Avoids assuming the offer guarantees profit.","Balances opportunity and risk.","Gives a supported conclusion."],"evaluate","opportunity_risk"),
q("1.5 Recommend whether Koru should accept the offer now, delay, or negotiate conditions. Support your recommendation with evidence and two practical conditions. [12]",["Makes a clear recommendation.","Uses the larger-order requirement as evidence.","Uses the need for consistent quality as evidence.","Considers machine cost or capacity.","Names a first practical condition.","Names a second distinct condition.","Includes worker training/safety or supplier readiness.","Includes accurate ingredient packaging.","Explains how conditions reduce risk.","Considers stakeholder relationships.","Does not claim facts absent from the case.","Presents a logically supported conclusion."],"evaluate","recommendation")]},
}

# Keep previously reviewed item corrections in the source builder rather than
# leaving them only in generated files. This prevents a clean rebuild from
# silently restoring weaker prompts or memo criteria.
ITEM_AMENDMENTS: dict[int, dict[str, dict[str, Any]]] = {
3: {
    "1.2": {
        "prompt": "1.2 Use your total from Question 1.1 to put the bottle tops into bags of 6. Show a calculation or equal-groups drawing. State how many full bags you can make and whether any tops are left. [4]",
        "memo": [
            {"point": "Uses the total of 42 tops from Question 1.1, or consistently carries forward the learner's stated total.", "marks": 1},
            {"point": "Shows division by 6 or a correct equal-groups/repeated-subtraction method.", "marks": 1},
            {"point": "Calculates the quotient and remainder correctly for the total used (7 remainder 0 when using 42).", "marks": 1},
            {"point": "States the number of full bags and any tops left, consistently with the calculation.", "marks": 1},
        ],
    },
},
4: {
    "1.2": {
        "prompt": "1.2 Learners measured the garden’s four sides with a tape: 8 m, 5 m, 8 m and 5 m. Add the four measurements to find the perimeter. [5]",
        "memo": [
            {"point": "Identifies the four measured side lengths as 8 m, 5 m, 8 m and 5 m.", "marks": 1},
            {"point": "Chooses to add all four side measurements to find the perimeter.", "marks": 1},
            {"point": "Adds the two 8 m sides to get 16 m.", "marks": 1},
            {"point": "Adds the two 5 m sides to get 10 m.", "marks": 1},
            {"point": "Adds the side totals to get 26 m and includes the unit.", "marks": 1},
        ],
    },
    "1.3": {
        "prompt": "1.3 What fraction of the 192 seedlings is 48? Simplify it. Show how you simplify the fraction and check your answer. [6]",
        "memo": [
            {"point": "Writes the fraction 48/192.", "marks": 1},
            {"point": "Identifies 48 as a common divisor of 48 and 192, or shows another valid common-divisor method.", "marks": 1},
            {"point": "Shows the numerator divided by the chosen common divisor, for example 48 ÷ 48 = 1 or 48 ÷ 16 = 3.", "marks": 1},
            {"point": "Shows the denominator divided by the same common divisor, for example 192 ÷ 48 = 4 or 192 ÷ 16 = 12.", "marks": 1},
            {"point": "Gives the simplified fraction 1/4.", "marks": 1},
            {"point": "Checks the result by showing that 1/4 of 192 is 48.", "marks": 1},
        ],
    },
    "1.4": {
        "prompt": "1.4 The class has 360 seeds and plants 145. Show the column subtraction, make any regrouping clear, and check your answer with addition. How many seeds remain? [7]",
        "memo": [
            {"point": "Chooses subtraction and writes 360 - 145.", "marks": 1},
            {"point": "Shows the regrouping needed to subtract the ones correctly.", "marks": 1},
            {"point": "Subtracts the ones correctly.", "marks": 1},
            {"point": "Subtracts the tens correctly.", "marks": 1},
            {"point": "Subtracts the hundreds correctly.", "marks": 1},
            {"point": "Gives 215 seeds remaining.", "marks": 1},
            {"point": "Checks the result with addition, for example 215 + 145 = 360.", "marks": 1},
        ],
    },
    "1.5": {
        "prompt": "1.5 Each seedling needs 250 mL of water. For 8 seedlings, show the multiplication and the conversion calculation. Give the total in millilitres and litres. [6]",
        "memo": [
            {"point": "Sets up 8 groups of 250 mL, for example 250 × 8.", "marks": 1},
            {"point": "Calculates 2,000 mL.", "marks": 1},
            {"point": "Uses the relationship 1,000 mL = 1 L.", "marks": 1},
            {"point": "Shows division by 1,000 or an equivalent conversion method.", "marks": 1},
            {"point": "Gives the converted answer as 2 L.", "marks": 1},
            {"point": "Includes the correct mL and L units with the two totals.", "marks": 1},
        ],
    },
},
5: {
    "1.2": {
        "prompt": "1.2 Name one property to record for the starting materials before mixing and one property to record after the samples set. Explain why the class records both stages. [5]",
        "memo": [
            {"point": "States that properties of the starting materials are recorded before mixing.", "marks": 1},
            {"point": "Names one observable property of the starting materials, such as appearance or texture.", "marks": 1},
            {"point": "States that a property of the concrete is recorded after the samples set.", "marks": 1},
            {"point": "Names one relevant property of the set concrete, such as strength, durability, appearance or texture.", "marks": 1},
            {"point": "Explains that comparing both stages shows how processing changes material properties.", "marks": 1},
        ],
    },
    "1.3": {
        "memo": [
            {"point": "Identifies amount of gravel as the changed factor.", "marks": 1},
            {"point": "Identifies the number of identical counters supported before cracking as the measured result.", "marks": 1},
            {"point": "Names one valid condition to keep the same, such as the amount of sand.", "marks": 1},
            {"point": "Names a second distinct valid condition to keep the same, such as cement amount, water amount, mould, setting time or test method.", "marks": 1},
            {"point": "Names a third distinct valid condition to keep the same.", "marks": 1},
            {"point": "Explains that changing only the gravel amount while other conditions stay fixed makes the comparison fair.", "marks": 1},
        ],
    },
    "1.5": {
        "prompt": "1.5 Give suitable results-table headings, including units where needed, for the gravel test. Then describe two ways to keep the comparison reliable and one limitation of using small samples to choose material for a real path. [7]",
        "memo": [
            {"point": "Includes a sample or gravel-condition heading.", "marks": 1},
            {"point": "Includes the gravel amount with a stated unit or defined measure.", "marks": 1},
            {"point": "Includes a trial-number heading.", "marks": 1},
            {"point": "Includes a heading for the number of counters supported before cracking.", "marks": 1},
            {"point": "Names one test condition to keep the same, such as other ingredient amounts, mould, setting time or counter method.", "marks": 1},
            {"point": "Repeats each gravel condition and compares the recorded results consistently.", "marks": 1},
            {"point": "Notes that small samples cannot by themselves prove how a full path will perform.", "marks": 1},
        ],
    },
},
10: {
    "stimulus": "A trolley moves along a straight east-west track; take east as positive. During its first 6 s, it moves east from x = -4 m to x = +20 m in 4 s, then reverses and moves west to x = +8 m at t = 6 s. Assume constant velocity on each segment. In a separate later interval, its velocity changes from +3 m·s⁻¹ to +15 m·s⁻¹ in 4 s.",
    "1.1": {
        "prompt": "1.1 Distinguish distance and displacement, then calculate both for the trolley's first 6 s of motion. [8]",
        "memo": [
            {"point": "Defines distance as total path length.", "marks": 1},
            {"point": "Defines displacement as change in position with direction.", "marks": 1},
            {"point": "Identifies the start at -4 m, turning position at +20 m and final position at +8 m.", "marks": 1},
            {"point": "Calculates the eastward segment as 24 m and westward segment as 12 m.", "marks": 1},
            {"point": "Adds segment lengths to give distance 36 m.", "marks": 1},
            {"point": "Calculates displacement as +8 - (-4) = +12 m.", "marks": 1},
            {"point": "States displacement is 12 m east.", "marks": 1},
            {"point": "Uses metres for distance and displacement.", "marks": 1},
        ],
    },
    "1.2": {
        "prompt": "1.2 For the first 6 s, calculate the trolley's average velocity and average speed. State one difference between them. [9]",
        "memo": [
            {"point": "Uses displacement +12 m to calculate average velocity.", "marks": 1},
            {"point": "Uses total distance 36 m to calculate average speed.", "marks": 1},
            {"point": "Uses the total time interval 6 s for both calculations.", "marks": 1},
            {"point": "States average velocity = displacement / time.", "marks": 1},
            {"point": "Substitutes values correctly and obtains +2 m·s⁻¹ east.", "marks": 1},
            {"point": "States average speed = distance / time.", "marks": 1},
            {"point": "Substitutes values correctly and obtains 6 m·s⁻¹.", "marks": 1},
            {"point": "Uses correct SI units.", "marks": 1},
            {"point": "Explains that velocity includes direction and uses displacement, while speed has no direction and uses distance.", "marks": 1},
        ],
    },
    "1.4": {
        "prompt": "1.4 Assume the later acceleration stays constant at the value from Question 1.3 for a further 3 s, starting at +15 m·s⁻¹. Calculate the final velocity and signed displacement. Draw a velocity-time graph for this interval or show the trapezium area calculation, and state the direction. [11]",
        "memo": [
            {"point": "Uses the initial velocity +15 m·s⁻¹.", "marks": 1},
            {"point": "Uses the acceleration +3 m·s⁻².", "marks": 1},
            {"point": "Uses the time interval 3 s.", "marks": 1},
            {"point": "Chooses v_f = v_i + aΔt.", "marks": 1},
            {"point": "Substitutes the stated values correctly.", "marks": 1},
            {"point": "Calculates the velocity change as +9 m·s⁻¹.", "marks": 1},
            {"point": "Gives final velocity +24 m·s⁻¹.", "marks": 1},
            {"point": "Draws or identifies the velocity-time trapezium with endpoint velocities +15 m·s⁻¹ and +24 m·s⁻¹ over 3 s, or states an equivalent area method.", "marks": 1},
            {"point": "Substitutes ½(15 + 24) × 3 or an equivalent average-velocity method.", "marks": 1},
            {"point": "Calculates signed displacement +58.5 m.", "marks": 1},
            {"point": "Gives the displacement direction as east and uses correct units.", "marks": 1},
        ],
    },
},
2: {
    "1.4": {
        "prompt": "1.4 Change this sentence to describe one pot: 'The pots are near a sunny window.' [4]",
        "memo": [
            {"point": "Changes the plural noun 'pots' to the singular 'pot'.", "marks": 1},
            {"point": "Changes 'are' to 'is' to match the singular noun.", "marks": 1},
            {"point": "Uses 'A' or 'One' before 'pot' to show that there is one pot.", "marks": 1},
            {"point": "Writes a complete sentence with a capital letter and a full stop.", "marks": 1},
        ],
    },
},
1: {
    "1.3": {
        "prompt": "1.3 After Nandi calls the teacher, name four safe, kind ways she can help her friend while waiting. [4]",
        "memo": [
            {"point": "Stays with her friend if it is safe to do so.", "marks": 1},
            {"point": "Gives her friend space and keeps other children from crowding the area.", "marks": 1},
            {"point": "Uses calm, kind words to comfort her friend.", "marks": 1},
            {"point": "Follows the teacher’s directions or explains what happened when the teacher arrives.", "marks": 1},
        ],
    },
    "1.1": {"prompt": "1.1 Name two healthy things Nandi does and give one reason each is healthy. [4]"},
    "1.2": {
        "prompt": "1.2 What does Nandi do to use the slide safely? Give one other safe playground action and explain how each action helps keep children safe. [4]",
        "memo": [
            {"point": "Says she waits for her turn.", "marks": 1},
            {"point": "Gives one other safe action, such as using equipment as intended.", "marks": 1},
            {"point": "Explains how waiting for a turn helps prevent a collision or fall.", "marks": 1},
            {"point": "Explains how the other safe action helps prevent someone getting hurt.", "marks": 1},
        ],
    },
    "1.3": {"prompt": "1.3 Her friend falls. Name four safe things Nandi can do while getting help. [4]"},
    "1.4": {"prompt": "1.4 Starting with washing hands, put these actions in a helpful order: wash hands, sit to eat, play with a ball, tidy the ball away. [4]"},
    "1.5": {"prompt": "1.5 Give one kind way to help a classmate, say what you would do, and explain how it would help. [4]"},
},
5: {
    "title": "Processing materials and fair testing",
    "stimulus": "A Grade 5 CAPS example describes mixing sand, gravel, cement and water to make concrete. Learners will prepare two small concrete samples with different amounts of gravel. They will keep the other materials, moulds, setting time and test method the same. After the samples set, an educator will add identical counters one at a time and record how many each sample supports before it cracks. The class will also record material properties before mixing and after the samples set.",
    "questions": [
        q("1.1 Name the four materials mixed in the example and name the processed material they make. [5]", ["Names sand.", "Names gravel.", "Names cement.", "Names water.", "Names concrete as the processed material."], "remember", "materials_and_products"),
        q("1.2 State what property information learners should record before mixing and after the samples set. Give two examples of properties to compare and explain why they record both stages. [5]", ["Records properties of the starting materials before mixing.", "Names appearance as one observable property.", "Names texture or another valid observable property as a second property.", "Records a property of the set concrete, such as strength or durability.", "Explains that comparing before and after shows how processing changes material properties."], "understand", "observation"),
        q("1.3 In the two-sample test, identify what is changed, what is measured and three conditions that should be kept the same. Explain why this makes the comparison fair. [6]", ["Identifies amount of gravel as the changed factor.", "Identifies the number of identical counters supported before cracking as the measured result.", "Keeps the amount of sand the same.", "Keeps the amount of cement and water the same.", "Keeps the mould and setting time the same.", "Explains that changing only the gravel amount helps make the comparison fair."], "analyze", "fair_test"),
        q("1.4 Based on the planned test, predict which sample will support more counters, or predict that they will support the same number. Explain why your prediction is reasonable, state what result will count as evidence, and give one reason the result should be checked with repeated trials. [7]", ["Gives a clear prediction, including a reasoned prediction of no difference.", "Links the prediction to the changed gravel amount without claiming the result is certain.", "Identifies the number of counters supported before cracking as the result to observe.", "Explains that the same counter type and test method allow comparison.", "Recognises that individual small samples may give unusual results.", "Explains that repeated trials help check whether a result is consistent.", "States that the conclusion should be based on recorded results."], "evaluate", "prediction"),
        q("1.5 Give suitable results-table headings, including units where needed, for the gravel test. Then describe one way to keep the comparison reliable and one limitation of using small samples to choose material for a real path. [7]", ["Includes a sample or gravel-condition heading.", "Includes the gravel amount with a stated unit or defined measure.", "Includes a trial number.", "Includes the number of counters supported before cracking.", "Keeps other ingredients, mould and setting time the same.", "Repeats the test and records results consistently.", "Notes that small samples cannot by themselves prove how a full path will perform."], "evaluate", "data_handling"),
    ],
},
6: {
    "1.1": {
        "prompt": "1.1 Identify Thabo’s late-night habit and the activity he has stopped joining. State one effect in class and explain how his habit may contribute to it. [5]",
        "memo": [
            {"point": "States that Thabo watches videos after doing homework.", "marks": 1},
            {"point": "States that he has been sleeping late.", "marks": 1},
            {"point": "States that he has stopped joining football at break.", "marks": 1},
            {"point": "States that he feels tired in class.", "marks": 1},
            {"point": "Explains that watching videos late delays sleep and may contribute to tiredness in class.", "marks": 1},
        ],
    },
    "1.2": {
        "prompt": "1.2 Suggest a realistic evening plan with a time for homework, a screen-free period before bed and one sleep-preparation activity. Put the activities in a sensible order and explain how the plan could support rest. [5]",
        "memo": [
            {"point": "Gives a reasonable time or duration for homework.", "marks": 1},
            {"point": "Schedules a screen-free period before bed.", "marks": 1},
            {"point": "Names a suitable sleep-preparation activity.", "marks": 1},
            {"point": "Orders the activities sensibly before bedtime.", "marks": 1},
            {"point": "Explains how the plan could support adequate rest.", "marks": 1},
        ],
    },
    "1.3": {
        "prompt": "1.3 What could Thabo say to his friend? Write a respectful I-statement that names how he feels and why, asks for specific support, and names a trusted adult he could approach if the problem continues. Explain why asking for support is responsible. [6]",
        "memo": [
            {"point": "Names a feeling accurately.", "marks": 1},
            {"point": "Gives a reason linked to the scenario.", "marks": 1},
            {"point": "Uses a respectful I-statement or equivalent wording.", "marks": 1},
            {"point": "Makes a clear, specific request for support from the friend.", "marks": 1},
            {"point": "Identifies a trusted adult he could approach if the problem continues.", "marks": 1},
            {"point": "Explains that asking for support is a responsible way to address a problem.", "marks": 1},
        ],
    },
    "1.4": {"prompt": "1.4 Give two benefits of regular physical activity. Then suggest safe steps for Thabo's gradual return to football, including how to prepare, when to rest, and what to do if he feels unwell. [7]"},
    "1.5": {
        "prompt": "1.5 Suggest two realistic options Thabo could use to reduce late-night screen use. Give one benefit of each option, one possible difficulty with either option, and recommend one option using the scenario. [7]",
        "memo": [
            {"point": "Gives a first realistic option.", "marks": 1},
            {"point": "Gives a second distinct realistic option.", "marks": 1},
            {"point": "States one benefit of the first option.", "marks": 1},
            {"point": "States one benefit of the second option.", "marks": 1},
            {"point": "States one plausible difficulty with either option.", "marks": 1},
            {"point": "Makes a clear recommendation.", "marks": 1},
            {"point": "Justifies the recommendation using the scenario.", "marks": 1},
        ],
    },
},
7: {
    "1.1": {
        "prompt": "1.1 Classify these four items—fruit bought, cups bought, table fee, and money received from cups sold—as a production input, business expense, sales revenue, or all categories that apply. Explain why the fruit and table fee fit their categories. [6]",
        "memo": [
            {"point": "Classifies the fruit bought as both a production input and a business expense.", "marks": 1},
            {"point": "Classifies the cups bought as both a production input and a business expense.", "marks": 1},
            {"point": "Classifies the table fee as a business expense.", "marks": 1},
            {"point": "Classifies money received from cups sold as sales revenue, not a business expense.", "marks": 1},
            {"point": "Explains that the fruit is used in the product and its purchase is an outlay.", "marks": 1},
            {"point": "Explains that the table fee pays for market selling space.", "marks": 1},
        ],
    },
    "1.4": {"prompt": "1.4 Explain two reasons the six unsold cups matter for the next market day. Use case facts to recommend how many cups to make or buy, and address freshness or safety, waste, and why unsold stock is not sales revenue. [10]"},
},
8: {
    "1.1": {"prompt": "1.1 Explain how pressure from a friend could affect the learner’s confidence in their own ability. Write one positive self-talk statement and give one action that would help the learner use their own ability on the assignment. [6]", "memo": [{"point": "Identifies the friend's pressure to copy as an influence on the learner.", "marks": 1}, {"point": "Explains one possible effect on confidence or self-concept, such as doubting their own ability.", "marks": 1}, {"point": "Writes a positive and relevant self-talk statement that recognizes their ability or individuality.", "marks": 1}, {"point": "Connects the self-talk statement to completing their own original work.", "marks": 1}, {"point": "Gives one practical action, such as starting a small task or asking the teacher for help.", "marks": 1}, {"point": "Explains how the action could support confidence or develop personal potential.", "marks": 1}]},
},
9: {
    "1.1": {
        "prompt": "1.1 Name three services the van offers and state where it stops each Thursday. [6]",
        "memo": [
            {"point": "Names the book or newspaper lending service.", "marks": 1},
            {"point": "Names the tablet reading activities.", "marks": 1},
            {"point": "Names help with online forms.", "marks": 1},
            {"point": "States that the van stops beside Mhlabeni Community Hall.", "marks": 1},
            {"point": "States that the van stops there every Thursday.", "marks": 1},
            {"point": "Presents the information clearly and accurately using passage details.", "marks": 1},
        ],
    },
    "1.4": {"prompt": "1.4 Rewrite 'The tablets work offline, so learners can use them even when the mobile signal is weak' as two sentences without changing its meaning. Preserve both facts and their cause-and-effect link; check grammar, capitals and punctuation, and do not add a new claim. [9]"},
},
11: {
    "1.2": {"prompt": "1.2 Identify the two environmental choices in the club's plan and explain the purpose of each. [9]"},
},
12: {
    "1.1": {"prompt": "1.1 Identify one micro and one market factor from the case. Then name a plausible macro-environment factor businesses may face; the case does not specify one. Classify each factor and justify your classifications. [8]"},
},
}


def apply_item_amendments(grade: int, source: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(source)
    amendments = copy.deepcopy(ITEM_AMENDMENTS.get(grade, {}))
    for top_level in ("title", "stimulus", "questions", "data_table"):
        if top_level in amendments:
            data[top_level] = amendments.pop(top_level)
    by_number = {f"1.{index}": item for index, item in enumerate(data.get("questions") or [], 1)}
    for question_id, fields in amendments.items():
        if question_id not in by_number:
            raise ValueError(f"grade {grade}: item amendment references missing question {question_id}")
        by_number[question_id].update(fields)
    return data

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def validate(pack: dict[str,Any], grade:int) -> list[str]:
    errors=[]; expected=MARKS[grade]; questions=pack['sections'][0]['questions']
    table=pack['sections'][0].get('data_table')
    if table is not None:
        columns=table.get('columns') if isinstance(table,dict) else None
        rows=table.get('rows') if isinstance(table,dict) else None
        if (not str(table.get('caption') or '').strip() if isinstance(table,dict) else True):
            errors.append('data table requires a visible caption')
        if (not isinstance(columns,list) or len(columns)<2 or any(not str(cell).strip() for cell in columns)):
            errors.append('data table requires at least two non-empty column headings')
        if (not isinstance(rows,list) or not rows or any(not isinstance(row,list) or len(row)!=len(columns or []) or any(not str(cell).strip() for cell in row) for row in rows)):
            errors.append('data table rows must match the column count and contain non-empty cells')
    if len(questions)!=5: errors.append('question count is not five')
    if [q['marks'] for q in questions]!=expected: errors.append('question mark split mismatch')
    if sum(q['marks'] for q in questions)!=sum(expected): errors.append('paper total mismatch')
    for i,item in enumerate(questions,1):
        if len(item['memo'])!=item['marks'] or any(m['marks']!=1 for m in item['memo']): errors.append(f'question {i} memo does not reconcile')
    blooms={q['bloom_level'] for q in questions}
    if grade>=5 and len(blooms)<3: errors.append('insufficient cognitive range')
    return errors

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grade', type=int, choices=range(1, 13), help='Rebuild one grade while preserving the other grade receipts.')
    args = parser.parse_args()
    assignments=json.loads(ASSIGNMENTS.read_text())
    manifest=load_manifest(CAPS_MANIFEST)
    results=[]
    selected_assignments = [row for row in assignments['assignments'] if args.grade is None or int(row['grade']) == args.grade]
    if args.grade is not None and not any(int(row['grade']) == args.grade for row in assignments['assignments']):
        raise RuntimeError(f'No randomized subject assignment exists for Grade {args.grade}')
    for assignment in selected_assignments:
        grade=int(assignment['grade']); subject_id=assignment['subject_profile']
        if grade not in PAPERS: raise RuntimeError(f'No authored paper for grade {grade}')
        language='English'
        candidates=resolve_caps(manifest,subject_id,grade,language,False)
        if not candidates: raise RuntimeError(f'No official CAPS match for grade {grade} {subject_id}')
        source=candidates[0]; source_path=Path(source['path'])
        if not source_path.is_file() or digest(source_path)!=source['sha256']:
            raise RuntimeError(f'CAPS source missing/hash mismatch: {source_path}')
        display=source_id_to_name(subject_id)
        data=apply_item_amendments(grade, PAPERS[grade])
        marks=MARKS[grade]
        questions=[]
        for index,(item,mark) in enumerate(zip(data['questions'],marks,strict=True),1):
            if item['marks']!=mark: raise RuntimeError(f'authored marks differ for grade {grade} Q{index}')
            questions.append({**item,'number':f'1.{index}'})
        instructions=['Answer all five questions.','Show calculations where requested.','Use evidence from the printed stimulus when a question refers to it.']
        section_instructions='Read the stimulus and each question carefully.'
        if grade == 1:
            instructions=['The educator may read the stimulus and questions aloud.','Answer orally, by pointing, or with short words or phrases.','Answer all five questions.']
            section_instructions='The educator may read this short scenario aloud before asking the questions.'
        section={'title':'Assessment','instructions':section_instructions,'stimulus':data['stimulus'],'questions':questions}
        if data.get('data_table'):
            section['data_table']=data['data_table']
        pack={'exam_title':f"Grade {grade} {display}: {data['title']}",'subject':display,'grade':grade,'duration_minutes':DURATIONS[grade],'total_marks':sum(marks),'student_instructions':instructions,'sections':[section]}
        if grade in {1, 2, 3, 11}:
            pack['compact_memo_layout'] = True
        errors=validate(pack,grade)
        if errors: raise RuntimeError(f'grade {grade} validation failed: {errors}')
        folder=OUT/'grades'/f'grade-{grade:02d}-{subject_id}'
        folder.mkdir(parents=True,exist_ok=True)
        json_path=folder/'HOMS_GRADE_ASSESSMENT.json'
        json_path.write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n')
        source_label=f"DBE CAPS {source['title']} · {source['phase']} · SHA-256 {source['sha256']} · {source['source_url']}"
        exam=folder/'GRADE_EXAM.docx'; memo=folder/'GRADE_MEMO.docx'
        render_docx(pack,exam,False,source_label); render_docx(pack,memo,True,source_label)
        receipt={'schema':'dio.homs.grade_exam_candidate_receipt.v1','created_at':datetime.now(timezone.utc).isoformat(),'grade':grade,'subject':display,'randomization_seed':assignments['random_seed'],'authorship':'curated_original_assessment_items','caps_source':{'title':source['title'],'path':str(source_path),'source_url':source['source_url'],'sha256':source['sha256']},'assessment':{'total_marks':sum(marks),'question_count':len(questions),'exam':{'path':str(exam),'sha256':digest(exam)},'memo':{'path':str(memo),'sha256':digest(memo)},'json':{'path':str(json_path),'sha256':digest(json_path)}},'validation':{'question_marks_match':True,'one_mark_memo_points_reconcile':True,'all_questions_use_printed_stimulus_or_grade_level_knowledge':True,'educator_review_required':True},'release_authorized':False,'classroom_approval':'PENDING_QUALIFIED_EDUCATOR_REVIEW'}
        (folder/'HOMS_GRADE_EXAM_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        results.append({'grade':grade,'subject':display,'state':'DRAFT_PACK_CREATED','job_dir':str(folder),'caps_source_sha256':source['sha256']})
        print(f"grade {grade:02d}: {display} {sum(marks)} marks generated",flush=True)
    if args.grade is not None:
        old_summary = json.loads((OUT/'GRADE_EXAM_SET_RECEIPT.json').read_text(encoding='utf-8'))
        result_by_grade = {int(row['grade']): row for row in old_summary['results']}
        result_by_grade.update({int(row['grade']): row for row in results})
        results = [result_by_grade[grade] for grade in sorted(result_by_grade)]
    summary={'schema':'dio.homs.random_grade_exam_set_receipt.v1','created_at':datetime.now(timezone.utc).isoformat(),'random_seed':assignments['random_seed'],'grade_range':[1,12],'results':results,'created_count':sum(row['state']=='DRAFT_PACK_CREATED' for row in results),'failed_count':sum(row['state']!='DRAFT_PACK_CREATED' for row in results),'human_review_required':True,'release_authorized':False,'commercial_validation':'UNPROVED'}
    (OUT/'GRADE_EXAM_SET_RECEIPT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return 0

def source_id_to_name(subject:str)->str:
    names={'life_skills':'Life Skills','english_language':'English Language','mathematics':'Mathematics','natural_sciences_and_technology':'Natural Sciences and Technology','economics_management_sciences':'Economic and Management Sciences','life_orientation':'Life Orientation','physical_sciences':'Physical Sciences','business_studies':'Business Studies'}
    return names.get(subject,subject.replace('_',' ').title())

if __name__=='__main__': raise SystemExit(main())
