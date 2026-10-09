"""Research from a topic: the brief, the run's rules, and the check on its citations.

The reader's rule is that nothing comes from memory and every claim has a source. A
prompt can only ask for that. So the server also keeps the list of pages the run was
actually shown, and says which citations are not on it.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import md
from .config import EXPAND_SENTINEL, RESEARCH_SENTINEL, SOURCES_HEADING, UNVERIFIED_HEADING
from .context import instructions_block

EXPAND_PREAMBLE = (
    "You turn a short research topic into a detailed, exhaustive research brief that a "
    "separate researcher with web access will follow. Do not research the topic and do not "
    "answer it. Reply with the brief only, in plain markdown, with no greeting and no "
    "closing remark. The reader will edit it before it is used."
)

EXPAND_REQUIREMENTS = (
    "The brief must cover, each under its own heading:",
    "- Goal: what the reader should understand or be able to decide at the end.",
    "- Scope: what is in, what is out, the time frame, and the regions or fields covered.",
    (
        "- Key sub-questions: an exhaustive numbered list, from definitions and background to "
        "current state, numbers, key players, competing views, risks, and open questions."
    ),
    (
        "- Angles to check: technical, practical, economic, historical, and critical, where "
        "each applies."
    ),
    (
        "- Sources to prefer: the primary and authoritative sources for this topic, and the "
        "kinds of sources to distrust."
    ),
    "- Report structure: the sections the final report should have, in order.",
    "State any assumption you made about what the reader meant, so they can correct it.",
)

RESEARCH_PREAMBLE = (
    "You are a researcher writing a report for a reader. Follow the research brief below. "
    "Write mathematics as LaTeX: $...$ inline and $$...$$ on its own line for display."
)

RESEARCH_RULES = (
    "## Rules for this research",
    "",
    (
        "- Gather every fact with the web search and web fetch tools. Use nothing from memory: "
        "if you did not read it on a page during this run, leave it out."
    ),
    (
        "- Search widely first, then fetch and read the best pages. Do not rely on search "
        "snippets alone for a claim."
    ),
    (
        "- Back every factual claim with an inline markdown link to the page it came from, "
        "placed right where the claim is made. Link only to pages you searched or fetched in "
        "this run. Never write a URL from memory."
    ),
    (
        "- Prefer primary and authoritative sources: official documents, standards, papers, "
        "original data, and reputable publications. Avoid content farms and unsourced posts."
    ),
    "- Give the date of time-sensitive facts. Where sources disagree, say so and cite both.",
    "- If the web does not answer part of the brief, say that plainly. Do not fill the gap.",
    (
        "- Do all the research first, then write the report once, in full, as your final "
        "message. Do not narrate your progress."
    ),
    "- Start the report with a single # heading that names it. Use plain markdown.",
    (
        "- Do not add a list of sources or references at the end. One is added for you from "
        "the pages you actually read."
    ),
)

# Query keys that track a click and never change the page.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = frozenset({"fbclid", "gclid", "ref_src"})


def build_expand_prompt(topic: str) -> str:
    parts = [
        EXPAND_PREAMBLE,
        "",
        *EXPAND_REQUIREMENTS,
        "",
        *instructions_block(),
        EXPAND_SENTINEL,
        "",
        topic.strip(),
        "",
    ]
    return "\n".join(parts)


def build_research_prompt(topic: str, brief: str) -> str:
    parts = [
        RESEARCH_PREAMBLE,
        "",
        *RESEARCH_RULES,
        "",
        *instructions_block(),
        "## Topic",
        "",
        topic.strip(),
        "",
        RESEARCH_SENTINEL,
        "",
        brief.strip(),
        "",
    ]
    return "\n".join(parts)


def cited_urls(markdown: str) -> list[str]:
    """Every web link in a report, once each, in the order first cited."""
    found: dict[str, None] = {}
    for token in md.parse(markdown):
        for child in token.children or []:
            if child.type != "link_open":
                continue
            href = str(child.attrGet("href") or "")
            if href.startswith(("http://", "https://")):
                found.setdefault(href)
    return list(found)


def normalize(url: str) -> str:
    """One page, one spelling, so a trailing slash is not reported as a made-up source."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in _TRACKING_KEYS and not key.startswith(_TRACKING_PREFIXES)
        ]
    )
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), query, ""))


def verify(report: str, seen: list[str]) -> tuple[list[str], list[str]]:
    """The report's citations, and the ones that match no page the run was shown."""
    known = {normalize(url) for url in seen}
    cited = cited_urls(report)
    return cited, [url for url in cited if normalize(url) not in known]


def sources_section(*, cited: list[str], unverified: list[str]) -> str:
    """Only what the report cites. A search returns plenty of pages nobody should be sent to."""
    flagged = set(unverified)
    lines = ["", "---", "", f"## {SOURCES_HEADING}", ""]
    lines += [f"{n}. <{url}>" for n, url in enumerate((u for u in cited if u not in flagged), 1)]
    if unverified:
        lines += [
            "",
            f"### {UNVERIFIED_HEADING}",
            "",
            (
                "These links appear in the report, but the run neither found them by search nor "
                "opened them. Check each one before relying on it."
            ),
            "",
            *[f"- <{url}>" for url in unverified],
        ]
    return "\n".join(lines) + "\n"
