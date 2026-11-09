'use strict';
const $ = (id) => document.getElementById(id);
let bearer = '';
function message(text, bad = false) { $('message').textContent = text; $('message').className = bad ? 'error' : 'good'; }
async function api(url, opts = {}) {
  if (!bearer) throw new Error('Enter an API token');
  const response = await fetch(url, { ...opts, headers: {Authorization:`Bearer ${bearer}`, 'Content-Type':'application/json', ...(opts.headers || {})}, cache:'no-store'});
  const data = await response.json();
  if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed');
  return data;
}
function el(type, content) { const n = document.createElement(type); n.textContent = String(content); return n; }
function renderTable(rootId, cols, rows) {
  const root=$(rootId); root.replaceChildren();
  if(!rows.length) {root.append(el('p','No records.')); return;}
  const table=document.createElement('table'), thead=document.createElement('thead'), tr=document.createElement('tr');
  cols.forEach(c => tr.append(el('th',c)));thead.append(tr);table.append(thead);
  const tbody=document.createElement('tbody');
  rows.forEach(items=>{const row=document.createElement('tr');items.forEach(v=>row.append(el('td',v)));tbody.append(row);});
  table.append(tbody);root.append(table);
}
async function refresh() {
  try {
    const [inv,prop,audit,scenarios] = await Promise.all([api('/v1/nodes'),api('/v1/proposals'),api('/v1/audit'),api('/v1/settlement-scenarios')]);
    $('nodeCount').textContent=inv.nodes.length;
    $('proposalCount').textContent=prop.proposals.length;
    renderTable('nodes',['Node','Roles','Client','Stage'],inv.nodes.map(n=>[n.node_id,n.roles.join(', '),n.ethereum_client,n.status]));
    const root=$('proposals');root.replaceChildren();
    prop.proposals.forEach(n=>{
      const line=document.createElement('p');line.append(el('strong',n.node_id));line.append(el('span',` — ${n.roles.join(', ')} — ${n.status} `));
      if(n.status==='pending'){
        const b=el('button','Approve');b.className='secondary';
        b.addEventListener('click',async()=>{try{await api(`/v1/proposals/${encodeURIComponent(n.node_id)}/approve`,{method:'POST'});await refresh();}catch(e){message(e.message,true);}});line.append(b);
      }root.append(line);
    });
    if(!prop.proposals.length)root.append(el('p','No proposals yet.'));
    renderTable('audit',['Time','Action','Node'],audit.events.slice(-12).reverse().map(e=>[e.time,e.event,e.node_id]));
    renderTable('model',['Evidence','Provider','Consumer','Unresolved'],scenarios.results.map(r=>[r.scenario,r.provider_credit,r.consumer_refund,r.unresolved]));
    message('Authenticated — showing local desired state.');
  }catch(e){message(e.message,true);}
}
$('connect').addEventListener('click',()=>{bearer=$('token').value;$('token').value='';refresh();});
$('enroll').addEventListener('submit',async (ev)=>{
  ev.preventDefault();
  try {
    const body={node_id:$('node_id').value,private_ip:$('private_ip').value,ssh_user:$('ssh_user').value,
      roles:$('roles').value.split(',').map(s=>s.trim()).filter(Boolean),ethereum_client:$('ethereum_client').value,environment:$('environment').value};
    if(body.ethereum_client==='el_cl' && !body.roles.includes('ethereum_full_node'))body.roles.push('ethereum_full_node');
    if(body.ethereum_client==='el_cl_vc' && !body.roles.includes('validator'))body.roles.push('validator');
    await api('/v1/enrollment-proposals',{method:'POST',body:JSON.stringify(body)});
    await refresh();message('Proposal recorded; no VM contacted or role activated.');
  }catch(e){message(e.message,true);}
});
$('plan').addEventListener('click',async()=>{
  try{
    const paths=$('paths').value.split('\n').map(s=>s.trim()).filter(Boolean);
    const res=await api('/v1/deployment-plans',{method:'POST',body:JSON.stringify({paths})});
    $('planResult').textContent=JSON.stringify(res,null,2);
  }catch(e){message(e.message,true);}
});
