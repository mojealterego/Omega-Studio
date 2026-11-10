"""Deterministic failure classification and explicit bounded retry policy."""
import re
from dataclasses import dataclass

RULES={
    'timeout':re.compile(r'(timed? out|deadline exceeded)',re.I),
    'network':re.compile(r'(connection reset|temporary failure in name resolution|ECONNRESET|HTTP 503)',re.I),
    'resource':re.compile(r'(out of memory|ENOMEM|no space left on device)',re.I),
    'assertion':re.compile(r'(AssertionError|assertion failed|FAILED tests/)',re.I),
    'dependency':re.compile(r'(ModuleNotFoundError|command not found|package not found)',re.I),
}

@dataclass(frozen=True)
class FailureDiagnosis:
    category: str
    retryable: bool


def diagnose(log:str)->FailureDiagnosis:
    for category,pattern in RULES.items():
        if pattern.search(log): return FailureDiagnosis(category,category in ('timeout','network'))
    return FailureDiagnosis('unknown',False)


def retry_delay(attempt:int,base:float=0.5,cap:float=30.0)->float:
    if attempt<1: raise ValueError('Attempt starts at one')
    return min(cap,base*2**(attempt-1))
