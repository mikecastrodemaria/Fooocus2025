"""
Upscaler module.

custom-10:
  - Refactored to support arbitrary upscale architectures via
    ldm_patched.pfn.model_loading.load_state_dict (auto-detects ESRGAN,
    RealESRGAN/SRVGG, SwinIR, Swin2SR, HAT, DAT, SCUNet, OmniSR, SPSR,
    SwiftSRGAN — and the face restoration archs CodeFormer / GFPGAN /
    RestoreFormer for the face-restore pipeline).
  - perform_upscale() now accepts an optional model_path so the worker can
    pick any model the user has on disk; if None, falls back to the Fooocus
    bundled ESRGAN (legacy behaviour preserved).
  - Per-file LRU cache so switching between models in a session doesn't
    re-read 30+ MB from disk every call.
"""

import os
from collections import OrderedDict
from functools import lru_cache

import safetensors.torch
import torch

import modules.core as core
from ldm_patched.contrib.external_upscale_model import ImageUpscaleWithModel
from ldm_patched.pfn.architecture.RRDB import RRDBNet as ESRGAN
from ldm_patched.pfn.model_loading import load_state_dict as auto_load_state_dict
from modules.config import downloading_upscale_model

opImageUpscaleWithModel = ImageUpscaleWithModel()

# Legacy single-slot kept for the Fooocus default path (back-compat with
# anything that still imports `model` from this module).
model = None


def _load_state_dict_any(path: str):
    """Load a .pth / .safetensors / .bin checkpoint into a plain state_dict."""
    lower = path.lower()
    if lower.endswith('.safetensors'):
        return safetensors.torch.load_file(path, device='cpu')
    # .pth, .pt, .bin → torch.load
    return torch.load(path, map_location='cpu', weights_only=True)


@lru_cache(maxsize=4)
def _load_upscale_model(model_path: str):
    """Cached loader. Returns a torch.nn.Module ready for upscale.

    Strategy (custom-10.3):
      1. Try the auto-detector (handles ESRGAN/RealESRGAN/SwinIR/HAT/DAT/...).
      2. If that fails, fall back to the original Fooocus manual ESRGAN
         construction with the legacy 'residual_block_*' -> 'RDB*' rename.
      3. Only raise if BOTH paths fail — saves the day when the bundled
         loader doesn't recognise a non-standard ESRGAN variant whose
         keys still parse with a forced ESRGAN constructor.
    """
    print(f'[Upscaler] Loading upscale model: {model_path}')
    sd = _load_state_dict_any(model_path)

    # 1) Manual path when we see the legacy Fooocus key naming. The original
    #    Fooocus upscaler keys look like 'model.1.sub.N.residual_block_X.convY...'
    #    — 'residual_block_' is a substring, NOT a prefix. Match accordingly.
    if any('residual_block_' in k for k in sd.keys()):
        sdo = OrderedDict()
        for k, v in sd.items():
            sdo[k.replace('residual_block_', 'RDB')] = v
        m = ESRGAN(sdo)
        m.cpu(); m.eval()
        return m

    # 2) Auto-detector (covers most modern files).
    try:
        m = auto_load_state_dict(sd)
        m.cpu(); m.eval()
        return m
    except Exception as e_auto:
        # 3) Last-resort: force ESRGAN constructor with the legacy rename hack.
        # This mirrors the pre-custom-10 behaviour and recovers files that the
        # newer auto-detector chokes on (some community ESRGAN variants).
        try:
            sdo = OrderedDict()
            for k, v in sd.items():
                sdo[k.replace('residual_block_', 'RDB')] = v
            m = ESRGAN(sdo)
            m.cpu(); m.eval()
            print(f'[Upscaler] auto-detect failed ({type(e_auto).__name__}); legacy ESRGAN fallback succeeded.')
            return m
        except Exception as e_manual:
            # Both paths dead. Raise the original auto-detect error with extra
            # context so the caller can decide whether to fall back further.
            raise type(e_auto)(
                f'{e_auto} | legacy ESRGAN also failed: '
                f'{type(e_manual).__name__}: {e_manual}'
            )


def perform_upscale(img, model_path: str = None):
    """Upscale a numpy image.

    Args:
        img: HxWxC numpy array (uint8).
        model_path: absolute path to an upscale model. If None, the file is
            missing, or the file can't be parsed by any known arch, falls
            back to the bundled Fooocus ESRGAN with a console warning.

    Returns:
        Upscaled HxWxC numpy array.
    """
    global model

    print(f'Upscaling image with shape {str(img.shape)} ...')

    use_custom = bool(model_path) and os.path.isfile(model_path)

    active = None
    if use_custom:
        try:
            active = _load_upscale_model(model_path)
        except Exception as e:
            # custom-10.2: graceful fallback. Common cause: a community
            # checkpoint whose state-dict keys don't match any architecture
            # the bundled ldm_patched.pfn.model_loading auto-detects
            # (UnsupportedModel raised). Don't crash the whole generation —
            # warn loudly and fall back to the Fooocus default.
            print(f'[Upscaler] WARNING: cannot load {model_path} ({type(e).__name__}: {e}).')
            print(f'[Upscaler] Falling back to bundled Fooocus default upscaler.')

    if active is None:
        if model is None:
            # Lazily load the bundled default (downloads if missing).
            default_path = downloading_upscale_model()
            try:
                model = _load_upscale_model(default_path)
            except Exception as e_default:
                # custom-10.3: even the bundled default failed (usually means
                # the file at path_upscale_models/fooocus_upscaler_s409985e5.bin
                # was overwritten with a different model by some other tool).
                # Surface a CLEAR error instead of a cryptic UnsupportedModel.
                raise RuntimeError(
                    f'Fooocus default upscaler at {default_path} cannot be '
                    f'loaded ({type(e_default).__name__}: {e_default}). '
                    f'Likely the file was replaced with a non-ESRGAN model. '
                    f'Either delete that file (Fooocus will re-download the '
                    f'official one on next run) or point path_upscale_models '
                    f'to a folder that contains the real fooocus_upscaler.bin.'
                ) from e_default
        active = model

    img = core.numpy_to_pytorch(img)
    img = opImageUpscaleWithModel.upscale(active, img)[0]
    img = core.pytorch_to_numpy(img)[0]

    return img
