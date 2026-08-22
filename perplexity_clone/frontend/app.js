/* ==========================================================================
   Carnet de recherche — logique de l'interface (JavaScript pur, aucune
   dépendance externe : pas de React, pas de CDN de librairie). Le rendu
   est fait à la main via de simples manipulations du DOM, organisé par
   "composants" (fonctions de rendu), dans l'esprit de React mais sans
   la librairie.
   ========================================================================== */

const API = "http://localhost:8000";

const STEP_LABELS = {
  decompose: "Décomposition de la question",
  search: "Recherche web",
  scrape: "Lecture des pages",
  chunk: "Découpage du contenu",
  rerank: "Tri par pertinence",
  generate: "Rédaction de la réponse",
};
const STEP_ORDER = ["decompose","search","scrape","chunk","rerank","generate"];
const LEDGER_DELAYS = [3200,1800,2600,300,9000,14000];

const state = {
  conversations: [],
  activeId: null,
  messages: [],
  loading: false,
  ledgerStep: 0,
  apiUp: null,
};

let ledgerTimer = null;

function esc(s){
  const d = document.createElement('div');
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}
function fmtDate(ts){
  const d = new Date(ts*1000);
  return d.toLocaleDateString('fr-FR',{day:'2-digit',month:'short'}) + ' · ' +
         d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'});
}
function fmtSecs(s){ return s < 1 ? Math.round(s*1000)+'ms' : s.toFixed(1)+'s'; }

/* ---------- Rendu ---------- */

function renderSidebar(){
  const list = document.getElementById('conv-list');
  if(state.conversations.length === 0){
    list.innerHTML = '<div class="empty">Aucune recherche enregistrée pour l\'instant.</div>';
    return;
  }
  list.innerHTML = state.conversations.map(c => `
    <div class="conv-item ${c.id === state.activeId ? 'active' : ''}" data-id="${esc(c.id)}">
      <div class="conv-title">${esc(c.title)}</div>
      <div class="conv-date">${esc(fmtDate(c.created_at))}</div>
      <button class="conv-del" data-del="${esc(c.id)}" title="Supprimer">×</button>
    </div>
  `).join('');

  list.querySelectorAll('.conv-item').forEach(el=>{
    el.addEventListener('click', (e)=>{
      if(e.target.closest('.conv-del')) return;
      selectConversation(el.dataset.id);
    });
  });
  list.querySelectorAll('.conv-del').forEach(el=>{
    el.addEventListener('click', (e)=>{
      e.stopPropagation();
      deleteConversation(el.dataset.del);
    });
  });
}

function renderLedger(){
  if(!state.loading) return '';
  const rows = STEP_ORDER.map((key, idx)=>{
    const cls = idx < state.ledgerStep ? 'done' : idx === state.ledgerStep ? 'current' : '';
    return `<div class="ledger-row ${cls}"><span class="ledger-dot"></span><span>${STEP_LABELS[key]}</span></div>`;
  }).join('');
  return `<div class="ledger"><div class="ledger-title">Registre du pipeline</div>${rows}</div>`;
}

function renderMessage(m){
  const isUser = m.role === "user";
  let html = `<div class="msg ${isUser ? 'user' : 'assistant'}">
    <div class="msg-label ${isUser ? 'user' : 'assistant'}">${isUser ? 'Vous' : 'Assistant'}</div>
    <div class="msg-body">${esc(m.content)}</div>`;

  if(!isUser && m.timings && Object.keys(m.timings).length){
    html += `<div class="timing-row">${
      STEP_ORDER.filter(k=>m.timings[k]!==undefined)
        .map(k=>`<span>${STEP_LABELS[k]} <b>${fmtSecs(m.timings[k])}</b></span>`).join('')
    }</div>`;
  }
  if(!isUser && m.sources && m.sources.length){
    html += `<div class="sources"><div class="sources-title">Sources citées</div><ol>${
      m.sources.map(s=>`<li><span class="src-n">[${s.n}]</span><a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.url)}</a></li>`).join('')
    }</ol></div>`;
  }
  html += `</div>`;
  return html;
}

function renderThread(){
  const el = document.getElementById('thread-inner');
  if(state.messages.length === 0 && !state.loading){
    el.innerHTML = `<div class="intro">
      <div class="intro-mark">§</div>
      <p>Pose une question. La recherche s'appuie sur le web,
         le contenu est passé au crible d'un modèle tournant en local —
         aucune donnée n'est envoyée à un service tiers.</p>
    </div>`;
    return;
  }
  el.innerHTML = state.messages.map(renderMessage).join('') + renderLedger();
  document.getElementById('thread').scrollTop = document.getElementById('thread').scrollHeight;
}

function renderApiWarning(){
  const el = document.getElementById('api-warning');
  if(state.apiUp === false){
    el.style.display = 'block';
    el.innerHTML = `API locale injoignable sur ${esc(API)}. Lance <code>uvicorn api:app --reload</code> dans le dossier du projet.`;
  }else{
    el.style.display = 'none';
  }
}

function renderComposer(){
  document.getElementById('send-btn').disabled = state.loading || !document.getElementById('input').value.trim();
}

function render(){
  renderSidebar();
  renderThread();
  renderApiWarning();
  renderComposer();
}

/* ---------- Ledger animation pendant le chargement ---------- */

function startLedger(){
  state.ledgerStep = 0;
  clearTimeout(ledgerTimer);
  const tick = ()=>{
    state.ledgerStep = Math.min(state.ledgerStep + 1, STEP_ORDER.length - 1);
    renderThread();
    ledgerTimer = setTimeout(tick, LEDGER_DELAYS[state.ledgerStep] || 4000);
  };
  ledgerTimer = setTimeout(tick, LEDGER_DELAYS[0]);
}
function stopLedger(){
  clearTimeout(ledgerTimer);
}

/* ---------- Actions / appels API ---------- */

async function checkHealth(){
  try{
    const r = await fetch(API + "/health");
    state.apiUp = r.ok;
  }catch(e){ state.apiUp = false; }
  renderApiWarning();
}

async function loadConversations(){
  try{
    const r = await fetch(API + "/conversations");
    state.conversations = await r.json();
    renderSidebar();
  }catch(e){ /* API pas encore lancée */ }
}

async function selectConversation(id){
  state.activeId = id;
  const r = await fetch(`${API}/conversations/${id}/messages`);
  state.messages = await r.json();
  render();
}

function newConversation(){
  state.activeId = null;
  state.messages = [];
  document.getElementById('input').value = "";
  render();
}

async function deleteConversation(id){
  await fetch(`${API}/conversations/${id}`, {method:"DELETE"});
  if(id === state.activeId) newConversation();
  loadConversations();
}

async function send(){
  const input = document.getElementById('input');
  const query = input.value.trim();
  if(!query || state.loading) return;
  input.value = "";

  state.messages.push({role:"user", content:query, sources:[], timings:{}});
  state.loading = true;
  startLedger();
  render();

  try{
    const r = await fetch(API + "/ask", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({query, conversation_id: state.activeId}),
    });

    if(!r.ok){
      // L'API a bien répondu, mais avec une erreur (ex: 500 si Ollama a
      // expiré). On distingue ce cas d'une vraie panne réseau, pour ne
      // pas afficher à tort "API injoignable" alors qu'elle a répondu.
      let detail = `Erreur ${r.status}`;
      try{
        const errBody = await r.json();
        if(errBody.detail) detail = errBody.detail;
      }catch(_){ /* le corps n'était pas du JSON, on garde le code HTTP */ }
      throw new Error(`L'API a répondu avec une erreur (${detail}). Regarde le terminal où tourne uvicorn pour le détail technique.`);
    }

    const data = await r.json();
    state.activeId = data.conversation_id;
    state.messages.push({role:"assistant", content:data.answer, sources:data.sources, timings:data.timings});
    loadConversations();
  }catch(e){
    const isNetworkError = e instanceof TypeError; // fetch échoue avec un TypeError en cas de panne réseau/CORS
    state.messages.push({
      role:"assistant",
      content: isNetworkError
        ? "Impossible de joindre l'API locale. Vérifie que le serveur tourne (uvicorn api:app --reload)."
        : e.message,
      sources:[], timings:{},
    });
  }finally{
    state.loading = false;
    stopLedger();
    render();
  }
}

/* ---------- Écouteurs ---------- */

document.getElementById('new-btn').addEventListener('click', newConversation);
document.getElementById('send-btn').addEventListener('click', send);
document.getElementById('input').addEventListener('input', renderComposer);
document.getElementById('input').addEventListener('keydown', (e)=>{
  if(e.key === "Enter" && !e.shiftKey){
    e.preventDefault();
    send();
  }
});

/* ---------- Démarrage ---------- */

checkHealth();
loadConversations();
render();
