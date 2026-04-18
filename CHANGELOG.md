# Changelog — Fooocus2025 (mikecastrodemaria fork)

This fork is based on [lllyasviel/Fooocus](https://github.com/lllyasviel/Fooocus) **v2.5.5**.
Only fork-specific changes are listed here — upstream history is available via `git log`.

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
