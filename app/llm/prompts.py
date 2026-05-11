"""Prompt template loader — reads versioned YAML templates from config/prompts/."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from app.llm.provider import LLMError

_DEFAULT_PROMPTS_DIR = Path(__file__).parents[2] / "config" / "prompts"


class PromptError(LLMError):
    """Raised when a prompt template cannot be loaded or rendered."""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    system: str
    user: str
    max_tokens: int
    temperature: float

    def render_user(self, **variables: object) -> str:
        """Render the user template with the given variables.

        Args:
            **variables: Template variables ({{ var_name }} in YAML).

        Returns:
            Rendered string ready to pass to an LLM provider.

        Raises:
            PromptError: If a required variable is missing.
        """
        return _render(self.user, self.name, **variables)

    def render_system(self, **variables: object) -> str:
        """Render the system template (usually static, but supports variables)."""
        return _render(self.system, self.name, **variables)


def _render(template_str: str, template_name: str, **variables: object) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=False)
    try:
        tmpl = env.from_string(template_str)
        return tmpl.render(**variables).strip()
    except UndefinedError as exc:
        raise PromptError(f"Missing variable in prompt '{template_name}': {exc}") from exc
    except TemplateSyntaxError as exc:
        raise PromptError(f"Syntax error in prompt '{template_name}': {exc}") from exc


@lru_cache(maxsize=32)
def load_prompt(name: str, prompts_dir: Path | None = None) -> PromptTemplate:
    """Load and cache a prompt template by name.

    Args:
        name: Template name without extension (e.g. "meta_title").
        prompts_dir: Override directory (defaults to config/prompts/).

    Returns:
        Parsed and validated PromptTemplate.

    Raises:
        PromptError: If the file is missing or malformed.
    """
    directory = prompts_dir if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    path = directory / f"{name}.yaml"

    if not path.exists():
        available = [p.stem for p in directory.glob("*.yaml")] if directory.exists() else []
        raise PromptError(
            f"Prompt template '{name}' not found at {path}. "
            f"Available: {available or 'none'}"
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PromptError(f"Failed to parse prompt '{name}': {exc}") from exc

    for field in ("version", "system", "user", "max_tokens", "temperature"):
        if field not in raw:
            raise PromptError(f"Prompt '{name}' is missing required field '{field}'")

    return PromptTemplate(
        name=name,
        version=str(raw["version"]),
        system=str(raw["system"]),
        user=str(raw["user"]),
        max_tokens=int(raw["max_tokens"]),
        temperature=float(raw["temperature"]),
    )


def reset_prompt_cache() -> None:
    """Clear the prompt cache (useful in tests)."""
    load_prompt.cache_clear()
