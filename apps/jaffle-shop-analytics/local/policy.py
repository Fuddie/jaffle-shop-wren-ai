"""Fail-closed input, SQL, and response boundaries for the local demo."""
import json
import re
import unicodedata
from pathlib import Path
import sqlglot
from sqlglot import exp
from wren.config import WrenConfig
from wren.policy import validate_sql_policy

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
MODELS = {'customers', 'orders', 'payments', 'monthly_order_summary'}
FUNCTIONS = {'AND','OR','COUNT','SUM','AVG','MIN','MAX','ABS','ROUND','COALESCE','NULLIF','CONCAT','CONCAT_WS',
             'UPPER','LOWER','DATE_TRUNC','TIMESTAMP_TRUNC','CAST','TRY_CAST','EXTRACT','CASE','IF',
             'ROW_NUMBER','RANK','DENSE_RANK','LAG','LEAD','FIRST_VALUE','LAST_VALUE','FLOOR','CEIL',
             'LENGTH','SUBSTRING','TRIM','DATE_ADD','DATE_SUB','DATE_DIFF','DATEDIFF','TIME_TO_STR'}
DENIED = re.compile(r'\b(edit|modify|delete|remove|write|overwrite|create|deploy|commit|push|install|execute|shell|command|powershell|bash|cmd|curl|wget|python|javascript|subprocess|prompt|instruction|ignore|bypass|override|pretend|roleplay|credential|password|secret|token|environment|env|system|developer|filesystem|directory|directories|file|files|folder|registry|encode|base64|decode|upload|download|http|https|email|send)\b', re.I)
TOPIC = re.compile(r'\b(jaffle|shop|customers?|orders?|payments?|amounts?|monthly|months?|purchasing|completed|quality|failures?|revenue|refunds?|coupons?|gift cards?|spend|spending|sales)\b', re.I)
INTENT = re.compile(r'^(which|what|how|show|compare|are|is|do|does|did|list|count|calculate|find|give|tell|summari[sz]e|break|can|could|please|who|when|why|total|average|top)\b', re.I)

class Rejected(ValueError):
    pass

def question_policy(question):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
        raise Rejected('Enter an analytics question between 1 and 500 characters.')
    question = unicodedata.normalize('NFKC', question).strip()
    if len(question) > 500 or any(unicodedata.category(c).startswith('C') for c in question):
        raise Rejected('Use a single plain-text analytics question, up to 500 characters.')
    if DENIED.search(question) or re.search(r'[\\/`$;|<>{}\[\]]|--', question):
        raise Rejected('Only Jaffle Shop analytics questions are allowed. Commands, file access, credentials, and instruction changes are not accepted.')
    if not TOPIC.search(question) or not INTENT.search(question):
        raise Rejected('Ask about Jaffle Shop customers, orders, payments, monthly performance, or data quality.')
    return question

def sql_policy(sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 12000:
        raise Rejected('The query must be a bounded read-only analysis.')
    try:
        statements = sqlglot.parse(sql, read='duckdb')
        if len(statements) != 1 or statements[0] is None:
            raise Rejected('Only one read-only SELECT query is allowed per analysis.')
        ast = statements[0]
        validate_sql_policy(ast, MODELS, WrenConfig(strict_mode=True))
        for func in ast.find_all(exp.Func):
            name = func.name.upper() if isinstance(func, exp.Anonymous) else func.sql_name().upper()
            if name not in FUNCTIONS:
                raise Rejected('This function is outside the allowed analytics function set.')
        tables = list(ast.find_all(exp.Table))
        governed = {t.name for t in tables} & MODELS
        if not governed or len(tables) > 16 or any(n.args.get('recursive') for n in ast.find_all(exp.With)):
            raise Rejected('Use a bounded query over the existing governed models.')
        for literal in ast.find_all(exp.Literal):
            if literal.is_string and (len(literal.this) > 100 or re.search(r'[\\/]|://|[A-Za-z]:', literal.this)):
                raise Rejected('Paths and external data references are not allowed.')
        return ast, sorted(governed)
    except Rejected:
        raise
    except Exception:
        raise Rejected('Only read-only SQL over the governed Jaffle Shop models is allowed.') from None

def safe_text(value):
    text = str(value).replace(chr(0x2014), ',')
    # Reject rather than partially disclose diagnostic text or credentials.
    patterns = [r'[A-Za-z]:[\\/]', r'\\\\', r'/(?:Users|home|etc|tmp|var)/',
                r'\b(?:sk-|AKIA)[A-Za-z0-9_-]{12,}', r'\beyJ[A-Za-z0-9_-]{15,}',
                r'(?i)bearer\s+\S+', r'(?i)(?:password|api[_ -]?key|access[_ -]?token)\s*[:=]']
    if any(re.search(p, text) for p in patterns):
        raise Rejected('The answer contained unsupported diagnostic content. Please rephrase the analytics question.')
    return text

def clean_payload(payload):
    return json.loads(safe_text(json.dumps(payload, ensure_ascii=False, default=str)))
