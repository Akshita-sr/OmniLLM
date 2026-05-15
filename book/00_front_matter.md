---
title: "OmniLLM — The Complete Book"
subtitle: "Compare, Route, Orchestrate Every LLM — and Put Them Inside a Robot"
author: "Akshita-sr"
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
                ┌──────────────────────────────────────────┐
                │                                          │
                │              O m n i L L M               │
                │                                          │
                │           T H E   C O M P L E T E        │
                │                B O O K                   │
                │                                          │
                │   Compare, Route, Orchestrate Every LLM  │
                │   — and Put Them Inside a Robot.         │
                │                                          │
                │                                          │
                │           Akshita-sr  •  2026            │
                │                                          │
                └──────────────────────────────────────────┘
```

\newpage

# Copyright & Licence

This work documents the **OmniLLM** open-source project (MIT License,
copyright © 2026 Akshita-sr) and the *Embodied LLM Arena* research study
that the project supports.

This book is intended as **educational and reference material** for the
project's owner, future collaborators, thesis examiners, and anyone learning
how to build a multi-LLM platform connected to a social robot.

The source code is freely available at
[https://github.com/Akshita-sr/OmniLLM](https://github.com/Akshita-sr/OmniLLM).

\newpage

# Dedication

> *To everyone who looked at a chatbot and asked* —
> *"yes, but what would happen if I plugged it into a robot?"*

\newpage

# Preface — How to Read This Book

This book is unusual in one important way: **it is written for three
different readers at the same time.**

When you began this project, you were one of those readers. By the time you
finish reading the book, you will have walked through the perspective of all
three — and you will be able to *talk* to the project, the code, and the
research community fluently in any of the three languages.

## The Three Readers

| Reader | Who they are | What they need |
|--------|--------------|----------------|
| **The Owner** | You, the person who built this and may now have forgotten parts of it | A quick-take recap, "why did we do X this way", file paths, fast orientation |
| **The Beginner** | A friend or junior who has just learned Python and wants to understand the project from zero | Plain English explanations, mini-primers on jargon, worked examples, no skipping steps |
| **The Academic** | A thesis examiner, an HRI researcher, an LLM engineer evaluating the work | Motivation, literature context, formal evaluation, why the methodology is sound |

## The Layered Chapter Structure

Every chapter (from Part II onwards) follows the same three-layer structure
so you can read it the way that fits your purpose today:

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   ⚡  AT A GLANCE  (Owner's Recap)                                 │
│   One-sentence summary, file paths, the "why we built it this way" │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   📖  THE WALK-THROUGH  (Beginner's Path)                          │
│   Plain language, glossary inline, examples you can run,           │
│   Python concepts explained where they appear                      │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   🎓  ACADEMIC CONTEXT  (Researcher's Sidebar)                     │
│   Literature, citations, research justification,                   │
│   "why this approach is methodologically defensible"               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## How to Use This Book

| If you are… | Read… |
|-------------|-------|
| Re-learning your own project | Skim the "At a Glance" boxes; dive into the modules you have forgotten |
| Setting up the project on a new machine | Part V (Setup & Running) front-to-back |
| Onboarding a collaborator | Hand them Parts I, IV, and the relevant module chapter from Part III |
| Writing a thesis or paper | Read the "Academic Context" sidebars; consult Part VII for the experimental design |
| Connecting to a Pepper robot for the first time | Part IV, then Part V Chapter 12 |
| Trying to understand a single Python file | Find it in the index in Part III; each module has its own chapter |
| Just curious | Read the preface, then skip to Chapter 1 |

## A Note on Notation

Throughout the book:

- **Bold** marks a term being introduced for the first time. The first
  introduction is always a definition — not just a use of the word.
- `Code-style monospace` is used for filenames, command lines, function
  names, and code identifiers.
- > Block-quoted text contains direct quotes from the codebase or short
  > excerpts that are too important to paraphrase.
- 💡 Tips and rules of thumb are marked with the lightbulb glyph.
- ⚠️ Warnings and gotchas are marked with the warning glyph.
- 🎓 Academic-only material is marked with the mortar-board glyph; you
  may skim it on a first read.

## What This Book Does Not Cover

To keep the book finite, the following are **not** included in detail:

- Generic Python language tutorials — Appendix A has a focused primer for
  the parts you'll see in this codebase, but for a full tutorial we point
  you to the Python documentation.
- Generic Linux/Windows administration.
- The internal implementation details of LangGraph, LiteLLM, ChromaDB, or
  the NAOqi C++ middleware. We use these as black boxes and focus on how
  OmniLLM uses them.
- The full text of the OmniLLM source code (it lives in the repository).
  The book quotes excerpts; the code is the source of truth.

\newpage
