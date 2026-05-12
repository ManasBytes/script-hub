from __future__ import annotations

import re
from collections.abc import Mapping

_TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


def substitute_template_text(text: str, variables: Mapping[str, object], strict: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in variables:
            value = variables[key]
            return "" if value is None else str(value)
        if strict:
            raise KeyError(key)
        return match.group(0)

    return _TEMPLATE_PATTERN.sub(replace, text)


def substitute_template_value(value: object, variables: Mapping[str, object], strict: bool = False) -> object:
    if isinstance(value, str):
        return substitute_template_text(value, variables, strict=strict)
    if isinstance(value, list):
        return [substitute_template_value(item, variables, strict=strict) for item in value]
    if isinstance(value, dict):
        return {key: substitute_template_value(item, variables, strict=strict) for key, item in value.items()}
    return value
