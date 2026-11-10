"""Reviewable deterministic syntax correction; never silently rewrites workspaces."""
from __future__ import annotations
import ast
from dataclasses import dataclass
import hashlib
import re


class RepairRejected(ValueError):
    pass


@dataclass(frozen=True)
class RepairResult:
    repaired: str
    changed: bool
    original_sha256: str
    repaired_sha256: str
    operations: tuple[str, ...]
    requires_human_review: bool


_HEADER = re.compile(r'^(?P<indent>[ ]*)(?P<head>(?:async\s+def|def|class|if|elif|else|for|async\s+for|while|try|except|finally|with|async\s+with)\b.*?)(?P<tail>\s*)$')


def repair_python_syntax(source: str) -> RepairResult:
    if not isinstance(source, str) or len(source.encode('utf-8')) > 512 * 1024:
        raise RepairRejected('Source outside repair size limit')
    digest = hashlib.sha256(source.encode()).hexdigest()
    try:
        ast.parse(source)
    except SyntaxError:
        pass
    else:
        return RepairResult(source, False, digest, digest, (), False)
    lines = source.splitlines(keepends=True)
    candidates = []
    for i in range(len(lines) - 1):
        line = lines[i].rstrip('\r\n')
        match = _HEADER.fullmatch(line)
        if not match or match['head'].rstrip().endswith(':') or '#' in line:
            continue
        next_line = lines[i + 1]
        indentation = len(match['indent'])
        next_indent = len(next_line) - len(next_line.lstrip(' '))
        if next_indent <= indentation or not next_line.strip():
            continue
        if any(token in line for token in (';', '\\', 'lambda ')):
            continue
        candidates.append(i)
    if len(candidates) != 1:
        raise RepairRejected('No unique safe syntax correction')
    i = candidates[0]
    old = lines[i]
    newline = '\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else ''
    lines[i] = old.rstrip('\r\n').rstrip() + ':' + newline
    result = ''.join(lines)
    try:
        ast.parse(result)
    except SyntaxError as exc:
        raise RepairRejected('Proposed correction does not parse') from exc
    return RepairResult(result, True, digest, hashlib.sha256(result.encode()).hexdigest(),
                        ('insert_missing_colon',), True)
