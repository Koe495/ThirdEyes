"""Shared offline recognition grammar and exact command interpretation."""
import math
import unicodedata

from thirdeyes.object_catalog import TARGETS

COMMANDS = {'đọc văn bản': 'read', 'đọc chữ': 'read', 'đọc lại': 'repeat', 'lặp lại': 'repeat',
            'dừng đọc': 'cancel', 'dừng lại': 'cancel', 'trạng thái': 'status', 'kiểm tra': 'status'}

ALIASES = {
    'Xe buýt': ('xe buýt', 'xe bus'),
    'Máy nướng bánh mì': ('máy nướng bánh mì', 'máy nướng bánh'),
    'Bồn rửa': ('bồn rửa', 'bồn rửa chén', 'chậu rửa'),
    'Chai nước': ('chai', 'chai nước'),
    'Điện thoại': ('điện thoại', 'điện thoại di động'),
    'Cốc': ('cốc', 'ly', 'ca'),
    'Vali': ('vali', 'va li'),
    'Ghế sofa': ('ghế sô pha', 'sô pha'),
}


def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).lower().split())


def command_map():
    commands = dict(COMMANDS)
    for target in TARGETS:
        aliases = ALIASES.get(target, tuple(target.lower().split(' / ')))
        for alias in aliases:
            for prefix in ('tìm ', 'tìm cái '):
                phrase = normalize(prefix + alias)
                action = ('find', target)
                if phrase in commands and commands[phrase] != action:
                    raise ValueError('Ambiguous voice alias: ' + phrase)
                commands[phrase] = action
    return commands


VOICE_COMMANDS = command_map()
PHRASES = list(VOICE_COMMANDS) + ['[unk]']


def parse_command(result):
    text = result.get('text', '')
    words = result.get('result', [])
    if not isinstance(text, str) or not isinstance(words, list) or not words:
        return None
    confidence = [w.get('conf', 0) if isinstance(w, dict) else 0 for w in words]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in confidence):
        return None
    if min(confidence) < .35 or max(confidence) > 1 or sum(confidence) / len(confidence) < .75:
        return None
    # No fuzzy match: uncertain or compound requests must not start a wrong search.
    return VOICE_COMMANDS.get(normalize(text))
