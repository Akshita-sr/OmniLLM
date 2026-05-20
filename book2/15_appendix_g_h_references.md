\newpage

# Appendix G — External Resources: Papers, Libraries, Repositories (Annotated)

> *Every external work cited in this book. Organised by topic, with one-paragraph annotations on those that influenced specific design choices. Author/year format throughout; full bibliographic entries follow.*

\newpage

## G.1 — Pepper Robot: The Platform Itself

**Pandey & Gelin (2018) — "A Mass-Produced Sociable Humanoid Robot: Pepper, The First Machine of Its Kind"** — *IEEE Robotics & Automation Magazine.* The canonical introduction to Pepper as a research platform. Authors are from SoftBank/Aldebaran. Read this first if you have never used Pepper.

**Lafaye, Gouaillier & Wieber (2014) — "Linear model predictive control of the locomotion of Pepper, a humanoid robot with omnidirectional wheels"** — *IEEE Humanoids.* The original Pepper locomotion-control paper. Background reading.

**Mishra et al. (2024) — "An Exploration of the Pepper Robot's Capabilities: Unveiling Its Potential"** — *Applied Sciences.* Recent, very useful catalogue of Pepper's strengths and weaknesses (microphones, depth sensor, NAOmark detection, etc.). Strongly recommended for anyone deploying Pepper today.

**Gardecki & Podpora (2017) — "Experience from the operation of the Pepper humanoid robots"** — *IEEE PAEE.* Practitioner's report on Pepper's quirks; reads like a senior developer's blog. Useful gotcha reference.

**Bal, Tekerek, Gök & Şimşir (2024) — "Human Robot Interaction with Social Humanoid Robots"** — *El-Cezeri Fen ve Mühendislik Dergisi.* Recent overview of Pepper-specific HRI patterns.

**Sugiyama (2021) — "The Apparatgeist of Pepper-kun: An Exploration of Emerging Cultural Meanings of a Social Robot in Japan"** — book chapter. Cultural-context paper. Relevant to multi-site replication arguments.

\newpage

## G.2 — Pepper for Specific HRI Use Cases

### Receptionist / Front-Desk / Tour Guide

**Suddrey, Jacobson & Ward (2018) — "Enabling a Pepper Robot to provide Automated and Interactive Tours of a Robotics Laboratory"** — *arXiv*. Closest published cousin of OmniLLM's lab-tour scenario. Single-LLM-replacement architecture.

**Gardecki, Podpora, Beniak & Klin (2018) — "The Pepper Humanoid Robot in Front Desk Application"** — *IEEE PAEE.* Reception desk with NLU. Pre-LLM era; useful baseline.

**Draghici, Dobre, Misaros & Stan (2022) — "Development of a Human Service Robot Application Using Pepper Robot as a Museum Guide"** — *IEEE AQTR.* Museum guide use case.

**De Gauquier et al. (2018) — "Humanoid Robot Pepper at a Belgian Chocolate Shop"** — *HRI '18 Companion.* Real-world retail deployment.

**Aaltonen, Arvola, Heikkilä & Lammi (2017) — "Hello Pepper, May I Tickle You? Children's and Adults' Responses to an Entertainment Robot at a Shopping Mall"** — *HRI '17 Companion.* Field observation; first-encounter dynamics.

### Healthcare / Therapy

**Carros et al. (2022) — "Care Workers Making Use of Robots: Results of a Three-Month Study on Human-Robot Interaction within a Care Home"** — *CHI 2022.* Three-month longitudinal study with Pepper. The benchmark for "long-term deployment" research (cited in Chapter 33).

**Betriana et al. (2022) — "Characteristics of interactive communication between Pepper robot, patients with schizophrenia, and healthy persons"** — *Belitung Nursing Journal.* Schizophrenia patients interacting with Pepper. Methodologically interesting.

**Blindheim, Solberg, Hameed & Alnes (2023) — "Promoting activity in long-term care facilities with the social robot Pepper: a pilot study"** — *Informatics for Health and Social Care.* Activity-promotion intervention.

**Castellano, De Carolis, Macchiarulo & Pino (2022) — "Detecting Emotions During Cognitive Stimulation Training with the Pepper Robot"** — *Human-Friendly Robotics 2021.* Cognitive-stimulation therapy.

**Ampadu, Rokohl, Mahmood, Reichenbach & Huebner (2022) — "InjectMeAI—Software Module of an Autonomous Injection Humanoid"** — *Sensors.* Pepper performing autonomous injection (proof-of-concept). QiSDK + Python wrapper architecture.

**Uluer, Kose, Oz, Aydinalev & Barkana (2020) — "Towards An Affective Robot Companion for Audiology Rehabilitation: How Does Pepper Feel Today?"** — *IEEE RO-MAN.* Affective audiology companion.

**Stommel, de Rijk & Boumans (2022) — "'Pepper, what do you mean?' Miscommunication and repair in robot-led survey interaction"** — *IEEE RO-MAN.* Closely related to OmniLLM's experimental protocol: Pepper conducts surveys with elderly people. Documents misunderstanding patterns we should expect.

### Education / Tutoring

**Lehmann & Rossi (2019) — "Social Robots in Educational Contexts: Developing an Application in Enactive Didactics"** — *Journal of e-Learning.* Educational HRI overview.

**Pigureddu & Gena (2023) — "Using the power of memes: The Pepper Robot as a communicative facilitator for autistic children"** — *arXiv.* Autism-spectrum-focused communication study.

**De Carolis, D'Errico & Rossano (2021) — "Pepper as a Storyteller: Exploring the Effect of Human vs. Robot Voice on Children's Emotional Experience"** — *INTERACT 2021.* Pepper voice vs human voice for storytelling.

**Matulík, Vavrečka & Vidovićová (2020) — "Edutainment Software for the Pepper Robot"** — *ISCSIC 2020.* Education + entertainment chatbot architecture.

**Knežević et al. (2023) — "Physical Education Exercises Validation Through Child-Humanoid Robot Interaction"** — *Advances in Service and Industrial Robotics.* Pepper as exercise instructor.

**Yun et al. (2022) — "AI-Based Open-Source Gesture Retargeting to a Humanoid Teaching Robot"** — *AIED 2022.* Teacher-gesture retargeting to Pepper. Relevant to OmniLLM's gesture planner: validates that gesture-speech sync matters.

**Yoshino & Zhang (2020) — "Evaluation of Teaching Assistant Robot for Programming Classes"** — *Int. J. Information & Education Technology.* TA-robot evaluation.

\newpage

## G.3 — Pepper + LLMs (the most directly relevant cluster)

These are the closest published comparisons to OmniLLM. Most are post-2024.

**Hafez, Raneem Abdel — "Enhancing Human-Robot Interaction: Integrating Large Language Models and Advanced Speech Recognition into the Pepper Robot."** Recent thesis-level work integrating multiple LLMs and ASR into Pepper. Two-phase architecture (web server + Pepper). Closest in spirit to OmniLLM; OmniLLM extends with full benchmark + smart routing + agent graph.

**Mauliana, Ashok, Czernochowski & Berns (2025) — "Exploring LLM-powered multi-session human-robot interactions with university students"** — *Frontiers in Robotics and AI.* Open-domain multi-session university-student LLM dialogues with Pepper. Strongly relevant; multi-session study design that OmniLLM could replicate.

**Rahimi, Bahaj, Abrini, Khoramshahi, Ghogho & Chetouani (2025) — "USER-VLM 360: Personalized Vision Language Models with User-aware Tuning for Social Human-Robot Interactions"** — *arXiv 2502.10636.* Vision-language model + Pepper. Future-work direction for OmniLLM (Chapter 33).

**Dogan, Ozyurt, Cinar & Gunes (2025) — "GRACE: Generating Socially Appropriate Robot Actions Leveraging LLMs and Human Explanations"** — *ICRA 2025.* LLM-generated robot actions with social-appropriateness scoring. Closely relevant for the safety/etiquette dimension of OmniLLM's responses.

**Billing (2023) — "Language Models for Human-Robot Interaction"** — *HRI 2023 (extended abstract).* Conceptual position paper that motivated much of the subsequent work in this cluster.

**Sun et al. (2025) — "Trinity: A Modular Humanoid Robot AI System"** — *arXiv.* Modular humanoid AI architecture combining RL + LLM + VLM. Architectural counterpoint to OmniLLM (Trinity is more vertically integrated; OmniLLM is more horizontally modular).

\newpage

## G.4 — LLM Benchmarking and Evaluation

**Hendrycks, Burns, Basart, Zou, Mazeika, Song & Steinhardt (2021) — "Measuring Massive Multitask Language Understanding"** — *ICLR 2021.* MMLU benchmark. The reference text-only knowledge benchmark; H1 contrasts the *embodied* leaderboard against MMLU ranking.

**Chen et al. (2021) — "Evaluating Large Language Models Trained on Code"** — *arXiv 2107.03374.* HumanEval benchmark + Codex.

**Cobbe et al. (2021) — "Training Verifiers to Solve Math Word Problems"** — *arXiv 2110.14168.* GSM8K benchmark.

**Zhou et al. (2023) — "Instruction-Following Evaluation for Large Language Models"** — *arXiv 2311.07911.* IFEval — verifiable-instruction benchmark.

**Lin, Hilton & Evans (2022) — "TruthfulQA: Measuring How Models Mimic Human Falsehoods"** — *ACL 2022.* TruthfulQA benchmark.

**White et al. (2025) — "LiveBench: A Challenging, Contamination-Limited LLM Benchmark"** — *ICLR 2025.* LiveBench — contamination-resistant rotating benchmark. Methodologically influential for OmniLLM's "compare across rolling benchmark snapshots" approach.

**Chen et al. (2025) — "Dynamic Benchmarking of Reasoning Capabilities in Code Large Language Models Under Data Contamination"** — *ICML 2025.* Contamination-aware dynamic benchmarking.

**Mousavi et al. (2025) — "Garbage In, Reasoning Out? Why Benchmark Scores are Unreliable and What to Do About It"** — *arXiv.* Audits common reasoning benchmarks for design flaws. Worth reading before treating any single benchmark as authoritative.

**Li, Guerin & Lin (2024) — "An Open Source Data Contamination Report for Large Language Models"** — *arXiv 2310.17589.* Contamination report across 15 LLMs.

**Xu, Guan, Greene & Kechadi (2024) — "Benchmark Data Contamination of Large Language Models: A Survey"** — *arXiv.* Survey of benchmark contamination.

**Chen, Chen, Li et al. (2025) — "Recent Advances in Large Language Model Benchmarks against Data Contamination: From Static to Dynamic Evaluation"** — *arXiv 2502.17521.* Static-to-dynamic benchmarking survey.

**Liu, Iter, Xu, Wang, Xu & Zhu (2023) — "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment"** — *arXiv 2303.16634.* Establishes that LLM-as-judge with chain-of-thought and form-filling produces evaluations strongly correlated with human judgments. **Foundational for OmniLLM's evaluator.py.**

**Zheng, Chiang, Sheng et al. (2023) — "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"** — *NeurIPS 2023 Datasets & Benchmarks.* The position-bias swap-and-aggregate methodology that OmniLLM's pairwise judge uses.

**Chiang et al. (2024) — "Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference"** — *arXiv 2403.04132.* Chatbot Arena. **The direct inspiration for the *Embodied LLM Arena* name and the pairwise-preference ELO methodology.**

**Li, Dong, Chen et al. (2024) — "LLMs-as-Judges: A Comprehensive Survey on LLM-based Evaluation Methods"** — *arXiv.* Comprehensive recent survey.

**Guan, Wang, Bian et al. (2026) — "Evaluating LLM-based Agents for Multi-Turn Conversations: A Survey"** — *arXiv 2503.22458.* Multi-turn agent evaluation survey.

\newpage

## G.5 — LLM Routing, Ensembles, and Multi-Model Architecture

**Ong, Almahairi, Wu et al. (2025) — "RouteLLM: Learning to Route LLMs with Preference Data"** — *arXiv 2406.18665.* Learned routing between a stronger and weaker LLM. **The published-baseline methodology that OmniLLM's smart router extends.**

**Chen, Zaharia & Zou (2023) — "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance"** — *arXiv 2305.05176.* Three cost-reduction strategies: prompt adaptation, LLM approximation, LLM cascade. Influences OmniLLM's `LOWEST_COST` and `BEST_VALUE` strategies.

**Chen, Li, Chen et al. (2025) — "Harnessing Multiple Large Language Models: A Survey on LLM Ensemble"** — *arXiv 2502.18036.* Comprehensive ensemble survey. Taxonomy of ensemble methods that overlaps with OmniLLM's consensus engine.

**Kallem (2026) — "Learning to Trust the Crowd: A Multi-Model Consensus Reasoning Engine for Large Language Models"** — *arXiv 2601.07245.* Recent multi-model consensus paper. Findings on diminishing returns past 4 models inform Chapter 11.3's "why 3 not 5" argument.

**Fedus, Zoph & Shazeer (2022) — "Switch Transformers"** — *JMLR.* Mixture-of-experts at scale. Architectural background for why multi-model approaches are interesting at all.

**LiteLLM documentation — Router/Load-Balancing.** BerriAI's docs on `litellm`'s built-in routing primitives. Useful for understanding what the underlying library does.

**Latitude blog (2024) — "Dynamic LLM Routing: Tools and Frameworks."** Industry-perspective overview of LLM-routing tooling as of late 2024.

\newpage

## G.6 — Retrieval-Augmented Generation (RAG)

**Lewis et al. (2020) — "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"** — *NeurIPS 2020.* The original RAG paper.

**Karpukhin et al. (2020) — "Dense Passage Retrieval for Open-Domain Question Answering"** — *EMNLP 2020.* The dense-retrieval methodology used by sentence-transformers + ChromaDB.

**Es, James, Espinosa-Anke & Schockaert (2023) — "RAGAS: Automated Evaluation of Retrieval-Augmented Generation"** — *EACL 2024 demo.* RAG evaluation framework. Closely related to OmniLLM's faithfulness scoring.

\newpage

## G.7 — Human-Robot Interaction: Methodology

**Bartneck, Kulić, Croft & Zoghbi (2009) — "Measurement instruments for the anthropomorphism, animacy, likeability, perceived intelligence, and perceived safety of robots"** — *International Journal of Social Robotics.* **The Godspeed Questionnaire.** Standard HRI evaluation; used in OmniLLM (Chapter 27).

**Tabrez, Luebbers & Hayes (2020) — "A Survey of Mental Modeling Techniques in Human-Robot Teaming"** — *Current Robotics Reports.* Mental-model survey. Background for HRI theoretical framing.

**Bonarini (2020) — "Communication in Human-Robot Interaction"** — *Current Robotics Reports.* Multi-modal communication overview. Informs OmniLLM's gesture-speech-LED fusion.

**Fox & Gambino (2021) — "Relationship Development with Humanoid Social Robots: Applying Interpersonal Theories to Human–Robot Interaction"** — *Cyberpsychology, Behavior, and Social Networking.* Theoretical critique of the "humans treat robots like humans" assumption.

**Robinson, Tidd, Campbell, Kulić & Corke (2023) — "Robotic Vision for Human-Robot Interaction and Collaboration: A Survey and Systematic Review"** — *ACM Transactions on HRI.* Systematic review of HRI/C.

**Safavi, Olikkal, Pei et al. (2024) — "Emerging Frontiers in Human–Robot Interaction"** — *Journal of Intelligent & Robotic Systems.* Recent survey across 3 frontiers: collaboration, BCI, affective.

**Gross & Krenn (2023) — "A Communicative Perspective on Human–Robot Collaboration in Industry"** — *International Journal of Social Robotics.* Multi-modal communication taxonomy. Influences OmniLLM's task taxonomy.

**Pathi, Kiselev & Loutfi (2022) — "Detecting Groups and Estimating F-Formations for Social Human-Robot Interactions"** — *MTI.* F-formation detection (relevant if a future OmniLLM variant supports group interactions).

**Gao, Yang, Frisk, Hernandez, Peters & Castellano (2019) — "Learning Socially Appropriate Robot Approaching Behavior Toward Groups using Deep Reinforcement Learning"** — *RO-MAN.* Pepper approaching groups; RL methodology.

**Stancioi et al. (2021) — "Developing an application based on the interaction between humans and the Pepper robot"** — *EMES.* Taxonomy paper.

\newpage

## G.8 — HRI: Ethics, Trust, Perception, and Long-Term Effects

**Etemad-Sajadi, Soussan & Schöpfer (2022) — "How Ethical Issues Raised by Human-Robot Interaction can Impact the Intention to use the Robot?"** — *International Journal of Social Robotics.* Influences OmniLLM's consent/GDPR discussion.

**Horstmann & Krämer (2022) — "The Fundamental Attribution Error in Human-Robot Interaction"** — *International Journal of Social Robotics.* Attribution of agency to robots; relevant to trust ratings.

**Rossi, Holthaus, Dautenhahn, Koay & Walters (2018) — "Getting to know Pepper: Effects of people's awareness of a robot's capabilities on their trust in the robot"** — *HAI '18.* Trust × capability awareness.

**Sancarlo (Søraa), Nyvoll, Grønvik & Serrano (2021) — "Children's perceptions of social robots: a study of the robots Pepper, AV1 and Tessa at Norwegian research fairs"** — *AI & SOCIETY.* Multi-robot children's-perception study. Cross-cultural relevance.

**Duradoni, Colombini, Russo & Guazzini (2021) — "Robotic Psychology: A PRISMA Systematic Review on Social-Robot-Based Interventions in Psychological Domains"** — *J.* Systematic review of robot-mediated psychological interventions.

**Ye & Robert (2023) — "Human Security Robot Interaction and Anthropomorphism: An Examination of Pepper, RAMSEE, and Knightscope Robots"** — *RO-MAN 2023.* Anthropomorphism comparison.

**Stock — "Can Service Robots Hamper Customer Anger and Aggression After a Service Failure?"** Service-failure recovery experiment with Pepper.

**Zantou & Vernon (2023) — "Culturally Sensitive Human-Robot Interaction: A Case Study with the Pepper Humanoid Robot"** — *IEEE AFRICON.* Culture-aware HRI with Pepper.

**Chiang, Bruno, Menicatti, Recchiuto & Sgorbissa (2019) — "Culture as a Sensor? A Novel Perspective on Human Activity Recognition"** — *International Journal of Social Robotics.* **From the host lab (Sgorbissa, DIBRIS).** Culture-aware HAR architecture.

**Tanveer, Sgorbissa & Thomas (2020) — "An IPM Approach to Multi-robot Cooperative Localization"** — *ICAR 2020.* **From the host lab.** Multi-robot cooperative localisation with Pepper.

**Ghişa et al. (2020) — "The AMIRO Social Robotics Framework: Deployment and Evaluation on the Pepper Robot"** — *Sensors.* Modular social-robotics framework on Pepper.

\newpage

## G.9 — HRI: Navigation, Vision, Perception (Background)

**Ardón, Kushibar & Peng (2019) — "A Hybrid SLAM and Object Recognition System for Pepper Robot"** — *arXiv.* SLAM + object recognition on Pepper.

**Gómez, Mattamala, Resink & Ruiz-del-Solar (2019) — "Visual SLAM-Based Localization and Navigation for Service Robots: The Pepper Case"** — *RoboCup 2018.* Visual SLAM for Pepper.

**Alhmiedat, Marei, Messoudi et al. (2023) — "A SLAM-Based Localization and Navigation System for Social Robots: The Pepper Robot Case"** — *Machines.* SLAM + ROS for Pepper.

**Bista, Ward & Corke (2021) — "Image-Based Indoor Topological Navigation with Collision Avoidance for Resource-Constrained Mobile Robots"** — *Journal of Intelligent & Robotic Systems.* Topological navigation on Pepper.

**Perera, Pereira, Connell & Veloso (2017) — "Setting Up Pepper For Autonomous Navigation And Personalized Interaction With Users"** — *arXiv.* ROS + IBM cloud + Pepper.

**Bauer, Escalona, Cruz, Cazorla & Gomez-Donoso (2019) — "Improving the 3D Perception of the Pepper Robot Using Depth Prediction from Monocular Frames"** — *Advances in Physical Agents.* Pepper depth-perception limitation documentation.

**Bauer, Escalona, Cruz, Cazorla & Gomez-Donoso (2019) — "Refining the Fusion of Pepper Robot and Estimated Depth Maps Method for Improved 3D Perception"** — *IEEE Access.* Depth-perception refinement.

**Khalil, Coronado & Venture (2021) — "Human Motion Retargeting to Pepper Humanoid Robot from Uncalibrated Videos Using Human Pose Estimation"** — *RO-MAN.* Motion retargeting.

**Reyes, Gómez, Norambuena & Ruiz-del-Solar (2019) — "Near Real-Time Object Recognition for Pepper Based on Deep Neural Networks Running on a Backpack"** — *RoboCup 2018.* Pepper + Jetson backpack for vision.

**Ilyas et al. (2019) — "Teaching Pepper Robot to Recognize Emotions of Traumatic Brain Injured Patients Using Deep Neural Networks"** — *RO-MAN 2019.* Emotion recognition for patient populations.

\newpage

## G.10 — HRI: Crowd / Group / Navigation Among People

**Zhang, Amirian, Eberle, Pettré, Holloway & Carlson (2022) — "From HRI to CRI: Crowd Robot Interaction—Understanding the Effect of Robots on Crowd Motion"** — *International Journal of Social Robotics.* Crowd dynamics around Pepper.

**Kobayashi, Sugimoto, Tanaka et al. (2022) — "Robot Navigation Based on Predicting of Human Interaction and its Reproducible Evaluation in a Densely Crowded Environment"** — *International Journal of Social Robotics.* Crowded-environment navigation.

**Lo, Yamane & Sugiyama (2019) — "Perception of Pedestrian Avoidance Strategies of a Self-Balancing Mobile Robot"** — *IROS.* Pedestrian-avoidance perception.

**Mavrogiannis, Hutchinson, Macdonald, Alves-Oliveira & Knepper (2019) — "Effects of Distinct Robot Navigation Strategies on Human Behavior in a Crowded Environment"** — *HRI.* Strategy-effect study.

**Genevois, Spalanzani & Laugier (2023) — "Interaction-aware Predictive Collision Detector for Human-aware Collision Avoidance"** — *IV.* Interaction-aware collision avoidance.

**Ma, Qiu, Chen, Yao, Chen & Ji (2022) — "Asymmetric Self-Play for Learning Robust Human-Robot Interaction on Crowd Navigation Tasks"** — *CECIT.* Self-play RL for crowd navigation.

\newpage

## G.11 — Software Libraries (the dependencies)

| Library | Purpose | License | Project URL |
|---|---|---|---|
| `litellm` (BerriAI) | Unified LLM gateway | MIT | https://github.com/BerriAI/litellm |
| `langgraph` | Stateful agent graph | MIT | https://github.com/langchain-ai/langgraph |
| `langchain` | LLM application framework | MIT | https://github.com/langchain-ai/langchain |
| `chromadb` | Embedded vector DB | Apache-2.0 | https://github.com/chroma-core/chroma |
| `sentence-transformers` | Sentence embeddings | Apache-2.0 | https://github.com/UKPLab/sentence-transformers |
| `openai-whisper` | Speech-to-text | MIT | https://github.com/openai/whisper |
| `aiohttp` | Async HTTP client/server | Apache-2.0 | https://github.com/aio-libs/aiohttp |
| `flask` | HTTP server | BSD-3 | https://github.com/pallets/flask |
| `click` | CLI framework | BSD-3 | https://github.com/pallets/click |
| `rich` | Terminal rendering | MIT | https://github.com/Textualize/rich |
| `pytest` | Testing | MIT | https://github.com/pytest-dev/pytest |
| `xhtml2pdf` | HTML → PDF | Apache-2.0 | https://github.com/xhtml2pdf/xhtml2pdf |
| `reportlab` | PDF primitives | BSD-3 | https://www.reportlab.com/opensource/ |
| `markdown` | Markdown → HTML | BSD-3 | https://github.com/Python-Markdown/markdown |
| `pypdf` | PDF text extraction | BSD-3 | https://github.com/py-pdf/pypdf |
| `langdetect` | Backup language detection | Apache-2.0 | https://github.com/Mimino666/langdetect |
| `pyyaml` | YAML parser | MIT | https://github.com/yaml/pyyaml |

NAOqi Python 2.7 SDK is proprietary; obtained from SoftBank's developer portal subject to their EULA. Choregraphe is similarly licensed.

\newpage

## G.12 — Reference Implementations / Curated Awesome-Lists

**GT-RIPL/Awesome-LLM-Robotics** — comprehensive curated list of LLM-in-robotics papers, code, and websites. URL: https://github.com/GT-RIPL/Awesome-LLM-Robotics.

**junchenzhi/Awesome-LLM-Ensemble** — curated list accompanying Chen et al.'s LLM Ensemble survey. URL: https://github.com/junchenzhi/Awesome-LLM-Ensemble.

**LiteLLM Router docs.** Direct reference for the load-balancing primitives OmniLLM's smart router is built on top of.

**Open LLM Leaderboard (Hugging Face Spaces).** Public text-only LLM leaderboard. Reference point for H1.

**LiveBench (livebench.ai).** Rolling text-only benchmark. Reference for current SOTA per-axis.

**LMSYS Org / Chatbot Arena.** The text-only counterpart to the Embodied LLM Arena.

\newpage

## G.13 — Closely Related: Pepper Toolkits / Bridges

**Ganal, Siol & Lugrin (2023) — "PePUT: A Unity Toolkit for the Social Robot Pepper"** — *RO-MAN.* Unity-based Pepper toolkit. Architectural cousin of OmniLLM's bridge.

**McColl, Estivill-Castro, Gilmore, McColl & Hexel (2022) — "Enabling Modern Application Development with Swift on the Nao/Pepper Robots"** — *RoboCup 2021.* Swift-on-Pepper toolkit. Demonstrates that the Python-2.7 trap is real and others bridge around it differently.

**Pot, Monceaux, Gelin & Maisonnier (2009) — "Choregraphe: a graphical tool for humanoid robot programming"** — *RO-MAN.* The original Choregraphe paper.

\newpage

# Appendix H — Pepper-LLM Integration Survey — The State of the Field, May 2026

> *A short literature survey of the post-2023 cluster of papers integrating LLMs into Pepper. Written for the thesis examiner who wants a quick orientation in the field.*

\newpage

## H.1 — The Landscape

As of May 2026, published work integrating LLMs into Pepper specifically falls into roughly five clusters:

| Cluster | Representative work | Position w.r.t. OmniLLM |
|---|---|---|
| **Single-LLM replacement of legacy NLU** | Hafez (2024); Mauliana et al. (2025) | Closest baseline. OmniLLM extends with multi-model + smart routing. |
| **Multimodal (vision + language)** | Rahimi et al. (2025) USER-VLM 360 | Vision input we do not currently use. Future direction (Chapter 33). |
| **Socially-appropriate action generation** | Dogan et al. (2025) GRACE | Safety/etiquette filter. Future direction (Chapter 32). |
| **Conceptual / position pieces** | Billing (2023) | Foundational arguments. We cite these to frame the gap. |
| **Survey / vision-papers** | Sun et al. (2025) Trinity, Safavi et al. (2024) | Architectural overviews. OmniLLM is one instance of the pattern. |

## H.2 — What All Five Clusters Have in Common

- **Single LLM per system.** No prior published work — to the author's knowledge — compares multiple LLMs as interchangeable backends in the same Pepper deployment. **This is the gap OmniLLM fills.**
- **Single-site, often single-session.** Generalisation across labs and across sessions is rarely tested.
- **Text-or-judge evaluation.** Few papers cleanly distinguish text-only evaluation from embodied evaluation.
- **No RAG-vs-no-RAG isolation.** RAG is either present or absent throughout; few papers run the within-subject RAG-off control that H3 requires.

## H.3 — OmniLLM's Three Concrete Contributions

1. **A reproducible methodology for comparing N LLMs as social-robot brains.** The 5×4 within-subjects design, the Latin-square counterbalancing, the questionnaire instrument, and the open codebase together form a replicable pipeline. Any lab with a Pepper can run the same protocol.
2. **The Embodied LLM Leaderboard.** The first ELO-ranked leaderboard of LLMs by their performance as social-robot brains. Tested H1 (embodied vs text-only ranking differ).
3. **The smart-routing condition.** No prior work has tested *dynamic per-task routing* in live HRI. Condition C provides the first such data point.

## H.4 — Methodological Choices to Defend

A thesis examiner is likely to challenge:

| Challenge | Defence |
|---|---|
| *N=15 is small.* | Power analysis suffices for the within-subjects ANOVA (Chapter 23). Future replication explicitly proposed (Chapter 33). |
| *Single-site limits external validity.* | Acknowledged (Chapter 31). The contribution is methodological + initial empirical, not "this is the final embodied LLM ranking." |
| *Why these four task types and not others?* | T1–T4 mirror the standard HRI dialogue-act taxonomy (Chapter 23.4). Robust to adding more task types in future work. |
| *Why not include autonomous navigation?* | Out of scope (Chapter 4). Pepper-specific limitation. Future scope (Chapter 33). |
| *The cloud LLMs see participant text.* | Disclosed in consent form (Chapter 28). Future variant uses Ollama-only (Chapter 33). |
| *LLM-as-judge has self-preference bias.* | Acknowledged (Chapter 11.4). Cross-judge robustness check available; thesis's primary outcome is human Likert, not judge score. |
| *Why Pepper specifically?* | Citation density + lab availability + ready-made social affordances (Chapter 2). |

## H.5 — A Forward View

OmniLLM is the **first generation** of multi-LLM embodied benchmarking. By 2030, the author expects:

- The Embodied LLM Leaderboard (or its successor) to be the standard reference, just as Chatbot Arena is for text today.
- Models tested *as multi-modal embodied agents* will diverge sharply from models tested *as text chatbots*.
- The cost of running the full benchmark to fall by an order of magnitude (smaller, faster LLMs hitting the same quality).
- Counterbalancing automation, ethics-protocol templating, and questionnaire delivery will all be commodity tools.

This thesis is a snapshot of where the field is in May 2026. The codebase is built to be re-runnable in May 2027, in May 2028, and so on — with the same protocol, against the LLMs current at that date.

\newpage
