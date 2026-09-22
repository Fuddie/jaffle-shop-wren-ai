import {queries, months, statuses} from './queries.mjs';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = new Intl.NumberFormat('en-AU', {maximumFractionDigits: 0});
const money = new Intl.NumberFormat('en-AU', {style:'currency', currency:'AUD', currencyDisplay:'code'});
const decimal = new Intl.NumberFormat('en-AU', {minimumFractionDigits:2, maximumFractionDigits:2});
const cash = n => money.format(n ?? 0);
const label = s => s.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const monthLabel = date => new Intl.DateTimeFormat('en-AU', {month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(typeof date === 'number' ? date : `${String(date).slice(0,7)}-01T00:00:00Z`));
const controls = [$('month'), $('status'), $('reset')];
let engine, baseline, report, visibleMonthly = [], updateSerial = 0;
for (const month of months) $('month').add(new Option(monthLabel(month), month));
for (const status of statuses) $('status').add(new Option(label(status), status));
function setBusy(busy) { controls.forEach(e => e.disabled = busy); $('dashboard').setAttribute('aria-busy', String(busy)); }
async function fetchJSON(path) { const response = await fetch(path); if(!response.ok) throw new Error(`Could not load ${path}`); return response.json(); }
async function run(sqls) { const result = {}; for (const [name, sql] of Object.entries(sqls)) result[name] = await engine.query(sql); return result; }
function showError(error) { $('error').hidden = false; $('error-message').textContent = `${String(error.message || error)}. Check your internet connection for the Wren CDN, then try again.`; $('load-status').textContent = 'Snapshot unavailable. No substitute values are displayed.'; setBusy(false); }
function table(headers, rows, caption, totals) {
  const row = cells => `<tr>${cells.map((c,i) => `<${i===0?'th scope="row"':'td'}>${esc(c)}</${i===0?'th':'td'}>`).join('')}</tr>`;
  return `<div class="table-wrap" tabindex="0" role="region" aria-label="${esc(caption)}. Scroll horizontally on small screens."><table><caption>${esc(caption)}</caption><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.map(row).join('') : `<tr><td colspan="${headers.length}" class="empty">No orders match these filters.</td></tr>`}</tbody>${totals ? `<tfoot>${row(totals)}</tfoot>` : ''}</table></div>`;
}
function render(data, sqls) {
  const k = data.kpis[0];
  const selectedMonth = $('month').value, selectedStatus = $('status').value;
  const scope = `${selectedMonth ? monthLabel(selectedMonth) : 'All months'} · ${selectedStatus ? label(selectedStatus) : 'All statuses'}`;
  $('scope').textContent = scope;
  const cards = [
    ['Total order amount', k.total_order_amount, true, 'All selected statuses', 'primary'],
    ['Orders', k.order_count, false, 'One count per order', ''],
    ['Average order value', k.average_order_value, true, 'Across selected orders', ''],
    ['Completed-order amount', k.completed_order_amount, true, 'Completed orders only', '']
  ];
  $('kpis').innerHTML = cards.map(([name,value,currency,note,cls])=>`<article class="kpi ${cls}"><div class="kpi-label">${name}</div><div class="kpi-value">${currency ? '<small>AUD</small>' : ''}${value == null && name === 'Average order value' ? 'N/A' : currency ? decimal.format(value ?? 0) : number.format(value ?? 0)}</div><div class="kpi-note">${note}</div></article>`).join('');
  $('inventory').innerHTML = [[baseline.inventory[0].customer_count,'Customers','Full snapshot'],[k.purchasing_customers,'Purchasing customers','Selected scope'],[baseline.payments[0].payment_count,'Payments','Full snapshot']].map(([n,name,note])=>`<article class="inventory-card"><strong>${number.format(n)}</strong><div><span>${name}</span><small>${note}</small></div></article>`).join('');
  $('sql-overview').textContent = `-- Order KPIs: governed order_metrics expressions\n${sqls.kpis};\n\n-- Full-snapshot inventory\n${sqls.inventory};\n${sqls.payments};`;
  const cells = r => [monthLabel(r.order_month),r.order_count,r.purchasing_customers,cash(r.total_order_amount),cash(r.average_order_value),cash(r.completed_order_amount)];
  $('monthly-table').innerHTML = table(['Order month','Orders','Purchasing customers','Total amount (AUD)','Average order value (AUD)','Completed amount (AUD)'],data.monthly.map(cells),'Monthly performance · selected scope',['Selected total',k.order_count,k.purchasing_customers,cash(k.total_order_amount),k.average_order_value == null ? 'N/A' : cash(k.average_order_value),cash(k.completed_order_amount)]);
  $('sql-monthly').textContent = sqls.monthly + ';';
  $('customer-table').innerHTML = table(['Customer ID','Customer name','Orders','Total amount (AUD)'],data.customers.map(r=>[r.customer_id,`${r.first_name} ${r.last_name}`,r.order_count,cash(r.total_order_amount)]),'Top customers · selected scope');
  $('sql-customers').textContent = sqls.customers + ';';
  const maxStatus = Math.max(...data.status.map(r=>Number(r.total_order_amount)),1);
  $('status-chart').innerHTML = data.status.length ? data.status.map(r=>`<div class="status-item ${r.status === 'completed' ? 'completed' : ''}" tabindex="0" data-tip="${esc(`${label(r.status)}\n${r.order_count} orders\n${cash(r.total_order_amount)}`)}"><div class="status-row"><span>${esc(label(r.status))}<small>${r.order_count} orders</small></span><strong>${cash(r.total_order_amount)}</strong></div><div class="track" aria-hidden="true"><span style="width:${Number(r.total_order_amount)/maxStatus*100}%"></span></div></div>`).join('') : '<p class="empty">No orders match these filters.</p>';
  $('sql-status').textContent = sqls.status + ';';
  visibleMonthly = data.monthly;
  renderChart();
  window.dashboardState = {ready:true,month:selectedMonth,status:selectedStatus,results:data};
  $('load-status').textContent = `Snapshot ready · ${scope} · ${k.order_count} orders in view`;
}
function renderQuality(sqls) {
  const checks = [['orphanOrders','Orders without customers','Every order references a customer.'],['orphanPayments','Payments without orders','Every payment references an order.'],['mismatches','Order/payment amount mismatches','Payment totals match orders within AUD 0.000001.']];
  const passed = checks.every(([name])=>Number(baseline[name][0].issues)===0);
  $('quality-badge').textContent = passed ? '3 OF 3 PASSED' : 'REVIEW REQUIRED';
  $('quality-cards').innerHTML = checks.map(([key,title,desc])=>{const n=Number(baseline[key][0].issues);return `<article class="quality-card ${n ? 'issue' : ''}"><div class="check"><span>${n ? 'Review required' : '✓ Pass'}</span><span>${n} issues</span></div><strong>${title}</strong><p>${esc(n ? 'Review the flagged records in this snapshot.' : desc)}</p></article>`;}).join('');
  const total=baseline.monthly.reduce((n,r)=>n+Number(r.total_order_amount),0), count=baseline.monthly.reduce((n,r)=>n+Number(r.order_count),0);
  if(total !== 1672 || count !== 99 || Number(baseline.kpis[0].total_order_amount)!==total || Number(baseline.kpis[0].order_count)!==count) throw new Error('Browser snapshot reconciliation failed');
  $('reconciliation').textContent = `✓ Reconciled: monthly amounts sum to ${cash(total)} and monthly order counts sum to ${count}. Both match the full-snapshot order KPIs.`;
  $('sql-quality').textContent = checks.map(([key,title])=>`-- ${title}\n${sqls[key]};`).join('\n\n')+`\n\n-- Reconciliation compares the sum of monthly results to overall results\n${sqls.monthly};\n\n${sqls.kpis};`;
}
function renderChart() {
  const host=$('chart');
  if(!visibleMonthly.length){host.innerHTML='<p class="empty">No orders match these filters.</p>';return;}
  const width=Math.max(host.clientWidth,230), left=44, right=12, plot=width-left-right, slot=plot/visibleMonthly.length;
  const moneyTop=32,moneyBottom=174,countTop=230,countBottom=303;
  const moneyMax=Math.max(100,Math.ceil(Math.max(...visibleMonthly.map(r=>Number(r.total_order_amount)))/100)*100);
  const countMax=Math.max(10,Math.ceil(Math.max(...visibleMonthly.map(r=>Number(r.order_count)))/10)*10);
  let content=`<text class="axis-title" x="0" y="13">Order amount (AUD)</text><text class="axis-title" x="0" y="215">Order count</text>`;
  for(let i=0;i<=4;i++){const y=moneyBottom-(moneyBottom-moneyTop)*i/4;content+=`<line class="grid" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"/><text x="${left-8}" y="${y+4}" text-anchor="end">${Math.round(moneyMax*i/4)}</text>`;}
  for(let i=0;i<=2;i++){const y=countBottom-(countBottom-countTop)*i/2;content+=`<line class="grid" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"/><text x="${left-8}" y="${y+4}" text-anchor="end">${Math.round(countMax*i/2)}</text>`;}
  const points=[];
  visibleMonthly.forEach((r,i)=>{
    const x=left+slot*(i+.5),bar=Math.min(32,slot*.25),totalH=Number(r.total_order_amount)/moneyMax*(moneyBottom-moneyTop),completeH=Number(r.completed_order_amount)/moneyMax*(moneyBottom-moneyTop),cy=countBottom-Number(r.order_count)/countMax*(countBottom-countTop);
    points.push(`${x},${cy}`);
    const tip=`${monthLabel(r.order_month)}\nTotal amount: ${cash(r.total_order_amount)}\nCompleted amount: ${cash(r.completed_order_amount)}\nOrder count: ${r.order_count}`;
    content+=`<g tabindex="0" role="img" aria-label="${esc(tip.replaceAll('\n', ', '))}" data-tip="${esc(tip)}"><rect class="focus-area" x="${left+i*slot+2}" y="23" width="${Math.max(slot-4,1)}" height="315" rx="5"/><rect x="${x-bar-2}" y="${moneyBottom-totalH}" width="${bar}" height="${totalH}" rx="3" fill="#68adff"/><rect x="${x+2}" y="${moneyBottom-completeH}" width="${bar}" height="${completeH}" rx="3" fill="#ab96ff"/><circle cx="${x}" cy="${cy}" r="4" fill="#b9d4f5"/><text x="${x}" y="${cy-10}" text-anchor="middle">${r.order_count}</text><text x="${x}" y="328" text-anchor="middle">${esc(monthLabel(r.order_month).split(' ')[0])}</text></g>`;
  });
  host.innerHTML=`<svg viewBox="0 0 ${width} 350" width="${width}" height="350" role="group" aria-label="Monthly order amounts and counts for 2018, with independent labeled scales"><polyline points="${points.join(' ')}" fill="none" stroke="#b9d4f5" stroke-width="2"/>${content}</svg>`;
  // SVG group focus events are inconsistent across browsers. Bind directly
  // so keyboard users receive the same tooltip as pointer users.
  host.querySelectorAll('[data-tip]').forEach(node => node.addEventListener('focus', () => showTip(node)));
}
async function update(){
  const serial=++updateSerial;
  setBusy(true);$('error').hidden=true;$('load-status').textContent='Querying the governed snapshot…';
  try{
    const sqls=queries($('month').value,$('status').value);
    const data={...baseline,...await run(Object.fromEntries(['kpis','monthly','customers','status'].map(k=>[k,sqls[k]])))};
    if(serial===updateSerial)render(data,sqls);
  }catch(e){showError(e);}finally{if(serial===updateSerial)setBusy(false);}
}
async function boot(){
  setBusy(true);$('error').hidden=true;
  try{
    const [module,mdl,validation]=await Promise.all([import('https://unpkg.com/@wrenai/wren-core-wasm@0.4.1/dist/index.js'),fetchJSON('mdl.json'),fetchJSON('validation.json')]);
    report=validation;engine=await module.WrenEngine.init();
    for (const table of ['customers','orders','stg_payments']) {
      const response = await fetch(`data/${table}.parquet`);
      if (!response.ok) throw new Error(`Could not load the ${table} snapshot`);
      await engine.registerParquet(table, await response.arrayBuffer());
    }
    await engine.loadMDL(mdl,{source:''});
    const sqls=queries();baseline=await run(sqls);
    renderQuality(sqls);render(baseline,sqls);
    $('validation-note').textContent=`Validation: ${report.unique_queries_validated} distinct SQL queries passed through Wren across ${report.filter_combinations} filter combinations. Snapshot exported ${new Intl.DateTimeFormat('en-AU',{dateStyle:'long',timeZone:'UTC'}).format(new Date(report.validated_at))} (UTC). Browser queries also reconcile the baseline before displaying it.`;
    setBusy(false);
  }catch(e){showError(e);}
}
$('month').addEventListener('change',update);$('status').addEventListener('change',update);
$('reset').addEventListener('click',()=>{$('month').value='';$('status').value='';update();});
$('retry').addEventListener('click',()=>location.reload());
let resizeTimer;new ResizeObserver(()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(renderChart,80);}).observe($('chart'));
const tooltip=$('tooltip');
function hideTip(){tooltip.hidden=true;}
function showTip(target){if(!target)return;tooltip.textContent=target.dataset.tip;tooltip.hidden=false;const rect=target.getBoundingClientRect();tooltip.style.left=`${Math.max(8,Math.min(rect.left,innerWidth-tooltip.offsetWidth-8))}px`;tooltip.style.top=`${Math.max(8,Math.min(rect.bottom+8,innerHeight-tooltip.offsetHeight-8))}px`;}
document.addEventListener('pointerover',e=>showTip(e.target.closest('[data-tip]')));
document.addEventListener('pointerout',e=>{if(e.target.closest('[data-tip]'))hideTip();});
document.addEventListener('focusin',e=>showTip(e.target.closest('[data-tip]')));
document.addEventListener('focusout',hideTip);document.addEventListener('keydown',e=>{if(e.key==='Escape')hideTip();});
window.addEventListener('scroll',hideTip,{passive:true});
boot();
