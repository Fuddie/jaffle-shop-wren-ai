"""Loopback-only dashboard and question service. Start from the project root with -B."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'local'))
import json
import threading
import time
import uuid
import copy
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from agent import Run, TIMEOUT_SECONDS, executable
from policy import Rejected, question_policy
from serve import Handler as StaticHandler

PORT=4174
ORIGIN=f'http://127.0.0.1:{PORT}'
ALLOWED_ORIGINS={ORIGIN,'http://127.0.0.1:4173'}
MODEL='gpt-5.6-luna'
REASONING='low'
MANIFEST_READY=(Path(__file__).resolve().parents[2]/'target'/'mdl.json').is_file()
APP=Path(__file__).resolve().parent
CURATED_FILE=APP/'verified-examples.json'
CACHE_FILE=APP/'local-cache.json'
LOCK=threading.Lock()
JOBS={}
ACTIVE=None
def normalize(question):
    return ' '.join(question.casefold().split())
def load_cache():
    try:
        data=json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        return {str(k):v for k,v in data.items() if isinstance(v,dict) and v.get('accepted') and v.get('read_only') and v.get('project_unchanged')}
    except (OSError,ValueError):
        return {}
def load_curated():
    try:
        data=json.loads(CURATED_FILE.read_text(encoding='utf-8'))
        return {normalize(x['question']):x for x in data.get('examples',[]) if isinstance(x,dict) and x.get('question') and x.get('accepted')}
    except (OSError,ValueError):
        return {}
CACHE=load_cache()
CURATED=load_curated()
def persist_cache():
    tmp=CACHE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(CACHE,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    tmp.replace(CACHE_FILE)

def work(job_id,run):
    global ACTIVE
    try:
        answer=run.execute()
        answer['elapsed_ms']=round((time.monotonic()-JOBS[job_id]['started_at'])*1000,1)
        answer['cached']=False
        with LOCK:
            JOBS[job_id].update(state='complete',answer=answer,elapsed_ms=answer['elapsed_ms'],stage='Answer ready')
            with LOCK:
                CACHE[JOBS[job_id]['cache_key']]=copy.deepcopy(answer)
                persist_cache()
    except Rejected as error:
        with LOCK:
            JOBS[job_id].update(state='cancelled' if run.cancelled.is_set() else 'error',error=str(error),stage='Cancelled' if run.cancelled.is_set() else 'Error')
    except Exception:
        with LOCK:
            JOBS[job_id].update(state='error',error='The local question service could not complete this request. Try Verified examples.')
    finally:
        with LOCK:
            ACTIVE=None

class Handler(StaticHandler):
    def log_message(self,*args):
        pass  # No question text, diagnostics, or file paths in HTTP logs.

    def valid_host(self):
        return self.client_address[0]=='127.0.0.1' and self.headers.get('Host')==f'127.0.0.1:{PORT}'

    def reply(self,status,payload):
        data=json.dumps(payload,ensure_ascii=False,default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):
            pass

    def end_headers(self):
        origin=self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type, X-Jaffle-Request')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        super().end_headers()

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403,{'error':'Use the loopback dashboard origin.'})
        path=urlsplit(self.path).path
        if path=='/local-status.json':
            try:
                executable()
                available=True
            except Rejected:
                available=False
            return self.reply(200,{'available':available,'timeout_seconds':TIMEOUT_SECONDS,'busy':ACTIVE is not None,'model':MODEL,'reasoning_effort':REASONING,'manifest_ready':MANIFEST_READY,'cache_entries':len(CACHE)})
        if path.startswith('/api/jobs/'):
            with LOCK:
                job=JOBS.get(path.removeprefix('/api/jobs/'))
                data={k:v for k,v in job.items() if k in ('state','answer','error','stage','elapsed_ms')} if job else None
            return self.reply(200,data or {'state':'error','error':'This question is no longer available. Ask again.'})
        allowed={'/','/index.html','/styles.css','/app.mjs','/queries.mjs','/ask.mjs','/ask.css',
                 '/mdl.json','/validation.json','/verified-examples.json',
                 '/data/customers.parquet','/data/orders.parquet','/data/stg_payments.parquet'}
        if path not in allowed:
            return self.reply(404,{'error':'Not found.'})
        super().do_GET()

    def do_HEAD(self):
        if not self.valid_host():
            return self.reply(403,{'error':'Use the loopback dashboard origin.'})
        if urlsplit(self.path).path not in ('/data/customers.parquet','/data/orders.parquet','/data/stg_payments.parquet'):
            return self.reply(404,{'error':'Not found.'})
        super().do_HEAD()

    def do_OPTIONS(self):
        if not self.valid_host() or self.headers.get('Origin') not in ALLOWED_ORIGINS:
            return self.reply(403,{'error':'Use the loopback dashboard origin.'})
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        global ACTIVE
        if not self.valid_host() or self.headers.get('Origin') not in ALLOWED_ORIGINS or self.headers.get('X-Jaffle-Request')!='1':
            return self.reply(403,{'error':'Questions must originate from the local dashboard.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.reply(415,{'error':'Only JSON requests are supported.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 1<=length<=4096:
                raise Rejected('Request is too large.')
            self.connection.settimeout(5)
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict):
                raise Rejected('Invalid request.')
            path=urlsplit(self.path).path
            if path=='/api/ask':
                question=question_policy(payload.get('question'))
                key=' '.join(question.casefold().split())
                with LOCK:
                    if ACTIVE is not None:
                        return self.reply(409,{'error':'One question is already running. Wait for it to finish or cancel it.'})
                    job_id=uuid.uuid4().hex
                    if key in CURATED:
                        answer=copy.deepcopy(CURATED[key]); answer.update(mode='local',cached=False,instant_verified=True,elapsed_ms=0.0)
                        JOBS.clear(); JOBS[job_id]={'state':'complete','answer':answer,'elapsed_ms':0.0,'stage':'Instant verified answer','cache_key':key}
                        return self.reply(202,{'id':job_id,'state':'running','verified':True})
                    if key in CACHE:
                        answer=copy.deepcopy(CACHE[key]); answer['cached']=True; answer['elapsed_ms']=0.0
                        JOBS.clear(); JOBS[job_id]={'state':'complete','answer':answer,'elapsed_ms':0.0,'stage':'Cached answer','cache_key':key}
                        return self.reply(202,{'id':job_id,'state':'running','cached':True})
                    run=Run(question,model=MODEL,reasoning_effort=REASONING,stage_callback=lambda stage: self.set_stage(job_id,stage))
                    JOBS.clear()
                    JOBS[job_id]={'state':'running','run':run,'started_at':time.monotonic(),'stage':'Understanding question','cache_key':key}
                    ACTIVE=job_id
                threading.Thread(target=work,args=(job_id,run),daemon=True).start()
                return self.reply(202,{'id':job_id,'state':'running'})
            if path=='/api/cache/clear':
                with LOCK:
                    CACHE.clear();
                    try: CACHE_FILE.unlink()
                    except FileNotFoundError: pass
                return self.reply(200,{'cleared':True})
            if path=='/api/cancel':
                with LOCK:
                    job=JOBS.get(payload.get('id'))
                    run=job['run'] if job and job['state']=='running' else None
                if run:
                    run.cancel()
                return self.reply(200,{'cancelled':bool(run)})
            return self.reply(404,{'error':'Not found.'})
        except Rejected as error:
            return self.reply(400,{'error':str(error)})
        except Exception:
            return self.reply(400,{'error':'Invalid request. Enter a plain-text analytics question.'})

    @staticmethod
    def set_stage(job_id, stage):
        with LOCK:
            if job_id in JOBS: JOBS[job_id]['stage']=stage

if __name__=='__main__':
    print(f'Jaffle Shop and Ask Wren: {ORIGIN}/',flush=True)
    print('Local demo. One read-only question at a time. Ctrl+C stops the service.',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with LOCK:
            run=JOBS[ACTIVE]['run'] if ACTIVE else None
        if run:
            run.cancel()
    finally:
        server.server_close()
