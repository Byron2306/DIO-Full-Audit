"use strict";

const $ = selector => document.querySelector(selector);
const messages = $("#messages"), product = $("#product"), nameInput = $("#name"), emailInput = $("#email"), orgInput = $("#organisation");
const messageInput = $("#message"), filesInput = $("#files"), fileCount = $("#fileCount"), sendButton = $("#send"), notice = $("#notice");
const routeState = $("#routeState"), routeCandidates = $("#routeCandidates");
const params = new URLSearchParams(location.search);
const apiOrigin = params.get("api") || (location.port === "8765" ? "http://127.0.0.1:8770" : location.origin);
let conversationId = null;
let sessionReady = false;

function endpoint(path){ return `${apiOrigin}${path}`; }
function escapeText(value){ return String(value ?? ""); }
function messageNode(row){
  const wrap = document.createElement("article");
  const customer = row.role === "customer";
  wrap.className = `msg ${customer ? "customer" : "vesper"}`;
  const avatar = document.createElement("div"); avatar.className = "avatar"; avatar.textContent = customer ? "Y" : "V";
  const bubble = document.createElement("div"); bubble.className = "bubble"; bubble.textContent = escapeText(row.text);
  if ((row.attachment_ids || []).length){
    const chips = document.createElement("div"); chips.className = "attachments";
    for (const id of row.attachment_ids){ const chip = document.createElement("span"); chip.className = "chip"; chip.textContent = id; chips.appendChild(chip); }
    bubble.appendChild(chips);
  }
  const meta = document.createElement("div"); meta.className = "meta"; meta.textContent = customer ? "You" : "Vesper · governed response"; bubble.appendChild(meta);
  wrap.append(avatar,bubble); return wrap;
}
function renderSession(session){
  messages.replaceChildren(...(session.messages || []).map(messageNode));
  messages.scrollTop = messages.scrollHeight;
  const route = session.route || {};
  if (route.state === "RESOLVED"){
    routeState.textContent = route.incarnation || "Resolved"; routeState.className = "state ok";
  } else if (route.state === "NEEDS_YOU"){
    routeState.textContent = "Needs clarification"; routeState.className = "state wait";
  } else {
    routeState.textContent = "Awaiting request"; routeState.className = "state wait";
  }
  routeCandidates.textContent = (route.candidates || []).length ? `Candidates: ${route.candidates.map(row => row.incarnation).join(" · ")}` : "";
}
async function jsonFetch(path, options={}){
  const response = await fetch(endpoint(path), options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || body.error || `HTTP ${response.status}`);
  return body;
}
async function loadProducts(){
  const body = await jsonFetch("/api/vesper/chat/products");
  for (const incarnation of body.incarnations || []){
    const option = document.createElement("option"); option.value = incarnation; option.textContent = incarnation; product.appendChild(option);
  }
  const hinted = params.get("incarnation") || "";
  if (hinted && [...product.options].some(option => option.value === hinted)) product.value = hinted;
}
async function startSession(){
  if (sessionReady) return;
  sendButton.disabled = true;
  const payload = {
    surface: product.value ? "product_site" : "dio_web",
    incarnation_hint: product.value || null,
    name: nameInput.value,
    email: emailInput.value,
    organisation: orgInput.value,
  };
  const body = await jsonFetch("/api/vesper/chat/session", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  conversationId = body.session.conversation_id;
  sessionReady = true;
  renderSession(body.session);
  sendButton.disabled = false;
}
const asBase64 = file => new Promise((resolve,reject)=>{ const reader = new FileReader(); reader.onload = ()=>resolve(String(reader.result).split(",",2)[1]); reader.onerror = reject; reader.readAsDataURL(file); });
async function encodeFiles(files){
  const rows = [];
  for (const file of files){
    if (file.size > 10 * 1024 * 1024) throw new Error(`${file.name} exceeds the 10 MiB per-file limit`);
    rows.push({filename:file.name,mime_type:file.type||"application/octet-stream",role:"customer_source",content_base64:await asBase64(file)});
  }
  return rows;
}
async function send(){
  const text = messageInput.value.trim();
  const selected = [...filesInput.files];
  if (!text && !selected.length) return;
  sendButton.disabled = true; messageInput.disabled = true; filesInput.disabled = true; notice.classList.remove("error");
  notice.textContent = "Vesper is binding the conversation, quarantining source files and resolving the product handoff…";
  try{
    if (!sessionReady) await startSession();
    const attachments = await encodeFiles(selected);
    const body = await jsonFetch("/api/vesper/chat/message", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({conversation_id:conversationId,message:text,attachments,incarnation_hint:product.value||null})
    });
    renderSession(body.session);
    messageInput.value = ""; filesInput.value = ""; fileCount.textContent = "No files selected";
    notice.textContent = body.session.handoff?.state === "READY_FOR_PRODUCT_EXECUTION"
      ? `Governed handoff ready for ${body.session.handoff.incarnation}. Product execution is still internally/human gated.`
      : "Vesper needs more routing context before product execution can begin.";
  }catch(error){ notice.textContent = `REFUSED: ${error.message}`; notice.classList.add("error"); }
  finally{ sendButton.disabled = false; messageInput.disabled = false; filesInput.disabled = false; messageInput.focus(); }
}

filesInput.addEventListener("change",()=>{ const files=[...filesInput.files]; fileCount.textContent = files.length ? `${files.length} file${files.length===1?"":"s"}: ${files.map(file=>file.name).join(", ")}` : "No files selected"; });
sendButton.addEventListener("click",send);
messageInput.addEventListener("keydown",event=>{ if (event.key === "Enter" && !event.shiftKey){ event.preventDefault(); send(); } });
product.addEventListener("change",()=>{ if (!sessionReady) return; notice.textContent = "Product context changed after the conversation started. Start a fresh page session to bind a different exact product context."; notice.classList.add("error"); });

(async()=>{
  try{ await loadProducts(); await startSession(); }
  catch(error){ notice.textContent = `Vesper could not start: ${error.message}`; notice.classList.add("error"); sendButton.disabled = true; }
})();
