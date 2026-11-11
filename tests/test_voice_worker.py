import unittest

from ocr_runtime.voice_worker import select_input_device


class FakeSoundDevice:
    default = type('Default', (), {'device': (1, 0)})()
    devices = [
        {'name': 'Microphone Array (Realtek(R) Au', 'hostapi': 0, 'max_input_channels': 2},
        {'name': 'Microphone Array (Realtek(R) Audio)', 'hostapi': 1, 'max_input_channels': 2},
        {'name': 'Microphone Array (Realtek(R) Audio)', 'hostapi': 2, 'max_input_channels': 2},
        {'name': 'Stereo Mix (Realtek Audio)', 'hostapi': 2, 'max_input_channels': 2},
        {'name': 'Speakers (Realtek Audio)', 'hostapi': 2, 'max_input_channels': 0},
    ]

    @classmethod
    def query_devices(cls, index=None, kind=None):
        if index is None:
            return cls.devices
        return cls.devices[index]


class VoiceWorkerTests(unittest.TestCase):
    def test_selects_requested_microphone_using_preferred_host_api(self):
        index, device = select_input_device(FakeSoundDevice, 'Microphone Array (Realtek(R) Audio)')
        self.assertEqual(index, 2)
        self.assertEqual(device['hostapi'], 2)

    def test_default_microphone_is_preserved_without_selector(self):
        index, device = select_input_device(FakeSoundDevice, None)
        self.assertEqual(index, 1)
        self.assertEqual(device, FakeSoundDevice.devices[index])

    def test_missing_microphone_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'Không tìm thấy micro'):
            select_input_device(FakeSoundDevice, 'micro không tồn tại')


if __name__ == '__main__':
    unittest.main()
