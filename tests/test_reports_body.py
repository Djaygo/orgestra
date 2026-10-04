from datetime import datetime

from orgestra.reports.body import issue_body, issue_title

NOW = datetime(2026, 10, 4, 12, 30)


def test_title_is_prefixed_with_the_site():
    assert issue_title("Broken search") == "[site] Broken search"


def test_body_fences_the_description_and_the_context():
    body = issue_body("it fails\non click", "/talks/2025/x", "Mozilla/5.0", NOW)

    assert body == (
        "## Description\n\n```\nit fails\non click\n```\n\n"
        "## Context\n\n```\nPage: /talks/2025/x\nBrowser: Mozilla/5.0\nReported: 2026-10-04 12:30 UTC\n```\n"
    )


def test_a_longer_fence_wraps_text_containing_backticks_and_mentions():
    body = issue_body("a ```code``` b @octocat", "/", "UA", NOW)

    assert "````\na ```code``` b @octocat\n````" in body


def test_the_context_cannot_break_out_of_its_fence_either():
    body = issue_body("ok", "/p", "UA ```` @mention", NOW)

    assert "`````\nPage: /p\nBrowser: UA ```` @mention" in body
