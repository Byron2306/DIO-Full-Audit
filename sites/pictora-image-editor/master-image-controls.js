/* PICTORA_MASTER_IMAGE_CONTROL_V4: real image-input binding for nominated masters.
   No Krea2 ControlNet is installed or activated; uses Pictora's normal file inputs. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const TAG = 'PICTORA_MASTER_IMAGE_CONTROL_V4';
  const make = (tag, attrs={}, text='') => {
    const el=document.createElement(tag);
    for(const [k,v] of Object.entries(attrs)) el.setAttribute(k,v);
    if(text) el.textContent=text;
    return el;
  };
  function start() {
    const panel=$('pictoraMasterLibrary');
    const gallery=$('masterLibraryGallery');
    const status=$('masterLibraryState');
    if(!panel||!gallery||!status||$('masterImageControlV4'))return false;
    const controls=make('section',{id:'masterImageControlV4',style:'border:1px solid #75617a;border-radius:9px;padding:12px;margin-top:10px'});
    controls.append(make('div',{},'Image conditioning from selected master'));
    controls.append(make('p',{style:'font-size:12px;opacity:.85'},'Use the actual verified pixels as img2img source, or as a pose reference only when the checkpoint supports pose ControlNet. Selection alone never activates image control.'));
    const choice=make('div',{id:'masterImageChoiceV4',style:'font-size:12px;margin-bottom:8px'},'Choose a thumbnail first.');
    const buttons=make('div',{style:'display:flex;gap:8px;flex-wrap:wrap'});
    const src=make('button',{type:'button',id:'masterUseAsSource',style:'padding:8px'},'Use selected as source (img2img)');
    const pose=make('button',{type:'button',id:'masterUseAsPose',style:'padding:8px'},'Use selected as pose reference');
    const clear=make('button',{type:'button',id:'masterClearImageSelection',style:'padding:8px'},'Clear selection');
    buttons.append(src,pose,clear);
    controls.append(choice,buttons);
    // Insert after gallery so the selected thumbnail and its controls stay together.
    gallery.after(controls);
    let selected=null;
    let catalog=new Map();
    fetch('/api/studio/master-library').then(r=>{if(!r.ok)throw Error('Catalog HTTP '+r.status);return r.json()}).then(d=>{
      if(d.schema!=='dio.pictora.master_library.v1'||!Array.isArray(d.assets))throw Error('Invalid master catalog');
      catalog=new Map(d.assets.map(a=>[a.id,a]));
    }).catch(e=>choice.textContent='Image binding unavailable: '+e.message);
    gallery.addEventListener('click', ev=>{
      const card=ev.target.closest('button');
      const img=card?.querySelector('img[src*="/api/studio/master-library/thumb/"]');
      if(!img||!gallery.contains(card))return;
      const id=img.getAttribute('src').split('/').pop();
      selected=catalog.get(id)||null;
      choice.textContent=selected?`Selected: ${selected.relative_path} · SHA256 ${selected.sha256} · approval=${selected.approval}`:'Catalog entry unavailable; reload gallery.';
    });
    async function bind(role) {
      if(!selected){choice.textContent='Select a thumbnail before binding an image.';return;}
      // Native Pictora input handles are exposed by the narrowly scoped studio.js hook.
      const input=window.__pictoraMasterImageInputsV4?.[role];
      if(!(input instanceof HTMLInputElement)||input.type!=='file'){
        choice.textContent='REFUSE: Image input not found. No render settings changed.';return;
      }
      if(role==='pose'){
        if(input.disabled || input.closest('[hidden], [aria-disabled="true"]')){
          choice.textContent='REFUSE: This checkpoint does not support a pose reference. Choose a supported SD1.5/SDXL checkpoint.';return;
        }
        const cp=$('studioCheckpoint')?.value||'';
        if(/krea2/i.test(cp)){
          choice.textContent='REFUSE: Krea 2 has no admitted Pictora pose-ControlNet lane. Use image-to-image source instead.';return;
        }
      }
      src.disabled=true;pose.disabled=true;
      choice.textContent='Verifying master image before attaching…';
      try {
        const response=await fetch('/api/studio/master-library/source/'+selected.id,{cache:'no-store'});
        if(!response.ok) throw Error('Server refused master: HTTP '+response.status);
        const bytes=await response.arrayBuffer();
        const expected=selected.sha256;
        if(!window.crypto?.subtle) throw Error('Browser cannot verify SHA-256; use localhost / SSH tunnel.');
        const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
        if(actual!==expected) throw Error('Master SHA256 mismatch; no image attached');
        const filename=selected.relative_path.split('/').pop();
        const mime=response.headers.get('Content-Type')||'image/png';
        const transfer=new DataTransfer();
        transfer.items.add(new File([bytes],filename,{type:mime}));
        if(role==='source') {
          const mode=$('studioMode');
          if(!mode||!Array.from(mode.options).some(o=>o.value==='image_to_image')) throw Error('Image-to-image mode unavailable');
          mode.value='image_to_image';mode.dispatchEvent(new Event('change',{bubbles:true}));
          // Krea2 uses an encoded source latent. Keep initial denoise moderate and editable.
          const denoise=$('studioDenoise');
          if(denoise){denoise.value='0.4';denoise.dispatchEvent(new Event('input',{bubbles:true}));}
        }
        input.files=transfer.files;
        input.dispatchEvent(new Event('change',{bubbles:true}));
        window.__pictoraMasterImageSelectionName=filename;
        window.__pictoraMasterImageSelection={id:selected.id,sha256:expected,role,provenance:'verified_file_input_sha256'};
        choice.textContent=`Attached ${filename} to ${role==='source'?'img2img source':'pose reference'} · verified SHA256 ${expected}. Review mode, denoise, prompt and rights before rendering.`;
        status.textContent=`Image control input attached: ${filename}. This is no longer text-only. Original remains immutable.`;
      } catch(err){choice.textContent='REFUSE image binding: '+err.message;}
      finally{src.disabled=false;pose.disabled=false;}
    }
    src.onclick=()=>bind('source');
    pose.onclick=()=>bind('pose');
    clear.onclick=()=>{selected=null;choice.textContent='Gallery selection cleared. Previously attached files remain in Pictora input fields until explicitly removed.';};
    return true;
  }
  function boot(){if(start())return; const observer=new MutationObserver(()=>{if(start())observer.disconnect();});observer.observe(document.body,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
