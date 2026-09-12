"""Unit tests for conversation continuity formatting."""

from __future__ import annotations

from hindsight_pipeline_2.kivi.conversation_context import (
    format_continuity_block,
    user_lines_from_continuity_block,
)


def test_empty_context_returns_current_message_only():
    block = format_continuity_block([], "Hello there")
    assert block == "Current message:\nHello there"


def test_none_context_returns_current_message_only():
    block = format_continuity_block(None, "Follow up")
    assert block == "Current message:\nFollow up"


def test_formats_user_and_assistant_turns():
    context = [
        {"role": "user", "content": "What is Kivi?"},
        {"role": "assistant", "content": "Kivi is your assistant."},
        {"role": "user", "content": "Tell me more."},
        {"role": "assistant", "content": "Sure, I can help with notes."},
    ]
    block = format_continuity_block(context, "Thanks")
    assert "Recent conversation:" in block
    assert "User: What is Kivi?" in block
    assert "Assistant: Kivi is your assistant." in block
    assert "Current message:\nThanks" in block


def test_skips_invalid_messages():
    context = [
        {"role": "user", "content": "Hi"},
        {"role": "system", "content": "ignored"},
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "Hello"},
    ]
    block = format_continuity_block(context, "Next")
    assert "User: Hi" in block
    assert "Assistant: Hello" in block
    assert "system" not in block.lower() or "ignored" not in block


def test_user_lines_from_continuity_block():
    block = format_continuity_block(
        [
            {"role": "user", "content": "I am preparing for a biology exam."},
            {"role": "assistant", "content": "Good luck!"},
        ],
        "What exam am I preparing for?",
    )
    assert user_lines_from_continuity_block(block) == ["I am preparing for a biology exam."]
