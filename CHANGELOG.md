# Changelog — Fooocus2025 (mikecastrodemaria fork)

This fork is based on [lllyasviel/Fooocus](https://github.com/lllyasviel/Fooocus) **v2.5.5**.
Only fork-specific changes are listed here — upstream history is available via `git log`.

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
