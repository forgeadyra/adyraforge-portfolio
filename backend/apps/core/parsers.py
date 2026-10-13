"""JSON parser hardened against pathological nesting.

DRF's JSONParser only catches ValueError, so a deeply nested body such as
"[[[[...]]]]" raised RecursionError and returned a 500 to anonymous callers
(found in the v2 audit). Bodies are rejected with 400 if they can't be parsed
or nest deeper than MAX_JSON_DEPTH; the depth check is iterative.
"""

from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

MAX_JSON_DEPTH = 20


def json_depth(value: Any) -> int:
    deepest = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, dict):
            children = node.values()
        elif isinstance(node, list):
            children = node
        else:
            continue
        deepest = max(deepest, depth)
        if deepest > MAX_JSON_DEPTH:
            return deepest
        stack.extend((child, depth + 1) for child in children)
    return deepest


class SafeJSONParser(JSONParser):
    def parse(self, stream: Any, media_type: str | None = None, parser_context: Any = None) -> Any:
        try:
            data = super().parse(stream, media_type, parser_context)
        except RecursionError as exc:
            raise ParseError("JSON is nested too deeply.") from exc
        if json_depth(data) > MAX_JSON_DEPTH:
            raise ParseError("JSON is nested too deeply.")
        return data
