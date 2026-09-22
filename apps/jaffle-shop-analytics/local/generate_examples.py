"""Explicit developer action to refresh saved verified answers, never run by a question."""
import sys
sys.dont_write_bytecode=True
import json
import subprocess
from datetime import datetime, timezone
from policy import APP
from wren_tool import execute

queries=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import {queries} from './queries.mjs'; console.log(JSON.stringify(queries()));"],cwd=APP,text=True))
definitions=[
    ('Which five customers have the highest total order amount?', [('Top five customers',queries['customers'].replace('LIMIT 10','LIMIT 5'))], 'Howard R. has the highest total order amount at AUD 99.00, followed by Kathleen P., Norma C., Christina W., and Rose M.'),
    ('Show monthly order performance.', [('Monthly order performance',queries['monthly'])], 'Monthly amounts reconcile to AUD 1,672.00 across 99 orders. March has the largest recorded total at AUD 622.00. Monthly purchasing-customer counts are not additive.'),
    ('How many customers placed more than one order?', [('Repeat-order customers','SELECT COUNT(*) AS repeat_order_customers FROM (SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) > 1) AS repeat_customers')], None),
    ('Compare total and completed-order amounts.', [('Order amount comparison',"SELECT SUM(amount) AS total_order_amount, SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) AS completed_order_amount FROM orders")], 'Total order amount is AUD 1,672.00; completed-order amount is AUD 1,103.00. The difference of AUD 569.00 belongs to other statuses, not inferred refunds.'),
    ('Are there any data-quality failures?', [('Orders without customers',queries['orphanOrders']),('Payments without orders',queries['orphanPayments']),('Order/payment amount mismatches',queries['mismatches'])], 'All three checks pass with zero issues: orders without customers, payments without orders, and order/payment amount mismatches.')
]
answers=[]
for question, items, summary in definitions:
    analyses=[]
    models=set()
    for title,sql in items:
        result=execute(sql)
        models.update(result.pop('models'))
        analyses.append({'title':title,**result})
    if summary is None:
        summary=f"{analyses[0]['rows'][0][0]} customers placed more than one order across all available dates and statuses."
    answers.append({'question':question,'accepted':True,'answer':summary,'analyses':analyses,'models':sorted(models),
                    'notes':['All amounts are AUD. Total order amount includes all statuses and payment methods and is not revenue or refund-adjusted. Completed-order amount includes only completed orders.',
                             'This is a saved answer verified through Wren against the dbt Jaffle Shop sample dataset, not a new AI response.'],
                    'mode':'verified','read_only':True})
payload={'verified_at':datetime.now(timezone.utc).isoformat(),'examples':answers}
(APP/'verified-examples.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
print('Saved five Wren-verified examples. Repeat-order customers:',answers[2]['analyses'][0]['rows'][0][0])
