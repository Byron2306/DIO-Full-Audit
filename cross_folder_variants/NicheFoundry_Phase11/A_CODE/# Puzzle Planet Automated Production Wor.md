# Puzzle Planet Automated Production Workflow

## 1. Channel format

**Working name:** Puzzle Planet
**Format:** Interactive quiz adventures
**Audience:** All-ages and family-safe by default
**Episode length:** Approximately 6 to 10 minutes
**Questions per episode:** 6 to 10
**Primary formats:** Long-form quiz adventures, Shorts and themed compilations

Each episode places the viewer inside a small narrative:

* Escape Dinosaur Island.
* Repair the Space Station.
* Solve the Museum Mystery.
* Cross the Mythology Maze.
* Rescue the Lost Expedition.
* Identify the Secret Animal.
* Unlock the World Map.
* Survive the Science Laboratory.

The story gives each quiz a distinct identity and helps prevent the channel from becoming a collection of mechanically interchangeable question slides. This matters because YouTube’s monetisation rules specifically scrutinise repetitive and mass-produced content with little meaningful variation.

---

# 2. Governing principle

The workflow follows one rule:

> **Automate production mechanics, but never automate editorial responsibility.**

The system may generate:

* Episode concepts.
* Source-grounded questions.
* Plausible answer options.
* Narration.
* Gamma presentation cards.
* ElevenLabs voice clips.
* Countdown sequences.
* Subtitles.
* Thumbnails.
* Final video renders.
* Private YouTube uploads.

A person must approve:

* The factual accuracy of every answer.
* Whether each question has only one correct answer.
* Age appropriateness.
* Audience classification.
* Synthetic-media disclosure.
* The title and thumbnail.
* The final rendered video.
* Publication.

The workflow therefore has two separate automations:

1. **Generate and verify the episode.**
2. **Approve, render and upload privately.**

No workflow publishes directly to the public channel.

---

# 3. System architecture

```text
EPISODE BRIEF
      ↓
SOURCE RETRIEVAL
      ↓
OLLAMA STRUCTURED QUIZ GENERATION
      ↓
DETERMINISTIC VALIDATION
      ↓
SECOND OLLAMA EDITORIAL AUDIT
      ↓
DUPLICATE AND SAFETY CHECK
      ↓
GAMMA STORYBOARD AND CARD GENERATION
      ↓
HUMAN APPROVAL GATE
      ↓
ELEVENLABS NARRATION
      ↓
LOCAL COUNTDOWN AND VIDEO RENDER
      ↓
CAPTIONS + THUMBNAIL + QA
      ↓
PRIVATE YOUTUBE UPLOAD
      ↓
HUMAN WATCH-THROUGH
      ↓
MANUAL PUBLICATION
```

---

# 4. Stage One: Episode brief

The workflow begins through an n8n webhook or local command.

Example brief:

```json
{
  "working_title": "Escape Dinosaur Island",
  "topic": "dinosaurs and fossils",
  "story_premise": "Solve six questions to repair the time portal.",
  "age_band": "8-13",
  "difficulty": "mixed",
  "question_count": 6,
  "countdown_seconds": 8,
  "audience_mode": "general_family",
  "contains_synthetic_media": false,
  "source_mode": "wikipedia",
  "source_queries": [
    "Dinosaur",
    "Fossil",
    "Tyrannosaurus"
  ],
  "visual_direction": "Cinematic family adventure with large readable game cards."
}
```

## Required editorial fields

| Field                   | Purpose                               |
| ----------------------- | ------------------------------------- |
| Topic                   | Defines the knowledge area            |
| Story premise           | Makes the episode distinct            |
| Age band                | Controls vocabulary and difficulty    |
| Question count          | Controls duration                     |
| Countdown duration      | Controls interaction pacing           |
| Audience mode           | Records the human audience decision   |
| Synthetic-media setting | Records the human disclosure decision |
| Source queries          | Grounds the questions                 |
| Visual direction        | Gives Gamma a coherent design target  |

---

# 5. Stage Two: Source retrieval

The starter workflow retrieves evergreen source text from the English Wikipedia MediaWiki API.

It searches the supplied topics, extracts article text and stores:

```text
sources.json
```

Each source record contains:

* Page title.
* Source URL.
* Extracted source text.

The generation model is instructed to create questions **only from the supplied source packet**.

A creator-supplied source packet can replace Wikipedia. This is preferable for:

* Curriculum-specific quizzes.
* Sponsored educational episodes.
* History topics requiring specialist sources.
* Science topics requiring official sources.
* Brand or product quizzes.
* Original fictional universes.

The source layer should eventually support curated connectors for:

* NASA.
* National Geographic education resources.
* Museums.
* Encyclopaedias.
* Government geography databases.
* Creator-owned research packs.

---

# 6. Stage Three: Structured quiz generation

The workflow sends the brief and source packet to a local Ollama model.

Ollama supports structured output using a JSON schema through its chat API. This allows the workflow to require a predictable episode object rather than attempting to scrape loosely formatted model prose.

The generated object includes:

```text
episode_id
title
story_premise
age_band
audience_mode
contains_synthetic_media
intro_narration
questions[]
outro_narration
visual_direction
```

Every question contains:

```text
question_id
question
four answer options
correct option index
answer
explanation
source URLs
difficulty
```

## Generation constraints

The model is instructed to:

* Use exactly four options.
* Create only one correct answer.
* Avoid trick wording.
* Avoid disputed claims.
* Avoid politics, religion and medical advice.
* Avoid frightening or graphic details.
* Keep distractors plausible but fair.
* Progress from easier to harder questions.
* Add one interesting teaching point to every explanation.
* Cite at least one supplied source for each answer.

---

# 7. Stage Four: Automated validation

The workflow performs two different forms of validation.

## 7.1 Deterministic validation

Python checks:

* Exactly four options exist.
* Options are unique.
* The answer corresponds to the selected correct option.
* A source URL is recorded.
* No question is duplicated inside the episode.
* The question is not excessively similar to a previous archived episode.
* Required fields are present.
* Question and explanation lengths are sensible.

Archived questions are compared using text similarity. Questions above the configured similarity threshold are rejected.

## 7.2 Independent model audit

A second Ollama request acts as an editorial critic.

It checks:

* Whether the answer is explicitly supported by the source packet.
* Whether multiple options could reasonably be correct.
* Whether the wording is ambiguous.
* Whether the answer is accidentally disclosed.
* Whether distractors are deceptive.
* Whether the language is suitable for the age band.
* Whether two questions test essentially the same fact.

The critic returns:

```json
{
  "passed": true,
  "issues": [],
  "editor_summary": "All six questions are supported and unambiguous."
}
```

Any factual, safety or ambiguity error stops the workflow.

The rejected package remains available for inspection, but it cannot continue to voice generation or rendering.

---

# 8. Stage Five: Gamma visual production

Once the episode passes validation, the workflow creates a Gamma input document.

Card structure:

```text
Cover
Mission briefing
Question 1
Answer 1
Question 2
Answer 2
...
Final score
```

Question and answer cards are deliberately separated so the design cannot reveal an answer early.

The workflow sends the structured content to Gamma using:

```text
POST /v1.0/generations
```

The request uses:

```json
{
  "textMode": "preserve",
  "format": "presentation",
  "exportAs": "png"
}
```

Gamma generation is asynchronous. The workflow creates the generation, polls its status and downloads the completed PNG export. Gamma’s API supports presentation generation, PNG export and workspace themes, although API-key access currently requires an eligible paid Gamma plan.

## Recommended Gamma theme

Create one permanent 16:9 Puzzle Planet theme using:

* Large rounded display headings.
* High-contrast question cards.
* One dominant illustration per card.
* Four clearly separated answer boxes.
* Large answer letters.
* Consistent difficulty indicator.
* Dedicated answer-reveal layout.
* Space for the countdown overlay.
* No tiny paragraphs.
* No answer text inside decorative imagery.

Gamma provides the designed cards. The local renderer controls timing, narration, countdowns, subtitles and final assembly.

---

# 9. Human approval gate

Generation ends with:

```text
status: awaiting_human_approval
```

The episode directory contains:

```text
brief.json
sources.json
episode.json
verification.json
gamma_input.md
gamma_job.json
gamma_export.zip
approval_checklist.md
```

The reviewer confirms:

* Every answer is supported.
* Every question has only one correct answer.
* The Gamma cards match the episode data.
* Answers are not visible on question slides.
* Difficulty is appropriate.
* No question is humiliating or needlessly frightening.
* No unsafe challenge is encouraged.
* The episode is meaningfully different from previous uploads.
* Audience classification is correct.
* Synthetic-media disclosure is correct.

Family-safe content is not automatically “made for kids.” YouTube distinguishes broadly appealing general-audience animation from content specifically directed at children. Creators must classify the intended audience accurately rather than relying on a disclaimer or simply selecting the commercially convenient option.

Made-for-kids videos lose or restrict features such as comments, cards, end screens, memberships and certain notification or advertising functions.

---

# 10. Stage Six: ElevenLabs narration

After approval, the second workflow generates narration scene by scene.

Files are created as:

```text
000_cover.mp3
001_intro.mp3
002_question.mp3
003_answer.mp3
...
```

Scene-level generation allows individual questions to be corrected without regenerating the entire episode.

The ElevenLabs API accepts text, a voice ID, model ID and optional voice settings, returning the generated audio file. It also supports pronunciation dictionaries and continuity parameters for segmented narration.

## Recommended voice roles

| Role                | Style                            |
| ------------------- | -------------------------------- |
| Main host           | Warm, energetic and clear        |
| Mission computer    | Calm and slightly mechanical     |
| Villain or obstacle | Comic rather than frightening    |
| Answer reveal       | Enthusiastic but not shrieking   |
| Final score         | Encouraging at every score level |

The host should never ridicule a wrong answer. The channel’s emotional design should make viewers eager to try again rather than feel examined by a judgemental toaster.

---

# 11. Stage Seven: Local video rendering

The Python pipeline uses FFmpeg and Pillow.

For each scene it:

1. Loads the corresponding Gamma card.
2. Generates or loads the narration.
3. Creates a video segment matching the narration duration.
4. Adds countdown images after each question.
5. Inserts silent one-second countdown segments.
6. Concatenates all video segments.
7. Creates an SRT subtitle file.
8. Creates a thumbnail from the cover card.
9. Produces the final MP4.

Output:

```text
final.mp4
captions.srt
thumbnail.png
qa_report.json
```

The current starter renderer outputs:

```text
1920 × 1080
30 frames per second
H.264 video
AAC audio
```

Future upgrades can add:

* Animated progress maps.
* Sound effects.
* Licensed background music.
* Character animation.
* Correct-answer spark effects.
* Score counters.
* Round transitions.
* 9:16 Shorts rendering.
* Multilingual voice tracks.

---

# 12. Stage Eight: Quality assurance

The automated QA checks:

* Final video exists.
* File size is plausible.
* Video duration exceeds the minimum threshold.
* FFprobe can read the video.
* Captions exist.
* Thumbnail exists.
* Verification passed.
* Approval was explicitly supplied.

Future QA should add:

* Black-frame detection.
* Silence detection.
* Audio clipping detection.
* Caption overflow.
* Text readability scoring.
* Answer-card ordering.
* Visual similarity detection.
* Secret and personal-information scanning.
* Music licence validation.
* Pronunciation review.

A failed QA report prevents upload.

---

# 13. Stage Nine: Private YouTube upload

The workflow can optionally upload the completed video through the YouTube Data API.

It sets:

```text
privacyStatus: private
notifySubscribers: false
selfDeclaredMadeForKids: human-reviewed value
containsSyntheticMedia: human-reviewed value
```

It then uploads:

* The video.
* The custom thumbnail.
* The English caption track.

The YouTube API supports private uploads and exposes both the made-for-kids and synthetic-media fields in the video status resource. It also provides endpoints for uploading captions and custom thumbnails.

The creator then watches the private upload on:

* A phone.
* A computer.
* A television.
* Headphones.
* Phone speakers.
* Captions enabled.

Publication remains manual.

---

# 14. n8n workflow structure

## Workflow A: Generate Verified Episode

```text
Webhook
  ↓
Validate and Base64-encode brief
  ↓
Execute local generation pipeline
  ↓
Retrieve sources
  ↓
Generate structured episode
  ↓
Run validation
  ↓
Generate and download Gamma deck
  ↓
Return episode directory and approval status
```

Webhook:

```text
POST /webhook/puzzle-planet-generate
```

## Workflow B: Approve, Render and Upload

```text
Approval webhook
  ↓
Require approved=true
  ↓
Read verified episode package
  ↓
Generate ElevenLabs audio
  ↓
Render locally
  ↓
Run QA
  ↓
Optionally upload privately
  ↓
Return final file path or private video ID
```

Webhook:

```text
POST /webhook/puzzle-planet-approve
```

The supplied n8n workflows use the Execute Command node and are therefore intended for self-hosted n8n.

---

# 15. Recommended operating cadence

## Long-form

* One complete adventure every seven to ten days.
* Six to ten questions.
* A different story world for every episode.
* A recurring host and visual identity.

## Shorts

Create two Shorts per episode:

1. One fast question with a reveal.
2. One surprising explanation from the full episode.

## Monthly compilation

Combine related episodes:

* Ultimate Animal Challenge.
* Around the World Quiz.
* Dinosaur Survival Marathon.
* Space Mission Mega Quiz.
* Mythology Maze Collection.

Compilations should include new connective narration, score systems or bonus rounds rather than simply joining old files end to end.

---

# 16. Recommended first six episodes

| Episode                           | Core mechanic                 |
| --------------------------------- | ----------------------------- |
| Escape Dinosaur Island            | Repair a time portal          |
| Rescue the Space Station          | Restore six systems           |
| The Missing Museum Crown          | Eliminate suspects            |
| Journey Through the Human Body    | Reach the control room        |
| Around the World in Ten Questions | Collect passport stamps       |
| The Secret Animal Laboratory      | Identify creatures from clues |

This gives the channel variety across science, animals, geography, history and logic without losing its central game-show identity.

---

# 17. Final operating rule

The system should become faster over time, but not less responsible.

The competitive advantage is not merely that Puzzle Planet can generate quizzes automatically.

It is that the workflow can demonstrate:

* Where every fact came from.
* Which checks were passed.
* Which person approved it.
* Which assets were used.
* How the audience was classified.
* What was uploaded.
* Why the final episode was considered fit for publication.

That turns an automated quiz channel into a small, repeatable family-entertainment studio.
