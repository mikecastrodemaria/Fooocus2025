"""custom-8 (Asset Browser) — model indexer.

Walks `models/loras/`, `models/checkpoints/` (multiple paths), and
`models/embeddings/` to build the JSON manifests consumed by the SPA tabs:

- `outputs/_index/loras.json`
- `outputs/_index/checkpoints.json`
- `outputs/_index/embeddings.json`

Re-uses existing helpers:
- `modules.lora_metadata.get_lora_triggers_from_file` / `get_embedding_triggers_from_file`
- `modules.civitai_api.load_cached_triggers` (cache-only, NO API calls)
- `modules.civitai_api.load_cached_settings` (cache-only, NO API calls)

Designed for hundreds of models on a fast SSD: every path is touched at
most once, no network, thumbnails are written under `outputs/_previews/` and
re-used across reindexes (invalidation by source mtime).

**M2b ships the real implementation.** Toggle still respected.
"""
import datetime
import hashlib
import json
import os
import threading

import modules.config
from modules.util import get_file_from_folder_list


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

INDEX_DIR_NAME = '_index'
PREVIEWS_DIR_NAME = '_previews'
PLACEHOLDER_DIR_NAME = 'placeholders'


def _thumb_size() -> int:
    return int(modules.config.asset_browser_setting('thumbnail_size', 256))


def _thumb_quality() -> int:
    return int(modules.config.asset_browser_setting('thumbnail_quality', 85))


def _placeholder_label_max() -> int:
    return int(modules.config.asset_browser_setting('placeholder_label_max', 24))

# Lookup order for sidecar previews (A1111 / ComfyUI compatible).
PREVIEW_SUFFIXES = [
    '.preview.png', '.preview.jpg', '.preview.jpeg',
    '.png', '.jpg', '.jpeg',
    '_preview.png',
]

# Heuristic for negative-style embeddings.
NEGATIVE_PREFIXES = ('neg', 'bad', 'unaesthetic', 'fast_neg', 'fast-neg', 'easyneg')

_lock = threading.Lock()


# --------------------------------------------------------------------------
# Toggle helpers
# --------------------------------------------------------------------------

def _enabled() -> bool:
    return modules.config.asset_browser_enabled()


def _index_on_boot_enabled() -> bool:
    return _enabled() and bool(
        modules.config.asset_browser_setting('index_models_on_boot', True)
    )


def _outputs_root() -> str:
    return modules.config.path_outputs


def _index_dir() -> str:
    return os.path.join(_outputs_root(), INDEX_DIR_NAME)


def _previews_dir(kind: str) -> str:
    """outputs/_previews/<kind>/  — thumbnails of sidecar previews + placeholders."""
    return os.path.join(_outputs_root(), PREVIEWS_DIR_NAME, kind)


# --------------------------------------------------------------------------
# Preview discovery + placeholder generation
# --------------------------------------------------------------------------

def _find_sidecar_preview(model_filepath: str) -> str:
    """Return the first matching sidecar preview path next to the model file, or ''.

    Tries the 5 conventional suffixes in order.
    """
    if not model_filepath:
        return ''
    base, _ = os.path.splitext(model_filepath)
    for suffix in PREVIEW_SUFFIXES:
        candidate = base + suffix
        if os.path.isfile(candidate):
            return candidate
    return ''


def _hash_id(s: str, length: int = 12) -> str:
    """Stable short hash for cache keys."""
    return hashlib.sha1(s.encode('utf-8', errors='replace')).hexdigest()[:length]


def _make_placeholder_png(filename_for_label: str, dest_path: str) -> bool:
    """Generate a hash-derived gradient placeholder PNG with the filename overlay.
    Idempotent: returns True if dest already exists (or just got written).
    """
    try:
        if os.path.isfile(dest_path):
            return True
        from PIL import Image, ImageDraw, ImageFont

        h = hashlib.sha1(filename_for_label.encode('utf-8', errors='replace')).hexdigest()
        # Two colors derived from the hash.
        c1 = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        c2 = (int(h[6:8], 16), int(h[8:10], 16), int(h[10:12], 16))

        size = _thumb_size()
        im = Image.new('RGB', (size, size), c1)
        # Vertical linear gradient from c1 to c2.
        for y in range(size):
            t = y / max(1, size - 1)
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            for x in range(size):
                im.putpixel((x, y), (r, g, b))

        draw = ImageDraw.Draw(im)
        # Filename overlay (basename, no extension) — broken into chunks if too long.
        label = os.path.splitext(os.path.basename(filename_for_label))[0]
        max_len = _placeholder_label_max()
        if len(label) > max_len:
            head = max(4, (max_len - 1) // 2)
            tail = max(4, max_len - head - 1)
            label = label[:head] + '…' + label[-tail:]
        try:
            font = ImageFont.truetype('arial.ttf', 14)
        except Exception:
            font = ImageFont.load_default()
        # Center the text.
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = (size // 2, 14)
        tx = max(4, (size - tw) // 2)
        ty = size - th - 10
        draw.rectangle((0, ty - 4, size, ty + th + 4), fill=(0, 0, 0, 160))
        draw.text((tx, ty), label, fill=(255, 255, 255), font=font)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        im.save(dest_path, 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f'[asset-browser] placeholder gen failed for {filename_for_label}: {e}')
        return False


def _make_preview_thumb(source_path: str, dest_path: str) -> bool:
    """256x256 JPEG centre-crop thumbnail. Cached by source mtime."""
    try:
        if (os.path.isfile(dest_path)
                and os.path.getmtime(dest_path) >= os.path.getmtime(source_path)):
            return True
        from PIL import Image
        with Image.open(source_path) as im:
            im = im.convert('RGB')
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side))
            sz = _thumb_size()
            im = im.resize((sz, sz), Image.LANCZOS)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            im.save(dest_path, 'JPEG', quality=_thumb_quality(), optimize=True)
        return True
    except Exception as e:
        print(f'[asset-browser] preview thumb failed for {source_path}: {e}')
        return False


def _copy_full_preview(source_path: str, dest_path: str) -> bool:
    """Copy the original sidecar preview to outputs/_previews/<kind>/<hash>_full.<ext>
    so the SPA lightbox can show it at native resolution (instead of the 256x256
    thumbnail). Cached by source mtime — only re-copies if source is newer.
    """
    try:
        if (os.path.isfile(dest_path)
                and os.path.getmtime(dest_path) >= os.path.getmtime(source_path)):
            return True
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        import shutil
        shutil.copy2(source_path, dest_path)
        return True
    except Exception as e:
        print(f'[asset-browser] full-preview copy failed for {source_path}: {e}')
        return False


def _resolve_preview(model_rel_filename: str, model_full_path: str, kind: str) -> tuple:
    """Resolve sidecar preview OR placeholder, cache the thumbnail (always) AND
    the full-resolution copy (when sidecar exists), return
    (thumb_rel_path, full_rel_path, preview_kind).

    All paths are relative to outputs/, so the SPA can use them directly.
    preview_kind is 'sidecar' | 'placeholder'.

    For sidecars: full = copy of the original sidecar at native resolution.
    For placeholders: full = the 256x256 placeholder PNG itself.
    """
    cache_id = _hash_id(model_rel_filename)
    thumb_dir = _previews_dir(kind)
    thumb_path = os.path.join(thumb_dir, f'{cache_id}.jpg')
    rel_thumb = os.path.relpath(thumb_path, _outputs_root()).replace(os.sep, '/')

    sidecar = _find_sidecar_preview(model_full_path)
    if sidecar and _make_preview_thumb(sidecar, thumb_path):
        # Cache the full sidecar with its original extension (PNG/JPG/etc).
        ext = os.path.splitext(sidecar)[1].lower() or '.png'
        full_path = os.path.join(thumb_dir, f'{cache_id}_full{ext}')
        if _copy_full_preview(sidecar, full_path):
            rel_full = os.path.relpath(full_path, _outputs_root()).replace(os.sep, '/')
        else:
            rel_full = rel_thumb   # fallback to thumb if copy failed
        return rel_thumb, rel_full, 'sidecar'

    # Placeholder route — same image for thumb + full (placeholder is already 256x256).
    placeholder_dir = os.path.join(_outputs_root(), PREVIEWS_DIR_NAME, PLACEHOLDER_DIR_NAME)
    placeholder_png = os.path.join(placeholder_dir, f'{cache_id}.png')
    if _make_placeholder_png(model_rel_filename, placeholder_png):
        if _make_preview_thumb(placeholder_png, thumb_path):
            rel_full = os.path.relpath(placeholder_png, _outputs_root()).replace(os.sep, '/')
            return rel_thumb, rel_full, 'placeholder'
    # Last resort: empty preview.
    return '', '', 'missing'


# --------------------------------------------------------------------------
# Item builders (one per kind)
# --------------------------------------------------------------------------

def _stat_file(path: str) -> dict:
    try:
        st = os.stat(path)
        return {
            'size_bytes': int(st.st_size),
            'modified_at': datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds'),
        }
    except Exception:
        return {'size_bytes': None, 'modified_at': None}


def _read_cached_triggers(filename: str, kind: str) -> list:
    """Return triggers from local metadata + cached CivitAI (no API). Deduped, local first."""
    try:
        from modules import lora_metadata
        if kind == 'embedding':
            local = lora_metadata.get_embedding_triggers_from_file(filename, [modules.config.path_embeddings])
        else:
            local = lora_metadata.get_lora_triggers_from_file(filename, modules.config.paths_loras)
    except Exception:
        local = {}

    try:
        from modules import civitai_api
        civitai_kind = 'lora' if kind == 'lora' else ('embedding' if kind == 'embedding' else None)
        cached = civitai_api.load_cached_triggers(filename, kind=civitai_kind) if civitai_kind else None
    except Exception:
        cached = None

    merged = []
    seen = set()
    for w in (local or {}).get('trainedWords', []) or []:
        wl = str(w).strip().lower()
        if wl and wl not in seen:
            merged.append(w); seen.add(wl)
    for w in (cached or {}).get('trainedWords', []) or []:
        wl = str(w).strip().lower()
        if wl and wl not in seen:
            merged.append(w); seen.add(wl)
    return merged


def _civitai_url_from_cache(filename: str, kind: str) -> str:
    """Best-effort CivitAI URL from cached metadata. Empty if unknown."""
    try:
        from modules import civitai_api
        if kind == 'checkpoint':
            cached = civitai_api.load_cached_settings(filename)
        else:
            cached = civitai_api.load_cached_triggers(filename, kind=kind)
        if not cached:
            return ''
        # Several possible shapes — try a few keys.
        info = cached.get('model_info') or cached.get('model') or cached
        model_id = info.get('modelId') or info.get('id') or info.get('model_id')
        if model_id:
            return f'https://civitai.com/models/{model_id}'
    except Exception:
        pass
    return ''


def _checkpoint_consensus_from_cache(filename: str) -> dict:
    """Pull sampler/cfg/steps/clip_skip from civitai_cache if present. Empty otherwise."""
    try:
        from modules import civitai_api
        cached = civitai_api.load_cached_settings(filename)
    except Exception:
        cached = None
    if not cached or 'settings' not in cached:
        return {}
    s = cached.get('settings', {}) or {}
    out = {}
    for k_civ, k_out in [('sampler', 'sampler'), ('cfg', 'cfg'), ('steps', 'steps'),
                          ('clip_skip', 'clip_skip'), ('top_resolution', 'top_resolution')]:
        v = s.get(k_civ)
        if v not in (None, ''):
            out[k_out] = v
    base = (cached.get('model_info') or {}).get('baseModel')
    if base:
        out['base_model'] = base
    return out


def _build_lora_item(rel_filename: str, full_path: str) -> dict:
    preview, preview_full, preview_kind = _resolve_preview(rel_filename, full_path, 'loras')
    item = {
        'id': _hash_id(rel_filename, 16),
        'filename': os.path.basename(rel_filename),
        'rel_path': rel_filename.replace(os.sep, '/'),
        'subfolder': os.path.dirname(rel_filename).replace(os.sep, '/') or '.',
        'preview': preview,
        'preview_full': preview_full,
        'preview_kind': preview_kind,
        'trigger_words': _read_cached_triggers(rel_filename, 'lora'),
        'civitai_url': _civitai_url_from_cache(rel_filename, 'lora'),
    }
    item.update(_stat_file(full_path))
    return item


def _build_checkpoint_item(rel_filename: str, full_path: str) -> dict:
    preview, preview_full, preview_kind = _resolve_preview(rel_filename, full_path, 'checkpoints')
    consensus = _checkpoint_consensus_from_cache(rel_filename)
    item = {
        'id': _hash_id(rel_filename, 16),
        'filename': os.path.basename(rel_filename),
        'rel_path': rel_filename.replace(os.sep, '/'),
        'subfolder': os.path.dirname(rel_filename).replace(os.sep, '/') or '.',
        'preview': preview,
        'preview_full': preview_full,
        'preview_kind': preview_kind,
        'base_model': consensus.pop('base_model', None),
        'civitai_consensus': consensus or None,
        'civitai_url': _civitai_url_from_cache(rel_filename, 'checkpoint'),
    }
    item.update(_stat_file(full_path))
    return item


def _build_embedding_item(rel_filename: str, full_path: str) -> dict:
    preview, preview_full, preview_kind = _resolve_preview(rel_filename, full_path, 'embeddings')
    base = os.path.splitext(os.path.basename(rel_filename))[0].lower()
    is_negative_hint = any(base.startswith(p) for p in NEGATIVE_PREFIXES)
    item = {
        'id': _hash_id(rel_filename, 16),
        'filename': os.path.basename(rel_filename),
        'rel_path': rel_filename.replace(os.sep, '/'),
        'subfolder': os.path.dirname(rel_filename).replace(os.sep, '/') or '.',
        'preview': preview,
        'preview_full': preview_full,
        'preview_kind': preview_kind,
        'trigger': os.path.splitext(os.path.basename(rel_filename))[0],
        'is_negative_hint': is_negative_hint,
        'trigger_words': _read_cached_triggers(rel_filename, 'embedding'),
        'civitai_url': _civitai_url_from_cache(rel_filename, 'embedding'),
    }
    item.update(_stat_file(full_path))
    return item


# --------------------------------------------------------------------------
# Scanners
# --------------------------------------------------------------------------

def _resolve_full_path(rel_filename: str, paths) -> str:
    """Wrapper around get_file_from_folder_list that swallows misses."""
    try:
        full = get_file_from_folder_list(rel_filename, paths if isinstance(paths, list) else [paths])
        if full and os.path.isfile(full):
            return full
    except Exception:
        pass
    return ''


def scan_loras() -> list:
    items = []
    for filename in (modules.config.lora_filenames or []):
        full = _resolve_full_path(filename, modules.config.paths_loras)
        if not full:
            continue
        try:
            items.append(_build_lora_item(filename, full))
        except Exception as e:
            print(f'[asset-browser] scan_loras item failed for {filename}: {e}')
    return items


def scan_checkpoints() -> list:
    items = []
    for filename in (modules.config.model_filenames or []):
        full = _resolve_full_path(filename, modules.config.paths_checkpoints)
        if not full:
            continue
        try:
            items.append(_build_checkpoint_item(filename, full))
        except Exception as e:
            print(f'[asset-browser] scan_checkpoints item failed for {filename}: {e}')
    return items


def scan_embeddings() -> list:
    items = []
    for filename in (modules.config.embedding_filenames or []):
        full = _resolve_full_path(filename, [modules.config.path_embeddings])
        if not full:
            continue
        try:
            items.append(_build_embedding_item(filename, full))
        except Exception as e:
            print(f'[asset-browser] scan_embeddings item failed for {filename}: {e}')
    return items


# --------------------------------------------------------------------------
# Top-level orchestration
# --------------------------------------------------------------------------

def _write_manifest(name: str, items: list) -> None:
    os.makedirs(_index_dir(), exist_ok=True)
    payload = {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'count': len(items),
        'items': items,
    }
    path = os.path.join(_index_dir(), name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def scan_all_and_write() -> tuple:
    """Top-level entrypoint. Idempotent. Returns (ok, summary_dict)."""
    if not _enabled():
        return False, {'reason': 'asset_browser disabled'}
    summary = {}
    try:
        with _lock:
            loras = scan_loras()
            _write_manifest('loras.json', loras)
            summary['loras'] = len(loras)

            checkpoints = scan_checkpoints()
            _write_manifest('checkpoints.json', checkpoints)
            summary['checkpoints'] = len(checkpoints)

            embeddings = scan_embeddings()
            _write_manifest('embeddings.json', embeddings)
            summary['embeddings'] = len(embeddings)
        print(f'[asset-browser] scan complete: {summary}')
        return True, summary
    except Exception as e:
        print(f'[asset-browser] scan_all_and_write failed: {e}')
        summary['error'] = str(e)
        return False, summary


def maybe_start_boot_scan() -> None:
    if not _index_on_boot_enabled():
        return
    threading.Thread(
        target=scan_all_and_write,
        name='asset-browser-bootscan',
        daemon=True,
    ).start()
    print('[asset-browser] boot scan thread started.')
