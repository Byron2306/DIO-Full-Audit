const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let catalog = null, allJobs = {jobs:[], seeds:[]}, selected = null, sectionAuditRequest = 0;
let savedRecipes = [];
const roles = ['harmony','lead','bass','drums','keys','folk'];
const roleLabels = {harmony:'Harmony',lead:'Lead',bass:'Bass',drums:'Drums',keys:'Keys',folk:'Folk'};
const mixDefaults = {harmony:.78,lead:.58,bass:.95,drums:1.15,keys:.42,folk:.8};
const sectionAuditPanel = document.createElement('details');
sectionAuditPanel.className = 'section-audit';
sectionAuditPanel.hidden = true;
const sectionAuditSummary = document.createElement('summary');
sectionAuditSummary.textContent = 'Section performance';
const sectionAuditWrap = document.createElement('div');
sectionAuditWrap.className = 'section-audit-wrap';
const sectionAuditTable = document.createElement('table');
sectionAuditTable.setAttribute('aria-label', 'Measured events per section');
const sectionAuditHead = document.createElement('thead');
const sectionAuditHeaderRow = document.createElement('tr');
['Section','Bars',...roles.map(role=>roleLabels[role])].forEach(label=>{
  const cell=document.createElement('th');cell.scope='col';cell.textContent=label;sectionAuditHeaderRow.append(cell);
});
sectionAuditHead.append(sectionAuditHeaderRow);
const sectionAuditBody = document.createElement('tbody');
sectionAuditTable.append(sectionAuditHead,sectionAuditBody);
sectionAuditWrap.append(sectionAuditTable);
const sectionAuditNote = document.createElement('p');
sectionAuditNote.className = 'hint';
sectionAuditNote.textContent = 'Counts, density, velocity, and MIDI pitches come from the event plan. They describe the arrangement, not a genre-quality score.';
sectionAuditPanel.append(sectionAuditSummary,sectionAuditWrap,sectionAuditNote);
document.getElementById('renderNote').after(sectionAuditPanel);
const presets = {
  gm:{harmony:'gm_clean_guitar',lead:'gm_clean_guitar',bass:'gm_electric_bass',drums:'gm_kit',keys:'off',folk:'off'},
  heavy:{harmony:'gtx_sustain',lead:'gtx_sustain',bass:'growly_dirty',drums:'virtuosity',keys:'off',folk:'off'},
  clean:{harmony:'gm_clean_guitar',lead:'gm_clean_guitar',bass:'gm_electric_bass',drums:'virtuosity',keys:'off',folk:'off'},
  electronic:{harmony:'gm_synth_pad',lead:'gm_synth_lead',bass:'gm_synth_bass',drums:'gm_kit',keys:'gm_synth_pad',folk:'off'},
  jazz:{harmony:'gm_rhodes',lead:'gm_sax',bass:'gm_acoustic_bass',drums:'virtuosity',keys:'off',folk:'off'}
};
const blackMetalPresets = {
  '404':{title:'Winter Without Graves',bars:88,atmosphere:'COLD_DRONE'},
  '1993':{title:'Thrones Beneath Snow',bars:112,atmosphere:'CHOIR_SHADOW'},
  '8888':{title:'The Moon Refuses Us',bars:120,atmosphere:'SUBLIMINAL_PAD'}
};
function setStatus(message, error=false) {
  $('status').textContent=message;
  $('status').style.color=error?'#ff8c82':'#dfb86d';
}
async function api(path, options) {
  const response=await fetch(path,options);
  const value=await response.json();
  if(!response.ok) throw Error(value.error||`HTTP ${response.status}`);
  return value;
}
const recipeFields = ['genre','songType','title','mood','tempo','meter','bars','key','mode','tuning','tone','drive','attack','drumIntensity','seed','gain','preset','bmPreset','bmProduction','bmKeysKind','bmKeysMotion','bmKeysRegister','bmKeysDensity','bmKeysArpNotes','bmKeysArpRate','bmKeysArpShape','bmKeysLevel'];
function recipeControls() {
  const controls = {};
  for (const id of [...recipeFields,...roles.flatMap(role=>[`module_${role}`,`mix_${role}`])]) {
    const input = $(id);
    if (input) controls[id] = input.value;
  }
  return controls;
}
function refreshRecipeOptions(selectId='') {
  const select=$('recipeSelect'), prior=selectId||select.value;
  select.replaceChildren(new Option(savedRecipes.length?'Choose a saved recipe':'No saved recipes',''));
  for (const recipe of savedRecipes) select.add(new Option(recipe.name,recipe.id));
  if(savedRecipes.some(recipe=>recipe.id===prior))select.value=prior;
  const has=Boolean(select.value);
  $('loadRecipe').disabled=!has;$('deleteRecipe').disabled=!has;
}
async function refreshRecipes(selectId='') {
  try {
    const data=await api('/api/workflows');
    savedRecipes=Array.isArray(data.recipes)?data.recipes:[];
    refreshRecipeOptions(selectId);
    $('recipeState').textContent=`${savedRecipes.length} saved · stored on this machine`;
  } catch(error) {
    $('recipeState').textContent=`Recipe storage unavailable: ${error.message}`;
    $('saveRecipe').disabled=true;$('restoreStarters').disabled=true;
  }
}
function loadRecipe(recipe) {
  const controls=recipe.controls||{};
  if(controls.genre&&catalog.genres[controls.genre]) {
    $('genre').value=controls.genre;
    genreChanged();
  }
  if(controls.songType!==undefined&&[...$('songType').options].some(option=>option.value===controls.songType))$('songType').value=controls.songType;
  updateCompositionDefaults();
  for(const id of recipeFields) {
    if(id==='genre'||id==='songType'||controls[id]===undefined)continue;
    const input=$(id); if(!input)continue;
    const value=String(controls[id]);
    if(input.tagName==='SELECT'&&![...input.options].some(option=>option.value===value))continue;
    input.value=value;
  }
  for(const role of roles) {
    for(const prefix of ['module_','mix_']) {
      const id=prefix+role, input=$(id), value=controls[id];
      if(!input||value===undefined)continue;
      const text=String(value);
      if(input.tagName!=='SELECT'||[...input.options].some(option=>option.value===text&&!option.disabled))input.value=text;
    }
  }
  syncGuitarControls();
  const levelValue=$('bmKeysLevelValue'); if(levelValue)levelValue.textContent=`${$('bmKeysLevel').value} dB`;
  updateBlackMetalPanel();
  updateBlackMetalStatus();
  $('recipeName').value=recipe.name;
  setStatus(`Loaded “${recipe.name}”. Review the setup, then compile to create a new candidate.`);
}
function applyPreset() {
  const key=$('preset').value;
  const values=key==='genre'?{...catalog.genres[$('genre').value].default_modules}:presets[key];
  if(key==='genre'&&$('genre').value==='folk_metal') values.folk={drive:'bagpipe_sampled',space:'flute_sampled',fracture:'accordion_sampled'}[$('songType').value||'drive'];
  for(const role of roles) {
    const input=$('module_'+role), wanted=values[role]||'off';
    if(input && [...input.options].some(option=>option.value===wanted&&!option.disabled)) input.value=wanted;
  }
  syncGuitarControls();
}
function syncGuitarControls() {
  if (!catalog) return;
  const hasGuitar = ['harmony','lead'].some(role => {
    const module = catalog.modules[role]?.[$('module_'+role)?.value];
    return module?.instrument_family === 'guitar';
  });
  for (const [field, control] of [['tuningField','tuning'],['toneField','tone'],['driveField','drive'],['attackField','attack']]) {
    const label = $(field), input = $(control);
    if (label) label.classList.toggle('is-inactive', !hasGuitar);
    if (input) input.disabled = !hasGuitar;
  }
  $('guitarControlHint').textContent = hasGuitar
    ? 'Guitar tuning, amp tone, drive, and pick attack affect the selected guitar module.'
    : 'Select a guitar module in Harmony or Lead to enable tuning, amp tone, drive, and pick attack.';
}
function readBlackMetalControls() {
  return {
    black_metal_production:
      $('bmProduction')?.value
      || 'TERMINAL_DISEASE_V1',
    atmospheric_keys:{
    enabled:$('bmKeysKind').value!=='NONE',
    kind:$('bmKeysKind').value,
    level_db:Number($('bmKeysLevel').value),
    register:$('bmKeysRegister').value,
    motion:$('bmKeysMotion').value,
    density:$('bmKeysDensity').value,
    arp_notes:Number($('bmKeysArpNotes').value),
    arp_step_beats:Number($('bmKeysArpRate').value),
    arp_shape:$('bmKeysArpShape').value
  }};
}
function updateBlackMetalPanel() {
  const panel=$('blackMetalLab'), active=$('genre').value==='black_metal';
  panel.hidden=!active;
  if(active)panel.open=true;
  updateBlackMetalStatus();
}
function updateBlackMetalStatus() {
  const layer=readBlackMetalControls().atmospheric_keys;
  const moduleSelect=$('module_keys');
  const module=moduleSelect?.selectedOptions?.[0]?.textContent||'No keys module';
  $('bmKeysLevelValue').textContent=`${layer.level_db} dB`;
  $('bmKeysStatus').textContent=!layer.enabled
    ? 'Support layer off. The keys stem will stay silent unless you choose a separate keys module.'
    : moduleSelect?.value==='off'
      ? 'Layer selected, but the keys module is off. Choose a keys module to hear the atmospheric part.'
      : `Support layer active · ${layer.kind.replaceAll('_',' ').toLowerCase()} · ${layer.motion.replaceAll('_',' ').toLowerCase()} · ${layer.density.toLowerCase()} · arp ${layer.arp_notes} notes / ${layer.arp_step_beats} beats · ${module}.`;
}
function syncBlackMetalModule() {
  if(!$('module_keys')||$('genre').value!=='black_metal') { updateBlackMetalStatus(); return; }
  const kind=$('bmKeysKind').value, module=$('module_keys');
  const preferences=kind==='LAMENT_KEYS'
    ? [
        'nocturne_v4_funeral_motif',
        'nocturne_v4_machine_choir',
        'new_age_pad_sampled'
      ]
    : kind==='CHOIR_SHADOW'
    ? ['gm_choir','new_age_pad_sampled','gm_synth_pad']
    : ['new_age_pad_sampled','gm_synth_pad','gm_choir'];
  if(kind==='NONE') {
    if([...module.options].some(row=>row.value==='off'&&!row.disabled))module.value='off';
  } else {
    const available=preferences.find(value=>[...module.options].some(row=>row.value===value&&!row.disabled));
    if(available)module.value=available;
  }
  module.dispatchEvent(new Event('change',{bubbles:true}));
  updateBlackMetalStatus();
}
function applyFuneralDiseasePreset() {
  $('genre').value='black_metal';

  if($('bmProduction'))
    $('bmProduction').value='TERMINAL_DISEASE_V1';

  $('bmKeysKind').value='LAMENT_KEYS';
  $('bmKeysRegister').value='MID';
  $('bmKeysMotion').value='SLOW_CHAIN';
  $('bmKeysDensity').value='BREATHING';

  if($('bmKeysArpShape'))
    $('bmKeysArpShape').value='GRAVE_CRAWL';

  if($('bmKeysArpNotes'))
    $('bmKeysArpNotes').value='3';

  if($('bmKeysArpRate'))
    $('bmKeysArpRate').value='0.5';

  $('bmKeysLevel').value='-9';

  const module=$('module_keys');

  if(
    module
    && [...module.options].some(
      option =>
        option.value==='nocturne_v4_funeral_motif'
        && !option.disabled
    )
  ){
    module.value='nocturne_v4_funeral_motif';
  }

  updateBlackMetalStatus();
}


function applyBlackMetalPreset() {
  const row=blackMetalPresets[$('bmPreset').value];
  if(!row)return;
  $('genre').value='black_metal';
  genreChanged();
  $('title').value=row.title;
  $('bars').value=String(row.bars);
  $('seed').value=$('bmPreset').value;
  $('bmKeysKind').value=row.atmosphere;
  syncBlackMetalModule();
}
function updateCompositionDefaults() {
  const genre=catalog.genres[$('genre').value];
  if(!genre)return;
  const songType=$('songType').value;
  const frame=genre.song_type_defaults?.[songType]||{
    tempo_bpm:genre.default_tempo_bpm||genre.preferred_bpm,
    meter:genre.default_meter||genre.meters?.[0],
    bars:genre.default_bars
  };
  $('meter').options[0].textContent=`${songType?'Type':'Genre'} default · ${frame.meter}`;
  $('tempo').placeholder=`Default · ${frame.tempo_bpm} BPM`;
  $('bars').placeholder=`Default · ${frame.bars} bars`;
  const selectedType=(genre.song_types||[]).find(row=>row.key===songType)?.label;
  const defaultLabel=selectedType?`${selectedType} default`:'Genre default';
  $('genreHint').textContent=`${genre.family.toUpperCase()} · ${defaultLabel}: ${frame.tempo_bpm} BPM / ${frame.meter} / ${frame.bars} bars · tempo range ${genre.tempo_ranges_bpm.map(x=>x.join('–')).join(' / ')} BPM · Study: ${(genre.reference_artists||[]).join(', ')}`;
}
function genreChanged() {
  const key=$('genre').value, genre=catalog.genres[key];
  $('songType').innerHTML='<option value="">Free study</option>'+(genre.song_types||[]).map(x=>`<option value="${esc(x.key)}">${esc(x.label)}</option>`).join('');
  const defaultMeter=genre.default_meter||genre.meters?.[0]||'profile default';
  $('meter').innerHTML=`<option value="">Genre default · ${esc(defaultMeter)}</option>`+(genre.meters||[]).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
  $('styleNote').textContent=genre.style_observations||'';
  $('tempo').value=''; $('bars').value='';
  const [tonic,mode]=genre.default_tonal_center.split('-');
  $('key').value=tonic; $('mode').value=mode;
  $('tuning').value=genre.default_tuning;
  $('tone').value=genre.default_tone;
  $('drive').value=catalog.tone_profiles[genre.default_tone].drive;
  updateCompositionDefaults();
  $('preset').value='genre'; applyPreset();
  updateBlackMetalPanel();
  syncBlackMetalModule();
}
function renderModules() {
  const names={harmony:'Harmony / rhythm',lead:'Lead / melody',bass:'Low end',drums:'Percussion',keys:'Atmosphere / texture',folk:'Folk / acoustic color'};
  $('modules').innerHTML=roles.map(role=>`<label>${names[role]}<select id="module_${role}">${Object.entries(catalog.modules[role]).map(([id,x])=>`<option value="${esc(id)}" ${x.available?'':'disabled'}>${esc(x.label)}${x.available?'':' · missing'}</option>`).join('')}</select></label>`).join('');
  for(const role of roles) $('module_'+role).onchange=()=>{syncGuitarControls();if(role==='keys')updateBlackMetalStatus()};
  syncGuitarControls();
}
function renderMix() {
  const names={harmony:'Rhythm guitar',lead:'Lead',bass:'Bass',drums:'Drums',keys:'Keys',folk:'Folk'};
  $('mixLevels').innerHTML=roles.map(role=>`<label>${names[role]}<input id="mix_${role}" type="number" min="0" max="2" step="0.01" value="${mixDefaults[role]}"></label>`).join('');
}
function updateSelected() {
  if(!selected)return;
  const {lane,row}=selected,base=`/api/${lane}/${encodeURIComponent(row.job_id)}`;
  $('empty').hidden=true; $('current').hidden=false;
  $('currentGenre').textContent=row.genre.replaceAll('_',' ').toUpperCase()+' / '+(row.song_type||'FREE STUDY').toUpperCase();
  $('currentTitle').textContent=row.title;
  const details=[`${row.tempo_bpm} BPM`,row.meter,`${row.bars} bars`,row.tuning,row.tone_profile,row.gain_db!=null?`${row.gain_db} dB`:null,Object.values(row.modules||{}).filter(x=>x!=='off').join(' / ')].filter(Boolean);
  $('currentMeta').textContent=details.join(' · ');
  $('audioState').textContent=row.audio_state==='RENDERED'?'AUDIO READY':'MIDI COMPILED';
  $('player').hidden=row.audio_state!=='RENDERED';
  if(row.audio_state==='RENDERED')$('player').src=base+'/audio';else{$('player').pause();$('player').removeAttribute('src')}
  $('renderButton').textContent=row.audio_state==='RENDERED'?'Re-render audio':'Render audio';
  $('mediaHandoffButton').disabled=row.audio_state!=='RENDERED';
  $('mediaHandoffNote').hidden=true;
  $('mediaHandoffNote').classList.remove('media-handoff-error');
  $('mediaHandoffReceipt').hidden=true;
  $('midiLink').href=base+'/midi'; $('planLink').href=base+'/plan'; $('auditLink').href=base+'/audit'; $('receiptLink').href=base+'/receipt';
  loadSectionAudit(lane,row);
}
async function loadSectionAudit(lane,row) {
  const requestId=++sectionAuditRequest;
  sectionAuditPanel.hidden=false;
  sectionAuditBody.replaceChildren();
  const loading=document.createElement('tr');
  const message=document.createElement('td');message.colSpan=2+roles.length;message.textContent='Loading section measurements…';loading.append(message);sectionAuditBody.append(loading);
  try {
    const audit=await api(`/api/${lane}/${encodeURIComponent(row.job_id)}/audit`);
    if(requestId!==sectionAuditRequest)return;
    sectionAuditBody.replaceChildren();
    for(const section of audit.sections||[]) {
      const tr=document.createElement('tr');
      const title=document.createElement('th');title.scope='row';title.textContent=section.gesture||section.name||`Section ${section.index}`;tr.append(title);
      const bars=document.createElement('td');bars.textContent=String(section.bars);tr.append(bars);
      for(const role of roles) {
        const cell=document.createElement('td'),value=section.roles?.[role];
        if(value?.event_count) {
          cell.textContent=`${value.events_per_bar}/bar · v${Math.round(value.mean_velocity)}`;
          const pitches=Object.entries(value.midi_pitch_counts||{}).map(([pitch,count])=>`${pitch}×${count}`).join(', ');
          const articulations=Object.entries(value.articulations||{}).map(([name,count])=>`${name}×${count}`).join(', ');
          cell.title=[`${value.event_count} MIDI events`,pitches&&`MIDI notes ${pitches}`,articulations&&`Articulations ${articulations}`].filter(Boolean).join(' · ');
        } else { cell.textContent='—'; }
        tr.append(cell);
      }
      sectionAuditBody.append(tr);
    }
    if(!audit.sections?.length) {
      const tr=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=2+roles.length;cell.textContent='No section measurements are available for this candidate.';tr.append(cell);sectionAuditBody.append(tr);
    }
  } catch(error) {
    if(requestId!==sectionAuditRequest)return;
    const tr=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=2+roles.length;cell.textContent=`Section measurements unavailable: ${error.message}`;tr.append(cell);sectionAuditBody.append(tr);
  }
}
function listRows(rows,lane,target) {
  const filter=$('filter').value.toLowerCase();
  const filtered=rows.filter(row=>(row.genre+' '+row.title+' '+(row.song_type||'')).toLowerCase().includes(filter));
  $(target).innerHTML=filtered.map(row=>`<div class="song"><div><strong>${esc(row.title)}</strong><small>${esc(row.genre.replaceAll('_',' '))} · ${esc(row.song_type||'free')} · ${row.tempo_bpm} BPM · ${esc(row.meter)} · ${row.audio_state==='RENDERED'?'Audio':'MIDI'}</small></div><button data-job="${esc(row.job_id)}">OPEN</button></div>`).join('')||'<p class="hint">No matching songs.</p>';
  $(target).querySelectorAll('button').forEach(button=>button.onclick=()=>{selected={lane,row:rows.find(x=>x.job_id===button.dataset.job)};updateSelected();window.scrollTo({top:0,behavior:'smooth'})});
}
function refreshLists() {
  listRows(allJobs.seeds,'seeds','library');listRows(allJobs.jobs,'jobs','jobs');$('seedCount').textContent=allJobs.seeds.length;
}
async function refreshJobs() {allJobs=await api('/api/jobs');refreshLists()}
async function loadAtlasDomains() {
  try {
    const data=await api('/api/atlas/domains');
    $('atlasSummary').textContent=`${data.candidate_domain_count} candidates · ${data.unique_domain_count} Sonoris-specific`;
    $('atlasCounts').textContent=`${data.shared_domain_count} shared with Pictora · ${data.global_candidate_domain_union} domain union · ${data.execution_grade_signature_count} execution-grade signatures`;
    const list=$('atlasDomainList');list.replaceChildren();
    for(const domain of data.domains||[]) {
      const item=document.createElement('li'),title=document.createElement('strong'),task=document.createElement('span');
      title.textContent=`${domain.domain_id} · ${domain.domain_name}`;task.textContent=domain.domain_task_hypothesis;
      item.append(title,task);list.append(item);
    }
  } catch(error) {$('atlasSummary').textContent='Domain map unavailable'}
}
async function init() {
  catalog=await api('/api/catalog');
  $('genreCount').textContent=Object.keys(catalog.genres).length;
  $('moduleCount').textContent=Object.values(catalog.modules).reduce((n,choices)=>n+Object.values(choices).filter(x=>x.available).length,0);
  $('engineName').textContent=catalog.render_state==='SAMPLED_STEMS_GUITARIX_V2'?'Sampled stems · Guitarix v2':catalog.render_state||'Unavailable';
  $('genre').innerHTML=Object.entries(catalog.genres).map(([key,g])=>{
    const state=g.maturity?.state||'GENERIC_FIXTURE';
    const badge=
      state==='SPECIALIST'
        ? 'SPECIALIST'
        : state==='MIXED'
          ? 'MIXED'
          : 'GENERIC FIXTURE';

    return `<option value="${esc(key)}">${esc(g.label)} · ${esc(badge)}</option>`;
  }).join('');
  $('key').innerHTML=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'].map(k=>`<option value="${k}">${k}</option>`).join('');
  $('tuning').innerHTML=Object.entries(catalog.tunings).map(([key,x])=>`<option value="${esc(key)}">${esc(x.label)}</option>`).join('');
  $('tone').innerHTML=Object.keys(catalog.tone_profiles).map(key=>`<option value="${esc(key)}">${esc(key.replaceAll('_',' '))}</option>`).join('');
  renderModules();renderMix();genreChanged();
  $('genre').onchange=genreChanged;$('preset').onchange=applyPreset;
  $('songType').onchange=()=>{updateCompositionDefaults();if($('preset').value==='genre')applyPreset()};
  $('tone').onchange=()=>$('drive').value=catalog.tone_profiles[$('tone').value].drive;
  $('bmPreset').onchange=applyBlackMetalPreset;
  $('bmKeysKind').onchange=syncBlackMetalModule;
  if($('bmFuneralDiseasePreset')){
    $('bmFuneralDiseasePreset').onclick=
      applyFuneralDiseasePreset;
  }

  if($('bmProduction')){
    $('bmProduction').onchange=
      updateBlackMetalStatus;
  }
  for(const id of ['bmKeysMotion','bmKeysRegister','bmKeysDensity'])$(id).onchange=updateBlackMetalStatus;
  $('bmKeysLevel').oninput=updateBlackMetalStatus;
  $('resetButton').onclick=()=>{document.getElementById('composeForm').reset();genreChanged();setStatus('Controls reset.')};
  $('filter').oninput=refreshLists;
  $('saveRecipe').onclick=async()=>{
    const name=$('recipeName').value.trim();
    if(!name){$('recipeName').focus();$('recipeState').textContent='Enter a recipe name first.';return}
    $('saveRecipe').disabled=true;$('recipeState').textContent='Saving this setup…';
    try{const data=await api('/api/workflows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,controls:recipeControls()})});await refreshRecipes(data.recipe.id);$('recipeState').textContent=`Saved “${data.recipe.name}” · available after restart`;setStatus(`Saved session recipe “${data.recipe.name}”.`)}catch(error){$('recipeState').textContent=error.message}finally{$('saveRecipe').disabled=false}
  };
  $('restoreStarters').onclick=async()=>{
    $('restoreStarters').disabled=true;$('recipeState').textContent='Adding missing genre starter sessions…';
    try{
      const data=await api('/api/workflows/restore-starters',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
      savedRecipes=Array.isArray(data.recipes)?data.recipes:[];refreshRecipeOptions();
      const message=data.added?`Added ${data.added} original starter sessions · ${data.total}/${data.limit} saved`:`Starter sessions are already present · ${data.total}/${data.limit} saved`;
      $('recipeState').textContent=message;setStatus(message);
    }catch(error){$('recipeState').textContent=error.message;setStatus(error.message,true)}
    finally{$('restoreStarters').disabled=false}
  };
  $('loadRecipe').onclick=()=>{const recipe=savedRecipes.find(row=>row.id===$('recipeSelect').value);if(recipe)loadRecipe(recipe)};
  $('deleteRecipe').onclick=async()=>{
    const id=$('recipeSelect').value, recipe=savedRecipes.find(row=>row.id===id);if(!recipe)return;
    $('deleteRecipe').disabled=true;$('recipeState').textContent='Deleting recipe…';
    try{await api(`/api/workflows/${encodeURIComponent(id)}`,{method:'DELETE'});savedRecipes=savedRecipes.filter(row=>row.id!==id);$('recipeName').value='';refreshRecipeOptions();$('recipeState').textContent=`Deleted “${recipe.name}”.`;}
    catch(error){$('recipeState').textContent=error.message;$('deleteRecipe').disabled=false}
  };
  $('recipeSelect').onchange=()=>{const recipe=savedRecipes.find(row=>row.id===$('recipeSelect').value);$('loadRecipe').disabled=!recipe;$('deleteRecipe').disabled=!recipe;if(recipe)$('recipeName').value=recipe.name};
  await refreshRecipes();
  await refreshJobs();
  await loadAtlasDomains();
}
$('composeForm').onsubmit=async event=>{
  event.preventDefault();$('compileButton').disabled=true;setStatus('Compiling genre grammar, event score and MIDI…');
  try {
    const request={genre:$('genre').value,song_type:$('songType').value||undefined,title:$('title').value||undefined,mood:$('mood').value||undefined,
      tempo_bpm:$('tempo').value?Number($('tempo').value):undefined,meter:$('meter').value||undefined,bars:$('bars').value?Number($('bars').value):undefined,
      tonal_center:$('key').value+'-'+$('mode').value,seed:Number($('seed').value),gain_db:Number($('gain').value),tuning:$('tuning').value,
      tone_profile:$('tone').value,guitar_drive:Number($('drive').value),guitar_attack:Number($('attack').value),drum_intensity:Number($('drumIntensity').value),
      modules:Object.fromEntries(roles.map(role=>[role,$('module_'+role).value])),
      mix_levels:Object.fromEntries(roles.map(role=>[role,Number($('mix_'+role).value)]))
    };

    if(request.genre==='black_metal')Object.assign(request,readBlackMetalControls());
    const value=await api('/api/compile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    await refreshJobs();selected={lane:'jobs',row:value.receipt};updateSelected();setStatus('Song compiled. MIDI and receipt saved. Render audio to listen.');
  }catch(error){setStatus(error.message,true)}finally{$('compileButton').disabled=false}
};
$('renderButton').onclick=async()=>{
  if(!selected)return;$('renderButton').disabled=true;setStatus('Rendering selected instrument stems locally…');
  try {
    const value=await api('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:selected.row.job_id,lane:selected.lane,force:true})});
    selected.row=value.receipt;await refreshJobs();updateSelected();setStatus('Audio rendered. Listen, then adjust and compile another candidate.');
  }catch(error){setStatus(error.message,true)}finally{$('renderButton').disabled=false}
};
$('mediaHandoffButton').onclick=async()=>{
  if(!selected||selected.row.audio_state!=='RENDERED')return;
  const button=$('mediaHandoffButton'),note=$('mediaHandoffNote');button.disabled=true;button.textContent='Preparing held handoff…';note.hidden=false;note.textContent='Binding Sonoris audio and composition receipts for local campaign, offer, or explainer previews…';
  try{
    const result=await api('/api/media-handoffs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:selected.row.job_id,lane:selected.lane})});
    const env=result.pipeline_environment;
    $('mediaHandoffReceipt').href=`/api/media-handoffs/${encodeURIComponent(selected.lane)}/${encodeURIComponent(selected.row.job_id)}/receipt`;
    $('mediaHandoffReceipt').hidden=false;
    note.textContent=`Ready for local media review: ${result.handoff.title} · ${result.handoff.genre}. For a pipeline preview, set ${env.DIO_SONORIS_REVIEW_JOB} as DIO_SONORIS_REVIEW_JOB and ${env.DIO_SONORIS_REVIEW_LANE} as DIO_SONORIS_REVIEW_LANE. Rights remain unverified; publication and release stay unauthorized.`;
    setStatus('Sonoris review handoff prepared. Rights remain unverified and release is blocked.');
  }catch(error){note.textContent=`Handoff unavailable: ${error.message}`;note.classList.add('media-handoff-error')}
  finally{button.textContent='Prepare media review handoff';button.disabled=selected?.row.audio_state!=='RENDERED'}
};
init().catch(error=>setStatus('Studio startup failed: '+error.message,true));
