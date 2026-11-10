import math
import unittest
import unicodedata
from unittest.mock import patch

from thirdeyes.voice_grammar import parse_command, PHRASES, VOICE_COMMANDS
from thirdeyes.object_catalog import TARGETS
from thirdeyes.object_finding import prioritize_regions, describe_found
from thirdeyes.app import main


def heard(text, confidence=.95):
    return {'text': text, 'result': [{'word': word, 'conf': confidence} for word in text.split()]}


def region(distance=None, confidence=.9, hour=3, status='ok'):
    return {'depth': {'status': status, 'distance_m': distance},
            'confidence': confidence, 'clock_hour': hour}


class VoiceObjectTests(unittest.TestCase):
    def test_examples_and_vietnamese_synonyms(self):
        for text, target in [('tìm chai nước', 'Chai nước'), ('tìm chai', 'Chai nước'),
                             ('tìm điện thoại', 'Điện thoại'), ('tìm cái ghế', 'Ghế'),
                             ('tìm máy tính xách tay', 'Laptop'), ('tìm muỗng', 'Thìa / muỗng'),
                             ('tìm dù', 'Ô / dù'), ('tìm tô', 'Bát / tô'), ('tìm bút', 'Bút')]:
            self.assertEqual(parse_command(heard(text)), ('find', target))

    def test_all_targets_have_commands_in_shared_recognizer_grammar(self):
        targets = {action[1] for action in VOICE_COMMANDS.values() if isinstance(action, tuple)}
        self.assertEqual(targets, set(TARGETS))
        self.assertIn('[unk]', PHRASES)
        for phrase, action in VOICE_COMMANDS.items():
            self.assertIn(phrase, PHRASES)
            self.assertEqual(parse_command(heard(phrase)), action)

    def test_unicode_and_whitespace(self):
        text = unicodedata.normalize('NFD', '  TÌM   CHAI NƯỚC  ')
        self.assertEqual(parse_command(heard(text)), ('find', 'Chai nước'))

    def test_uncertain_unknown_or_compound_commands_are_rejected(self):
        for text in ('tìm', 'tìm chìa khóa', 'tìm chai nước và điện thoại', 'không tìm chai nước', '[unk]'):
            self.assertIsNone(parse_command(heard(text)))
        for confidence in (.1, .6, float('nan'), float('inf'), True, 'high'):
            self.assertIsNone(parse_command(heard('tìm chai nước', confidence)))
        self.assertIsNone(parse_command({'text': 'tìm chai nước'}))

    def test_existing_commands_preserved(self):
        for text, action in [('đọc văn bản', 'read'), ('đọc lại', 'repeat'), ('dừng lại', 'cancel'), ('trạng thái', 'status')]:
            self.assertEqual(parse_command(heard(text)), action)

    def test_voice_target_reaches_finder_without_controls(self):
        with patch('thirdeyes.app.configure_logging'), patch('thirdeyes.app.BeepPlayer'), \
             patch('thirdeyes.app.VoiceCommands') as voice, patch('thirdeyes.app.ObjectFinder') as finder, \
             patch('thirdeyes.app.TextReader') as reader, patch('thirdeyes.app.time.sleep'), patch('thirdeyes.app.render'):
            voice.return_value.state = 'idle'
            voice.return_value.listening = False
            voice.return_value.poll.side_effect = [parse_command(heard('tìm điện thoại')), None]
            finder.return_value.busy = reader.return_value.busy = False
            finder.return_value.poll.return_value = reader.return_value.poll.return_value = None
            finder.return_value.find.return_value = True
            result = main(['--demo', '--headless', '--max-frames', '2', '--mute', '--no-speech'])
            self.assertEqual(result, 0)
            self.assertEqual(finder.return_value.find.call_args.args[1], 'Điện thoại')
            finder.return_value.find.assert_called_once()


class NearestObjectTests(unittest.TestCase):
    def test_fourth_confidence_candidate_can_be_closest(self):
        regions = [region(3, .99), region(2.5, .95), region(2, .9), region(1, .6)]
        result = {'status': 'ok', 'regions': regions, 'max_results': 3}
        prioritize_regions(result)
        self.assertEqual([r['depth']['distance_m'] for r in result['regions']], [1, 2, 2.5])
        self.assertTrue(result['regions'][0]['preferred'])
        self.assertEqual(sum(r['preferred'] for r in result['regions']), 1)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['detected_count'], 4)

    def test_unknown_distance_never_treated_as_zero_or_closer(self):
        result = {'status': 'ok', 'target_label': 'Chai nước',
                  'regions': [region(None, .99), region(2, .6), region(.5, .98), region(0, .97)]}
        prioritize_regions(result)
        self.assertEqual(result['regions'][0]['depth']['distance_m'], 2)
        self.assertEqual(result['unmeasured_count'], 3)
        speech = describe_found(result)
        self.assertIn('trong các vật đo được', speech)
        self.assertIn('chưa thể so sánh đầy đủ', speech)
        self.assertEqual(speech.count('Tìm thấy'), 1)

    def test_all_unknown_falls_back_without_nearest_claim(self):
        result = {'status': 'ok', 'target_label': 'Ghế',
                  'regions': [region(None, .6, 9), region(1, .9, 3, 'mixed_depth')]}
        prioritize_regions(result)
        self.assertEqual(result['selection'], 'confidence_only')
        self.assertEqual(result['regions'][0]['clock_hour'], 3)
        self.assertIn('Chưa xác định được vật gần nhất', describe_found(result))
        self.assertIn('chưa đo được', describe_found(result))

    def test_bad_depth_and_confidence_tie(self):
        result = {'status': 'ok', 'regions': [region(float('nan')), region(float('inf')),
                  region(True), region(4.1), region(1.5, .6), region(1.5, .8)]}
        prioritize_regions(result)
        self.assertEqual(result['unmeasured_count'], 4)
        self.assertEqual(result['regions'][0]['confidence'], .8)

    def test_no_detection_does_not_create_a_preferred_object(self):
        result = {'status': 'not_found', 'regions': []}
        prioritize_regions(result)
        self.assertNotIn('selection', result)


if __name__ == '__main__':
    unittest.main()
