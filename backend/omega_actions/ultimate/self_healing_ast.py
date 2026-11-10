"""Conservative syntax repair with explicit diff; never executes generated code."""
from __future__ import annotations
import ast
import re

_HEADER = re.compile(r'^(\s*)(?:async\s+)?(?:def|class|if|elif|else|for|while|with|try|except|finally)\b.*\S\s*$')


def repair_python_source(source: str, *, max_bytes: int = 512 * 1024) -> dict:
    if not isinstance(source, str) or len(source.encode('utf-8')) > max_bytes:
        raise ValueError('Source must be text within quota')
    try:
        ast.parse(source)
        return {'source': source, 'repaired': False, 'changes': []}
    except SyntaxError as original:
        lines = source.splitlines(keepends=True)
        index = (original.lineno or 0) - 1
        if not 0 <= index < len(lines):
            raise
        line = lines[index]
        body, ending = (line[:-1], '\n') if line.endswith('\n') else (line, '')
        if body.endswith('\r'):
            body, ending = body[:-1], '\r' + ending
        # Reject inline comments and strings: guessing syntax in untrusted code is unsafe.
        if '#' in body or any(q in body for q in ('"', "'")) or not _HEADER.fullmatch(body):
            raise original
        if body.rstrip().endswith(':'):
            raise original
        lines[index] = body.rstrip() + ':' + ending
        candidate = ''.join(lines)
        try:
            ast.parse(candidate)
        except SyntaxError:
            raise original from None
        return {'source': candidate, 'repaired': True,
                'changes': [{'line': index + 1, 'rule': 'missing_header_colon'}]}
