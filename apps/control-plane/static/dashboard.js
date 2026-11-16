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
async function refreshChain() {
  try {
    const overview=await api('/v1/chain/overview');
    $('chainStatus').textContent='Chain '+overview.chainId+' · block '+overview.headNumber+
      ' · '+overview.contractAddresses.filter(x=>x.hasCode).length+' configured contracts with code';
    const blocks=await api('/v1/chain/blocks?limit=10');
    renderTable('chainBlocks',['Block','Hash','Transactions','Gas used','Finality'],
      blocks.blocks.map(b=>[b.number,b.hash,b.transactionCount,b.gasUsed,b.finality]));
    const from=Math.max(0,overview.headNumber-31);
    const events=await api('/v1/chain/events?start_block='+from+'&end_block='+overview.headNumber);
    renderTable('chainEvents',['Block','Contract','Event','Details','Transaction'],
      events.events.slice(-25).reverse().map(e=>[
        e.blockNumber,e.address,e.sseDecoded?.name||(e.topics||[])[0]||'—',
        e.sseDecoded?JSON.stringify(e.sseDecoded.parameters):'Raw event (unknown ABI)',
        e.transactionHash]));
  }catch(e){
    $('chainStatus').textContent='Unavailable: '+e.message;
    $('chainBlocks').textContent='No verified RPC response; contract state not displayed.';
    $('chainEvents').textContent='No live contract event data.';
  }
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
    await refreshChain();
    message('Authenticated — showing inventory and configured read-only chain data.');
  }catch(e){message(e.message,true);}
}
$('connect').addEventListener('click',()=>{bearer=$('token').value;$('token').value='';refresh();});
$('inspectLease').addEventListener('click',async()=>{
  try {
    const lease=Number($('leaseId').value),epoch=Number($('epochId').value);
    if(!Number.isSafeInteger(lease)||lease<1||!Number.isSafeInteger(epoch)||epoch<0)
      throw new Error('Enter valid lease and epoch IDs.');
    const result=await api('/v1/chain/leases/'+lease+'/epochs/'+epoch);
    $('leaseDetail').textContent=JSON.stringify({
      chainHead:result.inspection.blockNumber,
      blockHash:result.inspection.blockHash,
      lease:result.inspection.lease,
      epoch:result.inspection.epoch,
      settlementExplanation:result.explanation
    },null,2);
  }catch(e){$('leaseDetail').textContent='Inspection unavailable: '+e.message;}
});
$('lookupTx').addEventListener('click',async()=>{
  try {
    const hash=$('txhash').value.trim();
    if(!/^0x[0-9a-fA-F]{64}$/.test(hash))throw new Error('Enter a 32-byte transaction hash.');
    const result=await api('/v1/chain/transactions/'+encodeURIComponent(hash));
    $('txDetail').textContent=JSON.stringify(result,null,2);
  }catch(e){$('txDetail').textContent='Lookup failed: '+e.message;}
});

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
