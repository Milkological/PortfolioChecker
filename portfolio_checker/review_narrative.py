"""Optional LLM layer that turns computed findings into a written review.

The rule engine is the source of truth. A provider only rephrases what it found
— each one is given the computed numbers and told not to invent any others.

Every configured provider produces its own narrative, so two can be compared
side by side. Providers without a key are skipped, and every failure path
returns an error string instead of raising, so the dashboard always falls back
to the rule-based output rather than breaking.
"""

import json
from dataclasses import dataclass

from portfolio_checker.config import load_provider_configs

MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are reviewing someone's investment portfolio. They have \
explicitly asked for a blunt, unsparing assessment, so give them one.

You will receive two things: a JSON summary of the portfolio, and a list of \
findings already computed by a deterministic rule engine. Write the review from \
those, and only those.

Rules:
- Every number you cite must come from the data you were given. Do not estimate, \
extrapolate, or recall figures about any company from memory. If you want to \
make a point the data does not support, leave it out.
- Be direct. Name the biggest problem first and say plainly why it matters. No \
throat-clearing, no "it's worth considering that", no bothsidesing a clear \
issue.
- Bluntness means precision, not insult. Criticise the portfolio's structure, \
never the person. Do not be cruel, sarcastic, or condescending.
- Say what is actually good, if anything is, but do not pad the review with \
reassurance to soften the rest.
- Do not tell them to buy or sell specific securities, and do not predict \
prices. You are describing structural properties of what they hold — \
concentration, overlap, correlation, and the assumptions the projection rests \
on. Where a finding implies an action, describe the tradeoff rather than \
issuing an instruction.
- Note honestly where the data is thin. A finding marked as inferred rather \
than confirmed should be described that way.

Format: open with a two or three sentence verdict. Then the specific problems, \
worst first, as short paragraphs with a bolded lead. Then anything genuinely \
working. Keep the whole thing under 500 words. Plain prose, no preamble about \
what you are about to do."""

NO_PROVIDER_ERROR = (
    "No API key found for any provider — set ANTHROPIC_API_KEY or GEMINI_API_KEY, "
    "or add a [claude] or [gemini] section to config.ini."
)


@dataclass
class NarrativeResult:
    text: str = None
    error: str = None
    provider: str = ""
    model: str = ""

    @property
    def succeeded(self) -> bool:
        return bool(self.text)


def build_user_message(findings: list, summary: dict) -> str:
    return json.dumps({"portfolio": summary, "findings": findings}, indent=2, default=str)


# --- Claude -----------------------------------------------------------------


def _claude_client(config):
    import anthropic

    return anthropic.Anthropic(api_key=config.api_key)


def _call_claude(config, client, system_prompt, user_message) -> str:
    response = client.messages.create(
        model=config.model,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("the model declined to answer")
    return "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def _describe_claude_error(exc: Exception) -> str:
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return str(exc)

    if isinstance(exc, anthropic.AuthenticationError):
        return "the API key was rejected"
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "that key lacks permission for this model"
    if isinstance(exc, anthropic.NotFoundError):
        return "the configured model was not found"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate limited — try again shortly"
    if isinstance(exc, anthropic.APIStatusError):
        return f"the API returned HTTP {getattr(exc, 'status_code', 'error')}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "could not reach the API — check your connection"
    return str(exc)


# --- Gemini -----------------------------------------------------------------


def _gemini_client(config):
    from google import genai

    return genai.Client(api_key=config.api_key)


def _call_gemini(config, client, system_prompt, user_message) -> str:
    interaction = client.interactions.create(
        model=config.model,
        system_instruction=system_prompt,
        input=user_message,
    )
    return interaction.output_text or ""


def _describe_gemini_error(exc: Exception) -> str:
    try:
        from google.genai import errors
    except ImportError:  # pragma: no cover
        return str(exc)

    if isinstance(exc, errors.ClientError):
        code = getattr(exc, "code", None)
        if code in (401, 403):
            return "the API key was rejected"
        if code == 404:
            return "the configured model was not found"
        if code == 429:
            return "rate limited — try again shortly"
        return f"the API rejected the request (HTTP {code})" if code else str(exc)
    if isinstance(exc, errors.ServerError):
        return "the API returned a server error — try again shortly"
    if isinstance(exc, errors.APIError):
        return f"the API returned an error: {exc}"
    return str(exc)


PROVIDERS = {
    "claude": (_claude_client, _call_claude, _describe_claude_error),
    "gemini": (_gemini_client, _call_gemini, _describe_gemini_error),
}


def narrate(findings: list, summary: dict, config, client=None) -> NarrativeResult:
    """Ask one provider to write the review. Never raises."""
    handlers = PROVIDERS.get(config.name)
    if handlers is None:
        return NarrativeResult(error=f"Unknown provider {config.name!r}.", provider=config.label)

    make_client, call, describe_error = handlers
    result = NarrativeResult(provider=config.label, model=config.model)

    if not config.is_configured:
        result.error = f"{config.label}: no API key configured."
        return result

    if client is None:
        try:
            client = make_client(config)
        except ImportError:
            result.error = f"{config.label}: `{config.package}` is not installed (pip install {config.package})."
            return result
        except Exception as exc:
            result.error = f"{config.label}: could not create the client — {exc}"
            return result

    try:
        text = call(config, client, SYSTEM_PROMPT, build_user_message(findings, summary))
    except Exception as exc:
        result.error = f"{config.label}: {describe_error(exc)}"
        return result

    if not (text or "").strip():
        result.error = f"{config.label}: returned an empty response."
        return result

    result.text = text.strip()
    return result


def narrate_all(findings: list, summary: dict, configs=None, client_factory=None) -> list:
    """Run every configured provider, skipping any that has no key.

    Returns one NarrativeResult per configured provider. With none configured,
    returns a single result carrying the "no key anywhere" message so the caller
    has something to show.
    """
    configs = load_provider_configs() if configs is None else configs
    if not configs:
        return [NarrativeResult(error=NO_PROVIDER_ERROR)]

    return [
        narrate(findings, summary, config, client=client_factory(config) if client_factory else None)
        for config in configs
    ]
