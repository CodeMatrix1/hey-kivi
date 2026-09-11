"""Extract topic-bearing tokens from natural-language queries.

Used by cross-recall relevance checks (and similar paths) to ignore
grammatical filler, interrogatives, and recall-framing verbs — without
hard-coding domain terms like product names or meeting types.
"""

from __future__ import annotations

import re

# Articles, pronouns, prepositions, auxiliaries, conjunctions.
_GRAMMATICAL = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "as", "at", "by", "for", "from",
    "in", "into", "of", "on", "to", "with", "about", "over", "under", "up", "down",
    "i", "me", "my", "mine", "you", "your", "yours", "we", "our", "ours", "they",
    "their", "theirs", "it", "its", "this", "that", "these", "those", "he", "she",
    "him", "her", "his", "us", "them",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "do", "does", "did", "have", "has", "had", "will", "would", "could", "should",
    "can", "may", "might", "must", "shall",
    "not", "no", "nor", "so", "than", "too", "very", "just", "only", "also", "then",
})

# Question words — describe the ask shape, not the topic.
_INTERROGATIVE = frozenset({
    "what", "when", "where", "who", "whom", "whose", "which", "why", "how",
})

# How users phrase “look in my history” — not the subject matter.
_RECALL_FRAMING = frozenset({
    "already", "based", "bring", "compile", "discussed", "ever", "know", "mentioned",
    "pull", "recap", "remember", "remind", "said", "share", "shared", "summarize",
    "tell", "told", "together", "work", "worked", "working",
})

# Generic placeholders that rarely identify a topic on their own.
_GENERIC_PLACEHOLDER = frozenset({
    "anything", "anyone", "anybody", "day", "days", "number", "part", "parts",
    "somebody", "someone", "something", "stuff", "thing", "things", "time", "way",
    "ways",
})

QUERY_SCAFFOLDING = _GRAMMATICAL | _INTERROGATIVE | _RECALL_FRAMING | _GENERIC_PLACEHOLDER

# Phrase-shaped scaffolding (removed before tokenizing).
_PHRASE_PATTERNS = (
    # "the Kivi meeting", "a product sync meeting" — event label, not the underlying topic.
    re.compile(r"\b(?:the|a|an|my|our|this|that|next|last)?\s*\w+\s+meetings?\b", re.I),
)


def substantive_query_tokens(query: str, *, min_len: int = 3) -> list[str]:
    """Return lowercased tokens that may indicate what the user is asking about."""
    text = query
    for pattern in _PHRASE_PATTERNS:
        text = pattern.sub(" ", text)
    return [
        tok
        for tok in re.findall(r"\w+", text.casefold())
        if tok not in QUERY_SCAFFOLDING and len(tok) >= min_len
    ]
