"""Export governed data and validate every dashboard filter combination through Wren.

Run from the project root with the existing Wren Python environment.
Only writes inside this app folder. No source database or semantic edits.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import pyarrow.parquet as pq
from wren.cli import _build_engine

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
def main():
    script = "import {queries,months,statuses} from './queries.mjs'; const all=[]; for(const m of ['',...months]) for(const s of ['',...statuses]) all.push({month:m,status:s,queries:queries(m,s)}); console.log(JSON.stringify(all));"
    cases = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], cwd=APP, text=True))
    (APP / 'data').mkdir(exist_ok=True)
    (APP / 'mdl.json').write_bytes((ROOT / 'target/mdl.json').read_bytes())
    checked = {}
    baseline = {}
    with _build_engine(str(ROOT / 'target/mdl.json'), None, None) as engine:
        for model, physical in [('customers', 'customers'), ('orders', 'orders'), ('payments', 'stg_payments')]:
            sql = f'SELECT * FROM {model}'
            table = engine.query(sql)
            pq.write_table(table, APP / 'data' / f'{physical}.parquet')
            checked[sql] = table.num_rows
        for case in cases:
            result = {}
            for name, sql in case['queries'].items():
                if sql not in checked:
                    rows = engine.query(sql).to_pylist()
                    checked[sql] = len(rows)
                else:
                    rows = engine.query(sql).to_pylist() if not case['month'] and not case['status'] else None
                if rows is not None:
                    result[name] = rows
            if not case['month'] and not case['status']:
                baseline = result
        monthly = baseline['monthly']
        assert sum(r['total_order_amount'] for r in monthly) == 1672
        assert sum(r['order_count'] for r in monthly) == 99
        kpi = baseline['kpis'][0]
        assert kpi['total_order_amount'] == 1672 and kpi['order_count'] == 99
        assert kpi['purchasing_customers'] == 62 and round(kpi['average_order_value'], 2) == 16.89
        assert kpi['completed_order_amount'] == 1103
        assert baseline['inventory'][0]['customer_count'] == 100
        assert baseline['payments'][0]['payment_count'] == 113
        for name in ['orphanOrders', 'orphanPayments', 'mismatches']:
            assert baseline[name][0]['issues'] == 0
    report = {'validated_at': datetime.now(timezone.utc).isoformat(), 'engine': 'Wren 0.15.0',
              'unique_queries_validated': len(checked), 'filter_combinations': len(cases),
              'monthly_amount': 1672, 'monthly_orders': 99, 'baseline': baseline,
              'queries': list(checked)}
    (APP / 'validation.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['queries', 'baseline']}))

if __name__ == '__main__':
    main()
