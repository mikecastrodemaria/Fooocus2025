"""custom-8 (Asset Browser) — gallery writer.

Per-image hook called by `private_logger.log()` after each image is saved.
Keeps the JSON manifests + thumbnails in `outputs/` in sync so the standalone
HTML SPA at `outputs/index.html` can browse them.

**Toggle is non-negotiable.** When `asset_browser.enabled = False` (default),
every public function returns immediately with <1 µs overhead.

M2a (current): outputs gallery — thumbnails + manifest + days.json.
M2b (next): model_indexer for LoRAs/Checkpoints/Embeddings.
M3: PhotoSwipe + Dynamic Caption + Deep Zoom in the SPA.
"""
import datetime
import json
import os
import shutil
import threading

import modules.config

# --------------------------------------------------------------------------
# Constants & paths
# --------------------------------------------------------------------------

THUMBNAIL_SUFFIX = '_thumb.jpg'
TEMPLATE_DIR_NAME = 'gallery_template'
INDEX_DIR_NAME = '_index'
ASSETS_DIR_NAME = '_assets'
DAYS_INDEX_FILE = 'days.json'
MANIFEST_FILE = 'manifest.json'


def _thumb_size() -> int:
    return int(modules.config.asset_browser_setting('thumbnail_size', 256))


def _thumb_quality() -> int:
    return int(modules.config.asset_browser_setting('thumbnail_quality', 85))

# Process-wide lock — manifests are read-modify-write JSON files; without a
# lock two parallel image saves on the same day would race and clobber.
_lock = threading.Lock()

# Repo root for locating gallery_template/. private_logger.log() lives in
# Fooocus/modules/, so two levels up = Fooocus root.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_FOOOCUS_ROOT = os.path.dirname(_MODULE_DIR)


# --------------------------------------------------------------------------
# Toggle helpers
# --------------------------------------------------------------------------

def _enabled() -> bool:
    return modules.config.asset_browser_enabled()


def _outputs_root() -> str:
    return modules.config.path_outputs


def _index_dir() -> str:
    return os.path.join(_outputs_root(), INDEX_DIR_NAME)


def _assets_dir() -> str:
    return os.path.join(_outputs_root(), ASSETS_DIR_NAME)


# --------------------------------------------------------------------------
# Asset bootstrap (template -> outputs/)
# --------------------------------------------------------------------------

def ensure_gallery_assets() -> bool:
    """Copy gallery_template/index.html and _assets/* to outputs/. Idempotent.

    Called from `on_image_logged()` (lazy) and from the UI Reindex button.
    Only runs work when the feature is enabled.
    """
    if not _enabled():
        return False
    try:
        out_root = _outputs_root()
        os.makedirs(out_root, exist_ok=True)

        template_root = os.path.join(_FOOOCUS_ROOT, TEMPLATE_DIR_NAME)
        if not os.path.isdir(template_root):
            print(f'[asset-browser] gallery_template/ not found at {template_root}')
            return False

        # Always overwrite index.html so users get template upgrades for free.
        src_html = os.path.join(template_root, 'index.html')
        dst_html = os.path.join(out_root, 'index.html')
        if os.path.isfile(src_html):
            shutil.copy2(src_html, dst_html)

        # Copy _assets/ recursively (only files newer than dest).
        src_assets = os.path.join(template_root, ASSETS_DIR_NAME)
        if os.path.isdir(src_assets):
            dst_assets = _assets_dir()
            os.makedirs(dst_assets, exist_ok=True)
            for name in os.listdir(src_assets):
                src_f = os.path.join(src_assets, name)
                dst_f = os.path.join(dst_assets, name)
                if os.path.isfile(src_f):
                    if not os.path.isfile(dst_f) or os.path.getmtime(src_f) > os.path.getmtime(dst_f):
                        shutil.copy2(src_f, dst_f)

        os.makedirs(_index_dir(), exist_ok=True)
        # Mirror the SPA-relevant subset of asset_browser config so the
        # standalone HTML can read it via fetch() — keeps the SPA fully
        # autonomous (no Gradio endpoint needed).
        try:
            spa_settings = {
                'blur_thumbnails': bool(modules.config.asset_browser_setting('blur_thumbnails', False)),
                'thumbnail_size': int(modules.config.asset_browser_setting('thumbnail_size', 256)),
                'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
            }
            with open(os.path.join(_index_dir(), 'spa_settings.json'), 'w', encoding='utf-8') as _sf:
                json.dump(spa_settings, _sf, indent=2)
        except Exception as _se:
            print(f'[asset-browser] could not write spa_settings.json: {_se}')
        return True
    except Exception as e:
        print(f'[asset-browser] ensure_gallery_assets failed: {e}')
        return False


# --------------------------------------------------------------------------
# Thumbnail
# --------------------------------------------------------------------------

def _thumbnail_path(image_path: str) -> str:
    """e.g. outputs/2026-05-03/img.png -> outputs/2026-05-03/img_thumb.jpg"""
    base, _ = os.path.splitext(image_path)
    return base + THUMBNAIL_SUFFIX


def _generate_thumbnail(image_path: str) -> bool:
    """Square 256x256 JPEG centre-cropped. Returns True on success."""
    if not modules.config.asset_browser_setting('generate_thumbnails', True):
        return False
    try:
        from PIL import Image
        thumb_path = _thumbnail_path(image_path)
        if os.path.isfile(thumb_path) and os.path.getmtime(thumb_path) >= os.path.getmtime(image_path):
            return True  # already up-to-date
        with Image.open(image_path) as im:
            im = im.convert('RGB')
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side))
            sz = _thumb_size()
            im = im.resize((sz, sz), Image.LANCZOS)
            im.save(thumb_path, 'JPEG', quality=_thumb_quality(), optimize=True)
        return True
    except Exception as e:
        print(f'[asset-browser] thumbnail failed for {image_path}: {e}')
        return False


# --------------------------------------------------------------------------
# Manifest IO (per-day)
# --------------------------------------------------------------------------

def _date_dir_for(image_path: str) -> tuple:
    """Extract (date_string, dir) from a Fooocus output path.
    e.g. .../outputs/2026-05-03/2026-05-03_14-32-11_3847.png
    -> ('2026-05-03', '.../outputs/2026-05-03/')
    """
    parent = os.path.dirname(image_path)
    date_string = os.path.basename(parent)
    return date_string, parent


def _load_manifest(date_dir: str) -> dict:
    path = os.path.join(date_dir, MANIFEST_FILE)
    if not os.path.isfile(path):
        return {'date': os.path.basename(date_dir), 'images': []}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or 'images' not in data:
            return {'date': os.path.basename(date_dir), 'images': []}
        return data
    except Exception:
        return {'date': os.path.basename(date_dir), 'images': []}


def _save_manifest(date_dir: str, manifest: dict) -> None:
    path = os.path.join(date_dir, MANIFEST_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _build_image_entry(image_path: str, metadata=None, task=None) -> dict:
    """Build a manifest entry for a single image."""
    filename = os.path.basename(image_path)
    thumb_filename = os.path.basename(_thumbnail_path(image_path)) if os.path.isfile(_thumbnail_path(image_path)) else None
    width = height = None
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            width, height = im.size
    except Exception:
        pass
    created_at = datetime.datetime.fromtimestamp(os.path.getmtime(image_path)).isoformat(timespec='seconds')

    # Metadata is a list of (label, key, value) tuples per private_logger.log().
    meta_dict = {}
    if metadata:
        try:
            for item in metadata:
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    _, key, value = item[0], item[1], item[2]
                    meta_dict[str(key)] = str(value) if not isinstance(value, (int, float, bool)) else value
        except Exception:
            pass

    entry = {
        'id': os.path.splitext(filename)[0],
        'src': filename,
        'thumb': thumb_filename,
        'width': width,
        'height': height,
        'created_at': created_at,
        'metadata': meta_dict,
    }
    return entry


# --------------------------------------------------------------------------
# Days index
# --------------------------------------------------------------------------

def _scan_existing_dates(out_root: str) -> list:
    """Return sorted list of YYYY-MM-DD subdir names that contain at least one image file."""
    if not os.path.isdir(out_root):
        return []
    dates = []
    for name in os.listdir(out_root):
        if name.startswith('_') or name.startswith('.'):
            continue
        full = os.path.join(out_root, name)
        if not os.path.isdir(full):
            continue
        # Heuristic: looks like a date YYYY-MM-DD?
        if len(name) >= 10 and name[4] == '-' and name[7] == '-':
            dates.append(name)
    dates.sort(reverse=True)  # most recent first
    return dates


def _refresh_days_index() -> None:
    """Rewrite outputs/_index/days.json from the current state of outputs/."""
    out_root = _outputs_root()
    os.makedirs(_index_dir(), exist_ok=True)
    today = datetime.date.today().isoformat()
    days = []
    for date_string in _scan_existing_dates(out_root):
        date_dir = os.path.join(out_root, date_string)
        manifest = _load_manifest(date_dir)
        count = len(manifest.get('images', []))
        if count == 0:
            continue
        days.append({'date': date_string, 'count': count})
    payload = {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'today': today,
        'days': days,
    }
    with open(os.path.join(_index_dir(), DAYS_INDEX_FILE), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Public hooks
# --------------------------------------------------------------------------

def on_image_logged(image_path, metadata=None, task=None) -> None:
    """Called by `modules/private_logger.py::log()` right before it returns.

    Wrapped in try/except by the caller so any bug here can never break image
    generation. M2a: thumbnail + manifest append + days.json refresh.
    """
    if not _enabled():
        return
    try:
        with _lock:
            ensure_gallery_assets()
            _generate_thumbnail(image_path)
            date_string, date_dir = _date_dir_for(image_path)
            manifest = _load_manifest(date_dir)
            entry = _build_image_entry(image_path, metadata=metadata, task=task)
            # Replace existing entry for the same id (idempotent on retries).
            manifest['images'] = [im for im in manifest.get('images', []) if im.get('id') != entry['id']]
            manifest['images'].append(entry)
            # Sort newest first by created_at descending.
            manifest['images'].sort(key=lambda x: x.get('created_at', ''), reverse=True)
            manifest['date'] = date_string
            manifest['updated_at'] = datetime.datetime.now().isoformat(timespec='seconds')
            _save_manifest(date_dir, manifest)
            _refresh_days_index()
    except Exception as e:
        print(f'[asset-browser] on_image_logged failed for {image_path}: {e}')


def reindex_outputs() -> tuple:
    """Walks all date subdirs under outputs/, regenerates thumbnails + manifests
    for every image found. Used to backfill history when the user enables the
    feature for the first time. Returns (ok, message).
    """
    if not _enabled():
        return False, 'Asset Browser is disabled. Enable it in Advanced first.'
    try:
        out_root = _outputs_root()
        if not os.path.isdir(out_root):
            return False, f'Outputs directory does not exist: {out_root}'
        ensure_gallery_assets()

        total_images = 0
        total_days = 0
        with _lock:
            all_dates = _scan_existing_dates(out_root)
            print(f'[asset-browser] reindex starting: {len(all_dates)} date dir(s) under {out_root}')
            for di, date_string in enumerate(all_dates, start=1):
                date_dir = os.path.join(out_root, date_string)
                images = []
                for name in sorted(os.listdir(date_dir)):
                    lower = name.lower()
                    if name.startswith('.') or name.startswith('_'):
                        continue
                    if THUMBNAIL_SUFFIX in lower:
                        continue
                    if not (lower.endswith('.png') or lower.endswith('.jpg')
                             or lower.endswith('.jpeg') or lower.endswith('.webp')):
                        continue
                    image_path = os.path.join(date_dir, name)
                    _generate_thumbnail(image_path)
                    images.append(_build_image_entry(image_path))
                if not images:
                    print(f'[asset-browser]   [{di}/{len(all_dates)}] {date_string}: empty (no images)')
                    continue
                images.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                manifest = {
                    'date': date_string,
                    'images': images,
                    'updated_at': datetime.datetime.now().isoformat(timespec='seconds'),
                }
                _save_manifest(date_dir, manifest)
                total_images += len(images)
                total_days += 1
                print(f'[asset-browser]   [{di}/{len(all_dates)}] {date_string}: {len(images)} image(s) -> manifest + thumbs OK')
            _refresh_days_index()
            print(f'[asset-browser] reindex outputs done: {total_days}/{len(all_dates)} day(s) had images, {total_images} total')

        # Bundle the model indexer so a single Reindex click rebuilds everything.
        model_summary = ''
        try:
            from modules.model_indexer import scan_all_and_write
            mok, msummary = scan_all_and_write()
            if mok:
                model_summary = (f' · models: {msummary.get("loras", 0)} LoRAs, '
                                 f'{msummary.get("checkpoints", 0)} ckpts, '
                                 f'{msummary.get("embeddings", 0)} embeds')
        except Exception as me:
            model_summary = f' (model scan failed: {me})'

        return True, (f'Reindex complete: {total_days} day(s), '
                       f'{total_images} image(s).{model_summary}')
    except Exception as e:
        return False, f'Reindex failed: {e}'
