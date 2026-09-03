/* ==========================================================================
   Carnet de recherche — logique de l'interface (JavaScript pur, aucune
   dépendance externe : pas de React, pas de CDN de librairie). Le rendu
   est fait à la main via de simples manipulations du DOM, organisé par
   "composants" (fonctions de rendu), dans l'esprit de React mais sans
   la librairie.

   L'avancement affiché n'est pas simulé : il provient du flux SSE exposé
   par POST /ask/stream, qui émet l'étape réellement en cours puis la
   réponse fragment par fragment.
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

const EXAMPLES = [
  "Quel est l'impact réel des ZFE sur la qualité de l'air ?",
  "Différence entre RAG et fine-tuning",
  "Coût énergétique d'un modèle qui tourne en local",
  "Quantification GGUF : quelles pertes de qualité ?",
];

const state = {
  conversations: [],
  activeId: null,
  messages: [],
  loading: false,
  steps: {},        // clé d'étape -> {status: 'pending'|'running'|'done', duration}
  apiUp: null,
  statusOpen: false,   // la ligne de statut est-elle dépliée ?
  sidebarOpen: true,   // panneau d'historique visible ?
};

let controller = null;   // AbortController de la requête en cours
let healthTimer = null;
let pendingFrame = null; // requestAnimationFrame en attente pour le streaming

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

/* Transforme les mentions [Source N] du texte en pastilles cliquables vers la
   source correspondante, listée sous la réponse. Le texte est échappé d'abord :
   la notation ne contient aucun caractère HTML, elle survit intacte. */
function linkCitations(text, msgIdx){
  return esc(text).replace(/\[Source\s+(\d+)\]/g, (match, n) =>
    `<a class="cite" href="#src-${msgIdx}-${n}" data-cite="${msgIdx}-${n}">${n}</a>`);
}

/* ---------- Rendu ---------- */

function renderSidebar(){
  const list = document.getElementById('conv-list');
  if(state.conversations.length === 0){
    list.innerHTML = '<div class="empty">Aucune recherche enregistrée pour l\'instant.</div>';
    return;
  }
  // Les conversations sont regroupées par jour : un intitulé mono par journée.
  let lastDay = null;
  list.innerHTML = state.conversations.map(c => {
    const day = new Date(c.created_at*1000)
      .toLocaleDateString('fr-FR',{day:'2-digit',month:'short'});
    const head = day === lastDay ? '' : `<div class="day">${esc(day)}</div>`;
    lastDay = day;
    const time = new Date(c.created_at*1000)
      .toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'});
    return `${head}<div class="conv-item ${c.id === state.activeId ? 'active' : ''}" data-id="${esc(c.id)}">
      <div class="conv-title">${esc(c.title)}</div>
      <div class="conv-date">${esc(time)}</div>
      <button class="conv-del" data-del="${esc(c.id)}" title="Supprimer">×</button>
    </div>`;
  }).join('');
}

/* Ligne de statut : une seule ligne animée (étape en cours, temps écoulé,
   barre de progression). Les six étapes ne s'affichent qu'au clic. */
function renderStatus(){
  const bar = document.getElementById('status-bar');
  if(!state.loading){
    bar.className = '';
    bar.innerHTML = '';
    return;
  }
  const doneCount = STEP_ORDER.filter(k => (state.steps[k]||{}).status === 'done').length;
  const runningIdx = STEP_ORDER.findIndex(k => (state.steps[k]||{}).status === 'running');
  const idx = runningIdx === -1 ? Math.min(doneCount, STEP_ORDER.length-1) : runningIdx;
  const elapsed = STEP_ORDER.reduce((a,k) => a + ((state.steps[k]||{}).duration || 0), 0);

  const chips = STEP_ORDER.map(key => {
    const st = state.steps[key] || {status:'pending'};
    const time = st.duration !== undefined ? `<b>${fmtSecs(st.duration)}</b>` : '';
    return `<span class="step-chip ${st.status}"><i></i>${STEP_LABELS[key]}${time}</span>`;
  }).join('');

  bar.className = 'on';
  bar.innerHTML = `
    <div class="status-line" id="status-line">
      <span class="status-dot"><i></i></span>
      <span class="status-label">${STEP_LABELS[STEP_ORDER[idx]]}</span>
      <span class="status-meta">étape ${idx+1}/6 · ${fmtSecs(elapsed)}</span>
      <span class="status-more">détails ${state.statusOpen ? '▲' : '▼'}</span>
    </div>
    <div class="status-track"><div class="status-fill" style="width:${Math.round((idx+1)/6*100)}%"></div></div>
    ${state.statusOpen ? `<div class="status-steps">${chips}</div>` : ''}`;
}

function renderMessage(m, idx){
  const isUser = m.role === "user";
  // Pendant le streaming, le texte vit dans un span à part : le curseur
  // clignotant reste ainsi un nœud voisin, jamais écrasé par la mise à jour.
  const body = isUser
    ? esc(m.content)
    : (m.streaming
        ? `<span id="streaming-text">${esc(m.content)}</span><span class="caret"></span>`
        : linkCitations(m.content, idx));

  let html = `<div class="msg ${isUser ? 'user' : 'assistant'} ${m.error ? 'error' : ''}">
    <div class="msg-label">${isUser ? 'Vous' : 'Assistant'}</div>
    <div class="msg-body">${body}</div>`;

  if(!isUser && m.timings && Object.keys(m.timings).length){
    html += `<div class="timing-row">${
      STEP_ORDER.filter(k=>m.timings[k]!==undefined)
        .map(k=>`<span>${STEP_LABELS[k].toLowerCase()} ${fmtSecs(m.timings[k])}</span>`).join('')
    }</div>`;
  }
  if(!isUser && m.sources && m.sources.length){
    html += `<div class="sources"><div class="sources-title">Sources citées</div><ol>${
      m.sources.map(s=>`<li id="src-${idx}-${s.n}"><span class="src-n">${s.n}</span><a href="${esc(s.url)}" target="_blank" rel="noreferrer noopener">${esc(s.url)}</a></li>`).join('')
    }</ol></div>`;
  }
  html += `</div>`;
  return html;
}

function renderThread(){
  const el = document.getElementById('thread-inner');
  if(state.messages.length === 0 && !state.loading){
    el.innerHTML = `<div class="intro">
      <h1>Nouvelle recherche</h1>
      <p>Six étapes, exécutées en local : décomposition, recherche, lecture,
         découpage, tri, rédaction. Aucune donnée n'est envoyée à un service tiers.</p>
      <div class="examples">${
        EXAMPLES.map(q=>`<button class="example" data-example="${esc(q)}">${esc(q)}</button>`).join('')
      }</div>
    </div>`;
    return;
  }
  el.innerHTML = state.messages.map(renderMessage).join('');
  scrollToBottom();
}

function scrollToBottom(){
  const thread = document.getElementById('thread');
  thread.scrollTop = thread.scrollHeight;
}

/* Mises à jour ciblées pendant le streaming : réécrire tout le fil à chaque
   fragment reçu détruirait la sélection de texte et ferait ramer la page. */
function patchStreaming(){
  if(pendingFrame) return;
  pendingFrame = requestAnimationFrame(() => {
    pendingFrame = null;

    const text = document.getElementById('streaming-text');
    const last = state.messages[state.messages.length - 1];
    if(text && last && last.streaming){
      const thread = document.getElementById('thread');
      const wasAtBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 60;
      text.textContent = last.content;
      if(wasAtBottom) scrollToBottom();
    }

    renderStatus();
  });
}

function renderApiWarning(){
  const el = document.getElementById('api-warning');
  const badge = document.getElementById('api-badge');
  if(state.apiUp === false){
    el.style.display = 'block';
    el.innerHTML = `API locale injoignable sur ${esc(API)}. Lance <code>uvicorn api:app --reload</code> dans le dossier du projet.`;
    badge.className = 'badge badge-ok badge-down';
    badge.innerHTML = '<span class="badge-dot"></span>API hors ligne';
  }else{
    el.style.display = 'none';
    badge.className = 'badge badge-ok';
    badge.innerHTML = '<span class="badge-dot"></span>API 8000';
  }
}

function renderComposer(){
  const input = document.getElementById('input');
  const hasText = input.value.trim().length > 0;
  document.getElementById('send-btn').disabled = state.loading || !hasText;
  document.getElementById('stop-btn').className = state.loading ? 'on' : '';
  // Le champ grandit avec le texte, sans dépasser le max-height du CSS.
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 180) + 'px';
}

function render(){
  renderSidebar();
  renderThread();
  renderStatus();
  renderApiWarning();
  renderComposer();
}

/* ---------- Lecture du flux SSE ---------- */

/* Découpe le flux HTTP en événements SSE ("data: {...}\n\n") et appelle
   onEvent pour chacun. EventSource ne conviendrait pas ici : il ne sait
   émettre que des GET, or la question est envoyée en POST. */
async function readEventStream(response, onEvent){
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while(true){
    const {done, value} = await reader.read();
    if(done) break;
    buffer += decoder.decode(value, {stream:true}).replace(/\r\n/g, "\n");

    let sep;
    while((sep = buffer.indexOf("\n\n")) !== -1){
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for(const line of block.split("\n")){
        if(!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if(!payload) continue;
        try{ onEvent(JSON.parse(payload)); }
        catch(_){ /* fragment illisible : on ignore plutôt que de tout casser */ }
      }
    }
  }
}

/* Extrait un message lisible d'une réponse HTTP en erreur. FastAPI renvoie
   soit {detail: "..."} soit, pour une erreur de validation, une liste. */
async function errorDetail(response){
  try{
    const body = await response.json();
    if(typeof body.detail === 'string') return body.detail;
    if(Array.isArray(body.detail)){
      return body.detail.map(d => d.msg || JSON.stringify(d)).join(' ; ');
    }
  }catch(_){ /* le corps n'était pas du JSON */ }
  return `Erreur ${response.status}`;
}

/* ---------- Actions / appels API ---------- */

async function checkHealth(){
  try{
    const r = await fetch(API + "/health");
    state.apiUp = r.ok;
  }catch(e){ state.apiUp = false; }
  renderApiWarning();

  // Tant que l'API est absente, on retente : l'avertissement disparaît tout
  // seul dès qu'uvicorn démarre, sans recharger la page.
  clearTimeout(healthTimer);
  if(state.apiUp === false){
    healthTimer = setTimeout(checkHealth, 5000);
  }
}

async function loadConversations(){
  try{
    const r = await fetch(API + "/conversations");
    if(!r.ok) throw new Error(await errorDetail(r));
    state.conversations = await r.json();
    renderSidebar();
  }catch(e){
    console.warn("Liste des conversations indisponible :", e.message);
  }
}

async function selectConversation(id){
  try{
    const r = await fetch(`${API}/conversations/${id}/messages`);
    if(!r.ok) throw new Error(await errorDetail(r));
    state.activeId = id;
    state.messages = await r.json();
    render();
  }catch(e){
    notify(`Impossible d'ouvrir cette conversation : ${e.message}`);
  }
}

function newConversation(){
  state.activeId = null;
  state.messages = [];
  document.getElementById('input').value = "";
  render();
  document.getElementById('input').focus();
}

async function deleteConversation(id){
  try{
    const r = await fetch(`${API}/conversations/${id}`, {method:"DELETE"});
    if(!r.ok) throw new Error(await errorDetail(r));
    if(id === state.activeId) newConversation();
    await loadConversations();
    renderSidebar();
  }catch(e){
    notify(`Suppression impossible : ${e.message}`);
  }
}

function notify(message){
  state.messages.push({role:"assistant", content:message, sources:[], timings:{}, error:true});
  render();
}

function stop(){
  if(controller) controller.abort();
}

function toggleSidebar(){
  state.sidebarOpen = !state.sidebarOpen;
  document.body.classList.toggle('sidebar-hidden', !state.sidebarOpen);
}

async function send(){
  const input = document.getElementById('input');
  const query = input.value.trim();
  if(!query || state.loading) return;
  input.value = "";

  state.messages.push({role:"user", content:query, sources:[], timings:{}});
  const assistant = {role:"assistant", content:"", sources:[], timings:{}, streaming:true};
  state.messages.push(assistant);

  state.loading = true;
  state.steps = {};
  STEP_ORDER.forEach(k => state.steps[k] = {status:'pending'});
  controller = new AbortController();
  render();

  try{
    const r = await fetch(API + "/ask/stream", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({query, conversation_id: state.activeId}),
      signal: controller.signal,
    });

    if(!r.ok){
      // L'API a bien répondu, mais avec une erreur (ex: 502 si Ollama est
      // absent). On distingue ce cas d'une vraie panne réseau, pour ne pas
      // afficher à tort "API injoignable" alors qu'elle a répondu.
      throw new Error(await errorDetail(r));
    }

    let failure = null;

    await readEventStream(r, (event) => {
      switch(event.type){
        case "start":
          state.activeId = event.conversation_id;
          break;
        case "step":
          state.steps[event.step] = event.status === "done"
            ? {status:'done', duration:event.duration}
            : {status:'running'};
          patchStreaming();
          break;
        case "token":
          assistant.content += event.text;
          patchStreaming();
          break;
        case "done":
          assistant.content = event.answer;
          assistant.sources = event.sources;
          assistant.timings = event.timings;
          break;
        case "error":
          failure = event.message;
          break;
      }
    });

    if(failure) throw new Error(failure);
    await loadConversations();

  }catch(e){
    if(e.name === "AbortError"){
      assistant.content = (assistant.content ? assistant.content + "\n\n" : "") +
        "— Recherche interrompue. Cet échange n'a pas été enregistré.";
      assistant.error = true;
    }else{
      // fetch échoue avec un TypeError en cas de panne réseau / CORS
      const isNetworkError = e instanceof TypeError;
      assistant.content = isNetworkError
        ? "Impossible de joindre l'API locale. Vérifie que le serveur tourne (uvicorn api:app --reload)."
        : e.message;
      assistant.error = true;
      assistant.sources = [];
      if(isNetworkError) checkHealth();
    }
  }finally{
    assistant.streaming = false;
    state.loading = false;
    controller = null;
    render();
  }
}

/* ---------- Écouteurs ---------- */

document.getElementById('new-btn').addEventListener('click', newConversation);
document.getElementById('toggle-btn').addEventListener('click', toggleSidebar);
document.getElementById('send-btn').addEventListener('click', send);
document.getElementById('stop-btn').addEventListener('click', stop);
document.getElementById('input').addEventListener('input', renderComposer);
document.getElementById('input').addEventListener('keydown', (e)=>{
  if(e.key === "Enter" && !e.shiftKey){
    e.preventDefault();
    send();
  }
});

/* Délégation : la barre latérale, le fil et la ligne de statut sont réécrits
   en entier à chaque rendu, donc on écoute sur les conteneurs, qui eux ne
   bougent pas. */
document.getElementById('conv-list').addEventListener('click', (e)=>{
  const del = e.target.closest('.conv-del');
  if(del){
    e.stopPropagation();
    deleteConversation(del.dataset.del);
    return;
  }
  const item = e.target.closest('.conv-item');
  if(item) selectConversation(item.dataset.id);
});

// La ligne de statut se déplie / replie au clic (détail des six étapes).
document.getElementById('status-bar').addEventListener('click', (e)=>{
  if(!e.target.closest('.status-line')) return;
  state.statusOpen = !state.statusOpen;
  renderStatus();
});

document.getElementById('thread').addEventListener('click', (e)=>{
  const example = e.target.closest('.example');
  if(example){
    const input = document.getElementById('input');
    input.value = example.dataset.example;
    renderComposer();
    send();
    return;
  }
  const cite = e.target.closest('.cite');
  if(!cite) return;
  e.preventDefault();
  const target = document.getElementById(`src-${cite.dataset.cite}`);
  if(!target) return;
  const thread = document.getElementById('thread');
  thread.scrollTop = target.offsetTop - thread.clientHeight / 2;
  target.classList.remove('flash');
  void target.offsetWidth;   // force le redémarrage de l'animation
  target.classList.add('flash');
});

/* ---------- Démarrage ---------- */

checkHealth();
loadConversations();
render();
