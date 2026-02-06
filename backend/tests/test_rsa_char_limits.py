from __future__ import annotations

from app.services.analysis.rsa import DESC_MAX, HEADLINE_MAX, enforce_limits


def test_enforce_limits_trims_and_respects_max() -> None:
    headlines = ["A" * (HEADLINE_MAX + 10), "Short headline"]
    descs = ["B" * (DESC_MAX + 20), "Short description"]

    h2, d2, issues = enforce_limits(headlines, descs)

    assert all(len(h) <= HEADLINE_MAX for h in h2)
    assert all(len(d) <= DESC_MAX for d in d2)
    assert len(issues["headline_too_long"]) >= 1
    assert len(issues["description_too_long"]) >= 1

