# HOMS Tight 8 Spine

The tight 8 are the school-subject spine lanes that can be translated downward from FET to Senior, Intermediate and Foundation phases.

Economics is tracked as an extension lane, not part of the tight 8 spine, because it does not carry down to Grade 3 as directly as languages, mathematics, life skills, natural sciences and social sciences.

## Status

| Spine | Status | Source Assets | Release Blocked | Missing Source Types | Downward Carrier |
|---|---|---:|---:|---|---|
| English Language | `mechanics_passed_release_blocked` | 8 | 4 | none | early_language_task: oral prompt, picture prompt, phonics/vocabulary, sentence response |
| Afrikaans Language | `mechanics_passed_release_blocked` | 10 | 4 | none | early_language_task: oral/picture prompts, vocabulary, sentence response |
| Mathematics | `mechanics_passed_release_blocked` | 6 | 3 | none | concrete_number_task: number line, counting objects, shapes, measurement pictures |
| Life Orientation / Life Skills | `mechanics_passed_release_blocked` | 5 | 2 | none | life_skills_activity: oral/picture prompt, observation checklist, concrete wellbeing/environment tasks |
| Life Sciences -> Natural Sciences Life Strand | `mechanics_passed_release_blocked` | 10 | 3 | none | life_skills_beginning_knowledge: living/non-living, body/environment picture prompts |
| Physical Sciences -> Natural Sciences Physical Strand | `mechanics_passed_release_blocked` | 6 | 3 | none | life_skills_beginning_knowledge: materials, weather, movement, simple observation tasks |
| Geography -> Social Sciences Geography | `mechanics_passed_release_blocked` | 23 | 4 | none | life_skills_beginning_knowledge: places, weather, environment, simple map/picture awareness |
| History -> Social Sciences History | `mechanics_passed_release_blocked` | 6 | 4 | none | life_skills_beginning_knowledge: past/present, family/community stories, sequencing |

## Phase Translation

### English Language

- `fet_10_12`: language_integrated_assessment: comprehension, visual literacy, summary, transactional/creative writing
- `senior_7_9`: language_integrated_assessment: source reading, language-in-context, paragraph response
- `intermediate_4_6`: guided_language_task: text comprehension, vocabulary, simple visual interpretation
- `foundation_1_3`: early_language_task: oral prompt, picture prompt, phonics/vocabulary, sentence response
- Done means: official/curricular text and visual source candidates are embedded; language shell handles comprehension, visual literacy and writing tasks separately; reading and writing load obeys grade ladder

### Afrikaans Language

- `fet_10_12`: language_integrated_assessment: comprehension, visual literacy, summary, writing
- `senior_7_9`: language_integrated_assessment: source reading, taal-in-konteks, paragraph response
- `intermediate_4_6`: guided_language_task: reading, vocabulary, sentence/paragraph scaffold
- `foundation_1_3`: early_language_task: oral/picture prompts, vocabulary, sentence response
- Done means: Afrikaans source exemplars are added to the source bank; language shell supports Afrikaans instructions and memo wording; HL/FAL/SAL level is explicit in the request and receipt

### Mathematics

- `fet_10_12`: calculation_problem_solving: graph, geometry, algebra, data handling
- `senior_7_9`: pre_fet_problem_solving: multi-step calculations, graphs, geometry and pattern reasoning
- `intermediate_4_6`: guided_problem_solving: number operations, tables, simple graphs, measurement
- `foundation_1_3`: concrete_number_task: number line, counting objects, shapes, measurement pictures
- Done means: graph/diagram/table source candidates are readable; answers are mechanically derivable from supplied values; memo separates method, substitution, final answer and unit marks

### Life Orientation / Life Skills

- `fet_10_12`: practical_performance_or_portfolio: scenario, reflection, project and rubric evidence
- `senior_7_9`: life_orientation_task: scenario response, decision-making, wellbeing/citizenship evidence
- `intermediate_4_6`: life_skills_task: personal/social wellbeing, creative arts/physical education evidence
- `foundation_1_3`: life_skills_activity: oral/picture prompt, observation checklist, concrete wellbeing/environment tasks
- Done means: assessment avoids unsafe/private/sensitive prompts; portfolio/performance evidence is separated from written reflection; educator observation rubric is always included

### Life Sciences -> Natural Sciences Life Strand

- `fet_10_12`: data_diagram_practical_investigation: biological data, diagrams, investigation reasoning
- `senior_7_9`: natural_sciences_life_living: diagrams, practical observations, data interpretation
- `intermediate_4_6`: natural_sciences_technology_life_living: labelled diagrams, simple tables, observation sheets
- `foundation_1_3`: life_skills_beginning_knowledge: living/non-living, body/environment picture prompts
- Done means: biology diagrams are source-verified or explicitly schematic; Life Sciences graph exemplar gap is closed; human/anatomy diagrams are blocked until educator/source review

### Physical Sciences -> Natural Sciences Physical Strand

- `fet_10_12`: data_diagram_practical_investigation: apparatus, graphs, calculations, equations
- `senior_7_9`: natural_sciences_matter_energy_planet: experiments, graphs, diagrams, explanations
- `intermediate_4_6`: natural_sciences_technology_matter_energy: simple investigations, tables, labelled diagrams
- `foundation_1_3`: life_skills_beginning_knowledge: materials, weather, movement, simple observation tasks
- Done means: source graph/diagram/table candidates are readable; all calculation questions include values and units; unsafe practical instructions are blocked

### Geography -> Social Sciences Geography

- `fet_10_12`: source_based_plus_extended_response: maps, climate, geomorphology, settlement/economic sources
- `senior_7_9`: social_sciences_geography: maps, climate, population, settlement, resource sources
- `intermediate_4_6`: social_sciences_geography: simple maps, photographs, diagrams, tables
- `foundation_1_3`: life_skills_beginning_knowledge: places, weather, environment, simple map/picture awareness
- Done means: maps and photos are object-level curated, not page dumps; source classifier mismatches are resolved before release; questions never ask learners to answer from a missing map/visual

### History -> Social Sciences History

- `fet_10_12`: source_based_plus_essay: source reliability, evidence comparison, essay argument
- `senior_7_9`: social_sciences_history: source evidence, cause/effect, paragraph explanation
- `intermediate_4_6`: social_sciences_history: stories, timelines, pictures, simple source questions
- `foundation_1_3`: life_skills_beginning_knowledge: past/present, family/community stories, sequencing
- Done means: each source set has provenance and visible evidence; essay/paragraph length is phase appropriate; memo accepts defensible evidence-linked answers

## Extension Lane

- Economics / EMS Extension: valuable FET product, but it maps directly to Senior Phase EMS and only indirectly to Foundation/Intermediate money and community themes

## Release Rule

No subject is sellable until source release gates are cleared and educator approval is recorded.
