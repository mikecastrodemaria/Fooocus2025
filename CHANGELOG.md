# Changelog — Fooocus2025 (mikecastrodemaria fork)

This fork is based on [lllyasviel/Fooocus](https://github.com/lllyasviel/Fooocus) **v2.5.5**.
Only fork-specific changes are listed here — upstream history is available via `git log`.

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
