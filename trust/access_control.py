"""Lightweight access-control placeholder."""


def should_restrict(trust_score):
    """Return whether access should be restricted."""
    return trust_score < 60
