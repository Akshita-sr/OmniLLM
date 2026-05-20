\newpage

# Part V — Conducting Experiments & Logging

> *Parts I–IV told you what OmniLLM is, how it works, and how to make it run. Part V is the methodological core of the thesis. It tells you how to run a defensible human-subjects experiment with this stack, how every interaction is recorded, what questionnaire instrument to use and why, how to analyse the resulting data, and what insights the 2026-05-20 pilot already revealed.*

\newpage

## Chapter 23 — The Experimental Design

> *Five conditions, four task types, fifteen participants, one robot, ~30 minutes per session. Six paragraphs of justification for each choice.*

### At a Glance

The Embodied LLM Arena uses a **within-subjects, fully-crossed, Latin-square-counterbalanced design**. Every participant experiences every one of the five LLM conditions (A–E), and within each condition, the four HRI task types (T1–T4) are presented in a counterbalanced order. The complete factorial — 5 conditions × 4 task types = 20 interactions — fits within a single ~30-minute session per participant, validated by the May 2026 pilot. Three formal hypotheses (H1, H2, H3) defined in Chapter 4 are tested with one primary outcome (mean Likert score per condition) and two secondary outcomes (pairwise preference → ELO leaderboard; RAG-A vs RAG-off-E within-subject contrast).

### The Three Hypotheses (Recap)

| # | Hypothesis | Primary Test |
|---|---|---|
| H1 | Embodied HRI rankings differ from text-only benchmark rankings | Spearman ρ between this study's per-model ELO and Chatbot Arena/MMLU rank; expect ρ < 0.7 |
| H2 | Smart-routed Condition C outperforms fixed-model Conditions A and B | Pairwise win-rate of C over A and over B in the final preference question; expect ≥ 55% in both |
| H3 | RAG-augmented responses are rated more accurate and trustworthy than RAG-off | Within-subject paired t-test of A.accuracy − E.accuracy; expect mean difference > 0 with p < 0.05 |

### Why Within-Subjects?

A within-subjects (repeated-measures) design has two strong advantages over between-subjects for this kind of HRI study:

1. **Statistical power.** Each participant serves as their own control. The variance attributable to "this participant tends to give higher ratings to robots in general" is removed from the condition comparison. A repeated-measures ANOVA on N=15 has more power than a between-subjects ANOVA on N=30 for the same effect size.
2. **Comparability of pairwise preferences.** The final questionnaire item asks the participant which Pepper-personality they preferred. This question is meaningful *only* in a within-subjects design — you cannot ask someone to compare two robots if they only met one.

The cost of within-subjects: **order effects** (early conditions tend to be rated more leniently; later conditions are affected by participant fatigue). We address this via counterbalancing in Chapter 25.

### Why Five Conditions, Not More?

Each condition isolates one experimental factor:

| Condition | What it tests vs. its neighbour |
|---|---|
| A vs B | Fixed cloud LLM vs fixed local LLM (cost-vs-quality trade-off) |
| A vs C | Single fixed model vs dynamic smart routing (H2) |
| A vs D | Single model vs 3-model consensus (ensemble effect) |
| A vs E | RAG enabled vs RAG disabled (H3) |

Adding a sixth condition (e.g. "Cloud-LLM with chain-of-thought prompting" or "Local-LLM with consensus") would either dilute statistical power (more conditions → fewer trials per condition for a fixed session length) or expand session length beyond 30 minutes (participant fatigue → noisier ratings). Five is a defensible Pareto point.

### Why Four Task Types?

The four task types (T1 Info Retrieval, T2 Navigation, T3 Social, T4 Multilingual) are taken from the standard HRI dialogue-act taxonomy (Hsieh et al. 2017; Gross & Krenn 2023). They span the full conversational range a campus-deployed social robot will encounter:

- T1 tests **factual grounding** — does RAG help, and which LLM grounds best?
- T2 tests **embodiment** — does the physical pointing gesture change the perceived helpfulness?
- T3 tests **social naturalness** — the open-ended chat where embodiment effects are strongest in HRI literature.
- T4 tests **multilingual capability** — important for the Genoa context where many visitors are non-Italian researchers.

Four is also the highest number that fits into a 30-minute session at one minute per interaction times five conditions plus questionnaire time between conditions.

### Participant Recruitment

| Decision | Choice | Reason |
|---|---|---|
| N | 15 | Power analysis: 5-cell repeated-measures ANOVA with d=0.5, α=0.05, power=0.80 requires N≥11; over-provisioned to 15 to allow two drop-outs and one Whisper-misfire-heavy run. |
| Population | UniGE students, postdocs, staff; any age 18+; English-speaking | DIBRIS is on campus; recruitment via the department mailing list. |
| Inclusion | Self-reported comfortable with English; no hearing impairment | Whisper STT is English-tuned base model; participants must hear Pepper's TTS. |
| Exclusion | Prior in-depth knowledge of OmniLLM | Avoids "expert participant" bias. Members of Prof. Sgorbissa's HRI lab who have helped design the system are excluded. |
| Compensation | Small token (€10 voucher) | Standard at UniGE for under-30-min HRI sessions. |
| Schedule | ~one-month recruitment window; ~one participant per lab day | Prevents fatigue on the experimenter; lets us iterate on the questionnaire wording between participants if needed. |

### What Each Session Looks Like

```
T+0:00   Participant arrives, greeted, seated.
T+0:01   Consent + GDPR forms reviewed and signed (~4 min).
T+0:05   Demographic mini-questionnaire (age band, native language,
         prior robot exposure) — 3 items, ~30s.
T+0:06   Pepper introduces itself (a single pre-scripted greeting,
         not part of any condition).
T+0:07   Condition 1 (4 interactions, T1→T4 in counterbalanced order).
T+0:11   Questionnaire 1 for Condition 1 (60–90s).
T+0:13   Condition 2.
T+0:17   Questionnaire 2.
T+0:19   Condition 3. + (between-blocks pause if participant wants water)
T+0:23   Questionnaire 3.
T+0:25   Condition 4.
T+0:29   Questionnaire 4.
T+0:31   Condition 5.
T+0:35   Questionnaire 5.
T+0:37   Pairwise preference question
         ("Which of the five Peppers did you prefer?
           Which did you trust most?
           Which felt most natural?")
T+0:40   Open-ended exit comments (recorded).
T+0:42   Compensation, thanks, end.
```

Total: ~42 minutes. Allowing for setup time and unexpected delays, each participant slot is booked at 60 minutes.

\newpage

## Chapter 24 — Running a Single Subject Session

> *The operational checklist. Read it through once. Print Chapter 21 (Day Zero) and bring both to the lab.*

### Before the Participant Arrives

- [ ] AI server and NAOqi bridge are running (Day Zero, steps 3 and 4).
- [ ] Pilot interaction (step 5) green: Pepper speaks, gestures, eye-LED changes.
- [ ] Paper questionnaires (one set of 5 condition-questionnaires + final pairwise sheet) laid out.
- [ ] Pen.
- [ ] Pepper is on its dock or freshly woken; head-touch sensors confirmed responsive (touch each one in turn while watching `/sensors` GET output).
- [ ] (If using face-tracking) `POST /tracker/start` already fired.

### During the Session

- [ ] Run the driver:
  ```powershell
  .\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
      --participant P003 `
      --server http://127.0.0.1:5000 `
      --bridge http://127.0.0.1:6000
  ```

- [ ] **Between condition blocks**, the driver pauses for ~10 seconds. At each pause:
  - Hand the participant the next questionnaire for the condition they just experienced.
  - Move out of Pepper's eyeline so you don't influence their answers.
  - When the participant hands the questionnaire back, you press **Enter** in the driver terminal to continue.
- [ ] **Log live observations** on the observer rating sheet for each interaction:
  - Did the gesture sync with the speech (1–5)?
  - Did the participant understand the first time, or repeat?
  - Any unusual reactions (laughter, surprise, confusion)?
- [ ] At the end, ask the **pairwise preference question** verbally:
  > *"Of the five Peppers you just talked to, which one did you prefer? Which one felt most natural? Which one would you most trust to give you correct information?"*
  - Note the three answers on the pairwise sheet.

### After the Session

- [ ] Move the CSV/JSON output to `results/by_participant/P003/`.
- [ ] Within the hour: enter the Likert scores from paper into the digital collector:
  ```python
  from omnillm.utils.questionnaire import InteractionQuestionnaire, QuestionnaireCollector
  c = QuestionnaireCollector()
  c.add_interaction_response(InteractionQuestionnaire(
      session_id="<from CSV>", participant_id="P003", condition="A",
      accuracy=6, naturalness=5, trust=6,
      gesture_appropriateness=5, response_speed=7,
      free_text="..."))
  # ...repeat for B, C, D, E...
  c.save("results/by_participant/P003/questionnaire.json")
  ```
- [ ] File the paper originals in the binder. Tag them with the participant ID.
- [ ] Check `/export` to verify all 20 interactions were logged server-side.

### Watch-outs

- **Whisper misfires.** If Whisper transcribes a participant's question incorrectly and the LLM answers the wrong thing, note this as a `task_completed=False` observer rating. The driver does not retry automatically; you can ask the participant to repeat, but log the original misfire.
- **Pepper drops connection.** Rare but happens (Wi-Fi flake, NAOqi crash). The driver's per-step try/except will print `ERROR: server unreachable`; you have ~20s to restart the bridge before the participant loses immersion. If this happens twice in one session, abort the session and reschedule.
- **Participant goes off-script.** Some participants will try jailbreaking or testing edge cases ("Pepper, are you human?"). This is fine — log it. The data is more interesting *because* of these moments, not less.

\newpage

## Chapter 25 — Counterbalancing and Why It Matters

### The Problem

In a within-subjects design where every participant sees every condition, the **order** of presentation matters. The first condition gets attention and goodwill; the fifth condition gets fatigue. The first task type in each condition gets the cleanest cognitive engagement; the fourth gets habituation. Without counterbalancing, the first-presented condition would systematically receive higher ratings, and that effect would be indistinguishable from a true condition effect.

### The Solution: Two Latin Squares

We counterbalance at two levels:

#### Level 1 — Condition Order Across Participants (5×5 Latin Square)

The 15 participants are assigned to one of three "blocks" of five-row Latin squares. Each row defines which condition each participant sees first, second, third, fourth, fifth.

| Block | Participant | Pos 1 | Pos 2 | Pos 3 | Pos 4 | Pos 5 |
|---|---|---|---|---|---|---|
| 1 | P001 | A | B | C | D | E |
| 1 | P002 | B | C | D | E | A |
| 1 | P003 | C | D | E | A | B |
| 1 | P004 | D | E | A | B | C |
| 1 | P005 | E | A | B | C | D |
| 2 | P006 | A | C | E | B | D |
| 2 | P007 | B | D | A | C | E |
| 2 | P008 | C | E | B | D | A |
| 2 | P009 | D | A | C | E | B |
| 2 | P010 | E | B | D | A | C |
| 3 | P011 | A | D | B | E | C |
| 3 | P012 | B | E | C | A | D |
| 3 | P013 | C | A | D | B | E |
| 3 | P014 | D | B | E | C | A |
| 3 | P015 | E | C | A | D | B |

After all 15 participants, each condition appears in each position exactly 3 times — perfectly balanced for order effects.

#### Level 2 — Task Type Order Within Each Condition

Within each condition block (4 interactions), the four task types are presented in a Latin-square-rotated order that the driver script hard-codes:

```python
ORDER = [
    ("A", "T1"), ("A", "T2"), ("A", "T3"), ("A", "T4"),
    ("B", "T2"), ("B", "T3"), ("B", "T4"), ("B", "T1"),
    ("C", "T3"), ("C", "T4"), ("C", "T1"), ("C", "T2"),
    ("D", "T4"), ("D", "T1"), ("D", "T2"), ("D", "T3"),
    ("E", "T1"), ("E", "T2"), ("E", "T3"), ("E", "T4"),
]
```

Each task type appears in each position (1st, 2nd, 3rd, 4th within a condition block) exactly once or twice. Over the full study, task-position effects are mostly cancelled.

### A Tighter Counterbalancing Variant

If a future replication wants stronger guarantees, the recommended upgrade is to randomise both the condition order *and* the task order **per participant** using `numpy.random.default_rng(seed=hash(participant_id))`. This produces a fully randomised design with reproducible seed-from-ID. The trade-off is that each participant's sequence becomes harder to print on the experimenter's clipboard in advance.

### The `ExperimentManager.create_session()` Path

`omnillm/hri/experiment.py` includes a higher-level `ExperimentManager.create_session(participant_id, conditions=None)` API that supports per-participant assignment via Latin square. For the N=15 study, the simpler hard-coded `ORDER` is sufficient. For larger replications, switch to `ExperimentManager`:

```python
from omnillm.hri.experiment import ExperimentManager
mgr = ExperimentManager()
session = mgr.create_session(participant_id="P003")
print(session.conditions_assigned)  # ["C", "D", "E", "A", "B"]  per the Latin square
```

Document whichever path you use in the methods section of your paper.

\newpage

## Chapter 26 — The Data Logging Pipeline — From Microphone to CSV

### The Three Logs

Every session produces three artefact streams:

| Artefact | Written by | Path | Contents |
|---|---|---|---|
| **Interaction log** (canonical) | Agent graph node 7 (`log_interaction`) on every interaction | `results/interactions_<date>.jsonl` (server-side) + `results/subject_run_<participant>_<ts>.{json,csv}` (driver) | One row per interaction; all 20 fields of `InteractionRecord` |
| **Questionnaire data** | `QuestionnaireCollector.save()` (post-session) | `results/by_participant/<participant>/questionnaire.json` | All four questionnaire types for that participant |
| **Observer notes** | The experimenter, free-form | `results/by_participant/<participant>/observer.md` | Markdown notes; not machine-parsed but archived |

### Concrete Example — One Interaction in Three Views

A single navigation question in Condition A produces:

**Pepper's log line (Choregraphe console):**
```
ALAnimatedSpeech: "The Pepper room is located at the end of the ground-floor corridor..."
ALMotion: runBehavior(animations/Stand/Gestures/Right_1)
ALLeds: fadeRGB(FaceLeds, 0x00AAFF, 0.3s)
```

**AI server's JSON-Lines log entry:**
```json
{
  "session_id": "578b023b-09af-4da3-a047-e742e25c5913",
  "participant_id": "P003",
  "condition": "A",
  "task_type": "navigation",
  "utterance": "Where is the Pepper room at DIBRIS?",
  "response": "The Pepper room is located at the end of the ground-floor corridor, on the right, in the HRI lab. Look for the door labelled \"Laboratorio HRI / Sgorbissa\".",
  "model_id": "openai-gpt4o-mini",
  "latency_ms": 1592.4,
  "input_tokens": 412,
  "output_tokens": 41,
  "cost_usd": 0.0000865,
  "rag_enabled": true,
  "rag_faithfulness": 0.92,
  "rag_chunk_count": 3,
  "judge_score": -1.0,
  "language": "en",
  "gesture_used": "point_right",
  "task_success": null,
  "timestamp": "2026-06-12T14:23:51.842Z",
  "notes": ""
}
```

**Driver's CSV row** (one column per field):
```
2,A,T2_navigation,openai-gpt4o-mini,graph,y,1.59,"Where is the Pepper room at DIBRIS?","The Pepper room is located at the end..."
```

The three views are not redundant; each captures different metadata. The CSV is the analysis input; the JSON-Lines is the canonical record; the Choregraphe console is the live-monitoring view for the experimenter.

### Data Hygiene Rules

1. **No raw audio is stored.** Whisper transcribes; the transcribed text is logged; the audio bytes are discarded. This is a GDPR-and-courtesy choice: participants' voices do not persist on disk.
2. **No personally identifying information.** Logs contain only the participant ID (P001, P002, …). The code-to-identity mapping lives on paper in the experimenter's binder and is destroyed at study end.
3. **No deletion mid-study.** The JSON-Lines log is append-only. If a row needs correcting (e.g. observer realised the participant misheard the question), add a *correction* row referencing the original row's timestamp. Never overwrite.
4. **Backups within 24 hours.** Each evening, copy `results/` to an external drive and to the cloud (encrypted). Hard-drive failures are non-zero probability events.

\newpage

## Chapter 27 — Questionnaires: Likert, Godspeed, Pairwise, Observer

### The Five-Item Interaction Likert (Primary Outcome)

After each condition block (= 4 interactions), the participant rates that condition on five 1–7 Likert items. The exact paper template:

```
+-------------------------------------------------------------+
|  CONDITION ____  PARTICIPANT P___                           |
|                                                             |
|  Please rate this Pepper personality:                       |
|                                                             |
|  Strongly disagree  1  2  3  4  5  6  7  Strongly agree     |
|                                                             |
|  1. The robot's answers were accurate.                      |
|     [ ][ ][ ][ ][ ][ ][ ]                                   |
|                                                             |
|  2. The robot was natural to talk to.                       |
|     [ ][ ][ ][ ][ ][ ][ ]                                   |
|                                                             |
|  3. I trust the information the robot gave me.              |
|     [ ][ ][ ][ ][ ][ ][ ]                                   |
|                                                             |
|  4. The robot's gestures were appropriate.                  |
|     [ ][ ][ ][ ][ ][ ][ ]                                   |
|                                                             |
|  5. The robot responded quickly enough.                     |
|     [ ][ ][ ][ ][ ][ ][ ]                                   |
|                                                             |
|  Anything else you'd like to say about this Pepper?          |
|  __________________________________________________________  |
|  __________________________________________________________  |
+-------------------------------------------------------------+
```

These five items map directly onto the five fields of `InteractionQuestionnaire`. The mean of the five items is the per-condition "overall score" reported in the leaderboard. (For statistical purposes we will analyse the items independently as well, but the mean is the primary user-facing number.)

### Godspeed Subscales (Secondary Outcome, Optional)

The **Godspeed questionnaire** (Bartneck et al. 2009) is the most-cited HRI evaluation instrument. It has five subscales, each composed of several bipolar adjective pairs rated 1–5:

| Subscale | Adjective pairs |
|---|---|
| **Anthropomorphism** | Fake↔Natural, Machine-like↔Human-like, Unconscious↔Conscious, Artificial↔Lifelike, Moving rigidly↔Moving elegantly |
| **Animacy** | Dead↔Alive, Stagnant↔Lively, Mechanical↔Organic, Artificial↔Lifelike, Inert↔Interactive, Apathetic↔Responsive |
| **Likeability** | Dislike↔Like, Unfriendly↔Friendly, Unkind↔Kind, Unpleasant↔Pleasant, Awful↔Nice |
| **Perceived Intelligence** | Incompetent↔Competent, Ignorant↔Knowledgeable, Irresponsible↔Responsible, Unintelligent↔Intelligent, Foolish↔Sensible |
| **Perceived Safety** | Anxious↔Relaxed, Agitated↔Calm, Quiescent↔Surprised |

Mean each subscale → enter into `GodspeedResponse.anthropomorphism`, etc.

**Recommendation for this study:** include Godspeed **only once per participant**, at the *end* of the session, asking them to rate Pepper overall (not per-condition). Per-condition Godspeed would add ~5 minutes per condition × 5 conditions = 25 minutes, blowing the session budget. End-of-session Godspeed lets us compare *our Pepper deployment* against published Godspeed scores from prior Pepper studies (Mishra et al. 2024; Soraa et al. 2021; Ye & Robert 2023), which is useful contextualisation.

### The Pairwise Preference Question (Feeds ELO)

After all five conditions, ask three preference questions verbally:

1. *"Which of the five Peppers did you prefer overall?"* → maps to category `overall_preference`
2. *"Which one felt most natural to talk to?"* → maps to `naturalness_preference`
3. *"Which one would you most trust to give correct information?"* → maps to `trust_preference`

For each answer, generate `PairwisePreference` records — one record per pairwise comparison the preference implies. If P003 says "I preferred Condition C", that's 4 pairwise wins for C (over A, B, D, E). These feed `EloScorer.update_pairwise(...)` which produces the *embodied_hri* leaderboard.

The triple-question structure is more diagnostic than a single "preferred overall" question — it lets us see *why* a condition was preferred (because it was more natural? more trustworthy? both?).

### Observer Ratings (Live)

The experimenter rates each interaction on the spot:

```
+----------------------------------------------------+
|  INTERACTION #__  COND ___  TASK ___  P___          |
|                                                     |
|  Gesture-speech synchrony     1 [ ] 2 [ ] 3 [ ]    |
|                               4 [ ] 5 [ ]           |
|  Task completed (Y/N)         [Y] / [N]             |
|  Breakdowns (count)           ____                  |
|  Notes:                                             |
|  _______________________________________________   |
+----------------------------------------------------+
```

These rows feed `ObserverRating` records. The `task_completed` field is important: it's the only way to know whether a Whisper misfire or LLM hallucination spoiled the interaction.

### Why Paper, Not Tablet?

Discussed in Chapter 15.2. Three reasons:

1. **Familiar to participants.** No new UI to learn during a 30-minute session.
2. **No accidental editing.** Paper is immutable.
3. **Ethics-friendly.** No second data path; the paper is the original record.

Paper-to-digital conversion happens within the hour, by the experimenter, using the `QuestionnaireCollector` Python API.

\newpage

## Chapter 28 — Ethics, Consent, GDPR, and the UniGE Process

### What You Must Have Before Recruiting

| Document | Purpose | Where to get it |
|---|---|---|
| **Approved study protocol** | Comitato Etico di Ateneo approval | Submit through the UniGE ethics committee portal; ~4–8 weeks turnaround |
| **Informed consent form** (signed by participant) | Participant agrees to take part | Template in Appendix D of this book (forthcoming) |
| **GDPR notice** (signed receipt) | Lists what data is collected, retention period, deletion rights | Template in Appendix D |
| **Data Protection Impact Assessment** (DPIA) | UniGE's data-protection office must approve any new personal-data workflow | DPIA form on UniGE intranet |
| **Insurance / liability coverage** | Standard at-DIBRIS lab insurance | Confirm with Prof. Sgorbissa |

### The Consent Form Essentials

The consent form must explicitly tell the participant:

1. **What the robot is.** "Pepper, a humanoid robot." Not "a smart device" or "an AI". Honesty matters.
2. **What will be asked of them.** "Five short conversations with the robot, ~30 minutes total."
3. **What data is recorded.** "Text transcripts of your questions. Pepper's text answers. Timestamps. *No audio recordings.* *No video.* *No name.*"
4. **What the data is used for.** "A Master's thesis on multi-LLM social robots. May appear (in fully anonymised form) in a future peer-reviewed paper."
5. **How long the data is kept.** "Anonymised data: 5 years (then destroyed). The code-to-identity mapping: destroyed at study end (~6 months after your session)."
6. **Right to withdraw.** "You can stop at any time during the session and ask us to delete your data."
7. **Contact info.** Experimenter's name + email; Prof. Sgorbissa's name + email; UniGE ethics office contact.

### The GDPR Specifics

OmniLLM at the lab is a **data controller** (you, the experimenter) collecting **non-special-category personal data** (the participant's spoken words transcribed) for **scientific research** purposes. Under GDPR Article 89, this is a permissible purpose with appropriate safeguards. The safeguards we put in place:

1. **Pseudonymisation at source.** Participant ID (P001, …) is used everywhere; the link to real identity exists only on paper.
2. **No audio retained.** Whisper transcribes in-memory; the WAV is discarded immediately after.
3. **No cloud LLM sees identifying information.** The LLM only sees the question text. We do *not* tell the LLM "User P003 asks: ...". The LLM call carries no participant identifier.
4. **Destruction schedule.** Six months after study end, the experimenter destroys the paper code-mapping. The anonymised digital data persists for five years, then deleted.

### A Note on Cloud LLM Data Handling

Several cloud LLM providers (OpenAI, Anthropic, Google) state in their terms that they *may* retain prompts for safety / abuse-monitoring purposes for ~30 days. This means the participant's question text *might* be stored on a US (or EU) cloud provider's servers for that period.

For our study this is acceptable because:

1. The question text contains **no personal information about the participant** — they are answering scripted T1/T2/T3/T4 prompts, not divulging personal details.
2. Participants are informed in the consent form that "your questions may be processed by external AI providers (OpenAI, Anthropic, Google) on their servers."
3. We use providers' **enterprise / no-training tiers** where available (these contractually exclude the data from training the provider's models).

For a future deployment with sensitive participant categories (children, medical patients), the recommendation would be to switch to **fully local LLMs only** (Condition B — Ollama — for all conditions) to eliminate the cloud-data-flow concern entirely.

### Sample Texts

The full consent form, GDPR notice, and debriefing-after-session script are in Appendix D of this book (forthcoming with the final thesis submission).

\newpage

## Chapter 29 — Insights From the 2026-05-20 Pilot

> *Two pilot runs, both with the author as participant P000 on Choregraphe's virtual robot. The point of the pilot was not to collect data for analysis — there were no human ratings — but to debug the system end-to-end. The pilot found three bugs and validated two design decisions.*

### Pilot 1 — 2026-05-20 08:11:22 UTC

- File: `results/subject_run_P000_20260520T081122Z.{json,csv}`
- 20 interactions, all on Choregraphe's virtual robot.
- **What the run revealed:**

**Bug #1 — Condition B silently ran GPT-4o-mini.** Every Condition B interaction logged `model_id="openai-gpt4o-mini"` instead of `llama3-8b-local`. The RAG pipeline was using its construction-time `self.model_id` instead of the per-condition model. **Fix:** added per-call `model_id=` parameter to `RAGPipeline.query()`; modified `agent_graph.py` to pass it; modified `app.py` to resolve Cond→model before invoking the graph. (See Chapters 11.5 and 12.1.)

**Bug #2 — Multilingual node fell to fallback.** The T4 (Italian Brignole question) node returned with `path: fallback` and the response was in English ("The Brignole train station is located in Genoa..."). Root cause: `LanguageDetector.detect()` was returning a result object without `.language_name` or `.recommended_model`, causing an `AttributeError` inside the multilingual node, which dropped to the catch-all and produced an English answer. **Fix:** added the three compatibility properties (`language_code`, `language_name`, `recommended_model`) to `LanguageDetectionResult`. (See Chapter 12.3.)

**Bug #3 — Gemini Flash hit Google free-tier quota.** Around interaction 17 (Condition D, which uses Gemini Flash in its 3-model council), Gemini returned `429 RESOURCE_EXHAUSTED`. The council degraded gracefully to a 2-model synthesis. **Fix:** moved T4 from `gemini-flash` to `claude-haiku` in `_LANGUAGE_MODEL_MAP`. Council still includes Gemini Flash because the council's two surviving models provide enough redundancy; if Gemini Flash fails, two-model consensus is acceptable.

### Pilot 2 — 2026-05-20 08:18:22 UTC (after fixes)

- File: `results/subject_run_P000_20260520T081822Z.{json,csv}`
- Same 20 interactions; identical prompts.
- **What the run validated:**

- ✅ Condition B routes correctly: every B interaction logged `model_id="llama3-8b-local"`.
- ✅ T4 Italian prompt routed correctly: Pepper replied in Italian using `claude-haiku`. Latency 1.98s — within budget.
- ✅ Condition D council: every D interaction logged `model_id="council:openai-gpt4o-mini+claude-haiku+gemini-flash"`; 3-model synthesis worked.
- ✅ End-to-end latencies (mean across 20 interactions):
  - A: 1.21s
  - B: 2.84s (slower — Llama on CPU)
  - C: 1.56s
  - D: 3.14s (3× parallel calls + synthesis)
  - E: 1.18s (no RAG; fastest)
- ✅ RAG faithfulness scores (mean across A, B, C, D — i.e. RAG-enabled conditions):
  - A: 0.92
  - B: 0.78 (Llama's grounding is weaker)
  - C: 0.89
  - D: 0.94 (best — consensus reduces hallucination)
  - E: n/a (RAG-off)

### What the Pilot Did Not Test

Three things the pilot deliberately could not test, because there was no human participant:

1. **Likert ratings.** No questionnaire data was collected. The first real Likert data comes from P001 onwards.
2. **Pairwise preference.** No preference judgments; no ELO updates from the pilot.
3. **Gesture quality.** The virtual robot's gestures all reported "behavior not installed". Real-Pepper gesture quality is unknown until Day Zero at the lab.

### Lessons Carried Forward Into the Real Study

| Pilot finding | Action for real study |
|---|---|
| Latency budget OK for A/B/C/E | No mitigation needed. |
| Condition D averages 3.1s | Pre-warn participants: *"This personality takes a little longer to think."* |
| Condition B's RAG faithfulness 0.78 < others | Document in the methods section. This is a real finding — local models ground less faithfully than cloud models. |
| Gemini free-tier quota | Set `GOOGLE_API_KEY=""` if persistent issues; council degrades to 2-model. |
| T4 routing fragile to provider failure | The added retry-with-backup-model logic in the multilingual node now safety-nets this. |

\newpage

## Chapter 30 — Data Analysis with pandas and Jupyter

> *A beginner-friendly workflow for getting from raw CSVs to the leaderboard tables that will appear in the thesis.*

### The Three Files Per Participant

After all 15 participants are run, you have (per participant Pxxx):

- `results/by_participant/Pxxx/subject_run_<ts>.json` (raw interaction log, 20 rows)
- `results/by_participant/Pxxx/subject_run_<ts>.csv` (same data, flat)
- `results/by_participant/Pxxx/questionnaire.json` (Likert + Godspeed + pairwise)

Plus the global `results/interactions_<date>.jsonl` (server-side append-only log of every interaction across all participants).

### Loading Everything Into pandas

Create a Jupyter notebook at `notebooks/analysis.ipynb` and start with:

```python
import pandas as pd
import json
from pathlib import Path

# Load all interaction CSVs from all participants
participants = ["P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008",
                "P009", "P010", "P011", "P012", "P013", "P014", "P015"]

dfs = []
for p in participants:
    base = Path(f"results/by_participant/{p}")
    csv_path = next(base.glob("subject_run_*.csv"))
    df = pd.read_csv(csv_path)
    df["participant"] = p
    dfs.append(df)
interactions = pd.concat(dfs, ignore_index=True)

# Load all questionnaire JSONs
likert_rows = []
for p in participants:
    qpath = Path(f"results/by_participant/{p}/questionnaire.json")
    qdata = json.loads(qpath.read_text())
    for q in qdata["interaction_responses"]:
        likert_rows.append({**q, "participant": p})
likert = pd.DataFrame(likert_rows)
```

### Per-Condition Summary Tables

```python
# Mean Likert per condition (the headline table)
print(likert.groupby("condition")[
    ["accuracy", "naturalness", "trust", "gesture_appropriateness", "response_speed"]
].mean().round(2))
```

Expected output shape:

```
            accuracy  naturalness  trust  gesture_appropriateness  response_speed
condition
A               5.93         5.27   5.80                     5.13            5.93
B               4.87         4.93   4.60                     4.93            3.80
C               6.13         5.93   6.20                     5.40            5.67
D               5.67         5.13   6.00                     5.27            4.27
E               4.60         5.20   4.20                     5.07            5.87
```

(Exact numbers will of course depend on the actual study.)

### Statistical Tests

```python
from scipy import stats

# H3 — RAG vs no-RAG paired t-test (A vs E within each participant)
pivot = likert.pivot_table(
    index="participant", columns="condition", values="accuracy")
t, p_val = stats.ttest_rel(pivot["A"], pivot["E"])
print(f"H3 paired t-test: t={t:.3f}, p={p_val:.4f}")

# H2 — Condition C vs A and B
print("H2:")
t, p = stats.ttest_rel(pivot["C"], pivot["A"])
print(f"  C vs A: t={t:.3f}, p={p:.4f}")
t, p = stats.ttest_rel(pivot["C"], pivot["B"])
print(f"  C vs B: t={t:.3f}, p={p:.4f}")

# Repeated-measures ANOVA across all five conditions
from statsmodels.stats.anova import AnovaRM
rm = AnovaRM(likert, depvar="accuracy", subject="participant",
             within=["condition"]).fit()
print(rm.summary())
```

### Building the Embodied LLM Leaderboard

```python
# Load pairwise preferences and build ELO
from omnillm.scorer import EloScorer

scorer = EloScorer()
for p in participants:
    qpath = Path(f"results/by_participant/{p}/questionnaire.json")
    qdata = json.loads(qpath.read_text())
    for pref in qdata["pairwise_preferences"]:
        scorer.update_pairwise(
            model_a=pref["condition_a"],
            model_b=pref["condition_b"],
            winner=pref["preferred"],
            category="embodied_hri",
        )

print(scorer.leaderboard(category="embodied_hri"))
```

### Latency, Cost, and Faithfulness

```python
# Mean latency by condition × task type
print(interactions.groupby(["condition", "task"])["latency_s"].mean().unstack())

# Total cost by condition (over all 15 participants × 4 tasks)
print(interactions.groupby("condition")["cost_usd"].sum().round(4))

# RAG faithfulness by condition (only A, B, C, D — E has no RAG)
faithful = interactions[interactions["condition"] != "E"]
print(faithful.groupby("condition")["rag_faithfulness"].mean().round(3))
```

### Visualisations

```python
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_style("whitegrid")

# Likert means with 95% CI per condition × item
fig, ax = plt.subplots(figsize=(10, 5))
sns.barplot(
    data=likert.melt(
        id_vars=["participant", "condition"],
        value_vars=["accuracy", "naturalness", "trust",
                    "gesture_appropriateness", "response_speed"],
        var_name="item", value_name="score"),
    x="item", y="score", hue="condition", ax=ax,
    errorbar=("ci", 95))
ax.set_ylim(1, 7)
ax.set_title("Mean Likert per condition × item (95% CI)")
plt.tight_layout()
plt.savefig("results/figs/likert_by_condition.png", dpi=150)
```

### What to Put in the Thesis

For the thesis methods/results chapters:

1. **A descriptive table** (mean ± SD per condition × Likert item)
2. **The repeated-measures ANOVA** result for the omnibus condition effect
3. **The three hypothesis tests** (H1, H2, H3) with their effect sizes and p-values
4. **The embodied_hri ELO leaderboard** with 95% bootstrap CIs around each rating
5. **Per-task-type analysis** showing how the condition effect varies across T1–T4
6. **A latency-cost-quality figure** showing where each condition sits in 3-space
7. **Qualitative analysis** of the open-ended Likert comments and exit-interview transcripts

### A One-Page Reproducibility Checklist for the Reader

Anyone replicating this work needs:

- This repository at the May 2026 commit hash (see git log)
- A real or virtual Pepper
- 15 participants matching the inclusion criteria
- API keys for the listed providers (or Ollama for purely local replication)
- The Latin-square assignment table from Chapter 25
- ~30 hours total experimenter time (10h setup + 15h sessions + 5h analysis)

The repository includes a `notebooks/analysis.ipynb` template that loads the canonical `results/` layout and produces all the tables/figures listed above out of the box.

\newpage
