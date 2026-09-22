const $=id=>document.getElementById(id);
const SERVICE_BASE=location.port==='4173'?'http://127.0.0.1:4174':location.origin;
let examples=[], verifiedAt='', available=false, busy=false, jobId=null, pollTimer=null, started=0, modeTouched=false;
const modes=[...document.querySelectorAll('input[name="ask-mode"]')];
const mode=()=>modes.find(r=>r.checked).value;
const money=new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD',currencyDisplay:'code'});
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text).replaceAll('\u2014',',');if(className)node.className=className;return node;}
function error(message){$('ask-error').textContent=message;$('ask-error').hidden=false;}
function controls(){
  modes.forEach(r=>r.disabled=busy);
  $('ask-question').disabled=busy||mode()==='verified';
  $('ask-submit').disabled=busy||mode()!=='local'||!available||!$('ask-question').value.trim();
  $('ask-cancel').hidden=!busy;
  document.querySelectorAll('#ask-samples button').forEach(b=>b.disabled=busy);
  $('ask-samples-label').textContent=mode()==='verified'?'Suggested questions':'Suggested questions, or ask something new';
  $('ask-count').textContent=`${$('ask-question').value.length} / 500`;
}
async function request(path,body){
  const response=await fetch(`${SERVICE_BASE}${path}`,{method:'POST',headers:{'Content-Type':'application/json','X-Jaffle-Request':'1'},body:JSON.stringify(body),signal:AbortSignal.timeout(12000)});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'The local service could not accept this request.');
  return result;
}
function finish(message){busy=false;jobId=null;clearTimeout(pollTimer);$('ask-progress').textContent=message;$('ask-answer').setAttribute('aria-busy','false');controls();}
function format(value,column){if(value===null)return 'N/A';if(typeof value==='number'){if(/amount|value|spend/i.test(column))return money.format(value);return new Intl.NumberFormat('en-AU',{maximumFractionDigits:4}).format(value);}return String(value);}
function render(answer){
  const host=$('ask-answer');host.replaceChildren();host.hidden=false;
  const source=(answer.mode==='verified'||answer.instant_verified)?`INSTANT VERIFIED ANSWER - VERIFIED EXAMPLE - Saved governed result, LOCAL CODEX ANSWER not used - ${new Date(verifiedAt).toLocaleDateString('en-AU',{timeZone:'UTC'})}`:(answer.cached?`CACHED ANSWER - ${(answer.elapsed_ms/1000).toFixed(1)}s - LOCAL CODEX ANSWER - SQL independently verified through Wren`:`NEW ANALYSIS, TYPICALLY 30 TO 90 SECONDS - LOCAL CODEX ANSWER - ${(answer.elapsed_ms/1000).toFixed(1)}s - SQL independently verified through Wren`);
  host.append(element('p',source,'answer-source'));
  const heading=element('h3',answer.question);heading.tabIndex=-1;host.append(heading,element('p',answer.answer,'answer-summary'));
  for(const analysis of answer.analyses){
    host.append(element('h4',analysis.title));
    const region=element('div',undefined,'table-wrap');region.tabIndex=0;region.setAttribute('role','region');region.setAttribute('aria-label',`${analysis.title}. Scroll horizontally for all columns.`);
    const table=element('table'),thead=element('thead'),tr=element('tr');
    for(const name of analysis.columns){const th=element('th',name.replaceAll('_',' '));th.scope='col';tr.append(th);}thead.append(tr);table.append(thead);
    const tbody=element('tbody');for(const values of analysis.rows){const row=element('tr');values.forEach((v,i)=>row.append(element('td',format(v,analysis.columns[i]))));tbody.append(row);}table.append(tbody);region.append(table);host.append(region);
    if(!analysis.rows.length)host.append(element('p','No matching records.'));
    if(analysis.truncated)host.append(element('p','Showing the first 200 rows. Refine the question for a smaller result.','truncated'));
    const details=element('details',undefined,'sql-block'),summary=element('summary','Inspect generated SQL'),pre=element('pre',analysis.sql);pre.tabIndex=0;details.append(summary,pre);host.append(details);
  }
  const context=element('details',undefined,'result-context');context.append(element('summary',`Governed context and business rules - Models and views used: ${answer.models.join(', ')} - Total order amount is not revenue`));context.append(element('p',`Models and views used: ${answer.models.join(', ')}`,'result-models'));const notes=element('ul');for(const note of answer.notes)notes.append(element('li',note));context.append(notes);host.append(context);
  heading.focus({preventScroll:true});
}
async function poll(){
  if(!jobId)return;
  try{
    const response=await fetch(`${SERVICE_BASE}/api/jobs/${jobId}`,{signal:AbortSignal.timeout(12000)});
    if(!response.ok)throw new Error('The question status is unavailable.');
    const result=await response.json();
    if(result.state==='complete'){render(result.answer);finish('Answer ready.');return;}
    if(result.state==='error'||result.state==='cancelled'){if(result.state==='error')error(result.error);finish(result.state==='cancelled'?'Question cancelled.':'Question could not complete.');return;}
    const seconds=Math.floor((Date.now()-started)/1000);$('ask-progress').textContent=`${result.stage||'Working'} - ${seconds}s`;
    if(seconds>195){await request('/api/cancel',{id:jobId}).catch(()=>{});throw new Error('The question timed out. Try a simpler question.');}
    pollTimer=setTimeout(poll,1000);
  }catch(e){if(jobId)request('/api/cancel',{id:jobId}).catch(()=>{});error('The local service connection was lost or the request timed out. Use Verified examples, or restart the local service.');finish('Question stopped.');}
}
$('ask-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy||!available||mode()!=='local')return;
  const question=$('ask-question').value.trim();if(!question||question.length>500){error('Enter a question between 1 and 500 characters.');return;}
  busy=true;started=Date.now();$('ask-error').hidden=true;$('ask-answer').hidden=true;$('ask-answer').setAttribute('aria-busy','true');$('ask-progress').textContent='Understanding question - 0s';controls();
  try{const result=await request('/api/ask',{question});jobId=result.id;poll();}catch(e){error(e.message||'The local service is unavailable. Choose Verified examples.');finish('Question not started.');}
});
$('ask-clear-cache').addEventListener('click',async()=>{try{await request('/api/cache/clear',{});$('ask-progress').textContent='Local answer cache cleared.';}catch{error('The local cache could not be cleared.');}});
$('ask-cancel').addEventListener('click',async()=>{
  if(!jobId){$('ask-progress').textContent='Starting the request. Cancel will be available in a moment.';return;}
  $('ask-cancel').disabled=true;
  try{await request('/api/cancel',{id:jobId});$('ask-progress').textContent='Cancelling the local agent…';}catch{error('Cancellation could not reach the service. The server timeout remains active.');}finally{$('ask-cancel').disabled=false;}
});
$('ask-question').addEventListener('input',controls);
modes.forEach(r=>r.addEventListener('change',()=>{modeTouched=true;$('ask-error').hidden=true;$('ask-answer').hidden=true;$('ask-progress').textContent='';controls();}));
function showSuggestions(){
  const term=$('ask-search').value.trim().toLowerCase();
  document.querySelectorAll('#ask-samples button').forEach(button=>{button.hidden=!!term&&!button.textContent.toLowerCase().includes(term);});
}
async function init(){
  try{
    const response=await fetch('verified-examples.json');if(!response.ok)throw new Error();const data=await response.json();examples=data.examples.map(x=>({...x,mode:'verified',instant_verified:true,cached:false}));verifiedAt=data.verified_at;
    for(const example of examples){const button=element('button',example.question);button.type='button';button.addEventListener('click',()=>{$('ask-error').hidden=true;$('ask-question').value=example.question;if(mode()==='verified'){render(example);$('ask-progress').textContent='Instant verified answer shown. No AI request was made.';}else{$('ask-question').focus();}controls();});$('ask-samples').append(button);}
    showSuggestions();
  }catch{error('Saved examples could not load. Refresh the dashboard.');}
  try{const response=await fetch(`${SERVICE_BASE}/local-status.json`,{signal:AbortSignal.timeout(3000)});if(response.ok){const data=await response.json();available=data.available===true;}}catch{available=false;}
  $('ask-service-status').textContent=available?`Local service connected at ${SERVICE_BASE}. Luna, low reasoning. One read-only question at a time.`:'Local service offline. Verified examples remain available without an AI connection.';
  if(available&&!modeTouched)modes.find(r=>r.value==='local').checked=true;
  controls();
}
$('ask-search').addEventListener('input',showSuggestions);
init();
