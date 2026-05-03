"""custom-8 (Asset Browser) — gallery writer.

This module is the per-image hook called by `private_logger.log()` after each
image is saved. Its sole responsibility is to keep the JSON manifests + thumbs
+ DZI tiles in `outputs/` in sync with what was generated, so the standalone
HTML SPA at `outputs/index.html` (built in M2/M3) can browse them.

**Toggle is non-negotiable.** When `asset_browser.enabled = False` in
config.txt (the default), every public function here returns immediately with
<1 µs overhead — a single dict access — so users on old hardware never see a
slowdown caused by this feature being installed.

This is **M1 (Foundation only)**. No real work happens yet — just the toggle
plumbing and a safety net so the rest of Fooocus keeps generating images
exactly as before. M2 will add: thumbnail generation, manifest writes, DZI
tiling, asset bootstrap. M3 adds the SPA frontend.
"""
import modules.config


def _enabled() -> bool:
    """Hot-path check. Inlined would be nicer but a function call is still
    sub-microsecond and lets us evolve the check without touching callers.
    """
    return modules.config.asset_browser_enabled()


def on_image_logged(image_path, metadata, task=None) -> None:
    """Called by `modules/private_logger.py::log()` right before it returns.

    Wrapped in try/except by the caller so any bug here can never break image
    generation. M1: returns immediately if the feature is disabled.
    """
    if not _enabled():
        return
    # M2 TODO: append to outputs/<DATE>/manifest.json, generate thumb,
    # generate DZI tiles if size > 4MP, refresh outputs/_index/days.json.
    # For now we just print so the user sees the hook fire when they enable it.
    print(f'[asset-browser] (M1 stub) on_image_logged: {image_path}')


def reindex_outputs() -> tuple:
    """User-triggered: rebuild manifests for ALL existing images in outputs/.

    Called from the 🔄 Reindex button in the UI accordion. M1: stub.
    Returns (ok, message).
    """
    if not _enabled():
        return False, 'Asset Browser is disabled. Enable it in Advanced first.'
    return True, 'M1 stub — outputs reindex will run in M2.'


def ensure_gallery_assets() -> bool:
    """Copy the SPA template + PhotoSwipe assets to outputs/_assets/ + outputs/index.html
    if they are missing. Idempotent. M1: stub.
    """
    if not _enabled():
        return False
    # M2 TODO: copy from gallery_template/ to outputs/.
    return False
