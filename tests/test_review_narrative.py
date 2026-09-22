import json
from dataclasses import dataclass

import pytest

from portfolio_checker.config import ProviderConfig
from portfolio_checker.review_narrative import (
    NO_PROVIDER_ERROR,
    build_user_message,
    narrate,
    narrate_all,
)

try:  # both SDKs are optional — the rule-based review works without either
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

try:
    from google.genai import errors as genai_errors
except ImportError:  # pragma: no cover
    genai_errors = None

needs_anthropic = pytest.mark.skipif(anthropic is None, reason="anthropic SDK not installed")
needs_genai = pytest.mark.skipif(genai_errors is None, reason="google-genai SDK not installed")

CLAUDE = ProviderConfig("claude", "Claude", "k", "claude-opus-5", "anthropic")
GEMINI = ProviderConfig("gemini", "Gemini", "k", "gemini-3.8-flash", "google-genai")

FINDINGS = [{"severity": "critical", "title": "Too concentrated", "detail": "...", "evidence": {}}]
SUMMARY = {"total_value": 1000.0, "positions": []}


# --- fakes ------------------------------------------------------------------


@dataclass
class FakeBlock:
    text: str
    type: str = "text"


@dataclass
class FakeAnthropicResponse:
    content: list
    stop_reason: str = "end_turn"


class FakeEndpoint:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClaudeClient:
    def __init__(self, response=None, error=None):
        self.messages = FakeEndpoint(response, error)


@dataclass
class FakeInteraction:
    output_text: str


class FakeGeminiClient:
    def __init__(self, response=None, error=None):
        self.interactions = FakeEndpoint(response, error)


# --- payload ----------------------------------------------------------------


def test_build_user_message_is_valid_json_containing_both_halves():
    payload = json.loads(build_user_message(FINDINGS, SUMMARY))

    assert payload["findings"] == FINDINGS
    assert payload["portfolio"] == SUMMARY


def test_build_user_message_survives_non_json_types():
    from datetime import date

    payload = build_user_message([{"evidence": {"when": date(2026, 1, 1)}}], SUMMARY)

    assert "2026-01-01" in payload


# --- Claude -----------------------------------------------------------------


def test_claude_returns_its_text():
    client = FakeClaudeClient(FakeAnthropicResponse(content=[FakeBlock("  One bet.  ")]))

    result = narrate(FINDINGS, SUMMARY, CLAUDE, client=client)

    assert result.succeeded
    assert result.text == "One bet."
    assert result.provider == "Claude"
    assert result.model == "claude-opus-5"


def test_claude_receives_the_model_and_system_prompt():
    client = FakeClaudeClient(FakeAnthropicResponse(content=[FakeBlock("ok")]))

    narrate(FINDINGS, SUMMARY, CLAUDE, client=client)

    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert "blunt" in call["system"]
    assert call["messages"][0]["role"] == "user"


def test_claude_ignores_non_text_blocks():
    client = FakeClaudeClient(
        FakeAnthropicResponse(content=[FakeBlock("thinking", type="thinking"), FakeBlock("review")])
    )

    assert narrate(FINDINGS, SUMMARY, CLAUDE, client=client).text == "review"


def test_claude_refusal_is_reported_without_raising():
    client = FakeClaudeClient(FakeAnthropicResponse(content=[FakeBlock("")], stop_reason="refusal"))

    result = narrate(FINDINGS, SUMMARY, CLAUDE, client=client)

    assert not result.succeeded
    assert "declined" in result.error


@needs_anthropic
def test_claude_authentication_error_is_described():
    error = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)

    result = narrate(FINDINGS, SUMMARY, CLAUDE, client=FakeClaudeClient(error=error))

    assert "Claude: the API key was rejected" == result.error


# --- Gemini -----------------------------------------------------------------


def test_gemini_returns_its_text():
    client = FakeGeminiClient(FakeInteraction(output_text="  Concentrated.  "))

    result = narrate(FINDINGS, SUMMARY, GEMINI, client=client)

    assert result.succeeded
    assert result.text == "Concentrated."
    assert result.provider == "Gemini"
    assert result.model == "gemini-3.8-flash"


def test_gemini_receives_the_model_and_system_instruction():
    client = FakeGeminiClient(FakeInteraction(output_text="ok"))

    narrate(FINDINGS, SUMMARY, GEMINI, client=client)

    call = client.interactions.calls[0]
    assert call["model"] == "gemini-3.8-flash"
    assert "blunt" in call["system_instruction"]
    assert json.loads(call["input"])["findings"] == FINDINGS


def test_gemini_empty_output_is_reported():
    result = narrate(FINDINGS, SUMMARY, GEMINI, client=FakeGeminiClient(FakeInteraction(output_text="")))

    assert not result.succeeded
    assert "empty" in result.error


@needs_genai
def test_gemini_rejected_key_is_described():
    error = genai_errors.ClientError.__new__(genai_errors.ClientError)
    error.code = 403

    result = narrate(FINDINGS, SUMMARY, GEMINI, client=FakeGeminiClient(error=error))

    assert "Gemini: the API key was rejected" == result.error


@needs_genai
def test_gemini_rate_limit_is_described():
    error = genai_errors.ClientError.__new__(genai_errors.ClientError)
    error.code = 429

    result = narrate(FINDINGS, SUMMARY, GEMINI, client=FakeGeminiClient(error=error))

    assert "rate limited" in result.error


@needs_genai
def test_gemini_server_error_is_described():
    error = genai_errors.ServerError.__new__(genai_errors.ServerError)
    error.code = 500

    result = narrate(FINDINGS, SUMMARY, GEMINI, client=FakeGeminiClient(error=error))

    assert "server error" in result.error


# --- shared behaviour -------------------------------------------------------


def test_unconfigured_provider_is_reported():
    config = ProviderConfig("gemini", "Gemini", "", "m", "google-genai")

    result = narrate(FINDINGS, SUMMARY, config)

    assert not result.succeeded
    assert "no API key" in result.error


def test_unknown_provider_is_reported():
    config = ProviderConfig("llama", "Llama", "k", "m", "nope")

    assert "Unknown provider" in narrate(FINDINGS, SUMMARY, config).error


def test_any_failure_becomes_an_error_string():
    client = FakeClaudeClient(error=RuntimeError("boom"))

    result = narrate(FINDINGS, SUMMARY, CLAUDE, client=client)

    assert not result.succeeded
    assert "boom" in result.error


# --- narrate_all ------------------------------------------------------------


def test_narrate_all_runs_every_configured_provider():
    clients = {
        "claude": FakeClaudeClient(FakeAnthropicResponse(content=[FakeBlock("from claude")])),
        "gemini": FakeGeminiClient(FakeInteraction(output_text="from gemini")),
    }

    results = narrate_all(
        FINDINGS, SUMMARY, configs=[CLAUDE, GEMINI], client_factory=lambda c: clients[c.name]
    )

    assert [r.provider for r in results] == ["Claude", "Gemini"]
    assert [r.text for r in results] == ["from claude", "from gemini"]


def test_narrate_all_keeps_going_when_one_provider_fails():
    clients = {
        "claude": FakeClaudeClient(error=RuntimeError("claude is down")),
        "gemini": FakeGeminiClient(FakeInteraction(output_text="from gemini")),
    }

    results = narrate_all(
        FINDINGS, SUMMARY, configs=[CLAUDE, GEMINI], client_factory=lambda c: clients[c.name]
    )

    assert not results[0].succeeded
    assert results[1].succeeded


def test_narrate_all_with_a_single_provider_returns_one_result():
    client = FakeGeminiClient(FakeInteraction(output_text="only gemini"))

    results = narrate_all(FINDINGS, SUMMARY, configs=[GEMINI], client_factory=lambda c: client)

    assert len(results) == 1
    assert results[0].text == "only gemini"


def test_narrate_all_without_any_provider_explains_why():
    results = narrate_all(FINDINGS, SUMMARY, configs=[])

    assert len(results) == 1
    assert results[0].error == NO_PROVIDER_ERROR
    assert not results[0].succeeded
