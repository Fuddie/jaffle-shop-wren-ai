"""Narrow stdio MCP server: fixed semantic context plus guarded Wren SELECT queries."""
import sys
sys.dont_write_bytecode = True
import json
from datetime import date, datetime
from pathlib import Path
from policy import APP, ROOT, Rejected, sql_policy, clean_payload

def context():
    import wren
    skill = Path(wren.__file__).parent / 'skills_content/usage/SKILL.md'
    return {
        'skill': skill.read_text(encoding='utf-8'),
        'mdl': json.loads((ROOT/'target/mdl.json').read_text(encoding='utf-8')),
        'business_rules': (ROOT/'knowledge/rules/general.md').read_text(encoding='utf-8'),
        'scope': 'dbt Jaffle Shop sample dataset. Use query for all SQL validation and execution. No file changes, memory stores, indexing, or shell commands. Never infer refunds or label total order amount as revenue.',
    }

def execute(sql):
    ast, models = sql_policy(sql)
    from wren.cli import _build_engine
    from wren.config import WrenConfig
    from wren.policy import validate_read_only_ast
    import sqlglot
    with _build_engine(str(ROOT/'target/mdl.json'), None, None) as engine:
        engine._config = WrenConfig(strict_mode=True)
        planned = engine.dry_plan(sql)
        # Fail closed even if the transpiler were to produce unexpected statements.
        parsed = sqlglot.parse(planned, read='duckdb')
        if len(parsed) != 1 or parsed[0] is None:
            raise Rejected('The planned SQL was not a single read-only query.')
        validate_read_only_ast(parsed[0])
        result = engine.query(sql, limit=201)
    rows = result.to_pylist()
    if 'monthly_order_summary' in models:
        models = sorted(set(models + ['orders']))
    return clean_payload({'columns': result.column_names, 'rows': [[row[c] for c in result.column_names] for row in rows[:200]],
                         'truncated': len(rows)>200, 'models': models, 'read_only': True, 'sql': sql})

TOOLS = [
    {'name':'context','description':'Load the Wren usage skill, existing compiled semantic models, cube, view, relationships, and Jaffle Shop business rules. Call first.', 'inputSchema':{'type':'object','properties':{},'additionalProperties':False},'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}},
    {'name':'query','description':'Validate one read-only governed SELECT query through Wren and execute it against the read-only Jaffle Shop database. Returns at most 200 rows. No external sources or writes.', 'inputSchema':{'type':'object','properties':{'sql':{'type':'string','maxLength':12000}},'required':['sql'],'additionalProperties':False},'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}
]

def main():
    if '--query' in sys.argv:
        try:
            request = json.loads(sys.stdin.read(16000))
            print(json.dumps({'ok':True, 'result':execute(request['sql'])}, default=str))
        except Exception:
            print(json.dumps({'ok':False, 'error':'The governed read-only query could not be validated or executed.'}))
        return
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if 'id' not in message:
                continue
            method = message.get('method')
            if method == 'initialize':
                result = {'protocolVersion':message['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'jaffle-wren-read-only','version':'1.0.0'}}
            elif method == 'tools/list':
                result = {'tools':TOOLS}
            elif method == 'ping':
                result = {}
            elif method == 'tools/call':
                params = message.get('params',{})
                try:
                    if params['name'] == 'context':
                        value = context()
                    elif params['name'] == 'query':
                        value = execute(params.get('arguments',{}).get('sql'))
                    else:
                        raise Rejected('Unsupported tool.')
                    result = {'content':[{'type':'text','text':json.dumps(value,default=str)}],'isError':False}
                except Exception:
                    result = {'content':[{'type':'text','text':'Query rejected or failed. Use a single read-only SELECT over customers, orders, payments, or monthly_order_summary and the supplied business rules.'}],'isError':True}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':message['id'],'error':{'code':-32601,'message':'Unsupported method'}}),flush=True)
                continue
            print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result},default=str),flush=True)
        except Exception:
            # Never echo raw messages, diagnostics, paths, or credentials.
            continue

if __name__ == '__main__':
    main()
