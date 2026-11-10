"""Bounded parallel static code analysis for Chat Leak/Duo offline engineering mode."""
from __future__ import annotations
import ast
import hashlib
import re
from .swarm import SwarmCoordinator, DuoCoordinator
from .quantum_ast import ASTResonator
from .self_healing import repair_python_syntax, RepairRejected
from dataclasses import asdict


def _finding(rule: str, severity: str, line: int, message: str) -> dict:
    return {'rule': rule, 'severity': severity, 'line': line, 'message': message}


def _unsafe_calls(tree: ast.AST) -> list[dict]:
    findings=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        name = node.func.id if isinstance(node.func,ast.Name) else (
            f'{node.func.value.id}.{node.func.attr}' if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) else '')
        if name in ('eval','exec'):
            findings.append(_finding('unsafe_eval','high',node.lineno,'Dynamic code execution requires review'))
        if name in ('os.system','subprocess.Popen','subprocess.run','subprocess.call'):
            if name=='os.system' or any(kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True for kw in node.keywords):
                findings.append(_finding('shell_execution','high',node.lineno,'Shell execution may enable command injection'))
    return findings


def _secrets(tree: ast.AST) -> list[dict]:
    findings=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.Assign,ast.AnnAssign)):continue
        targets=node.targets if isinstance(node,ast.Assign) else [node.target]
        value=node.value
        if not isinstance(value,ast.Constant) or not isinstance(value.value,str) or len(value.value)<16:
            continue
        for target in targets:
            if isinstance(target,ast.Name) and re.search(r'(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)',target.id,re.I):
                findings.append(_finding('hardcoded_secret','high',node.lineno,'Credential-like literal assigned to sensitive name'))
    return findings


def _complexity(tree: ast.AST) -> list[dict]:
    findings=[]
    branch_types=(ast.If,ast.For,ast.While,ast.Try,ast.BoolOp,ast.IfExp,ast.Match)
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            complexity=1+sum(isinstance(child,branch_types) for child in ast.walk(node))
            if complexity>12:
                findings.append(_finding('cyclomatic_complexity','medium',node.lineno,
                                         f'Function {node.name} has approximate complexity {complexity}'))
    return findings


def _imports(tree: ast.AST) -> list[dict]:
    findings=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module=='pickle':
            findings.append(_finding('unsafe_deserialization','medium',node.lineno,
                                     'Review deserialization of untrusted pickle data'))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='loads' and isinstance(node.func.value,ast.Name) and node.func.value.id=='pickle':
            findings.append(_finding('unsafe_deserialization','high',node.lineno,
                                     'pickle.loads can execute code from untrusted input'))
    return findings


def analyze_source(source: str, *, mode: str = 'leak', suggest_repair: bool = False) -> dict:
    if not isinstance(source,str) or not source or len(source.encode('utf-8'))>512*1024:
        raise ValueError('Source must be nonempty UTF-8 text under 512 KiB')
    if mode not in ('leak','duo'):
        raise ValueError('Mode must be leak or duo')
    digest=hashlib.sha256(source.encode('utf-8')).hexdigest()
    try:
        tree=ast.parse(source)
    except SyntaxError as exc:
        report = {'mode':mode,'syntax_valid':False,'verified':False,'sha256':digest,
                  'analyzers':0,'findings':[_finding('syntax_error','high',exc.lineno or 0,str(exc.msg))]}
        if suggest_repair:
            try:
                report['repair'] = asdict(repair_python_syntax(source))
            except RepairRejected:
                report['repair'] = {'changed':False,'requires_human_review':True,
                                    'reason':'No deterministic safe correction found'}
        return report
    checkers=(_unsafe_calls,_secrets,_complexity,_imports)
    with SwarmCoordinator(max_workers=4,max_pending=4) as coordinator:
        reports=coordinator.map(lambda fn:fn(tree),checkers)
    findings=sorted((finding for report in reports for finding in report),key=lambda x:(x['line'],x['rule']))
    verified = DuoCoordinator(max_rounds=2).run(
        lambda text, attempt: ast.parse(text),
        lambda candidate: isinstance(candidate,ast.Module) and bool(candidate.body),source)
    embedding = ASTResonator(dimensions=64).embed(source)
    return {'mode':mode,'syntax_valid':True,'verified':bool(verified),
            'sha256':digest,'analyzers':len(checkers),'findings':findings,
            'ast_projection':{'dimensions':64,'self_projection':ASTResonator(64).project(embedding,embedding),
                              'scope':'CLASSICAL_CPU_HEURISTIC'},
            'scope':'DETERMINISTIC_STATIC_ANALYSIS_NOT_LLM'}
