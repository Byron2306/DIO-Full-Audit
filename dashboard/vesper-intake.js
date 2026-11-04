"use strict";

const $ = selector => document.querySelector(selector);
const messages = $("#messages"), product = $("#product"), nameInput = $("#name"), emailInput = $("#email"), orgInput = $("#organisation");
const messageInput = $("#message"), filesInput = $("#files"), fileCount = $("#fileCount"), sendButton = $("#send"), notice = $("#notice");
const routeState = $("#routeState"), routeCandidates = $("#routeCandidates");
const journeyState = $("#journeyState"), journeyDetails = $("#journeyDetails"), journeyFields = $("#journeyFields"), journeyActions = $("#journeyActions");
const params = new URLSearchParams(location.search);
const apiOrigin = params.get("api") || (["8765", "8766"].includes(location.port) ? "http://127.0.0.1:8770" : location.origin);
let conversationId = null;
let sessionReady = false;
let pendingSubmission = null;
let productContextChanged = false;
let currentJourney = null;
const sessionKey = `dio.vesper.web_session:${apiOrigin}:${params.get("incarnation") || ""}`;
const pendingKey = `${sessionKey}:pending`;

function restorePending(){
  const saved = sessionStorage.getItem(pendingKey);
  if (!saved) return;
  const pending = JSON.parse(saved);
  if (pending.conversationId !== conversationId || !pending.id || !pending.digest){
    throw new Error("An earlier submission needs reconciliation before this session can continue.");
  }
  pendingSubmission = pending;
  messageInput.value = pending.message;
  product.value = pending.hint || "";
  productContextChanged = pending.contextChanged;
  notice.textContent = pending.hasAttachments
    ? "An earlier submission is unresolved. Reselect its original files to retry the same request."
    : "An earlier submission is unresolved. Retry its original request for reconciliation.";
}

async function bindSubmission(draft){
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(draft));
  const digest = [...new Uint8Array(bytes)].map(value=>value.toString(16).padStart(2,"0")).join("");
  if (pendingSubmission && pendingSubmission.digest !== digest){
    throw new Error("The earlier submission is unresolved. Restore its original text, product selection and files before retrying.");
  }
  if (!pendingSubmission){
    const request = JSON.parse(draft);
    pendingSubmission = {id:crypto.randomUUID(), digest, conversationId,
      message:request.message, hint:request.incarnation_hint,
      contextChanged:request.product_context_changed, hasAttachments:request.attachments.length > 0};
    // Persist identity and exact-body digest BEFORE sending; large uploads stay in the file picker.
    sessionStorage.setItem(pendingKey, JSON.stringify(pendingSubmission));
  }
  return {...JSON.parse(draft), client_message_id:pendingSubmission.id};
}

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
function journeyButton(label, action, ref, handler){
  const button=document.createElement("button"); button.type="button"; button.className="journey-action"; button.textContent=label;
  button.addEventListener("click",()=>handler(action,ref)); journeyActions.appendChild(button);
}
function renderJourney(journey){
  currentJourney=journey; journeyFields.replaceChildren(); journeyActions.replaceChildren(); journeyDetails.replaceChildren();
  const view=journey?.view;
  if(!view){ journeyState.textContent="A product-matched request opens your order record"; return; }
  const facts=view.facts||{}, intake=facts.intake||{}, quote=facts.quote||{}, order=facts.order||{}, settlement=facts.settlement||{}, fulfilment=facts.fulfilment||{}, delivery=facts.delivery||{}, communication=facts.communication||{};
  journeyState.textContent=`${view.stage.replaceAll("_"," ")} · ${view.product_id||"DIO service"}`;
  journeyState.className="state "+(["QUOTE_READY","PAYMENT_VERIFIED","WORK_QUEUED","PROCESSING","REVIEW_READY","DELIVERED","CLOSED"].includes(view.stage)?"ok":"wait");
  const lines=[];
  if(view.case_id) lines.push(`Customer case reference: ${view.case_id}`);
  if(communication.customer_id) lines.push(`Customer ID: ${communication.customer_id}`);
  else lines.push(`Customer identity: ${communication.customer_identity_state||"unverified"} · account ID not linked`);
  if(communication.contact_email) lines.push(`Email on this case: ${communication.contact_email}`);
  if(fulfilment.job_id) lines.push(`Job ID: ${fulfilment.job_id}`);
  else lines.push("Job ID: assigned when product work starts");
  const attachmentGroups=new Map();
  for(const attachment of facts.attachments||[]){
    const key=attachment.sha256||attachment.file_name||attachment.attachment_id;
    const group=attachmentGroups.get(key)||{attachment,count:0}; group.count++; attachmentGroups.set(key,group);
  }
  for(const {attachment,count} of attachmentGroups.values()) lines.push(`Sample ${attachment.file_name||attachment.attachment_id}: ${attachment.state||"quarantined"}${count>1?` · ${count} identical upload records`:""} · not inspected`);
  if(intake.missing_input_ids?.length) lines.push(`Still needed: ${intake.missing_input_ids.join(", ")}`);
  const provided=intake.provided_inputs||{};
  if(Object.keys(provided).length){
    const units=(intake.required_inputs||[]).find(row=>row.field_id==="scope_quantity")?.semantic_unit||"units";
    const scopeParts=[];
    if(provided.scope_quantity) scopeParts.push(`${provided.scope_quantity} ${units}`);
    if(provided.buyer_class) scopeParts.push(`buyer ${provided.buyer_class}`);
    if(provided.requested_outcome) scopeParts.push(String(provided.requested_outcome));
    if(scopeParts.length) lines.push(`Saved customer-stated scope: ${scopeParts.join(" · ")}`);
  }
  if(facts.scope?.state) lines.push(`Scope: ${facts.scope.state.toLowerCase()}`);
  if(quote.quote_id){ const q=document.createElement("div"); q.className="quote"; q.textContent=`Quote ${quote.quote_id}: ${quote.currency||"ZAR"} ${quote.amount??"amount pending"} · presentation only`; journeyDetails.appendChild(q); }
  else if(quote.quote_request_id){ const q=document.createElement("div"); q.className="quote"; q.textContent=`Quote request ${quote.quote_request_id}: ${quote.quote_request_state==="needs_operator_review"?"awaiting operator pricing review":"recorded"} · no customer quotation issued`; journeyDetails.appendChild(q); }
  if(quote.reason) lines.push(`Quote review: ${String(quote.reason).replaceAll("_"," ")}`);
  if(order.invoice_id||order.invoice_state) lines.push(`Invoice: ${order.invoice_state||"not created"}${order.invoice_id?` · ${order.invoice_id}`:""}`);
  if(order.payment_state) lines.push(`Payment: ${order.payment_state}${order.checkout_available?" · checkout link issued":""}`);
  if(order.operator_review_required) lines.push("Next step: operator pricing review is pending");
  if(settlement.settlement_class) lines.push(`Payment verification: ${settlement.settlement_class}`);
  if(fulfilment.state) lines.push(`Work: ${fulfilment.state}`);
  if(communication.outlook_draft_count||communication.outlook_sent_receipt_count) lines.push(`Email: ${communication.outlook_draft_count} draft(s), ${communication.outlook_sent_receipt_count} send receipt(s)`);
  if(delivery.delivery_receipt_id) lines.push(`Return pack: ${delivery.sent?"delivered":"prepared, not sent"}`);
  else if(facts.deliverables?.manifest_id) lines.push(`Return pack: ${facts.deliverables.artifact_count||0} item(s) · ${facts.deliverables.release_state||"awaiting release review"}`);
  if(!order.invoice_id&&!order.checkout_available) lines.push("Invoice and checkout: not issued · email sending: approval required");
  journeyDetails.append(...lines.map(text=>{const row=document.createElement("div");row.textContent=text;return row;}));

  const actions=view.actions||[];
  const action=id=>actions.find(row=>row.action_id===id);
  if(action("OPEN_INTAKE")&&(intake.missing_input_ids||[]).length) journeyButton("Complete missing order details","OPEN_INTAKE",action("OPEN_INTAKE").action_ref,submitJourneyAction);
  if(action("RECORD_INTAKE_INPUTS")){
    const required=intake.required_inputs||[];
    const missing=new Set(intake.missing_input_ids||[]);
    const defs=required.filter(row=>missing.has(row.field_id));
    if(defs.length){
      const controls={};
      for(const field of defs){
        const wrap=document.createElement("div"),label=document.createElement("label");
        label.textContent=field.field_id==="requested_outcome"?"What outcome should this work produce?":field.field_id==="buyer_class"?"Who is the work for?":`How many ${field.semantic_unit||"units"} are in scope?`;
        wrap.appendChild(label);
        let input;
        if(field.kind==="enum"){
          input=document.createElement("select"); input.className="journey-input";
          const placeholder=document.createElement("option"); placeholder.value=""; placeholder.textContent="Choose one…"; placeholder.selected=true; input.appendChild(placeholder);
          (field.allowed_values||[]).forEach((value,index)=>{const option=document.createElement("option");option.value=value;option.textContent=field.labels?.[index]||value;input.appendChild(option);});
        }else if(field.kind==="integer"){
          input=document.createElement("input"); input.type="number"; input.min=field.minimum||1; input.placeholder="Enter a whole number"; input.className="journey-input";
        }else{
      input=document.createElement("textarea"); input.rows=3; input.maxLength=4000; input.placeholder=view.product_id==="Document Studio Edit"?"Include deliverables, formats, deadline, page cap and editing boundaries":"Describe the result you need"; input.className="journey-input";
        }
        wrap.appendChild(input); journeyFields.appendChild(wrap); controls[field.field_id]=input;
      }
      journeyButton("Save order details","RECORD_INTAKE_INPUTS",action("RECORD_INTAKE_INPUTS").action_ref,async(a,ref)=>{
        const inputs={}; for(const [key,control] of Object.entries(controls)) inputs[key]=control.value.trim();
        await submitJourneyAction(a,ref,{inputs});
      });
    }
  }
  if(action("ASSESS_SCOPE")&&!intake.missing_input_ids?.length) journeyButton("Review scope","ASSESS_SCOPE",action("ASSESS_SCOPE").action_ref,submitJourneyAction);
  if(action("PREPARE_QUOTE")&&(view.product_id!=="Document Studio Edit"||(facts.attachments||[]).length)) journeyButton("Prepare quote for operator review","PREPARE_QUOTE",action("PREPARE_QUOTE").action_ref,submitJourneyAction);
  else if(action("PREPARE_QUOTE")&&view.product_id==="Document Studio Edit"){const row=document.createElement("div");row.textContent="Upload one sample before requesting quote review; it will be held for operator clearance.";journeyDetails.appendChild(row);}
  if(action("REQUEST_OPERATOR")) journeyButton(view.stage==="QUOTE_READY"?"Request invoice & payment follow-up":"Ask an operator to review", "REQUEST_OPERATOR", action("REQUEST_OPERATOR").action_ref, submitJourneyAction);
}
async function refreshJourney(){
  if(!conversationId) return;
  const body=await jsonFetch(`/api/vesper/chat/journey?conversation_id=${encodeURIComponent(conversationId)}`);
  renderJourney(body.journey);
}
async function submitJourneyAction(action,actionRef,payload={}){
  journeyActions.querySelectorAll("button").forEach(button=>button.disabled=true);
  try{
    const result=await jsonFetch("/api/vesper/chat/journey",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conversation_id:conversationId,action,action_ref:actionRef,payload})});
    renderSession(result.session); renderJourney(result.journey); notice.textContent=`Order record updated: ${result.journey.view?.stage?.replaceAll("_"," ")||"active"}. No external payment, email, or release was triggered.`; notice.classList.remove("error");
  }catch(error){ notice.textContent=`Journey action needs attention: ${error.message}`; notice.classList.add("error"); await refreshJourney().catch(()=>{}); }
}
async function jsonFetch(path, options={}){
  const response = await fetch(endpoint(path), options);
  const body = await response.json();
  if (!response.ok){
    const error = new Error(body.message || body.error || `HTTP ${response.status}`);
    error.status = response.status; error.processingState = body.processing_state; throw error;
  }
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
  const savedId = sessionStorage.getItem(sessionKey);
  if (savedId){
    try{
      const saved = await jsonFetch(`/api/vesper/chat/session?conversation_id=${encodeURIComponent(savedId)}`);
      conversationId = saved.conversation_id; sessionReady = true;
      nameInput.value=saved.contact?.name||""; emailInput.value=saved.contact?.email||""; orgInput.value=saved.contact?.organisation||"";
      renderSession(saved); restorePending(); await refreshJourney(); sendButton.disabled = false; return;
    }catch(error){
      if (error.status !== 404) throw error;
      if (sessionStorage.getItem(pendingKey)) throw new Error("The earlier session has an unresolved submission and requires reconciliation.");
      sessionStorage.removeItem(sessionKey);
    }
  }
  const payload = {
    surface: product.value ? "product_site" : "dio_web",
    incarnation_hint: product.value || null,
    name: nameInput.value,
    email: emailInput.value,
    organisation: orgInput.value,
  };
  const body = await jsonFetch("/api/vesper/chat/session", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  conversationId = body.session.conversation_id;
  sessionStorage.setItem(sessionKey, conversationId);
  sessionReady = true;
  renderSession(body.session);
  await refreshJourney();
  sendButton.disabled = false;
}
const asBase64 = file => new Promise((resolve,reject)=>{ const reader = new FileReader(); reader.onload = ()=>resolve(String(reader.result).split(",",2)[1]); reader.onerror = reject; reader.readAsDataURL(file); });
async function encodeFiles(files){
  if(files.length>1) throw new Error("Attach one file per message. Send another message for each additional file.");
  const rows = [];
  for (const file of files){
    if (file.size > 2 * 1024 * 1024) throw new Error(`${file.name} exceeds the 2 MiB per-file limit`);
    rows.push({filename:file.name,mime_type:file.type||"application/octet-stream",role:"customer_source",content_base64:await asBase64(file)});
  }
  return rows;
}
async function send(){
  const text = messageInput.value.trim();
  const selected = [...filesInput.files];
  if (!text && !selected.length) return;
  sendButton.disabled = true; messageInput.disabled = true; filesInput.disabled = true; notice.classList.remove("error");
  notice.textContent = "Vesper is reviewing your request and holding uploaded files for review…";
  try{
    if (!sessionReady) await startSession();
    const attachments = await encodeFiles(selected);
    const draft = JSON.stringify({conversation_id:conversationId,message:text,attachments,
      incarnation_hint:product.value||null,product_context_changed:productContextChanged,
      contact_update:{name:nameInput.value,email:emailInput.value,organisation:orgInput.value}});
    const submission = await bindSubmission(draft);
    const body = await jsonFetch("/api/vesper/chat/message", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(submission)
    });
    renderSession(body.session); await refreshJourney();
    sessionStorage.removeItem(pendingKey);
    pendingSubmission = null; productContextChanged = false;
    messageInput.value = ""; filesInput.value = ""; fileCount.textContent = "No files selected";
    notice.textContent = body.session.handoff?.state === "READY_FOR_PRODUCT_EXECUTION"
      ? `Governed handoff ready for ${body.session.handoff.incarnation}. Product execution is still internally/human gated.`
      : "Vesper needs more routing context before product execution can begin.";
  }catch(error){
    if (error.processingState === "REJECTED_NO_CANONICAL_EFFECT"){
      sessionStorage.removeItem(pendingKey); pendingSubmission = null;
    }
    notice.textContent = `REFUSED: ${error.message}`; notice.classList.add("error");
  }
  finally{ sendButton.disabled = false; messageInput.disabled = false; filesInput.disabled = false; messageInput.focus(); }
}

filesInput.addEventListener("change",()=>{ const files=[...filesInput.files]; fileCount.textContent = files.length ? `${files.length} file${files.length===1?"":"s"}: ${files.map(file=>file.name).join(", ")}` : "No files selected"; });
sendButton.addEventListener("click",send);
messageInput.addEventListener("keydown",event=>{ if (event.key === "Enter" && !event.shiftKey){ event.preventDefault(); send(); } });
product.addEventListener("change",()=>{ productContextChanged = true; if (!sessionReady) return; notice.textContent = "Your next message will use the selected product context."; notice.classList.remove("error"); });

(async()=>{
  try{ await loadProducts(); await startSession(); }
  catch(error){ notice.textContent = `Vesper could not start: ${error.message}`; notice.classList.add("error"); sendButton.disabled = true; }
})();
