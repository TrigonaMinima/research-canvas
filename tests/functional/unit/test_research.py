"""Research from a topic: the two prompts, and the check that every citation was seen."""

from __future__ import annotations

from research_canvas import config, research, storage

FETCHED = "https://www.python.org/downloads/"
FOUND = "https://example.org/found"
INVENTED = "https://example.org/never-seen"

REPORT = (
    "# Python releases\n\n"
    f"The latest is 3.14 ([python.org]({FETCHED})). "
    f"An older guide disagrees ([guide]({FOUND})). "
    f"A third claim cites [this]({INVENTED}).\n"
)


# --- drafting the brief ---------------------------------------------------------


def test_should_carry_the_topic_into_the_brief_prompt():
    assert "solid state batteries" in research.build_expand_prompt("solid state batteries")


def test_should_mark_the_brief_prompt_so_a_stand_in_can_tell_it_apart():
    assert config.EXPAND_SENTINEL in research.build_expand_prompt("topic")


def test_should_ask_the_brief_for_sub_questions():
    assert "sub-questions" in research.build_expand_prompt("topic")


def test_should_ask_the_brief_for_a_source_quality_bar():
    assert "sources" in research.build_expand_prompt("topic").lower()


def test_should_carry_standing_instructions_into_the_brief_prompt(canvas_root):
    storage.write_instructions("Prefer British spelling.")
    assert "Prefer British spelling." in research.build_expand_prompt("topic")


# --- the research run -----------------------------------------------------------


def test_should_carry_the_approved_brief_into_the_research_prompt():
    assert "Cover cost per kWh." in research.build_research_prompt("t", "Cover cost per kWh.")


def test_should_mark_the_research_prompt_so_a_stand_in_can_tell_it_apart():
    assert config.RESEARCH_SENTINEL in research.build_research_prompt("t", "brief")


def test_should_forbid_answering_from_memory():
    assert "memory" in research.build_research_prompt("t", "brief")


def test_should_demand_a_link_for_every_claim():
    assert "inline markdown link" in research.build_research_prompt("t", "brief")


def test_should_tell_the_run_not_to_write_its_own_source_list():
    assert "Do not add a list of sources" in research.build_research_prompt("t", "brief")


def test_should_carry_standing_instructions_into_the_research_prompt(canvas_root):
    storage.write_instructions("Prefer British spelling.")
    assert "Prefer British spelling." in research.build_research_prompt("t", "brief")


# --- citations ------------------------------------------------------------------


def test_should_find_every_inline_link_in_a_report():
    assert research.cited_urls(REPORT) == [FETCHED, FOUND, INVENTED]


def test_should_find_a_bare_url_in_a_report():
    assert research.cited_urls("See https://example.org/bare for more.") == [
        "https://example.org/bare"
    ]


def test_should_list_a_url_cited_twice_only_once():
    assert research.cited_urls(f"[a]({FOUND}) and [b]({FOUND})") == [FOUND]


def test_should_treat_a_trailing_slash_as_the_same_page():
    assert research.normalize("https://example.org/a/") == research.normalize(
        "https://example.org/a"
    )


def test_should_treat_a_fragment_as_the_same_page():
    assert research.normalize("https://example.org/a#part") == research.normalize(
        "https://example.org/a"
    )


def test_should_treat_host_case_and_www_as_the_same_page():
    assert research.normalize("https://WWW.Example.org/a") == research.normalize(
        "https://example.org/a"
    )


def test_should_treat_tracking_parameters_as_the_same_page():
    assert research.normalize("https://example.org/a?utm_source=x") == research.normalize(
        "https://example.org/a"
    )


def test_should_keep_a_real_query_string_distinct():
    assert research.normalize("https://example.org/a?id=1") != research.normalize(
        "https://example.org/a?id=2"
    )


def test_should_flag_a_citation_the_run_never_saw():
    _, unverified = research.verify(REPORT, seen=[FETCHED, FOUND])
    assert unverified == [INVENTED]


def test_should_not_flag_a_citation_that_differs_only_by_a_trailing_slash():
    _, unverified = research.verify(f"[a]({FETCHED.rstrip('/')})", seen=[FETCHED])
    assert unverified == []


# --- the sources section --------------------------------------------------------


def test_should_head_the_sources_section():
    assert f"## {config.SOURCES_HEADING}" in _sources()


def test_should_list_a_cited_page_the_run_saw():
    assert FOUND in _sources().split(config.UNVERIFIED_HEADING)[0]


def test_should_list_an_unseen_citation_under_its_own_heading():
    assert INVENTED in _sources().split(config.UNVERIFIED_HEADING)[1]


def test_should_never_list_a_search_result_nobody_cited():
    assert "https://example.org/junk" not in _sources()


def test_should_leave_out_the_unverified_heading_when_every_citation_was_seen():
    section = research.sources_section(cited=[FETCHED], unverified=[])
    assert config.UNVERIFIED_HEADING not in section


def _sources() -> str:
    cited, unverified = research.verify(REPORT, seen=[FETCHED, FOUND, "https://example.org/junk"])
    return research.sources_section(cited=cited, unverified=unverified)


def test_should_leave_room_for_an_exhaustive_brief():
    from research_canvas.config import MAX_RESEARCH_PROMPT_CHARS

    assert MAX_RESEARCH_PROMPT_CHARS >= 50_000
