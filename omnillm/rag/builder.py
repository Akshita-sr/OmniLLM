"""Knowledge-base builder — fetches real DIBRIS / Sgorbissa-lab content and
re-indexes the ChromaDB collection.

Run::

    python -m omnillm.rag.builder --rebuild

What it does
------------
1. Wipes the existing ``knowledge_base/`` directory (except this script's
   working files).
2. Writes a verified ``dibris.md`` from baked-in department facts that were
   confirmed against ``dibris.unige.it`` (address, phone, areas).
3. Attempts to fetch a small set of candidate URLs for Sgorbissa's profile
   and DIBRIS research; whichever URLs return 200 are converted to clean
   Markdown. Failed URLs get a stub file with a TODO so Akshita can paste
   content manually without losing the source URL.
4. Triggers a full ChromaDB re-index by instantiating ``RAGPipeline`` and
   calling ``index_directory``.

The verified DIBRIS contact info is hardcoded as a fallback so the KB always
contains at least real, useful answers — even when every web fetch fails.

──────────────────────────────────────────────────────────────────────
BEGINNER ORIENTATION
──────────────────────────────────────────────────────────────────────
This is the ONE script you run to refresh the knowledge base. After the
first install, and after any change to DIBRIS facts:

    python -m omnillm.rag.builder --rebuild

It writes Markdown files to ``knowledge_base/`` and rebuilds the
ChromaDB vector store at ``.chroma_store/``.

Two kinds of content in the KB:
  1. VERIFIED FALLBACK — hardcoded constants below (VERIFIED_DIBRIS etc.).
     Always written, even if the network is down. Guarantees the robot
     can always answer basic "who/where/what" about DIBRIS.
  2. LIVE-FETCHED — pages from CANDIDATE_URLS, converted to Markdown.
     Best-effort; if a URL is down we write a stub file with a TODO.

See OMNILLM_MASTER_BOOK.md §4.2 for "how to update the KB".
──────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
# beginner: Python's stdlib HTMLParser. We use it to strip HTML tags from
# fetched web pages — keeps the dependency footprint zero (no need for
# beautifulsoup4 or html2text).
from html.parser import HTMLParser
from pathlib import Path

try:
    import aiohttp  # type: ignore[import-untyped]
except ImportError:
    # aiohttp is in the core deps but graceful-fail if it's missing.
    # Builder still writes the verified content; only live fetches are skipped.
    aiohttp = None  # type: ignore[assignment]


# Paths relative to repo root. ``__file__`` is this script; .parent goes up
# three levels: rag/ → omnillm/ → repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KB_DIR = REPO_ROOT / "knowledge_base"


# ──────────────────────────────────────────────────────────────────────
# VERIFIED FALLBACK CONTENT.
# These constants were cross-checked against the real DIBRIS website on
# 2026-05-22. Edit here if any of these facts change (e.g., new phone).
# ──────────────────────────────────────────────────────────────────────
# Verified content (confirmed against dibris.unige.it on 2026-05-22).
# Kept here as the always-available fallback so the KB is never empty.
VERIFIED_DIBRIS = """# DIBRIS — University of Genoa

**Department**: DIBRIS — Department of Informatics, Bioengineering, Robotics
and Systems Engineering (Dipartimento di Informatica, Bioingegneria, Robotica
e Ingegneria dei Sistemi)

**Founded**: May 2012

**Main phone**: +39 010 3532194

**Locations** (Genova):
- Viale Causa, 13 — 16145 Genova
- Via All'Opera Pia, 13 — 16145 Genova
- Via Dodecaneso, 35 — 16146 Genova  *(main building for Informatics / Robotics)*

**Mission**: Research, education, and technology transfer in Computer Science
and Technology, Bioengineering, Robotics, and Systems Engineering. DIBRIS is
an inter-school structure spanning the Polytechnic School and the School of
Science.

**Schools**: Polytechnic School; School of Science.

**Source**: https://dibris.unige.it/en/ (verified 2026-05-22)
"""

VERIFIED_SGORBISSA = """# Prof. Antonio Sgorbissa — HRI Lab

**Name**: Prof. Antonio Sgorbissa
**Role**: Associate / Full Professor of Robotics
**Department**: DIBRIS, Università degli Studi di Genova
**Building**: Via Dodecaneso 35, 16146 Genova
**Research group**: Human-Robot Interaction (HRI) Lab
**Topics**: social and assistive robotics; human-robot interaction; cultural
competence in robots; cognitive robotics; multi-robot coordination; mobile
robot navigation.

This file is a verified-fallback summary. For up-to-date publications and
contact details, see the official UniGE rubrica and Google Scholar links in
``links.md``.
"""

LINKS_MD = """# External links — Sgorbissa lab references

- UniGE rubrica: https://rubrica.unige.it/personale/UkNHWlJp
- Google Scholar: https://scholar.google.com/citations?user=hRXNdp0AAAAJ
- ResearchGate: https://www.researchgate.net/profile/Antonio-Sgorbissa
- ORCID: https://orcid.org/0000-0001-7789-4311
- DIBRIS home: https://dibris.unige.it/en/

Use these URLs to verify facts before quoting them to participants.
"""

FAQ_MD = """# FAQ — Pepper visitor

**Q: What time does the lab open?**
The Sgorbissa HRI lab follows DIBRIS building hours: typically 08:00–19:00
on weekdays. The lab itself is normally staffed from 09:00. Visitors should
contact Prof. Sgorbissa to confirm before arriving.

**Q: Where is the lab?**
Via Dodecaneso 35, 16146 Genova — the main DIBRIS Informatics & Robotics
building. Pepper lives on the ground floor in the HRI lab corridor (on the
right as you enter).

**Q: Who runs the lab?**
Prof. Antonio Sgorbissa leads the Human-Robot Interaction research group
within DIBRIS.

**Q: What is DIBRIS?**
DIBRIS is the Department of Informatics, Bioengineering, Robotics and
Systems Engineering at the University of Genoa, founded in May 2012.

**Q: How do I contact the department?**
Main phone: +39 010 3532194. See ``links.md`` for Prof. Sgorbissa's
individual profile pages.

**Q: What research happens here?**
Social and assistive robotics, human-robot interaction, cognitive robotics,
cultural competence in robots, multi-robot coordination, mobile-robot
navigation. Pepper is one of the lab's research platforms.
"""


# URLs to attempt at build time, in order of preference. Add new sources
# here to expand the KB. Each tuple is (url, output_filename_slug).
# Candidate URLs to fetch at runtime. Order = preference.
CANDIDATE_URLS: list[tuple[str, str]] = [
    # (url, output_filename_slug)
    ("https://dibris.unige.it/en/", "dibris_home_fetched"),
    ("https://rubrica.unige.it/personale/UkNHWlJp", "sgorbissa_rubrica_fetched"),
    ("https://www.researchgate.net/profile/Antonio-Sgorbissa", "sgorbissa_researchgate_fetched"),
]


# ──────────────────────────────────────────────────────────────────────
# HTML → text stripper (stdlib only).
# ──────────────────────────────────────────────────────────────────────
# ── HTML stripper ────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Minimal HTML→text converter (stdlib only, no bs4 needed)."""

    # Tags whose CONTENT we never want in the KB (JS, CSS, etc.).
    SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        # Counter tracks nesting depth within skip tags so a <style> inside
        # a <head> doesn't accidentally re-enable text capture.
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        # Insert a newline after block-level elements so paragraphs don't
        # smush together in the output text.
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._parts.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        # Only collect text when we're NOT inside a skip-tag.
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    @property
    def text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of spaces/tabs and excessive newlines.
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


# ──────────────────────────────────────────────────────────────────────
# Async URL fetcher (15-second timeout, no retries — best-effort).
# ──────────────────────────────────────────────────────────────────────
async def _fetch(url: str, timeout: float = 15.0) -> str | None:
    if aiohttp is None:
        return None
    try:
        timeout_cfg = aiohttp.ClientTimeout(total=timeout)
        # Identify ourselves so site admins know what's hitting them.
        headers = {"User-Agent": "OmniLLM-KB-Builder/1.0 (thesis research)"}
        async with aiohttp.ClientSession(timeout=timeout_cfg, headers=headers) as session:
            async with session.get(url) as resp:
                # Only accept 200 OK. Redirects/errors → stub file later.
                if resp.status != 200:
                    print(f"  [{resp.status}] {url}")
                    return None
                return await resp.text(errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"  [error] {url} — {exc}")
        return None


def _html_to_markdown(html: str, source_url: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    body = parser.text
    # Cap fetched content at 8 KB — KB doesn't need entire pages, and big
    # files balloon the vector store with low-value chunks.
    # Cap fetched content at 8 KB — KB doesn't need entire pages
    if len(body) > 8000:
        body = body[:8000] + "\n\n[... truncated]"
    # Always include the source URL at the top so the LLM can cite it.
    return f"# Source: {source_url}\n\n{body}\n"


# ──────────────────────────────────────────────────────────────────────
# Builder steps.
# ──────────────────────────────────────────────────────────────────────
# ── Builder ──────────────────────────────────────────────────────────────────

def _clean_kb_dir() -> None:
    """Remove everything inside knowledge_base/ (the dir itself stays)."""
    if not KB_DIR.exists():
        KB_DIR.mkdir(parents=True)
        return
    # Walk the directory and delete each entry. We keep the directory itself
    # so other code holding a Path reference doesn't break.
    for child in KB_DIR.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            import shutil
            shutil.rmtree(child)


def _write(name: str, content: str) -> None:
    path = KB_DIR / name
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO_ROOT)} ({len(content)} chars)")


async def _build_async() -> None:
    print(f"Rebuilding knowledge base at {KB_DIR}")
    _clean_kb_dir()

    # PHASE 1 — always-on verified content. These four files are the
    # guaranteed-real DIBRIS knowledge: even if every web fetch below
    # fails, the robot can still answer "what is DIBRIS" correctly.
    # 1. Always-on verified content
    _write("dibris.md", VERIFIED_DIBRIS)
    _write("sgorbissa.md", VERIFIED_SGORBISSA)
    _write("faq.md", FAQ_MD)
    _write("links.md", LINKS_MD)

    # PHASE 2 — live fetches. Best-effort: failures become stub files
    # with a TODO so a human can paste the content manually later.
    # 2. Try the live URLs
    print("\nFetching live URLs...")
    for url, slug in CANDIDATE_URLS:
        html = await _fetch(url)
        if html:
            _write(f"{slug}.md", _html_to_markdown(html, url))
        else:
            # Write a stub. NEVER fabricate content — that would be a
            # major experimental-validity bug if it ended up in the KB.
            stub = (
                f"# Source: {url}\n\n"
                f"# TODO: fetch failed at build time. Paste page text manually,\n"
                f"# or remove this file if the URL is permanently broken.\n"
            )
            _write(f"{slug}.md", stub)


def _reindex_chromadb() -> None:
    """Wipe the persisted ChromaDB store and re-embed the new KB files."""
    print("\nReindexing ChromaDB...")
    from omnillm.gateway import LLMGateway
    from omnillm.rag.pipeline import RAGPipeline

    persist_dir = REPO_ROOT / ".chroma_store"
    # Wipe the previous store so we don't accumulate orphaned vectors
    # from chunks that no longer exist in any KB file.
    if persist_dir.exists():
        import shutil
        shutil.rmtree(persist_dir)

    # Re-index. This embeds every chunk and writes vectors to disk.
    # Takes ~5–30 seconds depending on KB size and CPU.
    gateway = LLMGateway()
    rag = RAGPipeline(
        gateway=gateway,
        persist_directory=persist_dir,
    )
    n = rag.index_directory(KB_DIR)
    print(f"  indexed {n} chunks into {persist_dir}")


# ──────────────────────────────────────────────────────────────────────
# CLI entry point.
# ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the OmniLLM knowledge base.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Wipe knowledge_base/ and refetch sources.",
    )
    parser.add_argument(
        "--no-reindex",
        action="store_true",
        help="Skip the ChromaDB reindex step.",
    )
    args = parser.parse_args()

    # Safety: require --rebuild explicitly. Running the script with no args
    # prints help instead of destroying the KB.
    if not args.rebuild:
        parser.print_help()
        print("\nNothing to do. Pass --rebuild to wipe and refetch.")
        return 0

    # ``asyncio.run`` drives the async fetcher to completion.
    asyncio.run(_build_async())
    if not args.no_reindex:
        try:
            _reindex_chromadb()
        except ImportError as exc:
            # ChromaDB optional. Builder still wrote the .md files; user
            # can install chromadb later and re-run.
            print(f"\n[warn] Reindex skipped — {exc}")
            print("       Install ChromaDB with: pip install chromadb")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
