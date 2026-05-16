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
    """Cached loader. Returns a torch.nn.Module ready for upscale."""
    print(f'[Upscaler] Loading upscale model: {model_path}')
    sd = _load_state_dict_any(model_path)

    # Fooocus' bundled upscaler uses an old key naming ("residual_block_*").
    # Translate it on the fly so we can use the generic loader for it too.
    if any(k.startswith('residual_block_') for k in sd.keys()):
        sdo = OrderedDict()
        for k, v in sd.items():
            sdo[k.replace('residual_block_', 'RDB')] = v
        del sd
        m = ESRGAN(sdo)
    else:
        m = auto_load_state_dict(sd)

    m.cpu()
    m.eval()
    return m


def perform_upscale(img, model_path: str = None):
    """Upscale a numpy image.

    Args:
        img: HxWxC numpy array (uint8).
        model_path: absolute path to an upscale model. If None or the file
            doesn't exist, falls back to the bundled Fooocus ESRGAN.

    Returns:
        Upscaled HxWxC numpy array.
    """
    global model

    print(f'Upscaling image with shape {str(img.shape)} ...')

    use_custom = bool(model_path) and os.path.isfile(model_path)

    if use_custom:
        active = _load_upscale_model(model_path)
    else:
        if model is None:
            # Lazily load the bundled default (downloads if missing).
            default_path = downloading_upscale_model()
            model = _load_upscale_model(default_path)
        active = model

    img = core.numpy_to_pytorch(img)
    img = opImageUpscaleWithModel.upscale(active, img)[0]
    img = core.pytorch_to_numpy(img)[0]

    return img
