(() => {
  const $ = id => document.getElementById(id);
  const fields = ['studioMode','studioCheckpoint','studioPrompt','studioNegative','studioWidth','studioHeight','studioSteps','studioCfg','studioSampler','studioScheduler','studioDenoise','studioMaskGrow','studioMaskBlend','studioInpaintContext','studioInpaintWidth','studioInpaintHeight','studioDifferential','studioSeed','poseStrength','identityStrength','identityLoraStrength','faceReferenceStrength','compositionStrength'];
  const LEGACY_PRESET_STORAGE_KEY = 'pictora-studio-workflows-v1';
  const source = $('studioSource'), mask = $('studioMask'), canvas = $('studioPaint'), ctx = canvas.getContext('2d');
  let painting = false, latestImageUrl = '', latestImageBlob = null, latestObjectUrl = '', compareSourceObjectUrl = '', modelProfiles = {}, runtimeInfo = {};
  let maskZoom = 1, studioFeatures = {}, workflowPresets = [];

  async function refreshWorkflowPresets(selected = '') {
    const select = $('studioPresetSelect');
    let serviceAvailable = true;
    select.disabled = true;
    $('studioPresetName').disabled = true;
    $('studioSavePreset').disabled = true;
    try {
      let response = await fetch('/api/studio/workflows', {cache: 'no-store'});
      let data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not load saved workflows.');
      workflowPresets = Array.isArray(data.workflows) ? data.workflows : [];

      // Migrate named setups created by the earlier browser-only version.
      let legacy = [];
      try {
        const value = JSON.parse(localStorage.getItem(LEGACY_PRESET_STORAGE_KEY) || '[]');
        if (Array.isArray(value)) legacy = value.filter(row => row && typeof row.name === 'string' && row.controls && typeof row.controls === 'object');
      } catch (_) {}
      if (legacy.length) {
        let migrated = true;
        for (const row of legacy) {
          if (workflowPresets.some(saved => String(saved.name).toLocaleLowerCase() === row.name.trim().toLocaleLowerCase())) continue;
          try {
            const saved = await fetch('/api/studio/workflows', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: row.name, controls: row.controls})});
            if (!saved.ok) migrated = false;
          } catch (_) { migrated = false; }
        }
        if (migrated) {
          try { localStorage.removeItem(LEGACY_PRESET_STORAGE_KEY); } catch (_) {}
          response = await fetch('/api/studio/workflows', {cache: 'no-store'});
          data = await response.json();
          if (!response.ok) throw new Error(data.error || 'Could not reload migrated workflows.');
          workflowPresets = Array.isArray(data.workflows) ? data.workflows : [];
        } else {
          $('studioPresetStatus').textContent = 'Some earlier browser-only workflows could not be migrated; their local copy has been kept.';
        }
      }
      let legacyStillPresent = false;
      try { legacyStillPresent = Boolean(localStorage.getItem(LEGACY_PRESET_STORAGE_KEY)); } catch (_) {}
      if (!legacyStillPresent) {
        $('studioPresetStatus').textContent = 'Saved workflows persist on this machine and are shared by its browser profiles. Images and references are never stored in a workflow.';
      }
    } catch (error) {
      serviceAvailable = false;
      $('studioPresetStatus').textContent = `Saved workflow service unavailable: ${error.message} Renders can still run.`;
    }
    const presets = [...workflowPresets].sort((a, b) => a.name.localeCompare(b.name));
    select.replaceChildren(new Option('Choose a saved setup', ''));
    for (const preset of presets) {
      select.add(new Option(preset.name, preset.id));
    }
    if (selected && presets.some(row => row.id === selected)) {
      select.value = selected;
    }
    const hasSelection = Boolean(select.value);
    select.disabled = !serviceAvailable;
    $('studioPresetName').disabled = !serviceAvailable;
    $('studioSavePreset').disabled = !serviceAvailable;
    $('studioLoadPreset').disabled = !serviceAvailable || !hasSelection;
    $('studioDeletePreset').disabled = !serviceAvailable || !hasSelection;
    if (!presets.length) select.options[0].textContent = 'No saved workflows';
    return serviceAvailable;
  }

  async function saveWorkflowPreset() {
    const name = $('studioPresetName').value.trim();
    if (!name) {
      $('studioPresetStatus').textContent = 'Enter a name for this setup first.';
      $('studioPresetName').focus();
      return;
    }
    if (!$('studioCheckpoint').value) {
      $('studioPresetStatus').textContent = 'Wait for Pictora to discover a compatible checkpoint before saving.';
      return;
    }
    const controls = Object.fromEntries(fields.filter(id => $(id)).map(id => [id, $(id).value]));
    try {
      const response = await fetch('/api/studio/workflows', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, controls})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Workflow save failed.');
      await refreshWorkflowPresets(result.workflow.id);
      $('studioPresetName').value = name;
      $('studioPresetStatus').textContent = `Saved “${name}” on this machine. Images and references are not included.`;
    } catch (error) {
      $('studioPresetStatus').textContent = error.message;
    }
  }

  function loadWorkflowPreset() {
    const id = $('studioPresetSelect').value;
    const preset = workflowPresets.find(row => row.id === id);
    if (!preset) return;
    const checkpoint = preset.controls.studioCheckpoint;
    if (checkpoint && [...$('studioCheckpoint').options].some(option => option.value === checkpoint && !option.disabled)) {
      $('studioCheckpoint').value = checkpoint;
      applyCheckpointProfile();
    }
    for (const id of fields) {
      const input = $(id), value = preset.controls[id];
      if (input && value !== undefined && (id !== 'studioCheckpoint' || [...input.options].some(option => option.value === value && !option.disabled))) {
        input.value = value;
      }
    }
    setMode(true);
    updateReferenceSupport();
    $('studioPresetName').value = preset.name;
    $('studioPresetStatus').textContent = `Loaded “${preset.name}”. Re-select source and reference images for this render.`;
    $('studioHead').scrollIntoView({behavior: 'smooth', block: 'start'});
  }

  async function deleteWorkflowPreset() {
    const id = $('studioPresetSelect').value;
    const removed = workflowPresets.find(row => row.id === id);
    if (!removed) return;
    try {
      const response = await fetch(`/api/studio/workflows/${encodeURIComponent(id)}`, {method: 'DELETE'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Workflow deletion failed.');
      $('studioPresetName').value = '';
      await refreshWorkflowPresets();
      $('studioPresetStatus').textContent = `Deleted “${removed.name}” from this machine.`;
    } catch (error) {
      $('studioPresetStatus').textContent = error.message;
    }
  }

  $('studioSavePreset').addEventListener('click', saveWorkflowPreset);
  $('studioLoadPreset').addEventListener('click', loadWorkflowPreset);
  $('studioDeletePreset').addEventListener('click', deleteWorkflowPreset);
  $('studioPresetSelect').addEventListener('change', () => {
    const id = $('studioPresetSelect').value;
    const preset = workflowPresets.find(row => row.id === id);
    if (preset) $('studioPresetName').value = preset.name;
    $('studioLoadPreset').disabled = !preset;
    $('studioDeletePreset').disabled = !preset;
  });

  function applyMaskZoom() {
    const img = $('studioSourcePreview');
    const wrap = document.querySelector('.studio-canvas-wrap');

    if (
      !img ||
      !wrap ||
      !img.naturalWidth ||
      !img.naturalHeight
    ) {
      return;
    }

    const stage = wrap.parentElement;
    const availableWidth = Math.max(
      240,
      stage.clientWidth - 16
    );

    const availableHeight = Math.max(
      240,
      window.innerHeight * 0.65
    );

    const fitScale = Math.min(
      1,
      availableWidth / img.naturalWidth,
      availableHeight / img.naturalHeight
    );

    const scale = fitScale * maskZoom;

    wrap.style.width =
      `${Math.round(img.naturalWidth * scale)}px`;

    wrap.style.height =
      `${Math.round(img.naturalHeight * scale)}px`;

    wrap.style.maxWidth = 'none';
    wrap.style.maxHeight = 'none';
    wrap.style.flex = 'none';

    img.style.width = '100%';
    img.style.height = '100%';
    img.style.maxWidth = 'none';
    img.style.maxHeight = 'none';

    canvas.style.width = '100%';
    canvas.style.height = '100%';

    stage.style.overflow = 'auto';
    stage.style.display = 'block';

    const pct = Math.round(maskZoom * 100);

    $('maskZoom').value = maskZoom;
    $('maskZoomValue').textContent = `${pct}%`;
  }

  function setMaskZoom(value) {
    maskZoom = Math.max(
      0.5,
      Math.min(5, Number(value))
    );

    applyMaskZoom();
  }

  function status(message) { $('studioStatus').textContent = message; }
  function setMode(preserveDenoise=false) {
    const mode = $('studioMode').value;
    $('studioSourceField').hidden = mode === 'generate';
    $('studioMaskField').hidden = !['inpaint','reshape'].includes(mode);
    $('studioPaintHelp').hidden = !['inpaint','reshape'].includes(mode);
    const localEdit = ['inpaint','reshape'].includes(mode);

    $('studioMaskGrowField').hidden = !localEdit;
    $('studioMaskBlendField').hidden = !localEdit;
    $('studioInpaintContextField').hidden = !localEdit;
    $('studioInpaintWidthField').hidden = !localEdit;
    $('studioInpaintHeightField').hidden = !localEdit;

    $('studioDifferentialField').hidden = mode !== 'reshape';
    if (!preserveDenoise) {
      $('studioDenoise').value =
        mode === 'generate' ? '1' :
        mode === 'reshape' ? '0.82' :
        mode === 'inpaint' ? '0.60' :
        '0.60';
    }
    showSource();
  }
  async function showSource() {
    const file = source.files[0];
    if (!file) { $('studioSourcePreview').removeAttribute('src'); $('studioSourcePreview').hidden = true; $('studioEmpty').hidden = false; return; }
    const img = $('studioSourcePreview');
    img.onload = () => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.clearRect(0,0,canvas.width,canvas.height);

    // Preserve the source aspect ratio by default for img2img/inpaint.
    const maxDim = 1536;
    let w = img.naturalWidth;
    let h = img.naturalHeight;

    if (Math.max(w,h) > maxDim) {
      const scale = maxDim / Math.max(w,h);
      w *= scale;
      h *= scale;
    }

    w = Math.max(256, Math.round(w / 8) * 8);
    h = Math.max(256, Math.round(h / 8) * 8);

    $('studioWidth').value = w;
    $('studioHeight').value = h;

      maskZoom = 1;

      requestAnimationFrame(() => applyMaskZoom());

  };
    img.src = URL.createObjectURL(file); img.hidden = false; $('studioEmpty').hidden = true;
  }
  source.addEventListener('change', showSource);
  $('studioMode').addEventListener('change', () => setMode());

  function updateCheckpointTerms(profile) {
    const terms = profile?.terms || {};
    const termsState = String(terms.terms_state || 'UNVERIFIED');
    const licenseName = terms.license ? String(terms.license) : 'license not recorded';
    const sourceName = terms.upstream_source ? String(terms.upstream_source) : 'upstream source not recorded';
    const guidance = terms.workflow_guidance || {};
    const guidanceNotes = [];
    if (Number(guidance.clip_skip) > 1) guidanceNotes.push(`CLIP skip ${guidance.clip_skip} is applied automatically`);
    if (guidance.positive_prompt_prefix) guidanceNotes.push(`Adds the model's ${guidance.positive_prompt_prefix} quality tags unless already present`);
    if (guidance.sampler) guidanceNotes.push(`Recommended sampler: ${guidance.sampler}`);
    if (terms.source_file_sha256) guidanceNotes.push(`Upstream weight pinned · SHA-256 ${String(terms.source_file_sha256).slice(0, 16)}…`);
    else if (terms.observed_local_file_sha256) guidanceNotes.push(`Local weight pinned; upstream identity unresolved · SHA-256 ${String(terms.observed_local_file_sha256).slice(0, 16)}…`);
    const gpu = (runtimeInfo.devices || []).find(device => Number(device.vram_total_bytes) > 0);
    const modelGb = Number(profile?.local_file_bytes) > 0 ? Number(profile.local_file_bytes) / 1e9 : 0;
    const vramGb = gpu ? Number(gpu.vram_total_bytes) / 1e9 : 0;
    const freeGb = gpu ? Number(gpu.vram_free_bytes) / 1e9 : 0;
    const memoryNote = modelGb && gpu && Number(profile.local_file_bytes) > Number(gpu.vram_free_bytes)
      ? ` Checkpoint file ${modelGb.toFixed(1)} GB exceeds current free VRAM ${freeGb.toFixed(1)} GB of ${vramGb.toFixed(1)} GB; offload, slow rendering, or memory failure is possible.`
      : '';
    const restrictions = (terms.usage_constraints || []).slice(0, 2).join(' ');
    $('studioModelTerms').textContent = `Model terms: ${termsState} · ${licenseName} · ${sourceName}. Commercial use is ${terms.commercial_use === 'VERIFIED' ? 'marked verified in the manifest; review the receipt' : 'not cleared'}.${restrictions ? ` ${restrictions}` : ''}${memoryNote}`;
    $('studioModelGuidance').textContent = guidanceNotes.join(' · ');
  }

  function applyCheckpointProfile() {
    const profile = modelProfiles[$('studioCheckpoint').value];

    if (!profile) return;

    const d = profile.defaults || {};

    if (d.width) $('studioWidth').value = d.width;
    if (d.height) $('studioHeight').value = d.height;
    if (d.steps) $('studioSteps').value = d.steps;
    if (d.cfg !== undefined) $('studioCfg').value = d.cfg;
    if (d.sampler) $('studioSampler').value = d.sampler;
    if (d.scheduler) $('studioScheduler').value = d.scheduler;

    const mode = $('studioMode').value;

    if (mode === 'generate' && d.denoise_generate !== undefined) {
      $('studioDenoise').value = d.denoise_generate;
    } else if (
      mode === 'image_to_image' &&
      d.denoise_img2img !== undefined
    ) {
      $('studioDenoise').value = d.denoise_img2img;
    } else if (
      mode === 'inpaint' &&
      d.denoise_inpaint !== undefined
    ) {
      $('studioDenoise').value = d.denoise_inpaint;
    }

    const family = profile.family || 'unknown';

    updateCheckpointTerms(profile);

    $('studioHealth').dataset.family = family;
    updateReferenceSupport();
  }

  function updateReferenceSupport() {
    const profile=modelProfiles[$('studioCheckpoint').value];
    const supported={generate:profile?.generate,image_to_image:profile?.image_to_image,inpaint:profile?.inpaint,reshape:profile?.reshape};
    const modeSelect=$('studioMode');
    for(const option of modeSelect.options) option.disabled=!supported[option.value];
    if(!supported[modeSelect.value]) {
      modeSelect.value=Object.keys(supported).find(mode=>supported[mode])||'generate';
      setMode(true);
    }
    for(const role of ['pose','identity','composition','face_reference']) {
      const familySupport=Boolean(profile?.reference_controls?.[role]);
      const available=Boolean(studioFeatures[role]?.available)&&familySupport;
      const input=$(role+'Ref');
      const state=$(role+'State');
      const hadSelection=Boolean(input.files?.length);
      if(hadSelection&&!available) input.value='';
      input.disabled=!available;
      input.title=available?(role==='face_reference'?'Appearance guidance only; this does not lock identity':''):'This checkpoint has no installed, model-family-compatible control weights';
      state.textContent=available?(input.files?.[0]?`Selected · ${input.files[0].name}`:role==='face_reference'?'Ready · appearance guidance, not identity lock':'Ready'):hadSelection?'Selected image cleared · incompatible with this checkpoint':familySupport?'Unavailable in local ComfyUI':'Choose a checkpoint with compatible weights for this reference control';
      const clearButton=document.querySelector(`[data-clear-reference="${role}"]`);
      if(clearButton) clearButton.disabled=!input.files?.length;
    }
  }

  for(const role of ['pose','identity','composition','face_reference']) {
    const input=$(role+'Ref');
    const state=$(role+'State');
    const clearButton=document.querySelector(`[data-clear-reference="${role}"]`);
    input.addEventListener('change',()=>{
      state.textContent=input.files?.[0]?`Selected · ${input.files[0].name}`:'Ready';
      if(clearButton) clearButton.disabled=!input.files?.length;
    });
    clearButton?.addEventListener('click',()=>{
      input.value='';
      clearButton.disabled=true;
      const profile=modelProfiles[$('studioCheckpoint').value];
      const supported=Boolean(studioFeatures[role]?.available)&&Boolean(profile?.reference_controls?.[role]);
      state.textContent=supported?(role==='face_reference'?'Ready · appearance guidance, not identity lock':'Ready'):'Choose a checkpoint with compatible weights for this reference control';
    });
  }

  $('studioCheckpoint').addEventListener(
    'change',
    applyCheckpointProfile
  );



  $('maskZoom').addEventListener(
    'input',
    e => setMaskZoom(e.target.value)
  );

  $('zoomInMask').addEventListener(
    'click',
    () => setMaskZoom(maskZoom + 0.25)
  );

  $('zoomOutMask').addEventListener(
    'click',
    () => setMaskZoom(maskZoom - 0.25)
  );

  $('zoomResetMask').addEventListener(
    'click',
    () => setMaskZoom(1)
  );

  $('maskPanMode').addEventListener(
    'change',
    () => {
      const pan = $('maskPanMode').checked;

      canvas.style.pointerEvents =
        pan ? 'none' : 'auto';

      status(
        pan
          ? 'Pan mode enabled. Scroll around the zoomed image.'
          : 'Mask painting enabled.'
      );
    }
  );


  $('exportMask').addEventListener('click', async () => {
    if (!canvas.width || !canvas.height) {
      status('Choose a source image before exporting a mask.');
      return;
    }

    /*
     * The painting canvas itself is transparent with white strokes.
     * Export an explicit black-background / white-foreground mask
     * so it is directly reusable by Pictora and ComfyUI.
     */
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = canvas.width;
    exportCanvas.height = canvas.height;

    const exportCtx = exportCanvas.getContext('2d', {
      willReadFrequently: false
    });

    exportCtx.fillStyle = '#000000';
    exportCtx.fillRect(
      0,
      0,
      exportCanvas.width,
      exportCanvas.height
    );

    exportCtx.drawImage(
      canvas,
      0,
      0,
      exportCanvas.width,
      exportCanvas.height
    );

    const blob = await new Promise((resolve, reject) => {
      exportCanvas.toBlob(
        value => value ? resolve(value) : reject(
          new Error('Mask PNG encoding failed.')
        ),
        'image/png'
      );
    });

    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');

    const stamp = new Date()
      .toISOString()
      .replace(/[-:]/g, '')
      .replace(/\..+$/, '')
      .replace('T', 'T');

    a.href = url;
    a.download = `pictora-mask-${stamp}.png`;

    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(
      () => URL.revokeObjectURL(url),
      1000
    );

    status(
      `Mask exported · ${canvas.width}×${canvas.height} · white edit region on black background.`
    );
  });


  // MASK_IMPORT_TO_CANVAS
  mask.addEventListener('change', async () => {
    const file = mask.files[0];

    if (!file) {
      return;
    }

    if (!source.files[0]) {
      status('Choose the source image before importing a mask.');
      mask.value = '';
      return;
    }

    const url = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      try {
        if (!canvas.width || !canvas.height) {
          throw new Error(
            'Source canvas is not initialized.'
          );
        }

        /*
         * Imported masks are black-background / white-edit-region.
         * Draw only the luminance into our transparent painting
         * canvas so the white areas become the editable overlay.
         */
        const tmp = document.createElement('canvas');
        tmp.width = canvas.width;
        tmp.height = canvas.height;

        const tctx = tmp.getContext('2d', {
          willReadFrequently: true
        });

        tctx.fillStyle = '#000';
        tctx.fillRect(
          0,
          0,
          tmp.width,
          tmp.height
        );

        tctx.drawImage(
          img,
          0,
          0,
          tmp.width,
          tmp.height
        );

        const src = tctx.getImageData(
          0,
          0,
          tmp.width,
          tmp.height
        );

        const out = ctx.createImageData(
          canvas.width,
          canvas.height
        );

        for (let i = 0; i < src.data.length; i += 4) {
          const r = src.data[i];
          const g = src.data[i + 1];
          const b = src.data[i + 2];

          // Luminance threshold.
          const lum =
            0.2126 * r +
            0.7152 * g +
            0.0722 * b;

          if (lum >= 128) {
            out.data[i] = 255;
            out.data[i + 1] = 255;
            out.data[i + 2] = 255;
            out.data[i + 3] = 255;
          } else {
            // Black part becomes transparent in the editor.
            out.data[i] = 0;
            out.data[i + 1] = 0;
            out.data[i + 2] = 0;
            out.data[i + 3] = 0;
          }
        }

        ctx.clearRect(
          0,
          0,
          canvas.width,
          canvas.height
        );

        ctx.putImageData(out, 0, 0);

        status(
          `Mask imported · ${file.name} · ` +
          `${canvas.width}×${canvas.height}`
        );
      } catch (error) {
        status(
          'Mask import failed: ' + error.message
        );
      } finally {
        URL.revokeObjectURL(url);
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      status('Imported mask could not be decoded.');
    };

    img.src = url;
  });

$('clearMask').addEventListener('click', () => ctx.clearRect(0,0,canvas.width,canvas.height));
  function point(e) { const r = canvas.getBoundingClientRect(); return [(e.clientX-r.left)*canvas.width/r.width,(e.clientY-r.top)*canvas.height/r.height]; }
  canvas.addEventListener('pointerdown', e => {
    if (
      !['inpaint','reshape'].includes($('studioMode').value)
      || !source.files[0]
      || $('maskPanMode').checked
    ) return;
    painting = true; canvas.setPointerCapture(e.pointerId); const [x,y]=point(e);
    ctx.strokeStyle='#fff'; ctx.lineWidth=Number($('maskBrush').value)*canvas.width/canvas.getBoundingClientRect().width;
    ctx.lineCap='round'; ctx.lineJoin='round'; ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+.01,y+.01); ctx.stroke();
  });
  canvas.addEventListener('pointermove', e => { if(!painting)return; const [x,y]=point(e); ctx.lineTo(x,y); ctx.stroke(); });
  canvas.addEventListener('pointerup', () => painting=false);
  canvas.addEventListener('pointercancel', () => painting=false);
  function b64(file) { return new Promise((resolve,reject) => { const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result).split(',')[1]); reader.onerror=reject; reader.readAsDataURL(file); }); }
  function canvasBlob() { return new Promise(resolve => canvas.toBlob(resolve,'image/png')); }
  async function capabilities() {
    try {
      const response = await fetch('/api/studio/capabilities'); const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'ComfyUI unavailable');
      runtimeInfo = data.runtime || {};
      studioFeatures=data.features||{};
      modelProfiles = Object.fromEntries(
        (data.model_profiles || []).map(row => [row.name, row])
      );

      $('studioCheckpoint').replaceChildren(
        ...(data.model_profiles || []).map(profile => {
          const option = document.createElement('option');

          option.value = profile.name;

          const familyLabels = {
            krea2: 'Krea 2',
            sd15_anime: 'SD1.5 anime',
            sd15_inpaint: 'SD1.5 inpaint',
            sd15_realism: 'SD1.5 realism',
            sd15_standard: 'SD1.5 base',
            sdxl_anime: 'SDXL anime',
          };
          const label = familyLabels[profile.family] || profile.family;

          option.textContent =
            `${label} · ${profile.name}` +
            (profile.compatible ? '' : ' · unavailable');

          option.disabled = !profile.compatible;

          return option;
        })
      );
      let saved = {};
      try {
        const stored = JSON.parse(localStorage.getItem('pictora-studio-controls') || '{}');
        if (stored && typeof stored === 'object' && !Array.isArray(stored)) saved = stored;
      } catch (_) {}
      fields.forEach(id => { if (saved[id] !== undefined && $(id)) $(id).value=saved[id]; });
      const savedCheckpointExists = (data.model_profiles || []).some(row => row.name === saved.studioCheckpoint && row.compatible);
      if (!savedCheckpointExists) {
        const firstUsable = [...$('studioCheckpoint').options].find(option => !option.disabled);
        if (firstUsable) $('studioCheckpoint').value = firstUsable.value;
        applyCheckpointProfile();
      }
      updateCheckpointTerms(modelProfiles[$('studioCheckpoint').value]);
      setMode(true);
      updateReferenceSupport();
      $('studioHealth').textContent=`ComfyUI ready · ${data.checkpoints.length} checkpoints · local only`;
      const gpu=(runtimeInfo.devices||[]).find(device=>Number(device.vram_total_bytes)>0);
      $('studioRuntime').textContent=gpu?`${gpu.name} · ${(Number(gpu.vram_total_bytes)/1e9).toFixed(1)} GB VRAM · ${(Number(gpu.vram_free_bytes)/1e9).toFixed(1)} GB free at check`:'Local memory snapshot unavailable';
      $('studioRender').disabled=false;
      await refreshWorkflowPresets();
    } catch(error) { $('studioHealth').textContent=error.message+' · retrying'; $('studioRender').disabled=true; setTimeout(capabilities,5000); }
  }
  async function queue() {
    try {
      const response=await fetch('/api/studio/queue',{cache:'no-store'});
      const state=await response.json();
      if(!response.ok)throw new Error(state.error||'Queue unavailable');
      $('studioQueue').textContent=`${state.running} rendering · ${state.pending} queued`;
    } catch(error) { $('studioQueue').textContent='Render queue unavailable'; }
  }
  async function loadAtlasDomains() {
    try {
      const response=await fetch('/api/atlas/domains',{cache:'no-store'});
      const data=await response.json();
      if(!response.ok) throw new Error(data.error||'ATLAS map unavailable');
      $('atlasSummary').textContent=`${data.candidate_domain_count} candidates · ${data.unique_domain_count} Pictora-specific`;
      $('atlasCounts').textContent=`${data.shared_domain_count} shared with Sonoris · ${data.global_candidate_domain_union} domain union · ${data.execution_grade_signature_count} execution-grade signatures`;
      const list=$('atlasDomainList');
      list.replaceChildren();
      for(const domain of data.domains||[]) {
        const item=document.createElement('li');
        const title=document.createElement('strong');
        const task=document.createElement('span');
        title.textContent=`${domain.domain_id} · ${domain.domain_name}`;
        task.textContent=domain.domain_task_hypothesis;
        item.append(title,task);
        list.append(item);
      }
    } catch(error) { $('atlasSummary').textContent='Domain map unavailable'; }
  }
  async function history() {
    try {
      const data=await (await fetch('/api/studio/jobs')).json(); const list=$('studioHistory'); list.replaceChildren();
      for(const job of data.jobs) {
        const button=document.createElement('button'), image=document.createElement('img'), title=document.createElement('span');
        image.src=job.image_url; image.loading='lazy'; title.textContent=`${job.settings?.mode || 'render'} · ${job.job_id}`;
        button.append(image,title);
        button.addEventListener(
          'click',
          async()=> {
            try {
              await showResult(
                job.image_url,
                job.job_id,
                '',
                job.source_url || '',
                job.source_sha256 || ''
              );
            } catch(error) {
              status(error.message);
            }
          }
        );
        list.append(button);
      }
    } catch(error) { status('Could not load saved renders: '+error.message); }
  }
  async function sha256Hex(blob) {
    const bytes = await blob.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);

    return Array.from(new Uint8Array(digest))
      .map(x => x.toString(16).padStart(2, '0'))
      .join('');
  }

  async function showResult(url, jobId, expectedSha = '', sourceUrl = '', expectedSourceSha = '') {
    latestImageUrl = url;

    const response = await fetch(
      url + (url.includes('?') ? '&' : '?') + 't=' + Date.now(),
      { cache: 'no-store' }
    );

    if (!response.ok) {
      throw new Error(
        `Result fetch failed: HTTP ${response.status}`
      );
    }

    const blob = await response.blob();
    const actualSha = await sha256Hex(blob);

    if (
      expectedSha &&
      actualSha.toLowerCase() !== expectedSha.toLowerCase()
    ) {
      throw new Error(
        `RESULT SHA MISMATCH: expected ${expectedSha}, got ${actualSha}`
      );
    }

    latestImageBlob = blob;

    if (latestObjectUrl) {
      URL.revokeObjectURL(latestObjectUrl);
    }

    latestObjectUrl = URL.createObjectURL(blob);

    $('studioResult').style.display = 'block';
    $('studioResultImage').src = latestObjectUrl;
    $('studioCompareResult').src = latestObjectUrl;
    $('studioCompare').hidden = true;
    let compareMessage='';
    if(compareSourceObjectUrl) URL.revokeObjectURL(compareSourceObjectUrl);
    compareSourceObjectUrl = '';
    if(sourceUrl) {
      try {
        const sourceResponse=await fetch(sourceUrl,{cache:'no-store'});
        if(!sourceResponse.ok) throw new Error(`Source image fetch failed: HTTP ${sourceResponse.status}`);
        const sourceBlob=await sourceResponse.blob();
        const sourceSha=await sha256Hex(sourceBlob);
        if(expectedSourceSha&&sourceSha.toLowerCase()!==expectedSourceSha.toLowerCase()) throw new Error('Source image hash does not match its job receipt.');
        compareSourceObjectUrl=URL.createObjectURL(sourceBlob);
        $('studioCompareSource').src=compareSourceObjectUrl;
        $('studioCompare').hidden=false;
      } catch(error) {
        compareMessage=` · source comparison unavailable: ${error.message}`;
      }
    }

    $('studioDownload').href = latestObjectUrl;
    $('studioDownload').download = `pictora-${jobId}.png`;

    $('studioReceipt').href =
      `/api/studio/jobs/${jobId}/receipt`;

    $('studioResultNote').textContent =
      `Job ${jobId} · SHA256 ${actualSha.slice(0,16)}… · byte-exact result${compareMessage}`;
  }
  $('studioUseResult').addEventListener('click', async()=>{
    if(!latestImageBlob)return;

    const file=new File(
      [latestImageBlob],
      'pictora-result.png',
      {type:latestImageBlob.type || 'image/png'}
    );

    const transfer=new DataTransfer();
    transfer.items.add(file);
    source.files=transfer.files;

    $('studioMode').value='image_to_image';
    setMode();
    showSource();

    window.scrollTo({
      top:$('studioHead').offsetTop,
      behavior:'smooth'
    });
  });
  // PICTORA_MASTER_IMAGE_CONTROL_V4: references native input elements, no surrogate uploads.
  window.__pictoraMasterImageInputsV4={source,pose:$('poseRef')};
  $('studioRender').addEventListener('click', async()=>{
    if(!$('studioRights').checked){status('Confirm image and reference permissions before rendering.');return;}
    const mode=$('studioMode').value;
    if(mode!=='generate'&&!source.files[0]){status('Choose a source image.');return;}
    if(['inpaint','reshape'].includes(mode)&&!mask.files[0]){
      if(!canvas.width||!canvas.height){status('Wait for the source image preview to finish loading, then paint or upload a mask.');return;}
      if(!ctx.getImageData(0,0,canvas.width,canvas.height).data.some(x=>x)){status('Paint the inpaint region or upload a mask.');return;}
    }
    $('studioRender').disabled=true; status('ComfyUI is rendering locally. This can take several minutes…');
    try {
      const settings={mode,checkpoint:$('studioCheckpoint').value,prompt:$('studioPrompt').value,negative_prompt:$('studioNegative').value,
        width:Number($('studioWidth').value),height:Number($('studioHeight').value),steps:Number($('studioSteps').value),cfg:Number($('studioCfg').value),sampler:$('studioSampler').value,scheduler:$('studioScheduler').value,
        denoise:Number($('studioDenoise').value),seed:Number($('studioSeed').value),pose_strength:Number($('poseStrength').value),
        identity_strength:Number($('identityStrength').value),
        identity_lora_strength:Number($('identityLoraStrength').value),
        face_reference_strength:Number($('faceReferenceStrength').value),
        composition_strength:Number($('compositionStrength').value),

        mask_grow:Number($('studioMaskGrow').value),
        mask_blend:Number($('studioMaskBlend').value),
        inpaint_context:Number($('studioInpaintContext').value),
        inpaint_width:Number($('studioInpaintWidth').value),
        inpaint_height:Number($('studioInpaintHeight').value),

        differential_strength:Number($('studioDifferential').value)
      };
      const pureKreaPrompt = mode==='generate' && /krea2/i.test(settings.checkpoint);
      if(pureKreaPrompt) delete settings.pose_strength;
      const canonReceipt=window.__pictoraCharacterCanonReceipt;
      if(canonReceipt && $('studioPrompt').value.includes(canonReceipt.positive) && $('studioNegative').value.includes(canonReceipt.negative)){
        settings.character_canon_id=canonReceipt.id;
        settings.character_canon_sha256=canonReceipt.sha256;
        settings.character_canon_approval=canonReceipt.approval;
        settings.character_canon_provenance='client_reported_text_guided';
      }
      // PICTORA_MASTER_IMAGE_CONTROL_V4: client-reported binding.
      // Independently hashed original_inputs in the server receipt remain authoritative.
      const chosenMaster=window.__pictoraMasterImageSelection;
      const boundFile=chosenMaster?.role==='source'?source.files[0]:$('poseRef')?.files[0];
      if(chosenMaster && boundFile && boundFile.name===window.__pictoraMasterImageSelectionName){
        settings.master_image_id=chosenMaster.id;
        settings.master_image_sha256=chosenMaster.sha256;
        settings.master_image_role=chosenMaster.role;
        settings.master_image_provenance='client_reported_verified_master_input';
      }
      const images={};
      for(const [role,input] of [['source',source],['pose',$('poseRef')],['identity',$('identityRef')],['face_reference',$('face_referenceRef')],['composition',$('compositionRef')]]) {
        if(input.files[0] && !(pureKreaPrompt && role==='pose') && (role!=='source'||mode!=='generate')) images[role]={filename:input.files[0].name,base64:await b64(input.files[0])};
      }
      if(['inpaint','reshape'].includes(mode)) {
        const maskFile=mask.files[0] || new File([await canvasBlob()],'painted-mask.png',{type:'image/png'});
        images.mask={filename:maskFile.name,base64:await b64(maskFile)};
      }
      try {
        localStorage.setItem('pictora-studio-controls',JSON.stringify(Object.fromEntries(fields.map(id=>[id,$(id).value]))));
      } catch (_) {
        $('studioPresetStatus').textContent='Browser settings could not be saved; continuing with this render.';
      }
      const response=await fetch('/api/studio/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settings,images,owner_authorized:true})});
      const result=await response.json(); if(!response.ok)throw new Error(result.error || 'Render failed');
      await showResult(
        result.image_url,
        result.job_id,
        result.receipt_sha256,
        result.source_url || '',
        result.source_sha256 || ''
      );

      status(
        'Render complete · displayed result verified byte-for-byte.'
      );

      history();
    } catch(error) { status(error.message); } finally { $('studioRender').disabled=false; }
  });
  capabilities(); history(); queue(); loadAtlasDomains(); setInterval(queue,10000);
})();
