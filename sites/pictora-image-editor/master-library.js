/* Pictora Master Library v1. A review/prompt-preset UI, NOT an image conditioning path. */
(() => {
  'use strict';
  const poseRecipes = {
    none: {label:'No pose preset', positive:'', negative:''},
    overhead_supine: {label:'Lying on back · overhead', positive:'CAMERA AND COMPOSITION PRIORITY: a single adult character is lying completely flat on their back on a dark studio floor, supine, facing upward toward the camera. The camera is directly OVERHEAD in a birds-eye view, pointing straight down, perpendicular to the floor, never a front-facing standing portrait or side view. Her HEAD and horns appear at the TOP of the portrait image, shoulders and straight torso at the CENTER, legs extend toward the BOTTOM, and BOTH FEET are visible inside the lower frame with breathing room. The back of her head, shoulders, spine, and hips rest on the surface. Her head is supported by the floor and her face points upward to the overhead camera, not toward a camera at standing eye level. Both knees bend outward naturally and symmetrically; lower legs and feet stay entirely in the frame. Her arms rest comfortably alongside her body, slightly separated from the torso. The bat wings lie open against the ground behind and around the shoulders without hiding the figure. A complete HEAD-TO-FEET figure is visible in one image, with horns, hands, knees, lower legs, feet, and wings included, centered in a 2:3 upright canvas. POSE AND CAMERA OVERRIDE ANY PORTRAIT, HEADSHOT, BEAUTY SHOT, OR STANDING-CHARACTER FRAMING ASSUMPTIONS.', negative:'upside down, inverted orientation, head at bottom, feet at top, rotated 180 degrees, standing upright, seated, kneeling, side-lying, prone, standing eye-level camera, low-angle shot, side camera, oblique view, tilted camera, bust portrait, headshot, face close-up, beauty shot, waist-up crop, medium shot, zoomed in, cropped head, cropped horns, cropped knees, cropped lower legs, cropped feet, cut-off wings, missing feet, wrong foreshortening, extra legs, disconnected limbs'},
    side_recline: {label:'Lying on side', positive:'adult character reclining fully on their side, body supported by the floor, head to the left of the composition, bent knees, coherent limb positions, wide horizontal frame, full silhouette, natural perspective', negative:'standing, seated upright, overhead view, impossible joints, cropped body'},
    standing_front: {label:'Standing · full body', positive:'adult character standing upright facing the camera, head at top, feet at bottom, full-body camera framing, natural balanced stance, wings clearly visible behind the shoulders', negative:'cropped feet, cut off head, seated, reclining, rear view'},
    rear_three_quarter: {label:'Rear three-quarter · over shoulder', positive:'adult character standing in a three-quarter rear view, turning head naturally over one shoulder to face the camera, full readable torso, wings and tail silhouette, balanced portrait framing', negative:'full frontal shot, impossible neck twist, cut off horns'},
    seated: {label:'Seated', positive:'adult character sitting naturally on a solid surface, believable support and leg placement, relaxed posture, readable hands, coherent wings, centered camera framing', negative:'floating, standing, malformed chair, impossible joints'},
    low_crouch: {label:'Low crouch', positive:'adult character in a low stable crouching posture with bent knees and both feet grounded, centered front composition, visible horns and wings', negative:'floating, lying down, extra legs, cropped feet'}
  };
  const styleRecipes = {
    keep: {label:'Keep current checkpoint/style', checkpoint:null, positive:'', negative:'', defaults:{}},
    realism: {label:'Realism · Krea 2', checkpoint:'nudeFashionV1Krea2_v10_full_bf16.safetensors', positive:'polished photorealistic dark fantasy character rendering, soft controlled studio lighting, natural skin tones, detailed dark hair and wing membranes, rich shadow gradients', negative:'anime, cartoon, rough sketch, chibi, hand-painted cel shading', defaults:{studioWidth:'832',studioHeight:'1248',studioSteps:'10',studioCfg:'1.0',studioSampler:'euler',studioScheduler:'simple',studioDenoise:'1'}},
    anime: {label:'Anime · MeinaMix', checkpoint:'meinamix_meinaV11.safetensors', positive:'high quality 2D dark fantasy anime illustration applied consistently to the ENTIRE FULL-BODY SCENE, smooth luminous peach skin, polished clean line art, graceful anime shading, delicate anime facial features without a portrait crop, glossy flowing hair, crisp wings and coherent limb shading, maintain the pose and camera composition exactly as described', negative:'photograph, live action, skin pores, 3D render, CGI, messy linework, rough sketch, chibi', defaults:{studioWidth:'832',studioHeight:'1248',studioSteps:'34',studioCfg:'6.0',studioSampler:'dpmpp_2m',studioScheduler:'karras',studioDenoise:'1'}}
  };
  const $ = id => document.getElementById(id);
  const begin = '\n[PICTORA_MASTER_LIBRARY_PRESET_BEGIN]\n';
  const end = '\n[PICTORA_MASTER_LIBRARY_PRESET_END]';
  function stripPreset(text) {
    const a = String(text || '');
    const start = a.indexOf(begin);
    if (start < 0) return a;
    const stop = a.indexOf(end, start + begin.length);
    return stop < 0 ? a : (a.slice(0, start) + a.slice(stop + end.length)).trim();
  }
  function setForm(id, value) {
    const el = $(id);
    if (!el) return false;
    if (el.tagName === 'SELECT' && !Array.from(el.options).some(o => o.value === value)) return false;
    el.value = value;
    el.dispatchEvent(new Event('change', {bubbles:true}));
    return true;
  }
  function create(tag, attrs={}, text) {
    const el = document.createElement(tag);
    for (const [k,v] of Object.entries(attrs)) { if (k === 'className') el.className=v; else el.setAttribute(k,v); }
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function mount() {
    const render = $('studioRender');
    if (!render || $('pictoraMasterLibrary')) return;
    const panel = create('section',{id:'pictoraMasterLibrary',style:'border:1px solid #534a58;border-radius:12px;padding:16px;margin:16px 0;background:#201c26;color:#eee'});
    panel.append(create('h3',{},'🦇 Master Library · Pose + Style'));
    panel.append(create('p',{},'Review nominees, then apply a text-guided pose recipe and a rendering style. No pose ControlNet is used. Originals remain unchanged.'));
    const controls = create('div',{style:'display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end'});
    const character = create('select',{id:'masterCharacterPreset',style:'max-width:310px;padding:8px'});
    character.append(create('option',{value:'none'},'No character identity preset'));
    character.append(create('option',{value:'loading'},'Loading character canons…'));
    character.value='loading'; character.disabled=true;
    let characterRecipes={};
    const pose = create('select',{id:'masterPosePreset',style:'max-width:260px;padding:8px'});
    for (const [key,v] of Object.entries(poseRecipes)) pose.append(create('option',{value:key},v.label));
    const style = create('select',{id:'masterStylePreset',style:'max-width:260px;padding:8px'});
    for (const [key,v] of Object.entries(styleRecipes)) style.append(create('option',{value:key},v.label));
    const filter = create('select',{id:'masterAssetFilter',style:'padding:8px'});
    for (const [key,v] of [['nominated','Curated nominations'],['all','All indexed assets'],['Nude','Nude'],['black_bat_lingerie','Black bat lingerie'],['crimson_corset','Crimson corset'],['virgin_killer','Virgin killer']]) filter.append(create('option',{value:key},v));
    const search = create('input',{id:'masterAssetSearch',type:'search',placeholder:'Search filenames / pose...',style:'padding:8px;max-width:240px'});
    const apply = create('button',{type:'button',id:'masterApplyPreset',style:'padding:10px;cursor:pointer'},'Apply to prompt + settings');
    for (const [label,field] of [['Character canon',character],['Pose recipe',pose],['Rendering style',style],['Library view',filter]]) { const wrap=create('label',{style:'display:grid;gap:5px'});wrap.append(create('span',{},label),field);controls.append(wrap); }
    controls.append(search,apply);panel.append(controls);
    const state=create('p',{id:'masterLibraryState',style:'font-size:12px;opacity:.85'},'Loading master inventory…');panel.append(state);
    const gallery=create('div',{id:'masterLibraryGallery',style:'display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;max-height:440px;overflow:auto;margin-top:12px'});panel.append(gallery);
    render.parentNode.insertBefore(panel,render);
    let assets=[];
    fetch('/api/studio/character-canons').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{
      if(data.schema!=='dio.pictora.character_canon_catalog.v1'||!Array.isArray(data.recipes)) throw Error('Invalid canon catalog');
      characterRecipes=Object.fromEntries(data.recipes.map(c=>[c.id,c]));
      character.replaceChildren(create('option',{value:'none'},'No character identity preset'));
      for(const c of data.recipes) character.append(create('option',{value:c.id},c.label+' · unapproved'));
      character.value=characterRecipes.lilith_candidate_v1?'lilith_candidate_v1':'none';
      character.disabled=false;
    }).catch(err=>{character.value='loading';character.disabled=true;state.textContent='Character canon unavailable: '+err.message;});
    character.onchange=()=>{window.__pictoraCharacterCanonReceipt=null;};
    function redraw() {
      gallery.replaceChildren();
      const f=filter.value,q=search.value.toLowerCase().trim();
      const matches=assets.filter(a=>(f==='all'||(f==='nominated'&&a.nominated)||a.collection===f) && (`${a.label||''} ${a.relative_path||''} ${a.collection||''}`).toLowerCase().includes(q));
      for (const a of matches.slice(0,120)) {
        const card=create('button',{type:'button',style:'background:#302934;color:#fff;border:1px solid #62566c;border-radius:6px;padding:5px;cursor:pointer;text-align:left'});
        const img=create('img',{src:'/api/studio/master-library/thumb/'+a.id,alt:a.label||a.relative_path,loading:'lazy',style:'width:100%;height:145px;object-fit:contain;background:#111'});
        card.append(img,create('div',{style:'font-size:12px'},(a.label||a.relative_path.split('/').pop())));
        card.append(create('small',{},a.id+' · '+(a.nominated?'nominated':'unreviewed')));
        card.onclick=()=>{if (a.pose_preset && poseRecipes[a.pose_preset]) pose.value=a.pose_preset; state.textContent=`Selected ${a.relative_path} · SHA256 ${a.sha256}. Visual nomination only; this is NOT an image control input.`; gallery.querySelectorAll('button').forEach(b=>b.style.borderColor='#62566c');card.style.borderColor='#ef8ac7';};
        gallery.append(card);
      }
      state.textContent=`${matches.length} matching assets, showing ${Math.min(matches.length,120)}. Candidates are NOT automatically approved canonical masters.`;
    }
    filter.onchange=redraw;search.oninput=redraw;
    apply.onclick=()=>{
      const positive=$('studioPrompt'),negative=$('studioNegative');
      if(!positive||!negative){state.textContent='Could not locate prompt fields. No change made.';return;}
      if(character.disabled){state.textContent='Character catalog not ready; no prompt changes made.';return;}
      const canon=character.value==='none'?null:characterRecipes[character.value];
      if(character.value!=='none'&&!canon){state.textContent='Unknown character canon; no changes made.';return;}
      if(canon&&canon.approval!=='candidate_unapproved'){state.textContent='Unexpected canon status; no changes made.';return;}
      const p=poseRecipes[pose.value],s=styleRecipes[style.value];
      if(s.checkpoint){
        if(!setForm('studioCheckpoint',s.checkpoint)){state.textContent='Checkpoint not available: '+s.checkpoint+'. No prompt changes made.';return;}
      }
      setForm('studioMode','generate');
      for(const [id,value] of Object.entries(s.defaults)) if(!setForm(id,value)){state.textContent='Setting unavailable: '+id+' (review settings manually)';}
      // PICTORA_POSE_PRIORITY_V3: spatial constraints first; then canon; then style.
      const adds=[p.positive,canon?.positive,s.positive].filter(Boolean).join(', ');
      const negadds=[p.negative,canon?.negative,s.negative].filter(Boolean).join(', ');
      const cleanPositive=stripPreset(positive.value);
      const assembledPositive=(adds?begin+adds+end:'')+(cleanPositive?'\n'+cleanPositive:'');
      if(assembledPositive.trim().length>4000){state.textContent='Prompt exceeds 4000 characters: shorten custom text or change preset. Prompt text unchanged; checkpoint/settings may already have updated.';return;}
      // The negative prompt will be checked before any prompt field is modified.

      const cleanNegative=stripPreset(negative.value);
      const assembledNegative=(negadds?begin+negadds+end:'')+(cleanNegative?'\n'+cleanNegative:'');
      if(assembledNegative.trim().length>2000){state.textContent='Negative prompt exceeds 2000 characters: shorten custom text or change preset. Prompt text unchanged; checkpoint/settings may already have updated.';return;}
      positive.value=assembledPositive;
      negative.value=assembledNegative;
      for(const el of [positive,negative]) el.dispatchEvent(new Event('input',{bubbles:true}));
      window.__pictoraCharacterCanonReceipt=canon?{id:canon.id,sha256:canon.sha256,positive:canon.positive,negative:canon.negative,approval:canon.approval}:null;
      state.textContent=canon?'Applied '+canon.label+' (candidate; '+canon.sha256.slice(0,12)+'…), pose, and style. Review before rendering. No ControlNet enabled.':'Applied pose and style without character identity. Review before rendering.';
    };
    fetch('/api/studio/master-library').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{assets=data.assets||[];redraw()}).catch(e=>state.textContent='Master library unavailable: '+e.message);
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount); else mount();
})();
