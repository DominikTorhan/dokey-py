"""Minimal YAML reader covering the subset DoKey's config files use.

Supported: block mappings nested by indentation, block sequences, flow
sequences ``[a, b]``, flow mappings ``{a: b}``, single/double quoted scalars,
``#`` comments and blank lines. Bare integers become ints; every other scalar
stays a string.

Deliberately NOT supported, because no DoKey config uses them: anchors and
aliases, multi-line scalars, explicit tags, booleans/floats/null coercion, and
block mappings opened on a ``-`` line. Anything unsupported raises ValueError
rather than silently producing the wrong structure.

tests/test_yaml_lite.py checks this parser against PyYAML on every YAML file in
the repo, so the two cannot drift apart unnoticed.
"""

import re
from typing import Any, List, Optional, Tuple

_INT_RE = re.compile(r"^-?\d+$")
_QUOTES = "\"'"
# a quote only opens a quoted scalar at the start of a token, never mid-word:
# "alt+shift+'" is a plain scalar, "';'" is a quoted key
_OPENERS = " \t[{,:"


def safe_load(stream) -> Any:
    """Parse YAML text (or an open file object), mirroring yaml.safe_load."""
    text = stream.read() if hasattr(stream, "read") else stream
    lines = _clean(text)
    if not lines:
        return None
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


def _clean(text: str) -> List[Tuple[int, str]]:
    """Drop comments and blank lines, returning (indent, content) pairs."""
    out = []
    for raw in text.splitlines():
        content = _strip_comment(raw)
        if not content.strip():
            continue
        out.append((len(content) - len(content.lstrip(" ")), content.strip()))
    return out


def _strip_comment(line: str) -> str:
    out = []
    quote = None
    prev = " "  # start of line counts as whitespace
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            else:
                prev = ch
            continue
        if ch in _QUOTES and prev in _OPENERS:
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and prev in " \t":
            break
        out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _split_top(s: str, sep: str = ",") -> List[str]:
    """Split on `sep` at nesting depth 0, respecting quotes."""
    parts, buf, quote, depth, prev = [], [], None, 0, " "
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in _QUOTES and prev in _OPENERS:
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf, prev = [], " "
            continue
        buf.append(ch)
        prev = ch
    parts.append("".join(buf))
    return parts


def _split_key(s: str) -> Optional[Tuple[str, str]]:
    """Split "key: value" at the first structural colon, respecting quotes."""
    quote, prev = None, " "
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in _QUOTES and prev in _OPENERS:
            quote = ch
        elif ch == ":" and (i + 1 == len(s) or s[i + 1] in " \t"):
            return s[:i], s[i + 1 :].strip()
        prev = ch
    return None


def _unquote(s: str) -> Tuple[str, bool]:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in _QUOTES:
        return s[1:-1], True
    return s, False


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if not s:
        return None
    if s.startswith("["):
        if not s.endswith("]"):
            raise ValueError(f"unterminated flow sequence: {s!r}")
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_top(inner)]
    if s.startswith("{"):
        if not s.endswith("}"):
            raise ValueError(f"unterminated flow mapping: {s!r}")
        inner = s[1:-1].strip()
        if not inner:
            return {}
        result = {}
        for part in _split_top(inner):
            kv = _split_key(part.strip())
            if kv is None:
                raise ValueError(f"bad flow mapping entry: {part!r}")
            key, _ = _unquote(kv[0])
            result[key] = _parse_scalar(kv[1])
        return result
    value, was_quoted = _unquote(s)
    if not was_quoted and _INT_RE.match(value):
        return int(value)
    return value


def _is_seq(text: str) -> bool:
    return text == "-" or text.startswith("- ")


def _parse_block(lines, i: int, indent: int) -> Tuple[Any, int]:
    if i < len(lines) and _is_seq(lines[i][1]):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i: int, indent: int) -> Tuple[dict, int]:
    result = {}
    while i < len(lines):
        cur_indent, text = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"unexpected indent at {text!r}")
        kv = _split_key(text)
        if kv is None:
            raise ValueError(f"not a mapping entry: {text!r}")
        raw_key, rest = kv
        key, _ = _unquote(raw_key)
        if rest:
            result[key] = _parse_scalar(rest)
            i += 1
            continue
        nxt = i + 1
        if nxt < len(lines) and (
            lines[nxt][0] > cur_indent
            or (lines[nxt][0] == cur_indent and _is_seq(lines[nxt][1]))
        ):
            result[key], i = _parse_block(lines, nxt, lines[nxt][0])
        else:
            result[key] = None
            i += 1
    return result, i


def _parse_seq(lines, i: int, indent: int) -> Tuple[list, int]:
    result = []
    while i < len(lines):
        cur_indent, text = lines[i]
        if cur_indent < indent or not _is_seq(text):
            break
        rest = text[1:].strip()
        if rest:
            if _split_key(rest) and not rest.startswith(("[", "{")):
                raise ValueError(f"block mapping on a '-' line is unsupported: {text!r}")
            result.append(_parse_scalar(rest))
            i += 1
            continue
        nxt = i + 1
        if nxt < len(lines) and lines[nxt][0] > cur_indent:
            value, i = _parse_block(lines, nxt, lines[nxt][0])
            result.append(value)
        else:
            result.append(None)
            i += 1
    return result, i
