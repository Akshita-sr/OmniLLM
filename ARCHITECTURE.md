# OmniLLM -- Complete Architecture, Data Flow & Build Guide

> **Document purpose**: A single reference that explains *who talks to whom*, *what data travels where*, *which services are paid vs. free*, and *how to rebuild this project from scratch*.

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [Client-Server Topology](#2-client-server-topology)
3. [Endpoint Map -- Every Route, Source & Destination](#3-endpoint-map----every-route-source--destination)
4. [Data-Flow Walkthrough -- From Human Voice to Robot Speech](#4-data-flow-walkthrough----from-human-voice-to-robot-speech)
5. [LLM Provider Landscape -- Paid vs. Open-Source](#5-llm-provider-landscape----paid-vs-open-source)
6. [LangGraph Agent Pipeline -- Node-by-Node](#6-langgraph-agent-pipeline----node-by-node)
7. [RAG Pipeline Architecture](#7-rag-pipeline-architecture)
8. [Speech & Language Processing Flow](#8-speech--language-processing-flow)
9. [Experimental Conditions (A--E) -- Routing Architecture](#9-experimental-conditions-a-e----routing-architecture)
10. [Evaluation & Scoring Architecture](#10-evaluation--scoring-architecture)
11. [The "No Robot" Scenario -- How It Works Without Pepper](#11-the-no-robot-scenario----how-it-works-without-pepper)
12. [Building This Project From Scratch -- Chronological Guide](#12-building-this-project-from-scratch----chronological-guide)
13. [Complete Technology Stack Map](#13-complete-technology-stack-map)
14. [Full Prompt Lifecycle -- ASCII Diagram](#14-full-prompt-lifecycle----ascii-diagram)

---

## 1. High-Level System Architecture

```
+==========================================================================================================+
|                                        OmniLLM SYSTEM OVERVIEW                                           |
+==========================================================================================================+
|                                                                                                          |
|   HUMAN PARTICIPANT                    PEPPER ROBOT                         AI SERVER (Flask)             |
|   +-----------------+                  +-------------------+                +------------------------+    |
|   |                 |  speaks to       | NAOqi OS (Py 2.7) |  HTTP POST     | Python 3.x             |    |
|   |  "Where is      |  ------------->  | ALAudioDevice      | ----------->  | Flask :5000            |    |
|   |   Room 305?"   |                  | records WAV 16kHz  | /interact     |                        |    |
|   |                 |                  |                    |  JSON:        | +--------------------+ |    |
|   |                 |                  | naoqi_client.py    |  {audio:b64,  | | LangGraph Pipeline | |    |
|   |                 |                  |   (CLIENT)         |   condition,  | | (10-node DAG)      | |    |
|   |                 |                  |                    |   participant}| +--------------------+ |    |
|   |                 |                  |                    |               |         |               |    |
|   |                 |                  |                    |  <----------  |         v               |    |
|   |                 |  <-------------- | ALAnimatedSpeech   |  JSON:        | +--------------------+ |    |
|   |   hears Pepper  |  robot speaks   | ALLeds (eye color) |  {speech,     | | LiteLLM Gateway    | |    |
|   |   + sees gesture |  + gestures     | ALBehaviorManager  |   gesture,    | | (100+ providers)   | |    |
|   +-----------------+                  +-------------------+   emotion_led} | +--------------------+ |    |
|                                                                             +-----------|------------+    |
|                                                                                         |                 |
|                    +================================================================+   |                 |
|                    |                    EXTERNAL LLM PROVIDERS                       |   |                 |
|                    |  +----------+  +-----------+  +--------+  +----------+         |   |                 |
|                    |  | OpenAI   |  | Anthropic |  | Google |  | DeepSeek |         |<--+                 |
|                    |  | (paid)   |  | (paid)    |  | (paid) |  | (paid)   |         |                     |
|                    |  +----------+  +-----------+  +--------+  +----------+         |                     |
|                    |  +----------+  +-----------+  +--------+                       |                     |
|                    |  | Qwen     |  | Ollama    |  | Local  |                       |                     |
|                    |  | (paid)   |  | (FREE)    |  | Whisper|                       |                     |
|                    |  +----------+  +-----------+  | (FREE) |                       |                     |
|                    |                                +--------+                       |                     |
|                    +================================================================+                     |
+==========================================================================================================+
```

### Key Insight

The system has **three layers**:
1. **Physical Layer** -- The Pepper robot and human participant (real-world interaction)
2. **Orchestration Layer** -- The Flask AI server running the LangGraph pipeline (intelligence)
3. **Provider Layer** -- External LLM APIs + local models (the "brains")

---

## 2. Client-Server Topology

```
WHO IS THE CLIENT?              WHO IS THE SERVER?               PROTOCOL & FORMAT
==========================      ============================     ====================

Pepper Robot (NAOqi 2.7)   -->  Flask AI Server (Python 3.x)    HTTP/JSON on port 5000
  naoqi_client.py                 omnillm/server/app.py          Base64-encoded WAV audio
  Runs ON the robot               Runs on a laptop/PC/cloud      JSON response bodies
  Python 2.7 (NAOqi SDK)          Python 3.10+

Flask AI Server             -->  OpenAI API                      HTTPS/JSON
  via LiteLLM gateway              api.openai.com                 Bearer token auth
  omnillm/gateway.py               Paid cloud service             OpenAI chat format

Flask AI Server             -->  Anthropic API                   HTTPS/JSON
  via LiteLLM gateway              api.anthropic.com              x-api-key header
  omnillm/gateway.py               Paid cloud service             Anthropic messages format

Flask AI Server             -->  Google Gemini API               HTTPS/JSON
  via LiteLLM gateway              generativelanguage.googleapis  API key auth
  omnillm/gateway.py               Paid cloud service             Google AI format

Flask AI Server             -->  DeepSeek API                    HTTPS/JSON
  via LiteLLM gateway              api.deepseek.com               Bearer token auth
  omnillm/gateway.py               Paid (very cheap)              OpenAI-compatible format

Flask AI Server             -->  Qwen (DashScope) API            HTTPS/JSON
  via LiteLLM gateway              dashscope.aliyuncs.com         API key auth
  omnillm/gateway.py               Paid cloud service             OpenAI-compatible format

Flask AI Server             -->  Ollama (LOCAL)                   HTTP/JSON
  via LiteLLM gateway              localhost:11434                NO auth needed
  omnillm/gateway.py               FREE -- runs on your GPU       OpenAI-compatible format

Flask AI Server             -->  ChromaDB (LOCAL)                 In-process / HTTP
  omnillm/rag/pipeline.py          Embedded or localhost:8000     Python API / REST
                                    FREE -- local vector DB        Embedding vectors

Flask AI Server             -->  OpenAI Whisper API (optional)    HTTPS/multipart
  omnillm/robotics/whisper_stt.py   api.openai.com                Bearer token auth
                                    Paid cloud service             Audio file upload
```

### Summary Table

| Component | Role | Language | Runs On | Network |
|-----------|------|----------|---------|---------|
| `naoqi_client.py` | **Client** -- captures audio, executes robot actions | Python 2.7 | Pepper robot (NAOqi OS) | WiFi LAN |
| `app.py` (Flask) | **Server** -- orchestrates everything | Python 3.10+ | Laptop / PC / Cloud VM | localhost:5000 |
| LiteLLM | **Client** (inside Flask) -- calls LLM APIs | Python 3.10+ | Same as Flask server | Internet HTTPS |
| OpenAI, Anthropic, Google, DeepSeek, Qwen | **External Servers** -- paid LLM inference | - | Cloud data centers | Internet |
| Ollama | **Local Server** -- free LLM inference | Go + Python | Same machine or LAN | localhost:11434 |
| ChromaDB | **Local Server** -- vector database | Python | Same machine | In-process |
| Whisper (local) | **Library** -- free STT | Python | Same as Flask server | None (in-process) |

---

## 3. Endpoint Map -- Every Route, Source & Destination

### Flask AI Server Endpoints (app.py)

```
ENDPOINT          METHOD   SOURCE (who calls it)    PURPOSE                              RESPONSE FORMAT
================  =======  =======================  ===================================  ========================
/interact         POST     Pepper (naoqi_client.py)  Main HRI interaction loop            {speech, gesture,
                            OR any HTTP client        Audio/text in -> RobotAction out       emotion_led, metadata}

/transcribe       POST     Pepper or test client     Audio -> text (Whisper STT)          {text, language}

/evaluate         POST     Experimenter client       Log post-interaction questionnaire   {status: "ok"}
                                                      scores (Likert 1-7)

/health           GET      Monitoring / load balancer Liveness probe                      {status: "ok",
                                                                                            version: "0.1.0"}

/status           GET      Admin / debugging          Server configuration dump           {default_model, rag,
                                                                                            models[], langgraph}

/export           GET      Experimenter / analysis    Download all experiment logs         JSON / CSV file
```

### External API Endpoints Called BY OmniLLM

```
PROVIDER     ENDPOINT CALLED                              AUTH METHOD         COST MODEL
===========  ============================================  ==================  =================
OpenAI       POST https://api.openai.com/v1/chat/          Bearer OPENAI_      $2.50-$60 / 1M
              completions                                    API_KEY             output tokens

Anthropic    POST https://api.anthropic.com/v1/messages     x-api-key           $0.80-$75 / 1M
                                                             ANTHROPIC_API_KEY   output tokens

Google       POST generativelanguage.googleapis.com/v1/     API key param       $0.10-$10 / 1M
              models/{model}:generateContent                 GOOGLE_API_KEY      output tokens

DeepSeek     POST https://api.deepseek.com/v1/chat/         Bearer DEEPSEEK_    $0.27-$2.19 / 1M
              completions                                    API_KEY             output tokens

Qwen         POST https://dashscope.aliyuncs.com/           API key             $1.10-$3.40 / 1M
              compatible-mode/v1/chat/completions             QWEN_API_KEY        output tokens

Ollama       POST http://localhost:11434/v1/chat/            None (local)        $0.00 (FREE)
              completions                                                         Your GPU cost only

Whisper API  POST https://api.openai.com/v1/audio/           Bearer OPENAI_      ~$0.006 / minute
              transcriptions                                  API_KEY             of audio
```

---

## 4. Data-Flow Walkthrough -- From Human Voice to Robot Speech

This traces the **complete lifecycle** of a single interaction, byte by byte.

```
STEP  WHAT HAPPENS                          WHERE                    DATA FORMAT           FILE:LINE
====  ====================================  =======================  ====================  ===================
 1    Human speaks to Pepper                Physical world           Sound waves           --
 2    Pepper microphone captures audio      Pepper robot             16kHz WAV PCM         naoqi_client.py:196
 3    WAV encoded to base64 string          Pepper robot             base64 string         naoqi_client.py:228
 4    HTTP POST to /interact                Pepper -> Flask server   JSON body:            naoqi_client.py:233
                                                                      {audio: "UklGR...",
                                                                       participant_id,
                                                                       session_id,
                                                                       condition: "A"-"E",
                                                                       rag_enabled: bool}
 5    Flask receives, decodes base64        Flask server             bytes (WAV)           app.py:237
 6    LangGraph pipeline invoked            Flask server             HRIGraphState dict    app.py:260
 7    Node 1: Whisper transcribes audio     Flask server             "Where is Room 305?"  agent_graph.py:132
 8    Node 2: Language detected             Flask server             "en" (ISO 639-1)      agent_graph.py:157
 9    Node 3: Task classified               Flask server             "navigation" (T2)     agent_graph.py:175
10    Node 4: Conditional routing           Flask server             -> nav_rag node       agent_graph.py:497
11    Node 5: RAG retrieves context         Flask server             ChromaDB query ->     agent_graph.py:217
                                                                      [chunks with scores]
12    Node 5: LLM generates answer          Flask -> OpenAI/etc      HTTP POST to LLM     gateway.py:219
                                                                      {messages: [...]}
13    Node 5: Gesture planned               Flask server             "point_left" + LED    gesture_planner.py:112
14    Node 6: Smart router (Cond C/D)       Flask server             Model selection or    agent_graph.py:355
                                                                      consensus synthesis
15    Node 7: Action plan built             Flask server             {speech: "Room 305    agent_graph.py:430
                                                                       is on the left...",
                                                                       gesture: "point_left",
                                                                       emotion_led: "#00AAFF"}
16    Node 8: Interaction logged            Flask server             InteractionRecord     agent_graph.py:460
                                                                      -> JSON/CSV file
17    Flask returns JSON response           Flask -> Pepper          JSON: {speech,        app.py:275
                                                                      gesture, emotion_led,
                                                                      metadata: {model_id,
                                                                      latency_ms, cost_usd}}
18    Pepper sets eye LED color             Pepper robot             ALLeds.fadeRGB()      naoqi_client.py:278
19    Pepper triggers gesture behavior      Pepper robot             ALBehaviorManager     naoqi_client.py:282
                                                                      .runBehavior()
20    Pepper speaks response aloud          Pepper robot             ALAnimatedSpeech      naoqi_client.py:286
                                                                      .say(text)
21    Human hears response + sees gesture   Physical world           Sound + Motion        --
```

### Timing Budget

```
Target: < 3 seconds end-to-end for natural conversation feel

Whisper transcription:     ~200-500ms  (local) / ~300-800ms (API)
Language detection:         ~5-10ms    (rule-based, instant)
Task classification:       ~10-20ms   (rule-based) / ~500ms (LLM-based)
RAG retrieval:             ~50-200ms  (ChromaDB similarity search)
LLM generation:            ~500-2000ms (cloud) / ~1000-3000ms (local Ollama)
Gesture planning:          ~5-10ms    (rule-based, instant)
Network round-trip:        ~10-50ms   (LAN between Pepper and server)
────────────────────────────────────────
Total typical:             ~800-2500ms
```

---

## 5. LLM Provider Landscape -- Paid vs. Open-Source

```
+=============================================================================+
|                        LLM PROVIDER CLASSIFICATION                          |
+=============================================================================+
|                                                                             |
|  PAID CLOUD PROVIDERS (API key required, per-token billing)                 |
|  +-----------+  +------------+  +---------+  +----------+  +------+        |
|  | OpenAI    |  | Anthropic  |  | Google  |  | DeepSeek |  | Qwen |        |
|  | GPT-5.4   |  | Claude     |  | Gemini  |  | V3, R1   |  | 72B  |        |
|  | GPT-4o    |  | Opus 4.6   |  | 2.5 Pro |  |          |  |      |        |
|  | o1, o3    |  | Sonnet 4.6 |  | Flash   |  | Cheapest |  |      |        |
|  |           |  | Haiku 4.5  |  |         |  | cloud    |  |      |        |
|  | $$$$$     |  | $$$$       |  | $$      |  | $        |  | $$   |        |
|  +-----------+  +------------+  +---------+  +----------+  +------+        |
|                                                                             |
|  FREE / OPEN-SOURCE LOCAL (no API key, runs on your hardware)              |
|  +------------------------------------------------------------------+      |
|  | Ollama (localhost:11434)                                          |      |
|  |  +----------+  +-----------+  +----------+  +--------------+     |      |
|  |  | Llama 3  |  | Qwen 2.5  |  | Mistral  |  | DeepSeek-R1  |     |      |
|  |  | 8B       |  | 7B        |  | 7B       |  | 14B distill  |     |      |
|  |  +----------+  +-----------+  +----------+  +--------------+     |      |
|  |  Cost: $0.00 (only electricity for your GPU)                      |      |
|  |  Privacy: Data never leaves your machine                          |      |
|  +------------------------------------------------------------------+      |
|                                                                             |
|  FREE LOCAL TOOLS (no API key, bundled libraries)                          |
|  +------------------------------------------------------------------+      |
|  | OpenAI Whisper (local)  -- Speech-to-Text, runs on CPU/GPU       |      |
|  | ChromaDB (embedded)     -- Vector database, runs in-process       |      |
|  | langdetect (library)    -- Language detection, pure Python        |      |
|  +------------------------------------------------------------------+      |
+=============================================================================+
```

### Cost Comparison per 1 Million Output Tokens

| Provider | Model | Input Cost | Output Cost | Type |
|----------|-------|-----------|-------------|------|
| OpenAI | GPT-5.4 | $30.00 | $60.00 | Paid Cloud |
| OpenAI | GPT-4o | $2.50 | $10.00 | Paid Cloud |
| OpenAI | o3-mini | $1.10 | $4.40 | Paid Cloud |
| Anthropic | Claude Opus 4.6 | $15.00 | $75.00 | Paid Cloud |
| Anthropic | Claude Sonnet 4.6 | $3.00 | $15.00 | Paid Cloud |
| Anthropic | Claude Haiku 4.5 | $0.80 | $4.00 | Paid Cloud |
| Google | Gemini 2.5 Pro | $1.25 | $10.00 | Paid Cloud |
| Google | Gemini 2.5 Flash | $0.15 | $0.60 | Paid Cloud |
| Google | Gemini 2.0 Flash | $0.10 | $0.40 | Paid Cloud |
| DeepSeek | V3 | $0.27 | $1.10 | Paid Cloud |
| DeepSeek | R1 | $0.55 | $2.19 | Paid Cloud |
| Qwen | 2.5 72B | $1.10 | $3.40 | Paid Cloud |
| Ollama | Llama 3 8B | $0.00 | $0.00 | Free Local |
| Ollama | Qwen 2.5 7B | $0.00 | $0.00 | Free Local |
| Ollama | Mistral 7B | $0.00 | $0.00 | Free Local |
| Ollama | DeepSeek-R1 14B | $0.00 | $0.00 | Free Local |

---

## 6. LangGraph Agent Pipeline -- Node-by-Node

The core intelligence of OmniLLM is a **10-node directed acyclic graph (DAG)** built with LangGraph. Each node is a pure function that reads state, does work, and writes updated state.

```
                          +====================+
                          |      [START]        |
                          +=========|==========+
                                    |
                                    v
                     +------------------------------+
                     |   1. transcribe_audio         |
                     |   Whisper STT: bytes -> text  |
                     |   (skip if text-only input)   |
                     +--------------|---------------+
                                    |
                                    v
                     +------------------------------+
                     |   2. detect_language           |
                     |   Rule-based + n-gram ->      |
                     |   ISO 639-1 code ("en","fr")  |
                     +--------------|---------------+
                                    |
                                    v
                     +------------------------------+
                     |   3. classify_task             |
                     |   Keywords + patterns ->      |
                     |   T1/T2/T3/T4 + confidence    |
                     +--------------|---------------+
                                    |
                        +-----------+-----------+
                        |   CONDITIONAL BRANCH   |
                        |   (by task_type &      |
                        |    condition & rag)     |
                        +-----------+-----------+
                       /       |         |        \
                      v        v         v         v
              +--------+  +--------+  +--------+  +----------+
              | 4a. rag |  |4b. nav |  |4c.     |  |4d. multi |
              |         |  |  _rag  |  |direct  |  |lingual   |
              | T1 Info |  | T2 Nav |  |_llm    |  |_llm      |
              |Retrieval|  | + Dir  |  |T3 Chat |  |T4 Lang   |
              +----+---+  +---+----+  +---+----+  +----+-----+
                    \          |           |           /
                     \         |           |          /
                      v        v           v         v
                     +------------------------------+
                     |   5. smart_router             |
                     |   Cond A/B: pass-through      |
                     |   Cond C: SmartRouter.route()  |
                     |   Cond D: ConsensusEngine()   |
                     |   Cond E: pass-through (no RAG)|
                     +--------------|---------------+
                                    |
                                    v
                     +------------------------------+
                     |   6. generate_action_plan     |
                     |   Build RobotAction dict:     |
                     |   {speech, gesture, led_color}|
                     +--------------|---------------+
                                    |
                                    v
                     +------------------------------+
                     |   7. log_interaction           |
                     |   ExperimentLogger records:   |
                     |   model, latency, cost, RAG   |
                     |   metrics, task_type, etc.    |
                     +--------------|---------------+
                                    |
                                    v
                          +====================+
                          |       [END]         |
                          |  Return RobotAction |
                          +====================+
```

### State Object (flows through every node)

```python
HRIGraphState = {
    # Input (set at entry)
    "audio_bytes": bytes,           # Raw WAV from Pepper
    "utterance": str,               # Text (if text-only mode)
    "participant_id": str,          # e.g. "P001"
    "session_id": str,              # e.g. "S001-A"
    "condition": str,               # "A" | "B" | "C" | "D" | "E"
    "rag_enabled": bool,            # True for A-D, False for E

    # Intermediate (set by pipeline nodes)
    "detected_language": str,       # "en", "fr", "ja", ...
    "task_type": str,               # "info_retrieval" | "navigation" | "social_conversation" | "multilingual"
    "task_confidence": float,       # 0.0 - 1.0
    "rag_context": str,             # Retrieved context chunks
    "rag_chunks": list,             # DocumentChunk objects
    "rag_faithfulness": float,      # 0.0 - 1.0 (LLM-judged)

    # Output (read at exit)
    "response_text": str,           # "Room 305 is on your left..."
    "gesture": str,                 # "point_left"
    "led_color": str,               # "#00AAFF"
    "robot_action": dict,           # Final RobotAction
    "model_id": str,                # "openai-gpt4o-mini"
    "latency_ms": float,            # 1234.5
    "cost_usd": float,              # 0.0023
}
```

---

## 7. RAG Pipeline Architecture

```
+===================================================================================+
|                          RAG (Retrieval-Augmented Generation)                       |
+===================================================================================+
|                                                                                    |
|  INDEXING PHASE (happens once at server startup)                                   |
|  ============================================                                      |
|                                                                                    |
|  knowledge_base/                                                                   |
|    lab_info.txt  ----+                                                             |
|    visitor_profiles.csv  -+---> Text Extraction ---> Chunking (512 chars,          |
|    university_map.txt  ---+                          64 char overlap)               |
|    event_schedule.csv  ---+                              |                          |
|    research_projects.txt -+                              v                          |
|    faq.txt  ----+                                   Embedding Model                 |
|                                                     (sentence-transformers           |
|                                                      or ChromaDB default)           |
|                                                          |                          |
|                                                          v                          |
|                                                   +-------------+                   |
|                                                   |  ChromaDB    |                  |
|                                                   |  Vector Store |                 |
|                                                   |  (persistent)|                  |
|                                                   +-------------+                   |
|                                                                                    |
|  RETRIEVAL + GENERATION PHASE (happens per query)                                  |
|  ================================================                                  |
|                                                                                    |
|  User query: "Where is Room 305?"                                                  |
|       |                                                                            |
|       v                                                                            |
|  Embed query --> Similarity search in ChromaDB --> Top-k chunks (k=5)              |
|       |                                                                            |
|       v                                                                            |
|  Augmented prompt:                                                                 |
|  "Context: [chunk1: Building A floor 3...] [chunk2: Room 305 is near...]           |
|   Question: Where is Room 305?                                                     |
|   Answer based ONLY on the context above."                                         |
|       |                                                                            |
|       v                                                                            |
|  LLM generates answer (via LiteLLM Gateway)                                        |
|       |                                                                            |
|       v                                                                            |
|  Faithfulness scoring (LLM-as-Judge, 0-1 score)                                    |
|  Hallucination detection (word overlap heuristic)                                   |
|       |                                                                            |
|       v                                                                            |
|  RAGResponse {answer, chunks, faithfulness_score, hallucination_detected}           |
+===================================================================================+
```

### Fallback: When ChromaDB is unavailable

If ChromaDB fails to initialize, the RAG pipeline falls back to **keyword-based search** -- simple string matching over the raw text files. This ensures the system never crashes due to a vector DB issue.

---

## 8. Speech & Language Processing Flow

```
+=========================================================================+
|                    SPEECH & LANGUAGE PIPELINE                             |
+=========================================================================+
|                                                                          |
|  SPEECH-TO-TEXT (two backends, configurable)                             |
|                                                                          |
|  Option A: LOCAL Whisper (FREE, private)                                 |
|  +-------+    +---------------+    +-----------+    +--------+           |
|  | WAV   | -> | openai-whisper| -> | Model:    | -> | "Where |           |
|  | bytes |    | library       |    | tiny/base |    |  is    |           |
|  +-------+    | (Python)      |    | /small/   |    |  Room  |           |
|               | No network    |    | medium/   |    |  305?" |           |
|               +---------------+    | large-v3  |    +--------+           |
|                                    +-----------+                         |
|                                                                          |
|  Option B: OPENAI Whisper API (paid, higher accuracy)                    |
|  +-------+    +---------------+    +-----------+    +--------+           |
|  | WAV   | -> | HTTPS POST to | -> | whisper-1 | -> | "Where |           |
|  | bytes |    | api.openai.com|    | model     |    |  is    |           |
|  +-------+    | /v1/audio/    |    | (cloud)   |    |  Room  |           |
|               | transcriptions|    +-----------+    |  305?" |           |
|               +---------------+                     +--------+           |
|                                                                          |
|  LANGUAGE DETECTION (three-tier cascade)                                 |
|                                                                          |
|  Input: "Ou est la salle 305?"                                           |
|       |                                                                  |
|       v                                                                  |
|  Tier 1: Unicode script analysis (instant)                               |
|    - Arabic script? -> "ar"                                              |
|    - CJK characters? -> "zh"/"ja"/"ko"                                   |
|    - Cyrillic? -> "ru"                                                   |
|       |                                                                  |
|       v  (if Latin script, need more analysis)                           |
|  Tier 2: Word-level n-gram matching                                      |
|    - Check against high-frequency word lists                             |
|    - "est", "la" -> French detected -> "fr"                              |
|       |                                                                  |
|       v  (if still uncertain)                                            |
|  Tier 3: langdetect library (statistical model)                          |
|    - Character trigram analysis -> "fr" with confidence 0.95             |
|       |                                                                  |
|       v                                                                  |
|  Output: LanguageDetectionResult {lang: "fr", confidence: 0.95,          |
|           script: "latin", is_english: False}                            |
|       |                                                                  |
|       v                                                                  |
|  Language -> Optimal Model mapping:                                      |
|    "en" -> openai-gpt4o-mini (best English)                              |
|    "fr" -> gemini-flash (strong multilingual)                            |
|    "ja" -> gemini-flash (strong CJK)                                     |
|    "zh" -> gemini-flash                                                  |
|    "ar" -> gemini-flash                                                  |
+=========================================================================+
```

---

## 9. Experimental Conditions (A--E) -- Routing Architecture

The Embodied LLM Arena uses 5 experimental conditions to isolate what makes a good robot "brain":

```
+=============================================================================+
|                     5 EXPERIMENTAL CONDITIONS                               |
+=============================================================================+
|                                                                             |
|  Condition A: FIXED CLOUD BASELINE                                          |
|  +------------------+     +------------------+                              |
|  | Always uses:     |     | RAG: ON          |                              |
|  | openai-gpt4o-mini| --> | No routing logic |                              |
|  | (cloud, paid)    |     | Direct LLM call  |                              |
|  +------------------+     +------------------+                              |
|  Purpose: "How good is a single decent cloud model?"                        |
|                                                                             |
|  Condition B: FIXED LOCAL BASELINE                                          |
|  +------------------+     +------------------+                              |
|  | Always uses:     |     | RAG: ON          |                              |
|  | llama3-8b-local  | --> | No routing logic |                              |
|  | (Ollama, FREE)   |     | Direct LLM call  |                              |
|  +------------------+     +------------------+                              |
|  Purpose: "How good is a free local model on the same tasks?"               |
|                                                                             |
|  Condition C: SMART ROUTING (OmniLLM's key innovation)                      |
|  +------------------+     +------------------+     +------------------+     |
|  | Task classifier  |     | SmartRouter      |     | Best model for   |     |
|  | detects T1-T4    | --> | picks optimal    | --> | THIS specific    |     |
|  | task type        |     | model for task   |     | task (dynamic)   |     |
|  +------------------+     +------------------+     +------------------+     |
|  Purpose: "Does picking the right model per-task beat a fixed model?"       |
|                                                                             |
|  Condition D: CONSENSUS COUNCIL                                             |
|  +------------------+     +------------------+     +------------------+     |
|  | Query sent to    |     | 3 models respond |     | Judge synthesises|     |
|  | 3 models:        | --> | independently    | --> | best combined    |     |
|  | GPT-4o + Claude  |     | (parallel calls) |     | answer           |     |
|  | + Gemini         |     |                  |     |                  |     |
|  +------------------+     +------------------+     +------------------+     |
|  Purpose: "Does a council of models beat any single model?"                 |
|                                                                             |
|  Condition E: NO-RAG CONTROL                                                |
|  +------------------+     +------------------+                              |
|  | Always uses:     |     | RAG: OFF         |                              |
|  | openai-gpt4o-mini| --> | Pure LLM only    |                              |
|  | (same as A)      |     | No knowledge base|                              |
|  +------------------+     +------------------+                              |
|  Purpose: "How much does RAG actually help? (A vs E comparison)"            |
+=============================================================================+

Experimental Design: Within-subjects, counterbalanced
Expected: 48 participants x 5 conditions = 240 data points
Each participant does all 5 conditions (different task sets)
```

---

## 10. Evaluation & Scoring Architecture

```
+=============================================================================+
|                       EVALUATION PIPELINE                                    |
+=============================================================================+
|                                                                              |
|  AUTOMATIC EVALUATION (during interaction)                                   |
|                                                                              |
|  +-------------------+     +--------------------+     +------------------+   |
|  | LLM-as-Judge      |     | 3 evaluation modes |     | Output:          |   |
|  | (evaluator.py)    | --> | - Referenceless    | --> | score 0-1        |   |
|  | Uses: JUDGE_MODEL |     | - Reference-based  |     | + reasoning      |   |
|  | (default: GPT-4o) |     | - Pairwise (A/B)   |     |                  |   |
|  +-------------------+     +--------------------+     +------------------+   |
|                                                                              |
|  +-------------------+     +--------------------+     +------------------+   |
|  | RAG Faithfulness  |     | "Does the answer   |     | faithfulness:    |   |
|  | (rag/pipeline.py) | --> |  use ONLY the      | --> | 0.0 - 1.0       |   |
|  | LLM-as-Judge      |     |  retrieved context?"|    | + hallucination  |   |
|  +-------------------+     +--------------------+     |   detected: bool |   |
|                                                       +------------------+   |
|                                                                              |
|  ELO RATING SYSTEM (aggregated across sessions)                              |
|                                                                              |
|  +-------------------+     +--------------------+     +------------------+   |
|  | Pairwise results  |     | EloScorer          |     | Leaderboard:     |   |
|  | from evaluator    | --> | (scorer.py)        | --> | Model A: 1523    |   |
|  | and questionnaires|     | K-factor: 32       |     | Model B: 1487    |   |
|  | (win/loss/draw)   |     | Start: 1500 each   |     | Model C: 1456    |   |
|  +-------------------+     +--------------------+     +------------------+   |
|                                                                              |
|  HUMAN EVALUATION (post-interaction questionnaires)                          |
|                                                                              |
|  +-----------------------------+     +----------------------------------+    |
|  | InteractionQuestionnaire    |     | 5 items, 1-7 Likert scale:       |    |
|  | (per interaction)           | --> | accuracy, naturalness, trust,    |    |
|  |                             |     | gesture_appropriateness,          |    |
|  |                             |     | response_speed                    |    |
|  +-----------------------------+     +----------------------------------+    |
|                                                                              |
|  +-----------------------------+     +----------------------------------+    |
|  | GodspeedResponse            |     | 5 subscales, 1-5 Likert:         |    |
|  | (per condition, validated   | --> | anthropomorphism, animacy,       |    |
|  |  instrument from Bartneck)  |     | likeability, perceived_          |    |
|  |                             |     | intelligence, perceived_safety    |    |
|  +-----------------------------+     +----------------------------------+    |
|                                                                              |
|  +-----------------------------+     +----------------------------------+    |
|  | PairwisePreference          |     | "Which condition felt better?"   |    |
|  | (compare 2 conditions)      | --> | -> feeds into ELO system         |    |
|  +-----------------------------+     +----------------------------------+    |
|                                                                              |
|  +-----------------------------+     +----------------------------------+    |
|  | ObserverRating              |     | Experimenter live-codes:          |    |
|  | (by researcher during HRI)  | --> | gesture_sync_quality (1-5),      |    |
|  |                             |     | task_completed (bool),            |    |
|  |                             |     | breakdown_count (int)             |    |
|  +-----------------------------+     +----------------------------------+    |
+=============================================================================+
```

---

## 11. The "No Robot" Scenario -- How It Works Without Pepper

OmniLLM is designed to work **with or without** a physical Pepper robot. Here is how the architecture changes:

```
+=============================================================================+
|  WITH PEPPER ROBOT                      |  WITHOUT PEPPER ROBOT              |
+=============================================================================+
|                                         |                                    |
|  Input: Pepper's microphone             |  Input: HTTP POST with text        |
|  (ALAudioDevice captures WAV)           |  (curl, Postman, Python script,    |
|                                         |   or web frontend)                 |
|                                         |                                    |
|  Transport: naoqi_client.py sends       |  Transport: Direct HTTP POST       |
|  base64 audio to /interact              |  to /interact with {"text": "..."}|
|                                         |                                    |
|  Pipeline: Full LangGraph               |  Pipeline: SAME full LangGraph     |
|  (transcription + classification        |  (skips transcription node if      |
|   + routing + RAG + LLM)               |   text provided, rest identical)   |
|                                         |                                    |
|  Output: RobotAction executed by        |  Output: RobotAction returned as   |
|  Pepper (speech + gesture + LEDs)       |  JSON (speech text + gesture name  |
|                                         |   + LED color as metadata)         |
|                                         |                                    |
|  Evaluation: Full HRI study with        |  Evaluation: Can still run         |
|  human participants + questionnaires    |  automated benchmarks, LLM-as-     |
|                                         |  Judge, and ELO scoring            |
|                                         |                                    |
|  Use case: Research lab with Pepper     |  Use case: Development, testing,   |
|  for embodied LLM benchmarking          |  demo, or text-only chatbot        |
+=============================================================================+

The KEY architectural decision: The Flask server never assumes Pepper exists.
It always returns JSON. The naoqi_client.py is a SEPARATE process that
translates JSON -> robot actions. Remove it, and the server still works.
```

```
WITHOUT ROBOT -- Simplified Architecture:

  Human (browser/terminal)
       |
       |  HTTP POST /interact {"text": "Where is Room 305?"}
       v
  Flask AI Server (localhost:5000)
       |
       |  LangGraph pipeline (skip STT, run everything else)
       v
  LLM Providers (OpenAI / Ollama / etc.)
       |
       v
  JSON Response: {"speech": "Room 305 is on the third floor...",
                   "gesture": "point_left",
                   "emotion_led": "#00AAFF",
                   "metadata": {"model": "gpt-4o-mini", "latency_ms": 823}}
```

---

## 12. Building This Project From Scratch -- Chronological Guide

If you were starting this project from zero, here is the **exact order** of files to create and why:

### Phase 1: Foundation (Week 1-2) -- "Make one LLM answer a question"

```
Step  File to Create                    Why This Order
====  ================================  =============================================
 1    .env.example                      Define what API keys you'll need up front.
                                        Even if you only have one key, this file
                                        documents the project's external dependencies.

 2    requirements.txt                  Lock down your Python dependencies early.
                                        Start minimal: litellm, flask, python-dotenv.
                                        Add more as you need them.

 3    config/models.yaml                Define your model registry BEFORE writing code.
                                        Start with just 2-3 models (one cloud, one local).
                                        This is your source of truth for all model metadata.

 4    omnillm/__init__.py               Create the package structure.

 5    omnillm/gateway.py                THE most important file. Build the LiteLLM
                                        gateway first because everything depends on it.
                                        Test: can you send a prompt and get a response?
                                        This is your "Hello World" moment.

 6    omnillm/cli.py                    Build a simple CLI so you can test the gateway
                                        from the terminal: `omnillm ask "Hello"`
                                        This is your debugging tool for everything after.
```

**Milestone 1**: You can send a prompt to any LLM and get a response. Everything else builds on this.

### Phase 2: Intelligence Layer (Week 3-4) -- "Make it smart about choosing models"

```
 7    omnillm/router.py                 Smart model selection. Start with just 2
                                        strategies (LOWEST_COST, BEST_QUALITY).
                                        Add more strategies as you understand the
                                        problem better.

 8    omnillm/consensus.py              Multi-model council. This is where OmniLLM
                                        differentiates itself. Start with simple
                                        majority_vote, then add synthesis.

 9    omnillm/evaluator.py              LLM-as-Judge evaluation. You need this to
                                        MEASURE whether routing/consensus actually
                                        improves quality. Without measurement, you're
                                        guessing.

10    omnillm/scorer.py                 ELO rating system. Now you can rank models
                                        against each other objectively.
```

**Milestone 2**: You can route prompts intelligently, run a council, and measure quality with ELO scores.

### Phase 3: Knowledge Base (Week 5-6) -- "Give it domain knowledge"

```
11    omnillm/rag/__init__.py           Create the RAG subpackage.

12    omnillm/rag/pipeline.py           Build the RAG pipeline. Start with simple
                                        keyword search (no ChromaDB yet). Get the
                                        augmented-prompt pattern working first.
                                        THEN add ChromaDB for vector search.

13    knowledge_base/*.txt, *.csv       Create your actual knowledge base files.
                                        Start with one file (faq.txt), verify RAG
                                        works end-to-end, then add more files.
```

**Milestone 3**: The system can answer domain-specific questions using your knowledge base.

### Phase 4: HRI Components (Week 7-8) -- "Prepare for the robot"

```
14    omnillm/hri/__init__.py           Create the HRI subpackage.

15    omnillm/hri/classifier.py         Task classifier (T1-T4). Start with rule-based
                                        classification. This determines which pipeline
                                        branch handles each query.

16    omnillm/hri/language_detector.py  Language detection. Start with Unicode script
                                        analysis (the simplest tier), then add n-gram
                                        matching.

17    omnillm/robotics/__init__.py      Create the robotics subpackage.

18    omnillm/robotics/whisper_stt.py   Speech-to-text. Start with local Whisper
                                        (free, no API key needed). Add API backend later.

19    omnillm/robotics/gesture_planner.py  Gesture planning. Map response content to
                                        robot gestures and LED colors. Pure logic,
                                        no external dependencies.

20    omnillm/robotics/pepper.py        Pepper bridge (Python 3.x side). HTTP client
                                        that will talk to the NAOqi process.
```

**Milestone 4**: All HRI components exist and can be tested independently.

### Phase 5: The Pipeline (Week 9-10) -- "Wire everything together"

```
21    omnillm/hri/agent_graph.py        THE MOST COMPLEX FILE. Build the LangGraph
                                        pipeline that connects ALL components:
                                        STT -> language detect -> classify -> branch
                                        -> RAG/LLM -> router -> action plan -> log.
                                        Build ONE node at a time. Test after each.

22    omnillm/server/app.py             Flask server with /interact endpoint.
                                        This is the HTTP interface to the pipeline.
                                        Start with /health, then /interact.

23    omnillm/server/naoqi_client.py    Pepper NAOqi client (Python 2.7).
                                        BUILD THIS LAST because you need everything
                                        else working before testing on the real robot.
```

**Milestone 5**: End-to-end pipeline works. You can POST to /interact and get a RobotAction back.

### Phase 6: Experiment Infrastructure (Week 11-12) -- "Measure everything"

```
24    omnillm/utils/__init__.py         Create the utils subpackage.

25    omnillm/utils/experiment_logger.py  Logging infrastructure. Records every
                                        interaction for later analysis.

26    omnillm/utils/questionnaire.py    Questionnaire data models. Likert scales,
                                        Godspeed instrument, pairwise preferences.
                                        These feed into the ELO system.

27    tests/                            Write tests for everything. Aim for the
        test_gateway.py                 critical paths first (gateway, router, RAG).
        test_router.py                  Then expand to HRI components.
        test_consensus.py
        test_evaluator.py
        test_scorer.py
        test_hri.py
        test_rag.py
        test_gesture_planner.py
        test_experiment_logger.py
```

**Milestone 6**: Production-ready. All components tested, logging in place, ready for human participants.

### Phase 7: Documentation & Polish (Week 13+)

```
28    README.md                         Comprehensive project documentation.
29    GETTING_STARTED.md                Setup guide for new developers.
30    EXPLANATION.md                    Technical deep-dive.
31    ARCHITECTURE.md (this file)       Architecture reference.
```

### Visual: Build Order as a Dependency Graph

```
                    .env.example
                        |
                  requirements.txt
                        |
                  config/models.yaml
                        |
                   gateway.py  <------ THE FOUNDATION
                   /        \
                 cli.py    router.py
                            |
                       consensus.py
                            |
                       evaluator.py
                            |
                        scorer.py
                            |
                    rag/pipeline.py  +  knowledge_base/
                            |
              +-------------+-------------+
              |             |             |
         classifier.py  language_     whisper_stt.py
                        detector.py       |
              |             |        gesture_planner.py
              +-------------+             |
                     |              pepper.py
                     |                    |
                agent_graph.py  <---------+  (WIRES EVERYTHING)
                     |
                  app.py (Flask server)
                     |
              naoqi_client.py (robot bridge)
                     |
             experiment_logger.py
                     |
             questionnaire.py
                     |
                  tests/
```

---

## 13. Complete Technology Stack Map

```
+==============================================================================+
|                           TECHNOLOGY STACK                                     |
+==============================================================================+
|                                                                               |
|  LAYER              TECHNOLOGY           PURPOSE              PAID/FREE       |
|  ================== ==================== ==================== =============== |
|                                                                               |
|  ROBOT HARDWARE     Pepper (SoftBank)    Physical embodiment  Hardware cost   |
|                     NAOqi OS             Robot operating sys   Included w/robot|
|                     ALAudioDevice        Microphone capture    Included        |
|                     ALAnimatedSpeech     Expressive speech     Included        |
|                     ALLeds               Eye LED control       Included        |
|                     ALBehaviorManager    Gesture behaviors     Included        |
|                     ALMotion             Body movement         Included        |
|                                                                               |
|  ROBOT SOFTWARE     Python 2.7           NAOqi SDK language    Free            |
|                     naoqi (SDK)          Robot API access      Free            |
|                     requests             HTTP client           Free            |
|                                                                               |
|  SERVER RUNTIME     Python 3.10+         Server language       Free            |
|                     Flask                Web framework         Free            |
|                     asyncio              Async execution       Free (stdlib)   |
|                                                                               |
|  LLM ORCHESTRATION  LiteLLM              Unified LLM gateway   Free (library)  |
|                     LangGraph            Agent pipeline DAG    Free (library)  |
|                     LangChain            LLM framework         Free (library)  |
|                                                                               |
|  LLM PROVIDERS      OpenAI API           GPT-5.4, GPT-4o, o3  PAID            |
|  (CLOUD)            Anthropic API        Claude family         PAID            |
|                     Google AI API        Gemini family         PAID            |
|                     DeepSeek API         V3, R1                PAID (cheap)    |
|                     Qwen/DashScope API   Qwen 2.5 72B         PAID            |
|                                                                               |
|  LLM PROVIDERS      Ollama               Llama, Mistral, etc.  FREE            |
|  (LOCAL)            (localhost:11434)     Runs on your GPU     FREE            |
|                                                                               |
|  SPEECH-TO-TEXT     OpenAI Whisper       Local STT engine      FREE (library)  |
|  (LOCAL)            (openai-whisper pkg)  tiny to large-v3     FREE            |
|                                                                               |
|  SPEECH-TO-TEXT     OpenAI Whisper API   Cloud STT             PAID            |
|  (CLOUD)            (api.openai.com)     Higher accuracy       ~$0.006/min     |
|                                                                               |
|  VECTOR DATABASE    ChromaDB             Embedding storage     FREE            |
|                                          Similarity search     FREE            |
|                                                                               |
|  DATA FORMATS       JSON                 API communication     --              |
|                     YAML                 Configuration         --              |
|                     CSV                  Experiment logs        --              |
|                     WAV (16kHz PCM)      Audio transport        --              |
|                     Base64               Audio encoding         --              |
|                                                                               |
|  EVALUATION         LLM-as-Judge         Automated scoring      Uses LLM cost  |
|                     ELO system           Model ranking          Free (local)    |
|                     Godspeed instrument  HRI questionnaire      Free (paper)    |
|                     Likert scales        Subjective ratings     Free            |
|                                                                               |
|  TESTING            pytest               Unit test framework    Free            |
|                     278 test cases       Coverage               --              |
+==============================================================================+
```

---

## 14. Full Prompt Lifecycle -- ASCII Diagram

This is the **complete journey** of a single prompt through every system component:

```
 HUMAN                 PEPPER ROBOT              FLASK SERVER                    EXTERNAL SERVICES
 ======                ============              ============                    =================

 "Where is             Microphone
  Room 305?"  -------> ALAudioDevice
                       |
                       | 16kHz WAV PCM
                       v
                       naoqi_client.py
                       | base64 encode
                       |
                       | HTTP POST /interact
                       | {audio: "UklGR...",
                       |  participant: "P001",
                       |  condition: "C",
                       |  rag_enabled: true}
                       |
                       +--------------------->  app.py receives request
                                                |
                                                | base64 decode -> WAV bytes
                                                |
                                                | LangGraph.ainvoke(state)
                                                |
                                                v
                                           +---------+
                                           | Node 1  |
                                           | Whisper  |
                                           | STT     |-----------> [LOCAL] openai-whisper
                                           +---------+             model.transcribe()
                                                |                  OR
                                                |              [CLOUD] api.openai.com
                                                |                  /v1/audio/transcriptions
                                                | text: "Where is Room 305?"
                                                v
                                           +---------+
                                           | Node 2  |
                                           | Language |
                                           | Detect  |  (local, no network)
                                           +---------+
                                                |
                                                | lang: "en", confidence: 0.98
                                                v
                                           +---------+
                                           | Node 3  |
                                           | Task    |
                                           | Classify|  (local, rule-based)
                                           +---------+
                                                |
                                                | task: "navigation" (T2)
                                                v
                                           +---------+
                                           | Node 4b |
                                           | nav_rag |-----------> ChromaDB
                                           |         |             similarity_search()
                                           +---------+             (local, in-process)
                                                |
                                                | chunks: ["Room 305 is on
                                                |  floor 3, Building A..."]
                                                |
                                                | Augmented prompt sent to LLM
                                                +-------------------> LiteLLM
                                                                      |
                                                                      +---> [CONDITION C]
                                                                      |     SmartRouter picks
                                                                      |     best model for T2
                                                                      |
                                                                      +---> api.openai.com
                                                                      |     /v1/chat/completions
                                                                      |     (or whichever model
                                                                      |      was selected)
                                                                      |
                                                <---------------------+
                                                |
                                                | response: "Room 305 is on
                                                |  your left on the third floor"
                                                |
                                           +---------+
                                           | Node 4b |
                                           | Gesture |
                                           | Planner |  (local, rule-based)
                                           +---------+
                                                |
                                                | gesture: "point_left"
                                                | led: "#00AAFF" (blue)
                                                v
                                           +---------+
                                           | Node 5  |
                                           | Smart   |
                                           | Router  |  (Cond C: already routed)
                                           +---------+
                                                |
                                                v
                                           +---------+
                                           | Node 6  |
                                           | Action  |
                                           | Plan    |  (local, builds dict)
                                           +---------+
                                                |
                                                | RobotAction: {
                                                |   speech: "Room 305 is...",
                                                |   gesture: "point_left",
                                                |   emotion_led: "#00AAFF"
                                                | }
                                                v
                                           +---------+
                                           | Node 7  |
                                           | Logger  |-----------> experiment_logs/
                                           |         |             session_P001.json
                                           +---------+             (local file)
                                                |
                                                | JSON response
                       <------------------------+
                       |
                       | HTTP 200 JSON
                       | {speech, gesture,
                       |  emotion_led, metadata}
                       |
                       naoqi_client.py
                       |
                       +-- ALLeds.fadeRGB
                       |   ("FaceLeds",
                       |    0, 170, 255)     --> Pepper eyes glow BLUE
                       |
                       +-- ALBehaviorManager
                       |   .runBehavior(
                       |    "animations/.../
                       |     PointLeft")     --> Pepper points left
                       |
                       +-- ALAnimatedSpeech
                           .say("Room 305
                            is on your left
                            on the third
                            floor")          --> Pepper speaks
                                                      |
                                                      v
 Human hears  <---------------------------------------+
 "Room 305 is
  on your left"
 + sees Pepper
   point left
 + sees blue eyes

 TOTAL TIME: ~1-3 seconds
```

### Data Format Summary at Each Boundary

```
BOUNDARY                          FORMAT                    EXAMPLE
================================  ========================  ================================
Human -> Pepper microphone        Sound waves (analog)      Speech at ~60dB
Pepper mic -> naoqi_client        WAV PCM 16kHz 16-bit      Binary audio data
naoqi_client -> Flask server      HTTP POST, JSON body      {"audio": "UklGRi4A...",
                                  (audio as base64 string)    "condition": "C", ...}
Flask -> Whisper                  Python bytes              b'\x52\x49\x46\x46...'
Whisper -> pipeline               Python string             "Where is Room 305?"
Pipeline -> ChromaDB              Python string (query)     "Where is Room 305?"
ChromaDB -> pipeline              Python list of dicts      [{text: "Room 305...", score: 0.87}]
Pipeline -> LiteLLM               OpenAI chat format        {messages: [{role: "user", ...}]}
LiteLLM -> Cloud LLM              HTTPS POST, JSON          OpenAI/Anthropic/Google format
Cloud LLM -> LiteLLM              HTTPS response, JSON      {choices: [{message: {content: ...}}]}
LiteLLM -> pipeline               Python string             "Room 305 is on your left..."
Pipeline -> Flask                 Python dict               {"speech": "...", "gesture": "..."}
Flask -> naoqi_client             HTTP 200, JSON body       {"speech": "...", "gesture": "...",
                                                              "emotion_led": "#00AAFF"}
naoqi_client -> Pepper motors     NAOqi API calls           ALAnimatedSpeech.say("...")
Pepper speaker -> Human           Sound waves (analog)      Robot voice at ~70dB
```

---

## Summary

OmniLLM is a **three-layer architecture** where:

1. **The Pepper robot** is a thin client -- it only captures audio and executes physical actions. No intelligence lives on the robot.
2. **The Flask server** is the brain -- it runs a 10-node LangGraph pipeline that transcribes speech, detects language, classifies the task, retrieves knowledge, queries the optimal LLM(s), plans gestures, and logs everything.
3. **LLM providers** are interchangeable backends -- the system can use paid cloud APIs (OpenAI, Anthropic, Google, DeepSeek, Qwen) or free local models (Ollama) through LiteLLM's unified interface.

The **key innovation** is that the robot's "brain" is never locked to a single model. Through smart routing (Condition C) and consensus councils (Condition D), OmniLLM dynamically selects the best model for each specific task -- and the Embodied LLM Arena experimentally measures whether this actually makes the robot better at helping humans.

---

**Sources consulted for technology context:**
- [LiteLLM Routing & Load Balancing Documentation](https://docs.litellm.ai/docs/routing)
- [LLM Gateway Architecture and Multi-Model Routing](https://collinwilkins.com/articles/llm-gateway-architecture)
- [LangGraph Architecture and Design](https://medium.com/@shuv.sdr/langgraph-architecture-and-design-280c365aaf2c)
- [LangGraph in 2026: Build Multi-Agent AI Systems](https://dev.to/ottoaria/langgraph-in-2026-build-multi-agent-ai-systems-that-actually-work-3h5)
- [Pepper Robot NAOqi Python SDK](https://provenrobotics.ai/how-to-program-pepper-robot/)
- [Pepper Robot + ChatGPT Real-World Interactions](https://bransonbots.com/2025/06/10/pepper-robot-enhanced-by-chatgpt-engages-in-real-world-interactions/)
- [RAG Pipeline with ChromaDB Architecture](https://medium.com/@mr.melvin.redwing/building-an-advanced-retrieval-augmented-generation-rag-pipeline-using-chromadb-and-ollama-deb8c879d5c9)
- [Building Privacy-First RAG with LangChain](https://www.sitepoint.com/building-a-privacyfirst-rag-pipeline-with-langchain-and-local-llms/)
