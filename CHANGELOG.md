# Changelog — Fooocus2025 (mikecastrodemaria fork)

This fork is based on [lllyasviel/Fooocus](https://github.com/lllyasviel/Fooocus) **v2.5.5**.
Only fork-specific changes are listed here — upstream history is available via `git log`.

## [version bump] — 2026-05-02
### Changed
- **Version bumped from `2.5.5` to `2026.1.0`** (`fooocus_version.py`). The fork has diverged enough from upstream v2.5.5 that the inherited version string was confusing users into thinking the fork was unmaintained. Switched to CalVer (`YYYY.MINOR.PATCH`). PNG metadata `Version` field and the WebUI title both now read `Fooocus v2026.1.0`.

## [custom-7] — 2026-05-02
### Added
- **Aspect Ratios switched from Radio block to Dropdown**, with **`Custom`** as the first entry. Selecting any preset behaves exactly like before; selecting `Custom` reveals the Custom Resolution panel and routes generation through it. Choices use `(display_label, value)` tuples so the dropdown shows clean text (`1152×896 ∣ 9:7`) while the value passed to downstream code keeps the original HTML-formatted form for back-compat with `meta_parser` and preset round-trip.
- **Custom Resolution panel** under the Aspect Ratios accordion (revealed by selecting `Custom` in the dropdown). Lets users pick any aspect ratio + size on the fly without editing `config.txt` or restarting Fooocus.
  - **Toggle**: driven by the dropdown — selecting any preset other than `Custom` hides the panel and disables the override (visible-only checkbox is gone; an internal hidden flag still flows to the worker).
  - **Inputs**: ratio `W`/`H` (integers) + a **mode selector** (`Max edge` / `~1 MP target` / `Min edge`) + a **size slider** (512–2048, step 64).
  - **Quick ratio chips**: `1:1` `3:2` `4:3` `16:9` `21:9` `√2 (A4)` populate the ratio fields in one click. **🔄 Swap** flips W ↔ H for landscape/portrait.
  - **Live computed display**: `→ 1344 × 768 · 1.03 MP · 7:4` updates on every input change. Warns when total pixels fall below 0.25 MP or above 2 MP (non-blocking).
  - **Auto-snap to /64**: results are always rounded to multiples of 64 on both axes (SDXL hard requirement).
  - **💾 Save as preset entry**: one-click button that appends the computed `W*H` to `available_aspect_ratios` in `config.txt`, so the resolution shows up in the standard radio block on next restart.
- **Preset round-trip**: `save_preset_to_file` now writes a `custom_resolution` block (`{enabled, ratio_w, ratio_h, mode, size}`) into preset JSONs. Old presets without the block default to `enabled: false` (full back-compat). The block is invisible to vanilla Fooocus (not in `possible_preset_keys` allowlist), so cross-loading is safe.
### Added — utility
- New helper `compute_custom_wh(ratio_w, ratio_h, mode, size)` in `modules/util.py` — single source of truth for the snapping math, used by both the WebUI display and the worker override.
### Changed
- `modules/async_worker.py::AsyncTask` consumes 5 new flags after `use_aspect_for_vary`. When `custom_res_enabled` is true (or the dropdown sentinel value `'Custom'` arrives, as a safety net), the computed `W×H` is stuffed back into `self.aspect_ratios_selection` so the existing parsers (main path at line 1135, Vary path at line 458) pick up the override transparently — no downstream changes needed. Vary + custom-7 + custom-6 stack: selecting `Custom` plus turning on `Use Aspect for Vary` forces Vary outputs to the custom W×H.

### Fixed
- **Embeddings: duplicate trigger words from Windows-suffixed filenames.** When an embedding file like `neg_realism512 (1).safetensors` was selected, clicking *Prompt* / *Negative* inserted both `(embedding:neg_realism512 (1):1.0)` AND a redundant `neg_realism512` extra trigger (the canonical name returned by CivitAI, which differed from the local stem only by the Windows-duplicate ` (N)` suffix). Fixed by normalising stems and CivitAI candidates with `\s*\(\d+\)\s*$` stripped before the dedup check (`webui.py::_normalize_emb_token`). Now only the embedding tag itself is inserted; the redundant canonical name is correctly recognised as a duplicate of the local stem.

## [custom-6] — 2026-04-18
### Added
- **"Use selected Aspect Ratio for Vary" checkbox** under the Aspect Ratios accordion in the Advanced tab. When enabled, Vary (Subtle) and Vary (Strong) resize the input image to the selected aspect ratio's dimensions (centre-crop, `resize_mode=1`) before encoding, instead of following the input image's native shape-ceil. Unchecked = original upstream behavior. Does not affect Upscale (which keeps its fixed 1.5x/2x factor).

### Changed
- `modules/async_worker.py::AsyncTask` now consumes a new `use_aspect_for_vary` flag. The control is appended to `ctrls` right after `mixing_image_prompt_and_inpaint` and popped in the matching order.

## [custom-5] — 2026-04-18
### Added
- **Checkpoint trigger words** in the CivitAI panel. The fetch result now also surfaces the checkpoint's `trainedWords` (score_9 for Pony, NSFW-style activation tokens for some merges, etc.) in a highlighted block above the settings table. A **📋 Copy checkpoint triggers to prompt** button appears under the panel when triggers are available.
- **💾 Save CivitAI consensus as preset** — button under the CivitAI Apply control that writes a new preset `.json` combining:
  - The current base model, refiner, styles, aspect ratio, prompts, LoRAs, and embeddings.
  - The CivitAI consensus sampler / scheduler / CFG / steps / clip-skip, overriding whatever was in the UI.
  - Default preset name auto-suggested as `civitai_<ModelName>`; editable.
  - Calls the existing `save_preset_to_file()` so new presets appear in the preset dropdown and can be re-loaded normally.

## [custom-4] — 2026-04-18
### Added
- **Textual Inversion / Embeddings panel** in the Advanced tab (5 slots, matching the LoRA count).
  - Each slot: dropdown of available embeddings from `models/embeddings/`, weight slider, enable checkbox.
  - Mirrors the LoRA trigger-words UX: activation token is auto-detected (filename + any extra tokens from safetensors metadata or CivitAI), shown in a read-only field below the row.
  - **📋 To prompt** / **📋 To negative** buttons per slot insert `(embedding:<name>:<weight>)` into the corresponding textbox.
  - **Insert ALL active to prompt / negative** buttons below the rows insert every enabled embedding's activation token at once.
### Changed
- **Negative prompt moved** to the main prompt area, directly below the positive prompt. Previously buried in the Advanced tab; now visible without enabling Advanced. Styled to match the positive prompt (shared CSS on `#positive_prompt`, `#negative_prompt` — same rounded corners and background). Small spacer between the two textboxes.
- **Preset Manager moved** out of the Developer → Debug Tools tab and into the Advanced → main aspect section (where the negative prompt used to be). Wrapped in its own `gr.Accordion` labelled "💾 Preset Manager" (collapsed by default).
- **Preset Manager now saves embeddings** alongside LoRAs. Saved as `default_embeddings` in the preset JSON with the same `[enabled, name, weight]` shape as `default_loras`. (Loading embeddings from a preset on preset-switch is not yet wired — follow-up.)
- **Collapsible sections** in the Advanced tab — CivitAI, LoRA, and Embeddings are now `gr.Accordion` panels. LoRA starts open (most-used), CivitAI and Embeddings start collapsed to reduce visual clutter.
### Added (continued)
- **Wildcards panel** in the Advanced tab (below Embeddings) with full editor:
  - Dropdown of all `.txt` files in the wildcards folder.
  - **Editable scrollable text area** with the file's full contents (not just a preview — edit in place).
  - **💾 Save** writes the edited contents back to the selected file.
  - **➕ Create new** — type a name (letters/digits/_/- only) and save the current contents as a new `.txt` in the wildcards folder; name is sanitised and collisions are rejected.
  - **📋 Insert __token__ to prompt** inserts the `__filename__` token into the positive prompt, deduped.
  - Filesystem changes trigger `update_files()` so the dropdown refreshes immediately.
- **⚠️ Restart UI button** next to Refresh All Files — re-execs the Python process (`os.execv`) so edits to `config.txt`, custom Python modules, or external model additions are picked up cleanly. User must refresh the browser tab after ~30 s (SDXL reload on RTX 5090). Clearly labelled as secondary to "Refresh All Files", which already handles new-file discovery without restart.
### Refactored
- Generalised `fetch_lora_triggers_combined` → `fetch_model_triggers_combined(filename, paths, kind, api_key)` in `modules/civitai_api.py`; `kind='lora'` and `kind='embedding'` share the same pipeline with separate cache namespaces (`<name>.lora.civitai.json` / `<name>.embedding.civitai.json`). Legacy `fetch_lora_triggers_combined` kept as a shim for back-compat.
- `modules/lora_metadata.py` extended with `extract_embedding_triggers_from_metadata()` and `get_embedding_triggers_from_file()` — for embeddings the filename stem is always the primary trigger; extra tokens from `sd_embedding_tokens` / `modelspec.trigger_phrase` are appended when present.
- `modules/config.py`: new `embedding_filenames` list, populated by `update_files()` scanning `path_embeddings` for `.safetensors`/`.pt`/`.bin`.

## [custom-3] — 2026-04-18
### Added
- **LoRA trigger words — local metadata + CivitAI, merged**
  - Each LoRA slot now shows a read-only field with the LoRA's trigger words, auto-fetched on selection.
  - **Two sources, combined for coverage:**
    1. **Local safetensors metadata** (new `modules/lora_metadata.py`) — reads the `__metadata__` header of the `.safetensors` file to extract `modelspec.trigger_phrase`, top tags from `ss_tag_frequency` (filtered by frequency), and `ss_output_name`. Instant, offline, works for LoRAs never uploaded to CivitAI.
    2. **CivitAI `trainedWords`** — hash-based lookup as before, cached to disk per LoRA.
  - Merged list is deduped, local-first (ground truth from training), CivitAI-only extras appended.
  - **📋 Copy to prompt** button per slot appends that LoRA's triggers to the positive prompt, de-duplicated against what's already there.
  - **📋 Copy ALL active LoRA triggers to prompt** button below the LoRA rows gathers triggers from every *enabled* LoRA at once.
  - New helpers: `fetch_lora_triggers()`, `fetch_lora_triggers_combined()`, `format_lora_triggers_display()` in `modules/civitai_api.py`; `read_safetensors_metadata()`, `extract_triggers_from_metadata()`, `get_lora_triggers_from_file()` in `modules/lora_metadata.py`. Miss results are cached so LoRAs not on CivitAI don't keep hitting the API.

## [custom-2] — 2026-04-11
### Added
- **CivitAI Model Settings integration**
  - New module `modules/civitai_api.py` — CivitAI client with response caching.
  - Fetches community-recommended generation settings (sampler, CFG, steps, clip skip) for the currently selected model, aggregated from top-rated images on CivitAI.
  - New panel in the UI shows the consensus analysis.
  - **Apply** button injects recommended settings into the Fooocus UI.
  - CivitAI API key configurable via UI; persisted to `config.txt`.
  - API responses cached locally in `civitai_cache/` (git-ignored).

## [custom-1] — 2026-04-11
### Added
- **Save Preset button** in the Advanced → Developer tab.
  - Located in Developer Debug Tools, after the Metadata Scheme.
  - Saves the current Advanced settings as a new preset `.json`, or overwrites an existing preset, directly from the UI.

## Base
- Upstream Fooocus **v2.5.5** (commit `ae05379`).
