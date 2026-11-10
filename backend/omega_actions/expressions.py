"""Non-eval expression interpreter for a bounded subset of GitHub expression syntax."""
import re
from typing import Any

TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|('(?:''|[^'])*'|\"(?:\\.|[^\"])*\")|([A-Za-z_][\w.-]*)|(==|!=|>=|<=|&&|\|\||[!()<>+,]))", re.S)
EXPR = re.compile(r'\$\{\{\s*(.*?)\s*\}\}', re.S)

class ExpressionError(ValueError):
    pass

class Parser:
    def __init__(self, source: str, context: dict):
        self.context = context
        self.tokens = []
        pos = 0
        while pos < len(source):
            if source[pos:].isspace(): break
            m = TOKEN.match(source, pos)
            if not m: raise ExpressionError(f'Unsupported expression at position {pos}')
            self.tokens.append(next(g for g in m.groups() if g is not None))
            pos = m.end()
        if len(self.tokens) > 512: raise ExpressionError('Expression too complex')
        self.pos = 0
    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def take(self):
        t = self.peek()
        if t is None: raise ExpressionError('Unexpected end of expression')
        self.pos += 1
        return t
    def expect(self, token):
        if self.take() != token: raise ExpressionError(f'Expected {token}')
    def parse(self):
        val = self.expr(0)
        if self.peek() is not None: raise ExpressionError('Unexpected trailing expression')
        return val
    def expr(self, min_bp):
        tok = self.take()
        if tok == '!': left = not truth(self.expr(9))
        elif tok == '(':
            left = self.expr(0); self.expect(')')
        elif tok[0] in "'\"":
            left = tok[1:-1].replace("''", "'") if tok[0] == "'" else bytes(tok[1:-1], 'utf-8').decode('unicode_escape')
        elif tok[0].isdigit(): left = float(tok) if '.' in tok else int(tok)
        elif tok.lower() in ('true','false','null'):
            left = {'true':True,'false':False,'null':None}[tok.lower()]
        elif re.fullmatch(r'[A-Za-z_][\w.-]*',tok):
            if self.peek() == '(':
                self.take(); args = []
                while self.peek() != ')':
                    args.append(self.expr(0))
                    if self.peek() == ',': self.take()
                    elif self.peek() != ')': raise ExpressionError('Expected comma')
                self.expect(')')
                left = self.call(tok, args)
            else: left = self.lookup(tok)
        else: raise ExpressionError(f'Unsupported operand: {tok}')
        binding = {'||':(1,2),'&&':(3,4),'==':(5,6),'!=':(5,6),'<':(5,6),'>':(5,6),'<=':(5,6),'>=':(5,6)}
        while self.peek() in binding:
            op = self.peek(); lbp,rbp = binding[op]
            if lbp < min_bp: break
            self.take(); right = self.expr(rbp)
            if op == '||': left = truth(left) or truth(right)
            elif op == '&&': left = truth(left) and truth(right)
            elif op == '==': left = str(left).lower() == str(right).lower() if isinstance(left,str) and isinstance(right,str) else left == right
            elif op == '!=': left = left != right
            else:
                try: left = {'<':lambda: left<right, '>':lambda: left>right, '<=':lambda: left<=right, '>=':lambda: left>=right}[op]()
                except (TypeError,ValueError): left = False
        return left
    def lookup(self, key):
        obj = self.context
        for segment in key.split('.'):
            if segment.startswith('_'): raise ExpressionError('Private context access denied')
            if not isinstance(obj,dict): return ''
            obj = obj.get(segment, '')
        return obj
    def call(self, name, args):
        status = self.context.get('status','success')
        if name == 'success' and not args: return status == 'success'
        if name == 'failure' and not args: return status == 'failure'
        if name == 'cancelled' and not args: return status == 'cancelled'
        if name == 'always' and not args: return True
        if name == 'contains' and len(args)==2: return str(args[1]).lower() in str(args[0]).lower()
        if name == 'startsWith' and len(args)==2: return str(args[0]).lower().startswith(str(args[1]).lower())
        if name == 'endsWith' and len(args)==2: return str(args[0]).lower().endswith(str(args[1]).lower())
        if name == 'format' and args: return str(args[0]).format(*args[1:])
        raise ExpressionError(f'Function not supported: {name}')

def truth(value: Any) -> bool:
    return bool(value) and str(value).lower() not in ('false','0','none','null')

def evaluate(expr: Any, context: dict) -> Any:
    if isinstance(expr,bool): return expr
    if expr is None: return True
    if not isinstance(expr,str): return truth(expr)
    expr = expr.strip()
    if expr.startswith('${{') and expr.endswith('}}'): expr=expr[3:-2].strip()
    return Parser(expr, context).parse()

def interpolate(value: Any, context: dict) -> Any:
    if not isinstance(value,str): return value
    def sub(match):
        v = evaluate(match.group(1), context)
        if isinstance(v,bool): return str(v).lower()
        return '' if v is None else str(v)
    return EXPR.sub(sub,value)
