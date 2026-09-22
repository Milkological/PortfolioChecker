"""Optional configuration — the LLM providers used to write the portfolio review.

Any number of providers can be configured. For each one, the key is resolved as:
  1. its environment variable (ANTHROPIC_API_KEY / GEMINI_API_KEY)
  2. `api_key` under its section in config.ini
  3. absent, in which case that provider is skipped entirely

With no provider configured at all, the review still runs rule-based.
"""

import configparser
import os
from dataclasses import dataclass

DEFAULT_CONFIG_FILE = "config.ini"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    label: str
    env_vars: tuple
    default_model: str
    package: str


# Declaration order is the order narratives are produced in.
PROVIDER_SPECS = (
    ProviderSpec(
        name="claude",
        label="Claude",
        env_vars=("ANTHROPIC_API_KEY",),
        default_model="claude-opus-5",
        package="anthropic",
    ),
    ProviderSpec(
        name="gemini",
        label="Gemini",
        env_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        default_model="gemini-3.8-flash",
        package="google-genai",
    ),
)

SPECS_BY_NAME = {spec.name: spec for spec in PROVIDER_SPECS}


@dataclass
class ProviderConfig:
    name: str
    label: str
    api_key: str
    model: str
    package: str

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def _clean(value) -> str:
    return (value or "").strip()


def _read_parser(path):
    if not path or not os.path.exists(path):
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(path)
    except configparser.Error:
        return None
    return parser


def load_provider_configs(path=DEFAULT_CONFIG_FILE, env=None) -> list:
    """Every provider that has a usable API key, in declaration order.

    Providers without a key are omitted rather than returned unconfigured, so
    callers can simply iterate over whatever comes back.
    """
    env = os.environ if env is None else env
    parser = _read_parser(path)

    configured = []
    for spec in PROVIDER_SPECS:
        api_key = next((_clean(env.get(var)) for var in spec.env_vars if _clean(env.get(var))), "")
        model = spec.default_model

        if parser is not None and parser.has_section(spec.name):
            if not api_key:
                api_key = _clean(parser.get(spec.name, "api_key", fallback=""))
            model = _clean(parser.get(spec.name, "model", fallback="")) or spec.default_model

        if not api_key or api_key.endswith("..."):
            # Skip the untouched placeholder from config_example.ini.
            continue

        configured.append(
            ProviderConfig(
                name=spec.name,
                label=spec.label,
                api_key=api_key,
                model=model,
                package=spec.package,
            )
        )

    return configured
