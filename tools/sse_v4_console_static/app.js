// SSE V4 console client. SOURCE-ONLY (2026-11-27): never executed in a browser.
// No secrets, no login. Transactions are sent only by the user's own wallet
// (EIP-1193 window.ethereum) after explicit review.
"use strict";
const $ = (id) => document.getElementById(id);
let MODE = "public";
let mOffset = 0;

function esc(v) {
  return String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch("/api/" + path, opt);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
function table(rows, cols) {
  if (!rows.length) return "<p>None.</p>";
  return "<table><thead><tr>" + cols.map((c) => "<th>" + esc(c) + "</th>").join("") + "</tr></thead><tbody>" +
    rows.map((r) => "<tr>" + cols.map((c) => "<td>" + esc(r[c] === undefined ? "" : (typeof r[c] === "object" ? JSON.stringify(r[c]) : r[c])) + "</td>").join("") + "</tr>").join("") +
    "</tbody></table>";
}
function meta(j) {
  return '<p class="note">Block ' + esc(j.observedBlock) + " (" + (j.finalized ? "finalized" : "NOT finalized") + "), source: " + esc(j.source) + ", observed " + new Date(j.observedAt * 1000).toISOString() + "</p>";
}
function show(el, html) { $(el).innerHTML = html; }
function fail(el, e) { show(el, '<p class="err">' + esc(e.message || e) + "</p>"); }

async function sendWithWallet(intent, el) {
  const box = $(el);
  box.innerHTML = "<h3>Unsigned transaction</h3><pre>" + esc(JSON.stringify(intent, null, 2)) + "</pre>";
  if (!window.ethereum) { box.innerHTML += '<p class="note">No browser wallet detected. Sign with your owner-local agent CLI instead.</p>'; return; }
  const btn = document.createElement("button");
  btn.textContent = "Review and send with my wallet";
  btn.onclick = async () => {
    try {
      const chain = await window.ethereum.request({ method: "eth_chainId" });
      if (parseInt(chain, 16) !== intent.chainId) throw new Error("wallet is on the wrong chain");
      const [from] = await window.ethereum.request({ method: "eth_requestAccounts" });
      const h = await window.ethereum.request({ method: "eth_sendTransaction", params: [{ from, to: intent.to, data: intent.data, value: intent.value }] });
      box.innerHTML += "<p>Submitted " + esc(h) + ". Pending until included and finalized; check the Explorer tab.</p>";
    } catch (e) { box.innerHTML += '<p class="err">' + esc(e.message || e) + "</p>"; }
  };
  box.appendChild(btn);
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("nav button").forEach((x) => x.removeAttribute("aria-current"));
  b.setAttribute("aria-current", "page");
  document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== b.dataset.tab; });
}));

// --------------------------------------------------------- marketplace
async function loadMarket() {
  try {
    const s = $("mStatus").value;
    const j = await api("requests?offset=" + mOffset + "&limit=20" + (s ? "&status=" + s : ""));
    show("mList", meta(j) + "<p>" + j.total + " requests total.</p>" + table(j.rows, ["id", "statusName", "consumer", "maxEpochFee", "fixedEpochs", "maxEpochs", "seats", "standbys", "faultTolerance", "perReportReward", "bidCount", "profileHash"]));
    $("mList").querySelectorAll("tbody tr").forEach((tr, i) => { tr.tabIndex = 0; tr.onclick = () => loadRequest(j.rows[i].id); });
  } catch (e) { fail("mList", e); }
}
async function loadRequest(id) {
  try {
    const j = await api("request/" + id);
    let html = "<h3>Request " + esc(id) + "</h3>" + meta(j) + "<pre>" + esc(JSON.stringify(j.request, null, 2)) + "</pre><p class='note'>" + esc(j.note) + "</p>";
    html += table(j.bids, ["index", "provider", "epochFee", "epochs", "expiry", "withdrawn", "valid", "fundingWei", "offerHash"]);
    show("mDetail", html);
  } catch (e) { fail("mDetail", e); }
}
$("mStatus").onchange = () => { mOffset = 0; loadMarket(); };
$("mPrev").onclick = () => { mOffset = Math.max(0, mOffset - 20); loadMarket(); };
$("mNext").onclick = () => { mOffset += 20; loadMarket(); };

// ------------------------------------------------------------- request
function formObj(f) { return Object.fromEntries(new FormData(f).entries()); }
$("rPlan").onclick = async () => {
  const f = formObj($("rForm"));
  try {
    const j = await api("plan?seats=" + f.seats + "&b=" + f.faultTolerance + "&standbys=" + f.standbys + "&epochs=" + f.maxEpochs + "&fee=" + f.maxEpochFee + "&reward=" + f.perReportReward);
    const p = j.plan;
    let html = meta(j);
    if (!p.valid) { html += '<p class="err">' + esc(p.errors.join("; ")) + "</p>"; }
    else {
      html += "<p>Quorum q = " + p.quorum + " of n = " + p.seats + " (tolerates b = " + p.faultTolerance + " faulty seats under the stated assumptions).</p>";
      html += "<p>Eligible monitors now: " + p.observedEligible + " of " + p.observedPopulation + "; needed n+s = " + (p.seats + p.standbys) + ". Draw success probability ≈ " + (p.drawSuccessProbability.probability * 100).toFixed(2) + "%.</p>";
      html += "<p>Funding: service " + p.prices.serviceWei + " + monitor reports " + p.prices.monitorReportBudgetWei + " = <b>" + p.prices.totalFundingWei + " wei</b> (plus gas). Standbys are unpaid unless promoted.</p>";
      if (!p.feasibleNow) html += '<p class="warn">Not enough eligible monitors. Options (nothing is changed automatically):</p>' + table(p.alternatives, ["action", "seats", "standbys", "faultTolerance", "weakensFaultGoal", "requiresExplicitConsent", "tradeoff"]);
      html += '<p class="note">' + esc(p.assumptions.join(" · ")) + "</p>";
    }
    show("rPlanOut", html);
  } catch (e) { fail("rPlanOut", e); }
};
$("rUpload").onclick = async () => {
  const files = $("rFiles").files;
  try {
    const payload = [];
    for (const f of files) {
      const buf = new Uint8Array(await f.arrayBuffer());
      let bin = ""; for (const x of buf) bin += String.fromCharCode(x);
      payload.push({ name: f.name, base64: btoa(bin) });
    }
    const j = await api("upload", { files: payload });
    $("rForm").artifactCommitment.value = j.artifactCommitment;
    show("rOut", "<p>Commitment computed; files stay on this host.</p><pre>" + esc(JSON.stringify(j, null, 2)) + "</pre>");
  } catch (e) { fail("rOut", e); }
};
$("rForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const f = formObj(ev.target);
  const n = (k) => parseInt(f[k], 10);
  const body = {
    profileHash: f.profileHash, policyHash: f.policyHash, artifactCommitment: f.artifactCommitment,
    maxEpochFee: n("maxEpochFee"), biddingClose: Math.floor(Date.now() / 1000) + 60 * n("biddingMinutes"),
    fixedEpochs: f.epochMode === "fixed" ? n("maxEpochs") : 0, maxEpochs: n("maxEpochs"),
    seats: n("seats"), standbys: n("standbys"), faultTolerance: n("faultTolerance"), perReportReward: n("perReportReward"),
  };
  try { await sendWithWallet(await api("intent/createRequest", body), "rOut"); } catch (e) { fail("rOut", e); }
};

// --------------------------------------------------------------- lease
const PHASE_HELP = {
  PendingDraw: "Funded; waiting for the committed entropy block, then anyone may draw the committee.",
  Forming: "Committee drawn; monitors confirm; missing seats are replaced by standbys in fixed order.",
  Active: "Committee frozen. Epochs may start once the provider has accepted the exact terms.",
  Closed: "No new epochs. Open evidence windows and residuals are still honored.",
  Cancelled: "Refunded before any service started.",
};
async function loadLease() {
  try {
    const j = await api("lease/" + $("lId").value);
    const b = j.bundle, l = b.lease;
    let html = meta(j) + "<h3>Lease " + esc($("lId").value) + ": " + esc(b.phase) + "</h3><p class='note'>" + esc(PHASE_HELP[b.phase] || "") + "</p>";
    html += table([l], ["consumer", "provider", "providerAccepted", "seats", "standbys", "faultTolerance", "epochFee", "maxEpochs", "nextEpoch", "closedEpochs", "termsHash"]);
    html += "<h4>SSE accounting</h4>" + table([b.accounting], ["funded", "available", "exposure", "budget", "providerCredit", "consumerCredit", "conserved"]);
    if (b.assignment) html += "<h4>Committee formation</h4>" + table([b.assignment], ["phaseName", "deadline", "quorum", "confirmedCount", "nextStandby", "primary", "standby"]);
    if (b.members) html += "<h4>Frozen committee</h4><p>" + b.members.map(esc).join("<br>") + "</p>";
    html += "<h4>Epochs</h4>" + table(b.epochs.map((e) => ({ id: e.id, request: e.market.requestHash, responseAuthenticated: e.votes.responseAuthenticated, success: e.votes.successVotes, failure: e.votes.failureVotes, sealed: e.votes.monitoringSealed, outcome: ["None", "Success", "Failure"][e.votes.outcome], histories: e.science.mask, provider: e.science.providerCredit, consumer: e.science.consumerCredit, unresolved: e.science.unresolved, evidenceClosed: e.science.evidenceClosed })), ["id", "request", "responseAuthenticated", "success", "failure", "sealed", "outcome", "histories", "provider", "consumer", "unresolved", "evidenceClosed"]);
    html += '<p class="note">History mask bits: 1 = N (not received), 2 = F (received, failed), 4 = S (succeeded). Unresolved amounts stay escrowed until evidence or bilateral consent.</p>';
    html += '<div id="lActs"></div>';
    show("lOut", html);
    const acts = { PendingDraw: ["drawCommittee", "cancelExpiredDraw", "cancelUnaccepted", "acceptLease"], Forming: ["activateCommittee", "cancelUnformed", "cancelUnaccepted", "acceptLease"], Active: ["acceptLease", "closeLease", "forceCloseIdle", "cancelUnaccepted"] }[b.phase] || [];
    acts.forEach((a) => {
      const btn = document.createElement("button");
      btn.textContent = "Prepare " + a;
      btn.onclick = async () => { try { await sendWithWallet(await api("intent/" + a, { leaseId: parseInt($("lId").value, 10) }), "lActs"); } catch (e) { fail("lActs", e); } };
      $("lActs").appendChild(btn);
    });
  } catch (e) { fail("lOut", e); }
}
$("lLoad").onclick = loadLease;

// ------------------------------------------------------------ provider
$("bForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const f = formObj(ev.target);
  const body = { requestId: parseInt(f.requestId, 10), epochFee: parseInt(f.epochFee, 10), epochs: parseInt(f.epochs, 10), expiry: Math.floor(Date.now() / 1000) + 3600 * parseInt(f.hours, 10), endpointHash: f.endpointHash, offerHash: f.offerHash };
  try { await sendWithWallet(await api("intent/placeBid", body), "bOut"); } catch (e) { fail("bOut", e); }
};

// ------------------------------------------------------------- monitor
$("moReg").onclick = async () => { try { await sendWithWallet(await api("intent/registerMonitor", { capacity: parseInt($("moCap").value, 10) }), "moOut"); } catch (e) { fail("moOut", e); } };
$("moExit").onclick = async () => { try { await sendWithWallet(await api("intent/requestExit", {}), "moOut"); } catch (e) { fail("moOut", e); } };
$("moDone").onclick = async () => { try { await sendWithWallet(await api("intent/completeExit", {}), "moOut"); } catch (e) { fail("moOut", e); } };

// ------------------------------------------------------------- account
$("aLoad").onclick = async () => {
  try {
    const j = await api("account/" + $("aAddr").value);
    show("aOut", meta(j) + "<h4>Withdrawable (wei)</h4>" + table([j.withdrawable], ["market", "registry", "ledger"]) + "<h4>Monitor position</h4>" + table([j.monitor], ["bond", "capacity", "reserved", "available", "exiting"]));
  } catch (e) { fail("aOut", e); }
};

// ------------------------------------------------------------ explorer
$("eBlockGo").onclick = async () => { try { show("eOut", "<pre>" + esc(JSON.stringify(await api("block/" + encodeURIComponent($("eBlock").value)), null, 2)) + "</pre>"); } catch (e) { fail("eOut", e); } };
$("eTxGo").onclick = async () => { try { show("eOut", "<pre>" + esc(JSON.stringify(await api("tx/" + encodeURIComponent($("eTx").value)), null, 2)) + "</pre>"); } catch (e) { fail("eOut", e); } };
$("pGo").onclick = async () => {
  const slots = $("pSlots").value.split(",").map((s) => s.trim()).filter(Boolean).map((s) => "&slot=" + encodeURIComponent(s)).join("");
  try {
    const j = await api("proof?address=" + encodeURIComponent($("pAddr").value) + slots + "&block=" + encodeURIComponent($("pBlock").value));
    if (j.available === false) { show("eOut", '<p class="warn">' + esc(j.reason) + "</p>"); return; }
    let html = "<p>Account: <b>" + esc(j.account) + "</b> against stateRoot " + esc(j.stateRoot) + " at block " + esc(j.block) + "</p>";
    html += "<h4>Account proof path (nodes returned by the node only)</h4>" + table(j.accountPath, ["depth", "kind", "hash"]);
    j.storage.forEach((s) => { html += "<h4>Slot " + esc(s.slot) + " = " + esc(s.value) + " (" + esc(s.status) + ")</h4>" + table(s.path, ["depth", "kind", "hash"]); });
    html += '<p class="note">' + esc(j.note) + "</p>";
    show("eOut", html);
  } catch (e) { fail("eOut", e); }
};

// ---------------------------------------------------------------- init
(async () => {
  try {
    MODE = (await api("mode")).mode;
    const o = await api("overview");
    $("status").textContent = "Mode: " + MODE + " · finalized block " + o.finalizedHeight + " · " + o.counts.requests + " requests, " + o.counts.leases + " leases, " + o.counts.activeMonitors + " active monitors";
    if (MODE !== "local") { $("rUpload").disabled = true; $("rFiles").disabled = true; }
    loadMarket();
  } catch (e) { $("status").textContent = "Console unavailable: " + (e.message || e); }
})();

// ---------------------------------------------------------- node page
$("nLoad").onclick = async () => {
  try {
    const j = await api("node");
    const rows = ["latest", "safe", "finalized"].map((t) => ({ tag: t, number: j[t] && parseInt(j[t].number, 16), hash: j[t] && j[t].hash }));
    let html = "<p>Client " + esc(JSON.stringify(j.client)) + " · EL peers " + esc(JSON.stringify(j.peerCount)) + " · syncing " + esc(JSON.stringify(j.syncing)) + "</p>" + table(rows, ["tag", "number", "hash"]);
    html += "<p>Historical state at block 1: " + esc(j.historicalStateAtBlock1) + "</p>";
    html += "<h4>Consensus layer</h4><pre>" + esc(JSON.stringify(j.beacon, null, 2)) + "</pre>";
    show("nOut", html);
  } catch (e) { fail("nOut", e); }
};
$("vLoad").onclick = async () => {
  const ids = $("vIds").value.split(",").map((s) => s.trim()).filter(Boolean).map((s) => "id=" + encodeURIComponent(s)).join("&");
  try {
    const j = await api("validators?" + ids + "&state=" + $("vState").value);
    if (j.available === false) { show("vOut", '<p class="warn">' + esc(j.reason) + "</p>"); return; }
    const rows = (j.validators || []).map((v) => ({ index: v.index, status: v.status, balanceGwei: v.balance, effectiveGwei: v.validator.effective_balance, slashed: v.validator.slashed, activationEpoch: v.validator.activation_epoch, exitEpoch: v.validator.exit_epoch, pubkey: v.validator.pubkey }));
    show("vOut", "<p class='note'>State " + esc(j.state) + ", finalized flag " + esc(j.finalized) + ". " + esc(j.note) + "</p>" + table(rows, ["index", "status", "balanceGwei", "effectiveGwei", "slashed", "activationEpoch", "exitEpoch", "pubkey"]));
  } catch (e) { fail("vOut", e); }
};

// ------------------------------------------------- consumer epoch outputs
function showOutput(j) {
  const ok = j.verified ? "<p>Verified: output matches the finalized on-chain response hash.</p>"
    : '<p class="err">NOT verified: output does not match the finalized on-chain response hash (or none is recorded yet).</p>';
  let html = meta(j) + ok + table([j], ["onchainResponseHash", "outputResponseHash"]) + '<p class="note">' + esc(j.meaning) + "</p>";
  if (j.output !== undefined) {
    const blob = new Blob([JSON.stringify(j.output, null, 2)], { type: "application/json" });
    html += '<p><a download="sse-lease-' + esc($("lId").value) + "-epoch-" + esc($("oEpoch").value) + '.json" href="' + URL.createObjectURL(blob) + '">Save output</a></p>';
  }
  show("oOut", html);
}
$("oFetch").onclick = async () => {
  try {
    if (MODE !== "local") throw new Error("Download runs only in the owner-local console; paste the output to verify here.");
    if (!window.ethereum) throw new Error("No browser wallet detected.");
    const lid = Number($("lId").value), eid = Number($("oEpoch").value);
    const m = await api("output-message?lease=" + lid + "&epoch=" + eid);
    const [from] = await window.ethereum.request({ method: "eth_requestAccounts" });
    const msgHex = "0x" + Array.from(new TextEncoder().encode(m.message)).map((b) => b.toString(16).padStart(2, "0")).join("");
    const signature = await window.ethereum.request({ method: "personal_sign", params: [msgHex, from] });
    showOutput(await api("output-fetch", { providerUrl: $("oUrl").value.trim(), leaseId: lid, epochId: eid, expiry: m.expiry, signature }));
  } catch (e) { fail("oOut", e); }
};
$("oVerify").onclick = async () => {
  try {
    const output = JSON.parse($("oPaste").value);
    showOutput(await api("output-verify", { leaseId: Number($("lId").value), epochId: Number($("oEpoch").value), output }));
  } catch (e) { fail("oOut", e); }
};
