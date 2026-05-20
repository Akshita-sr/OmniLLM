\newpage

# Part VI — Future Scope & Improvements

> *Honest assessment first, then concrete next steps. This Part is short because the project is meant to ship and be used, not be eternally redesigned.*

\newpage

## Chapter 31 — Current Limitations — An Honest Assessment

### At a Glance

OmniLLM as of May 2026 is a complete, working, peer-reviewable system for benchmarking LLMs through embodied HRI with a single robot, single lab, English-and-Italian, and ~15 participants. It is **not** a generic platform for arbitrary social-robot deployment. This chapter catalogues the limitations — hardware, software, methodological, and scope — that a careful reader (especially a thesis examiner) will want to see acknowledged.

### Hardware Limitations

| Limitation | Why it matters | Workaround |
|---|---|---|
| **Pepper cannot walk.** Wheels, not legs. Stairs are fatal. | T2 (Navigation) tasks must remain *informational* ("Room 305 is on the third floor") rather than *autonomous* ("let me take you there"). | Acceptable for our study; out of scope. Future work could integrate a wheelchair-class mobile base. |
| **Pepper's microphones are noisy** beyond ~2 metres in open-plan space. | Whisper transcription quality drops; VAD-triggered conversation flakes. | Use the touch trigger; ask participants to speak closer. |
| **Pepper's depth sensor is mediocre** in bright conditions. | Bauer et al. (2019) document poor 3D perception. | We do not depend on depth in this study; future vision-based extensions would. |
| **Pepper's on-board CPU is too weak for any modern LLM.** | We must use an off-board AI server. | This is the fundamental driver of the two-process design and is unlikely to change for Pepper. |
| **NAOqi 2.5 is the last released SDK version (2017).** | No upstream security patches; bug fixes by community only. | Treat the bridge layer as a stable contract; the AI side can be modernised without touching NAOqi. |
| **NAOqi animation library does not include all 100+ animations on every robot.** | Some gestures the planner picks may not exist on a given Pepper. | Either pre-install the missing animations via Choregraphe, or filter `_TASK_DEFAULT_GESTURES` to a verified subset. |

### Software Limitations

| Limitation | Detail |
|---|---|
| **Rule-based task classifier** has finite coverage. Out-of-distribution prompts ("can you predict tomorrow's weather?") default to T1 (info_retrieval), then RAG fails (the KB has no weather data), then the LLM hallucinates. | Mitigation: classifier confidence threshold + safety prompts in the LLM system prompt ("if you don't know, say so"). |
| **No streaming responses.** Pepper waits for the LLM to finish, then speaks the entire response. Conversational naturalness suffers on long answers. | LangGraph supports streaming; we have not wired it through to NAOqi yet. ~1 week of work in Topology 2. |
| **No multi-turn memory across interactions.** Each `/interact` call is independent; Pepper has no recollection of what the participant just asked. | The thesis design treats each interaction as an isolated trial — appropriate for the experimental study, limiting for a long-form deployment. Adding a conversation-history field to `HRIGraphState` is straightforward. |
| **English-tuned Whisper-base.** Italian, French, Spanish transcription is noticeably weaker. | Bump to Whisper-small (`model_size="small"`) — already configurable; ~3× CPU cost. |
| **LLM-as-judge bias** toward its own provider family is documented (Zheng et al. 2023). | The thesis's primary outcome is human Likert, not judge score; judge feeds only the leaderboard. Cross-judge robustness check (Claude-Haiku-judge variant) is in Appendix G. |
| **No image / vision-language modality.** Pepper's cameras are not used by any LLM call. | A multimodal extension (e.g. GPT-4o-vision sees the visitor's face → adjusts greeting tone) is plausible future work but out of current scope. |
| **No safety filtering** between LLM output and robot speech. Pepper says whatever the LLM produces. | For an adult-participant, voluntary-consent study with scripted prompts, the risk surface is small. A children's-deployment version *must* add a safety filter (e.g. OpenAI's Moderation API). |

### Methodological Limitations

| Limitation | Detail |
|---|---|
| **N = 15** is modest. Power analysis says it suffices for the planned within-subjects ANOVA, but generalisability across populations is limited. | The thesis explicitly frames this as a pilot/proof-of-concept; replication at scale (N ≥ 50) is recommended in the discussion section. |
| **Single lab, single institution.** All participants from UniGE / DIBRIS. Cultural and institutional homogeneity. | Multi-site replication needed before claiming external validity. Cf. Carros et al. 2022 (Germany), Mishra et al. 2024 (Norway), Castellano et al. 2022 (Italy) — all single-site. |
| **No long-term study.** Each participant interacts once for 30 minutes. Novelty and Hawthorne effects are documented in HRI (Bartneck et al. 2009) and likely inflate ratings. | Future work: deploy in a real lab-reception setting for 4+ weeks (cf. Carros et al. 2022, 3-month care-home study). |
| **The four task prompts are fixed.** Every participant gets the same Brignole-station, lab-hours, Pepper-room questions. | Repetition reduces variability but limits the question-space sampled. Future: random selection from a 20-prompt pool per task. |
| **The five conditions are LLM-source-only.** We don't vary prompt-engineering, sampling temperature, or speech speed across conditions. | Those are valuable but separate experiments. Sequential studies could systematically vary each. |
| **No control over participant familiarity with LLMs.** Some participants will be AI experts; others first-time users. | We collect this as a demographic item; secondary analysis can subset by familiarity. |
| **Cloud-LLM data flow is real.** Despite the GDPR-friendly setup, OpenAI/Anthropic/Google servers do see the (anonymous) prompts for ~30 days. | Documented in the consent form; not a methodological flaw, but a transparency obligation. |

### Scope Limitations

| Out of scope by design | Why |
|---|---|
| Autonomous locomotion / SLAM | Pepper's wheels + lab geometry make this impractical for the experimental study |
| Group / multi-party dialogue | Adds combinatorial complexity to counterbalancing; one-on-one is the standard HRI baseline |
| Long-form storytelling or task-completion (e.g. recipe assistance) | Different timescale (minutes), different evaluation metrics |
| Vision-based emotion recognition | Adds a second modality; orthogonal to the LLM-comparison hypothesis |
| Fine-tuning any LLM | Defeats the "compare models as-shipped" premise; out of scope; would require an order of magnitude more data |
| Production deployment / commercial use | The MIT licence permits it; the codebase is research-grade, not hardened-grade |

\newpage

## Chapter 32 — Short-Term Improvements (Next 3 Months)

> *Achievable additions while the experimental study is running. Each one is scoped at ≤ 1 week of work.*

### 1. Streaming Speech

Wire LangGraph's async streaming through to NAOqi. As tokens arrive from the LLM, push partial sentences to `ALAnimatedSpeech.say()`. Pepper starts speaking while the LLM is still generating.

**Effort:** ~5 days. **Win:** Perceived latency drops from ~1.5s to ~0.4s (time-to-first-spoken-word) on Condition A.

### 2. Conversation Memory

Add a `conversation_history: list[dict]` field to `HRIGraphState`. Push every (utterance, response) pair onto the history. Prepend the last 3 turns into the LLM's messages list.

**Effort:** ~2 days. **Win:** Multi-turn coherence ("you mentioned Room 305 earlier..."). Enables follow-up questions, which the current study explicitly forbids.

### 3. Safety Filter

Wrap every LLM output through `openai.Moderation.create()` (or a local toxicity classifier) before passing to the gesture planner. If the output trips the filter, substitute a polite "I'd rather not answer that" line.

**Effort:** ~2 days. **Win:** Required for any future children's-deployment variant.

### 4. Tablet-Based Questionnaire UI

Build a small HTML page that runs on Pepper's chest tablet. After each condition block, Pepper says *"Please tap the screen to rate this conversation"* and the participant fills the Likert items directly. The page POSTs to `/evaluate`.

**Effort:** ~5 days. **Win:** Eliminates manual paper-to-digital conversion; faster sessions; richer real-time data.

### 5. Real-Time Cost Display

Pin a small terminal-window with `omnillm costs --watch` (auto-refreshing every 30 seconds) during sessions. Lets the experimenter spot a runaway model immediately.

**Effort:** ~1 day. **Win:** Avoid waking up to a $50 OpenAI bill from a misconfigured loop.

### 6. Whisper Model Auto-Selection

Detect the participant's preferred language at session start (from the demographic questionnaire) and load the appropriate Whisper model size: base for native English, small for non-native or Romance languages.

**Effort:** ~2 days. **Win:** Better transcription quality for L2 English speakers.

### 7. Per-Participant Custom Prompts

Allow the experimenter to swap the four canonical prompts for a participant-specific set (e.g. if the visitor specifically wants directions to a *different* room). Driven by a YAML file: `config/participant_prompts/P003.yaml`.

**Effort:** ~2 days. **Win:** Richer interactions for participants who want to explore.

\newpage

## Chapter 33 — Medium-Term Research Directions (Next 12 Months)

> *Studies that extend OmniLLM's contribution. Each is ≥ a month of work but builds on the existing infrastructure.*

### 1. Multi-Site Replication

Deploy the same OmniLLM + Pepper stack at 3+ partner labs (e.g. another Italian institution, one German, one Japanese — to capture the cultural variation Soraa et al. 2021 found in children's perceptions). Run the same 5×4 design at each site with N=15 per site. Cross-site comparison answers: *do embodied LLM rankings generalise?*

**Effort:** ~6 months calendar time, ~30 person-hours of code work (deploying to a new site is mostly configuration).

### 2. Vision-Language Integration

Wire GPT-4o-vision (or Claude 3.5 Sonnet with vision) into the agent graph. Pepper's chest camera captures a frame at the start of each interaction; the LLM receives both the spoken question *and* a description of the visitor's appearance, body language, expression. Hypothesis: does multimodal grounding improve perceived "Pepper notices me"?

**Effort:** ~2 months. **Risk:** privacy — image data is more sensitive than text. Needs separate ethics approval.

### 3. Adaptive Routing

Currently the smart router (Condition C) routes by *task type*. A trained adaptive router could additionally use: previous-turn participant rating, current detected emotion (via Whisper prosody features), per-participant historical preference. The router becomes a small reinforcement-learning agent over time.

**Effort:** ~3 months. **Risk:** drifts the experimental design from "compare LLMs" toward "compare router policies"; the paper would need to be about the router, not the LLMs.

### 4. Long-Term Field Study

Deploy OmniLLM-Pepper at a real DIBRIS reception desk for 4–8 weeks. Log every interaction. Measure: (a) novelty decay, (b) staff acceptance, (c) operational reliability, (d) whether real visitors find the LLM-based responses more or less satisfactory than the (prior) keyword chatbot. This is the Carros et al. 2022 model applied to LLMs.

**Effort:** 4–8 months calendar. Heaviest item; biggest paper.

### 5. A Children's Variant — With Safety Filters

Re-do the study with school-age children visiting DIBRIS as part of outreach. Requires: stricter safety filter, child-tuned voice, simpler prompts, separate ethics approval. Compares to Soraa et al. 2021 and Pigureddu & Gena 2023.

**Effort:** ~4 months (ethics is the bottleneck).

### 6. Open Embodied LLM Leaderboard

After collecting data from multiple sites, publish a continuously-updated *Embodied LLM Arena* leaderboard at a public URL (analogous to Chatbot Arena). Anyone running an OmniLLM-Pepper deployment can POST their pairwise preferences via a documented API; the leaderboard updates in real time. The community grows the dataset.

**Effort:** ~3 months. **Long-term impact:** highest of any item on this list.

\newpage

## Chapter 34 — Long-Term Vision — Where Embodied LLM Research Is Going

> *Speculative but grounded. None of these are tomorrow's work; all are within the field's 5-year horizon.*

### LLMs as a Commodity Substrate for Robotics

In 2026, "which LLM should this robot use?" is still an interesting research question. By 2030, the author expects this question to be answered the way "which database engine should this web app use?" is answered today — by default-good choices (PostgreSQL, GPT-class) plus narrow specialty cases. The contribution of *this* line of research is to establish the comparison methodology *before* the LLM choice becomes commoditised, so future practitioners have a documented evaluation framework.

### The Death of "the LLM" as a Single Component

The future of embodied AI is not a single LLM but a **constellation** of specialised models: a small fast model for short turns, a large slow model for hard questions, a vision-language model for perception, a code-trained model for behaviour synthesis, an embedding model for memory, a moderation classifier for safety. OmniLLM's *unified gateway* + *smart router* architecture is the right shape for this future — but the routing decisions will need to factor in many more dimensions than the six current strategies.

### Robot Middleware Will Catch Up — But Slowly

NAOqi will eventually be replaced (probably by ROS 2). When that happens, OmniLLM's `RobotBridge` abstraction makes the transition cheap: write a `Ros2Bridge(RobotBridge)` subclass, leave everything else untouched. The *HTTP-and-JSON between two-Python-versions* pattern is a transitional artefact that will fade — but the *AI server / robot bridge / abstract robot interface* layering will persist.

### Embodiment Will Be Measured Differently

Today's embodied evaluation borrows tools (Likert, Godspeed, pairwise) from disembodied chatbot evaluation. The author expects new measurement instruments to emerge:

- **Multimodal engagement metrics** (gaze, prosody, posture mirroring) extracted automatically from video, removing self-report bias.
- **Real-world utility metrics** (did the visitor actually go to the room Pepper pointed to?) — currently impossible because we don't track participants after the session.
- **Long-term relationship metrics** — does the same participant come back to interact with Pepper voluntarily, weeks later?

OmniLLM's logging infrastructure (every interaction, every model, every timestamp) is well-positioned to feed any of these future analyses.

### The Reproducibility Bar Will Rise

Chatbot Arena demonstrated that open methodology + open leaderboards + open data accelerates a field. The HRI community is still mostly closed-data; each paper reports its own population, its own robot, its own prompts, with no shared benchmark. OmniLLM is a *step toward* a shared benchmark. The author hopes the next 2–3 years see an "Embodied Arena" emerge as the HRI counterpart to Chatbot Arena — with this thesis among the first contributions.

\newpage
