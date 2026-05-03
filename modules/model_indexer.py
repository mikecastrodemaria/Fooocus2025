"""custom-8 (Asset Browser) — model indexer.

Walks `models/loras/`, `models/checkpoints/` (multiple folders), and
`models/embeddings/` to build the JSON manifests consumed by the SPA tabs:

- `outputs/_index/loras.json`
- `outputs/_index/checkpoints.json`
- `outputs/_index/embeddings.json`

Re-uses existing helpers:
- `modules.lora_metadata.get_lora_triggers_from_file` / `get_embedding_triggers_from_file`
- `modules.civitai_api.fetch_model_triggers_combined` (cached)
- `modules.civitai_api.fetch_civitai_settings` (cached)

so this module never makes a fresh CivitAI HTTP call when the cache is warm.

**M1 (Foundation only):** stubs that respect the toggle. No real scanning yet.
M2 implements `scan_loras()` / `scan_checkpoints()` / `scan_embeddings()`.
"""
import modules.config


def _enabled() -> bool:
    return modules.config.asset_browser_enabled()


def _index_on_boot_enabled() -> bool:
    return _enabled() and bool(
        modules.config.asset_browser_setting('index_models_on_boot', True)
    )


def scan_all_and_write() -> tuple:
    """Top-level entrypoint. Called once at startup (in a daemon thread) and
    again when the user clicks 🔄 Reindex everything. Idempotent.

    Returns (ok, summary_dict).
    """
    if not _enabled():
        return False, {'reason': 'asset_browser disabled'}
    # M2 TODO:
    #   loras = scan_loras()
    #   checkpoints = scan_checkpoints()
    #   embeddings = scan_embeddings()
    #   write_manifest('loras.json', loras)
    #   write_manifest('checkpoints.json', checkpoints)
    #   write_manifest('embeddings.json', embeddings)
    print('[asset-browser] (M1 stub) scan_all_and_write: would scan loras/checkpoints/embeddings here.')
    return True, {'loras': 0, 'checkpoints': 0, 'embeddings': 0, 'note': 'M1 stub'}


def maybe_start_boot_scan() -> None:
    """Called from launch.py just before webui import. Spawns the scan in a
    daemon thread only if the toggle + sub-toggle allow it. Costs nothing
    when disabled.
    """
    if not _index_on_boot_enabled():
        return
    import threading
    threading.Thread(
        target=scan_all_and_write,
        name='asset-browser-bootscan',
        daemon=True,
    ).start()
    print('[asset-browser] boot scan thread started (M1 stub — will do real work in M2).')
