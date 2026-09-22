const $=id=>document.getElementById(id);
let examples=[],verifiedAt='';
const modes=[...document.querySelectorAll('input[name="ask-mode"]')];
const money=new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD',currencyDisplay:'code'});
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text).replaceAll('\u2014',',');if(className)node.className=className;return node;}
function format(value,column){if(value===null)return 'N/A';if(typeof value==='number'){if(/amount|value|spend/i.test(column))return money.format(value);return new Intl.NumberFormat('en-AU',{maximumFractionDigits:4}).format(value);}return String(value);}
function render(answer){
 const host=$('ask-answer');host.replaceChildren();host.hidden=false;
 host.append(element('p',`INSTANT VERIFIED ANSWER - VERIFIED EXAMPLE - Saved, independently validated result - ${new Date(verifiedAt).toLocaleDateString('en-AU',{timeZone:'UTC'})}`,'answer-source'));
 const heading=element('h3',answer.question);heading.tabIndex=-1;host.append(heading,element('p',answer.answer,'answer-summary'));
 for(const analysis of answer.analyses){
  host.append(element('h4',analysis.title));
  const region=element('div',undefined,'table-wrap');region.tabIndex=0;region.setAttribute('role','region');region.setAttribute('aria-label',`${analysis.title}. Scroll horizontally for all columns.`);
  const table=element('table'),thead=element('thead'),tr=element('tr');
  for(const name of analysis.columns){const th=element('th',name.replaceAll('_',' '));th.scope='col';tr.append(th);}thead.append(tr);table.append(thead);
  const tbody=element('tbody');for(const values of analysis.rows){const row=element('tr');values.forEach((v,i)=>row.append(element('td',format(v,analysis.columns[i]))));tbody.append(row);}table.append(tbody);region.append(table);host.append(region);
  if(!analysis.rows.length)host.append(element('p','No matching records.'));
  if(analysis.truncated)host.append(element('p','Showing the first 200 rows. Refine the question for a smaller result.','truncated'));
  const details=element('details',undefined,'sql-block'),summary=element('summary','Inspect governed SQL'),pre=element('pre',analysis.sql);pre.tabIndex=0;details.append(summary,pre);host.append(details);
 }
 const context=element('details',undefined,'result-context');context.append(element('summary',`Governed context and business rules - Models and views used: ${answer.models.join(', ')}`));context.append(element('p',`Models and views used: ${answer.models.join(', ')}`,'result-models'));const notes=element('ul');for(const note of answer.notes)notes.append(element('li',note));context.append(notes);host.append(context);heading.focus({preventScroll:true});
}
function showSuggestions(){const term=$('ask-search').value.trim().toLowerCase();document.querySelectorAll('#ask-samples button').forEach(button=>{button.hidden=!!term&&!button.textContent.toLowerCase().includes(term);});}
function controls(){$('ask-submit').disabled=true;$('ask-count').textContent=`${$('ask-question').value.length} / 500`;}
async function init(){
 try{const response=await fetch('verified-examples.json');if(!response.ok)throw new Error();const data=await response.json();examples=data.examples.map(x=>({...x,mode:'verified',instant_verified:true}));verifiedAt=data.verified_at;
  for(const example of examples){const button=element('button',example.question);button.type='button';button.addEventListener('click',()=>{$('ask-question').value=example.question;render(example);$('ask-progress').textContent='Instant verified answer shown. No AI request was made.';controls();});$('ask-samples').append(button);}showSuggestions();
 }catch{$('ask-error').textContent='Verified examples could not load. Refresh the page.';$('ask-error').hidden=false;}
 $('ask-service-status').textContent='Public static demo. Verified examples are saved, independently validated answers. Live arbitrary Ask Wren questions are available only when running the project locally. See the repository README for local setup.';
 $('ask-search').addEventListener('input',showSuggestions);$('ask-question').addEventListener('input',controls);controls();
}
$('ask-form').addEventListener('submit',event=>{event.preventDefault();$('ask-progress').textContent='Choose a suggested verified question. Live arbitrary questions require the local project service.';});
init();
