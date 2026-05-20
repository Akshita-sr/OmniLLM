---
title: "The Embodied LLM Arena"
subtitle: "An Open-Source Framework for Benchmarking Every Large Language Model Through Human-Robot Interaction with Pepper"
author: "Akshita-sr"
affiliation: "DIBRIS — University of Genoa — Prof. Antonio Sgorbissa's HRI Lab"
date: "May 2026"
documentclass: book
papersize: a4
fontsize: 11pt
geometry: margin=2.5cm
toc: true
toc-depth: 3
numbersections: true
linkcolor: NavyBlue
urlcolor: NavyBlue
---

# Title Page

```
+------------------------------------------------------------+
|                                                            |
|                                                            |
|         T H E    E M B O D I E D    L L M    A R E N A     |
|                                                            |
|                                                            |
|         An Open-Source Framework for Benchmarking          |
|         Every Large Language Model Through                 |
|         Human-Robot Interaction with Pepper                |
|                                                            |
|                                                            |
|                     -- Built on OmniLLM --                 |
|                                                            |
|                                                            |
|             A Master's Thesis & Engineering Reference      |
|                                                            |
|                                                            |
|                          Akshita-sr                        |
|                                                            |
|             DIBRIS, University of Genoa  *  2026           |
|                                                            |
|       Prof. Antonio Sgorbissa's Human-Robot Interaction    |
|                              Lab                           |
|                                                            |
+------------------------------------------------------------+
```

\newpage

# Copyright & Licence

This book documents the **OmniLLM** open-source project (MIT License, copyright © 2026 Akshita-sr) and the **Embodied LLM Arena** research study that the project supports.

The book is written as:

1. an **educational reference** for the project owner, future collaborators, and the open-source community,
2. a **technical foundation** for a Master's thesis in Human-Robot Interaction submitted at the University of Genoa, DIBRIS, under the supervision of Prof. Antonio Sgorbissa, and
3. a **deployment guide** for the real Pepper robot located in Prof. Sgorbissa's lab at DIBRIS.

The source code is freely available at:

> [https://github.com/Akshita-sr/OmniLLM](https://github.com/Akshita-sr/OmniLLM)

\newpage

# Dedication

> *To everyone who ever looked at a chatbot and asked —*
>
> *"Yes, but what would it be like to talk to one with a body?"*

\newpage

# Acknowledgements

This work is conducted at the **Department of Informatics, Bioengineering, Robotics and Systems Engineering (DIBRIS), University of Genoa**, in the Human-Robot Interaction laboratory directed by **Prof. Antonio Sgorbissa**. The real Pepper robot used in the experimental study is hosted by that lab.

The OmniLLM software framework is built upon the following open-source projects, to whose authors and maintainers the author owes a profound debt:

- **LangGraph** and **LangChain** (Harrison Chase et al.) — for the agent graph runtime
- **LiteLLM** (BerriAI) — for the unified LLM provider gateway
- **ChromaDB** — for the local vector database underlying the RAG pipeline
- **OpenAI Whisper** — for local speech-to-text
- **Hugging Face sentence-transformers** — for semantic embeddings
- **NAOqi SDK** and **Choregraphe** (SoftBank / Aldebaran Robotics) — for Pepper's middleware and simulator
- **Flask**, **ReportLab**, **xhtml2pdf**, **DejaVu Sans/Mono** — for the AI server and this book's typesetting

\newpage

# Preface — How to Read This Book

This book is unusual in one important way: **it is written for three different readers at once.**

When you began this project, you (the author) were one of those readers. By the time you finish reading the book, you will have walked through the perspective of all three — and you will be able to *talk* to the project, the code, and the research community fluently in any of the three "languages."

## The Three Readers

| Reader | Who they are | What they need from the book |
|--------|--------------|----------------|
| **The Owner** | You — the person who built this and may have forgotten parts of it after a month | Quick-take recap boxes, file paths, "why did we do X this way?" justifications, fast orientation |
| **The Beginner** | A friend, intern, or junior developer who knows a little Python and wants to understand the system from zero | Plain-English explanations, mini-primers on jargon, worked examples, Python concepts explained at the point of first use, no skipping steps |
| **The Academic** | A thesis examiner, an HRI researcher, an LLM engineer evaluating the work for citation or replication | Literature context, formal evaluation methodology, hypotheses, why the design is methodologically defensible |

## The Layered Chapter Structure

Every chapter from Part II onwards follows the same **three-layer structure** so that you can read it the way that fits your purpose today:

```
+--------------------------------------------------------------------+
|                                                                    |
|   AT A GLANCE  (Owner's Recap)                                     |
|   One-paragraph summary, file paths, the "why we built it          |
|   this way" justification.                                         |
|                                                                    |
+--------------------------------------------------------------------+
|                                                                    |
|   THE WALK-THROUGH  (Beginner's Path)                              |
|   Plain language, jargon defined on first use, examples you can    |
|   actually run, Python concepts explained where they appear.       |
|                                                                    |
+--------------------------------------------------------------------+
|                                                                    |
|   ACADEMIC CONTEXT  (Researcher's Sidebar)                         |
|   Literature, citations, research justification, "why this         |
|   approach is methodologically defensible."                        |
|                                                                    |
+--------------------------------------------------------------------+
```

## How to Use This Book

| If you are… | Read… |
|-------------|-------|
| Re-learning your own project after a break | Skim the *At a Glance* boxes; dive into the modules you've forgotten |
| Setting up the project on a new machine | Part IV (Setup, Execution, Building from Scratch) front-to-back |
| Onboarding a collaborator | Hand them Parts I, II, and the relevant module chapter from Part III |
| Writing a thesis or paper based on this work | Read the *Academic Context* sidebars; consult Part V for the experimental design |
| Connecting to the real Pepper at DIBRIS for the first time | Part IV → Chapter "Day Zero — Real Pepper at the Lab" |
| Trying to understand a single Python file | Find it in the master file table in Part III, Chapter 9; each module has its own deep-dive chapter |
| Just curious | Read the Preface, then skip to Chapter 1 |

## A Note on Notation

Throughout this book:

- **Bold** marks a term being introduced for the first time. The first introduction is always a definition — not just a use of the word.
- `Code-style monospace` is used for filenames, command lines, function names, and code identifiers.
- > Block-quoted text contains direct quotes from the codebase or short excerpts that are too important to paraphrase.
- `(Tip)` marks a rule of thumb or shortcut that experienced users will appreciate.
- `(!)` marks a warning or known gotcha — usually a thing that bit the author in the past.
- `(Academic)` marks material aimed primarily at the thesis examiner; you may skim it on a first read.
- `(Beginner)` marks an inline mini-primer on a piece of Python or systems jargon; experienced developers may skip these blocks.

## What This Book Does Not Cover

To keep the book finite, the following are **not** included in detail:

- Generic Python language tutorials. Appendix A provides a focused primer on the parts of Python you will see in this codebase, but for a complete tutorial we point you to the official Python documentation.
- Generic Linux / Windows administration.
- The internal implementation details of LangGraph, LiteLLM, ChromaDB, or the NAOqi C++ middleware. We use these as black boxes and focus on how OmniLLM uses them. References to the upstream documentation are given where relevant.
- The full text of the OmniLLM source code (it lives in the repository). The book quotes excerpts; the code is the source of truth.

## A Word on the May 2026 Upgrade

The book you are reading is the **second edition** of the OmniLLM book. Between the first edition (168 pages, written in March 2026) and this edition, the project underwent a substantial upgrade in preparation for the live experimental study at DIBRIS. The major changes folded into this rewrite are:

- **A new robot bridge topology.** The first edition assumed Pepper polls the AI server (Python 2.7 → Python 3.x). The May 2026 upgrade adds a *reverse* topology where the Python 3.x AI server drives Pepper through a small HTTP bridge server running on Python 2.7. Both topologies are now first-class.
- **Three trigger modes for live conversation:** `text` (typed input — works on virtual Pepper too), `touch` (head-touch + 5-second audio capture, real Pepper only) and `vad` (continuous voice-activity detection, real Pepper only).
- **Face-tracking** via NAOqi's `ALTracker` is now integrated as a first-class interaction primitive, not an experimental extra.
- **Per-condition model resolution** moved from the LangGraph nodes into `omnillm/server/app.py`, fixing a bug where Condition B (fixed local Llama) silently ran the cloud default model.
- **Multilingual routing rerouted** from `gemini-flash` to `claude-haiku` after the Google free tier started rate-limiting Condition T4 mid-experiment.
- **Knowledge base rewritten** for the **University of Genoa / DIBRIS / Sgorbissa lab** context. The previous generic IRAI-Lab content is preserved under `knowledge_base/_legacy_irai/` for reference.
- **A two-run pilot** with the author as participant P000 (2026-05-20) revealed the silent-routing bug above and validated the rest of the pipeline end-to-end on Choregraphe's virtual Pepper.

If you have read the first edition, treat this one as a complete replacement. Section structure and chapter numbering have changed.

\newpage
