# Pictora Image Studio

Pictora's master local dashboard is served at `http://127.0.0.1:42153/`. It combines a ComfyUI-backed image studio with the non-destructive photo-editing pilot. Each render or edit writes a separate output and receipt containing its inputs, controls, workflow/model hashes, output hash, and review state.

## Studio controls

- Generate from a prompt, transform a source image, inpaint a painted or uploaded mask, and reshape a masked region.
- Select compatible local checkpoints across SD1.5 realism, anime, and inpaint families, SDXL anime, and Krea2.
- Add pose and composition references where the selected model family and installed weights support them.
- Reference controls update when the checkpoint changes. If a selected pose, identity, composition, or face appearance image is incompatible with the new checkpoint or missing local weights, Pictora clears that image and shows why before a render can be submitted. Each reference also has its own clear control and selected-file status.
- FaceID identity guidance is restricted to compatible SD1.5 profiles; it can guide resemblance but cannot guarantee an exact identity match. The SDXL face-reference adapter guides facial appearance from a cropped image and does not lock identity.
- Reuse a seed and saved controls for repeatable reruns. Render history remains local and survives dashboard restarts.
- Save up to 30 named render workflows in the local Pictora service store. A workflow restores mode, checkpoint, prompt, dimensions, sampler, seed, denoise, and reference strengths, and is available from browser profiles on this machine after a service restart. Source, mask, and reference images are intentionally excluded and must be selected again. Earlier browser-only workflows migrate into the service store on dashboard load.
- A new install seeds four editable starters for SD1.5 realism, SD1.5 anime, SDXL anime with composition guidance, and SD1.5 masked inpainting. The starters are only created when the persistent workflow store is first initialized; deleting them stays deleted after restart.
- Each installed checkpoint profile carries an explicit terms state from `config/pictora/checkpoint_terms_manifest_v1.json`. Five Civitai/Hugging Face checkpoints now have exact upstream version/file hashes; Pony V6 is also version/hash-pinned. The installed Krea 2 fine-tune is locally hash-pinned and its safetensors metadata reveals its base and merged adapter, but the adapter's origin/version is unidentified. All six remain `NOT_CLEARED` for commercial use; the selected state, attribution or model restrictions, and source/local hash proof appear in future render receipts. A compatible installed model is not automatically a cleared model.
- Capability discovery also reports local ComfyUI GPU/VRAM and RAM, plus the selected checkpoint file size. The dashboard warns when the selected weight file exceeds currently free VRAM; this is a capacity hint because ComfyUI may offload weights and free memory can change before sampling begins. New render receipts preserve this runtime snapshot and selected model file size.

## Recent live render proof

On 2026-10-31, the persistent studio rendered a 512×512 anime-family candidate through the live `/api/studio/render` route with `meinamix_meinaV11.safetensors`, seed `20261031`, 16 steps, and the local ComfyUI 0.42.0 runtime. The image, studio receipt, and ComfyUI receipt are under `deliverables/pictora_image_editor/studio_jobs/20261031T181001Z-e13d96db/`. The studio receipt binds output SHA-256 `4290fd34c2062a06dbeaf3a93184bf3f65eadb060d5b8403d6f23824a7776e2f` and records checkpoint terms as `UNVERIFIED`, commercial use `NOT_CLEARED`, `remote_processing=false`, and `release_authorized=false`. This proves an end-to-end local generation path; it does not clear that model for commercial use.

### Pony V6 model-specific setup

The installed `ponyDiffusionV6XL_v6StartWithThisOne.safetensors` file is 6,938,041,050 bytes; its local SHA-256 was verified against the published `67ab2fd8ec439a89b3fedb15cc65f54336af163c7eb5e4f2acc98f090a29b0b3` file hash. Pictora now pins this exact model version in `config/pictora/checkpoint_terms_manifest_v1.json` and refuses to apply its specialized workflow if a same-named weight file does not match. The live studio automatically applies CLIP skip 2 and the model's quality-tag prefix, and its Pony profile defaults to Euler ancestral, 25 steps, and 1024×1024. The source card explicitly recommends CLIP skip 2 and warns of blob-like output without it; it also recommends Euler ancestral at 25 steps and 1024px. [Pony V6 model card](https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL)

The same model card identifies a modified Fair AI Public License 1.0-SD, prohibits monetized inference through websites or applications without an additional agreement, and directs commercial users to contact the author. Accordingly Pictora records `IDENTIFIED_RESTRICTED` and `NOT_CLEARED`; this model is not approved for a paid/customer-facing inference service. [Fair AI Public License 1.0-SD](https://freedevproject.org/faipl-1.0-sd/)

### Checkpoint provenance update

The installed DreamShaper 8-inpainting, epiCRealism Natural Sin RC1 VAE, and MeinaMix V11 bytes match their exact Civitai version file hashes. Their model IDs/version IDs, creators, base families, commercial-use flags, and credit requirements are recorded in the manifest. The Stable Diffusion v1.5 base checkpoint matches the published Hugging Face file hash and CreativeML OpenRAIL-M model card. Source identity is therefore no longer inferred from a filename. Civitai version APIs do not return complete license text for these models, so Pictora keeps commercial service use held pending a terms review; creator-credit obligations remain visible in the model profile.

The local `nudeFashionV1Krea2_v10_full_bf16.safetensors` metadata identifies a Krea 2 Turbo base merged with `nsfwfashion-photo-v2.safetensors` at strength 1.0. Its exact installed bytes are pinned, but the adapter author/version and license are not known. Krea's Community License limits commercial use by company revenue and requires content-filter measures; Pictora has not established those conditions, so this profile remains release-held. See the [Krea 2 Community License](https://www.krea.ai/krea-2-licensing) and [commercial license guidance](https://www.krea.ai/open-source-pricing).

A live Pictora render with seed `20261034` verified the correct local weight hash, CLIP skip node, effective quality-tagged prompt, and Euler ancestral sampler in the ComfyUI workflow receipt. The output and receipts are under `deliverables/pictora_image_editor/studio_jobs/20261031T181826Z-e198fffa/`.

### Live inpaint and reference-control proofs

The base candidate was used with a painted mask and the dedicated DreamShaper inpaint checkpoint. After two indistinct revisions, render `20261031T181903Z-30285a03` inserted a distinct engraved gold medallion in the selected wall area. The generated image and full receipts remain unapproved candidates under `deliverables/pictora_image_editor/studio_jobs/20261031T181903Z-30285a03/`.

Render `20261031T182357Z-f3af8bc0` exercised pose conditioning, FaceID Plus V2 appearance guidance, and IP-Adapter Plus composition guidance together with compatible SD1.5 anime weights. Its receipt includes source, pose, identity, and composition hashes plus the exact local ControlNet, FaceID, IP-Adapter Plus, and CLIP Vision file sizes and SHA-256 hashes. Exact identity is not guaranteed. The image and receipts are under `deliverables/pictora_image_editor/studio_jobs/20261031T182357Z-f3af8bc0/`; release remains held.

The same output was then sent back through the live studio as an inpainting source with an explicit painted mask and the dedicated `DreamShaper_8_INPAINTING.inpainting.safetensors` checkpoint. Initial proof jobs (`20261031T181147Z-4b02e043` and `20261031T181246Z-bbc636b0`) preserved source and mask custody but rendered an indistinct small motif. A larger, clearer painted region and stronger prompt produced job `20261031T181903Z-30285a03`, with a distinct gold wall medallion. The separate result image, original inputs, model/runtime provenance, and render receipts are under `deliverables/pictora_image_editor/studio_jobs/`; the result remains an unapproved candidate and release-held.

The current local ComfyUI route was exercised again on 2026-10-31 with newly generated, synthetic source and mask inputs. Job `20261031T185825Z-39c726a4` completed through the dedicated inpaint checkpoint at 512×512; its receipt verifies the checkpoint against the pinned SHA-256. Pixel comparison found no changed pixels outside the painted mask expanded by the configured 8-pixel growth plus 16-pixel blend margin. The output and its input custody record are under `deliverables/pictora_image_editor/studio_jobs/20261031T185825Z-39c726a4/`.

Identity guidance also completed through the live API using the DIO virtual-guide asset as a reference. Job `20261031T185955Z-2d8025a5` records FaceID Plus V2, its input hash, the 0.82 strength, and the compatible EpicRealism checkpoint hash. Job `20261031T190035Z-0c63d130` completed a combined pose-and-identity render; its receipt records `OpenposePreprocessor`, `control_v11p_sd15_openpose.pth`, FaceID Plus V2, and the local SHA-256 of the control weights and CLIP Vision file. Both renders are review candidates; FaceID guides resemblance and does not guarantee identity, and the selected checkpoint's commercial-use terms remain uncleared.

## Photo-edit controls

- Exposure, contrast, saturation, tint, sharpness, crop, and median denoise run locally with Pillow.
- Clone stamp copies nearby image texture into a painted mask. This is a basic retouch brush, not content-aware healing.
- Background removal runs through the installed local ComfyUI `easy imageRemBg` node and preserves alpha when the installed graph supports it.
- Upscaling uses the locally installed RealESRGAN x4 model, then scales to the requested 2x or 4x output dimensions.
- Inputs are limited to PNG, JPEG, and WebP; the upload limit is 20 MB and processing rejects images above 80 megapixels.

## Run locally

The enabled `dio-pictora-studio.service` serves the master dashboard on port `42153`; the standalone edit pilot defaults to port `8765` when launched directly:

```bash
.venv/bin/python scripts/serve_pictora_image_editor.py
```

Both services bind to loopback. ComfyUI must be running for model-backed work. `/api/studio/capabilities` reports checkpoint and reference-control compatibility; `/api/capabilities` reports photo-edit operations.

## Product boundary

Every output is a candidate requiring human review. Generated or enhanced details can be wrong. Model and asset commercial rights have not been validated, so campaign and edited outputs remain unpublished and release-held.

See [live wiring evidence](../deliverables/pictora_image_editor/live_wiring_evidence/index.html) and its JSON manifest for actual generated previews and operation receipts.

## ATLAS exploration map

The live dashboard exposes 22 analogical ATLAS domain candidates: 17 shared with Sonoris and 5 Pictora-specific (`D403`, `D502`, `D716`, `D1405`, `D1715`). The union across both organs is 23 domains. ATLAS reports zero execution-grade signatures for Pictora; these links are exploration hypotheses, not capability proof, market evidence, or release authority.
