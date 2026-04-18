"""
LoRA safetensors metadata reader.

Reads the embedded __metadata__ header of a .safetensors LoRA file to extract
likely trigger words offline, without hashing the file or hitting the network.

Works for LoRAs trained with kohya-ss / sd-scripts (the majority). Falls back
gracefully for LoRAs without metadata or non-safetensors files.
"""

import json
import os
import struct

from modules.util import get_file_from_folder_list

# Sanity cap on header size — real headers are typically <1MB.
_SAFETENSORS_MAX_HEADER = 100 * 1024 * 1024

# How many of the top training tags to surface as triggers, at minimum.
_TOP_N_TAGS = 8
# Only keep tags whose frequency is at least this fraction of the most-frequent tag.
_MIN_FREQ_RATIO = 0.10


def read_safetensors_metadata(filepath):
    """Read the __metadata__ dict from a .safetensors header. Returns {} on any failure."""
    if not filepath or not os.path.isfile(filepath):
        return {}
    try:
        with open(filepath, 'rb') as f:
            header_len_bytes = f.read(8)
            if len(header_len_bytes) != 8:
                return {}
            header_len = struct.unpack('<Q', header_len_bytes)[0]
            if header_len <= 0 or header_len > _SAFETENSORS_MAX_HEADER:
                return {}
            header_bytes = f.read(header_len)
            if len(header_bytes) != header_len:
                return {}
            header = json.loads(header_bytes.decode('utf-8'))
        meta = header.get('__metadata__') or {}
        return meta if isinstance(meta, dict) else {}
    except Exception as e:
        print(f'[LoRA meta] read error for {os.path.basename(filepath or "?")}: {e}')
        return {}


def extract_triggers_from_metadata(meta):
    """Extract likely trigger words from a LoRA's __metadata__ dict.

    Strategy:
      1. modelspec.trigger_phrase  -> most reliable, explicit
      2. Top tags from ss_tag_frequency filtered by frequency
      3. ss_output_name            -> fallback when nothing else is present

    Returns:
        (list_of_triggers, source_label)
    """
    if not meta:
        return [], 'empty'

    triggers = []
    sources_used = []

    # 1. Explicit trigger phrase (newer kohya / modelspec)
    trigger_phrase = meta.get('modelspec.trigger_phrase') or meta.get('ss_trigger_phrase')
    if trigger_phrase:
        for part in str(trigger_phrase).split(','):
            p = part.strip()
            if p and p not in triggers:
                triggers.append(p)
        if triggers:
            sources_used.append('trigger_phrase')

    # 2. Top training tags from ss_tag_frequency
    raw_freq = meta.get('ss_tag_frequency')
    if raw_freq:
        try:
            if isinstance(raw_freq, str):
                raw_freq = json.loads(raw_freq)
        except Exception:
            raw_freq = None

        if isinstance(raw_freq, dict):
            # Shape: {concept_folder_name: {tag: count, ...}, ...}
            tag_counts = {}
            for tags in raw_freq.values():
                if isinstance(tags, dict):
                    for tag, count in tags.items():
                        try:
                            tag_counts[tag] = tag_counts.get(tag, 0) + int(count)
                        except (ValueError, TypeError):
                            pass

            if tag_counts:
                max_count = max(tag_counts.values())
                threshold = max_count * _MIN_FREQ_RATIO
                sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
                added_from_tags = 0
                for tag, count in sorted_tags[:_TOP_N_TAGS]:
                    if count < threshold:
                        break
                    t = str(tag).strip()
                    if t and t not in triggers:
                        triggers.append(t)
                        added_from_tags += 1
                if added_from_tags:
                    sources_used.append('ss_tag_frequency')

    # 3. Output name fallback
    if not triggers:
        output_name = meta.get('ss_output_name')
        if output_name:
            nm = str(output_name).strip()
            if nm:
                triggers.append(nm)
                sources_used.append('ss_output_name')

    if triggers:
        return triggers, '+'.join(sources_used) or 'metadata'
    return [], 'no usable fields in metadata'


def get_lora_triggers_from_file(lora_filename, paths_loras):
    """Resolve a LoRA filename to a path, read its metadata, extract triggers.

    Returns:
        {'trainedWords': [...], 'source': 'local:<label>', 'has_metadata': bool}
        or {'error': '...'} on failure.
    """
    if not lora_filename or lora_filename == 'None':
        return {'error': 'No LoRA selected.'}
    try:
        filepath = get_file_from_folder_list(lora_filename, paths_loras)
    except Exception as e:
        return {'error': f'Cannot locate LoRA on disk: {e}'}
    if not filepath or not os.path.isfile(filepath):
        return {'error': f'LoRA file not found: {lora_filename}'}
    if not filepath.lower().endswith('.safetensors'):
        return {'error': 'Not a safetensors file (no embedded metadata)'}

    meta = read_safetensors_metadata(filepath)
    triggers, source = extract_triggers_from_metadata(meta)
    return {
        'trainedWords': triggers,
        'source': f'local:{source}',
        'has_metadata': bool(meta),
    }
