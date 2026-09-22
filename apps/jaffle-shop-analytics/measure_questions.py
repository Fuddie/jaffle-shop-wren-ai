"""Measure local Ask Wren response latency for a fixed safe question set."""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE='http://127.0.0.1:4174'
QUESTIONS=[
    'Which customers have the most orders?',
    'What is the total order amount by order status?',
    'How many orders were placed in each month?',
]
def request(path,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    headers={'Content-Type':'application/json','Origin':BASE,'X-Jaffle-Request':'1'} if data else {}
    req=urllib.request.Request(BASE+path,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=20) as response:return json.loads(response.read())
def measure():
    measurements=[]
    for question in QUESTIONS:
        started=time.perf_counter(); job=request('/api/ask',{'question':question})
        while True:
            time.sleep(.25); result=request('/api/jobs/'+job['id'])
            if result['state']!='running':break
            if time.perf_counter()-started>210: raise TimeoutError(question)
        elapsed=round((time.perf_counter()-started)*1000,1)
        if result['state']!='complete': raise RuntimeError(result)
        measurements.append({'question':question,'elapsed_ms':elapsed,'answer':result['answer']})
    return {'measured_at':datetime.now(timezone.utc).isoformat(),'measurements':measurements,
            'median_ms':sorted(x['elapsed_ms'] for x in measurements)[1]}
if __name__=='__main__':
    out=measure(); path=Path(__file__).with_name('performance_baseline.json'); path.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'median_ms':out['median_ms'],'elapsed_ms':[x['elapsed_ms'] for x in out['measurements']]}))
