"""Offline SAPI process. Select only an installed Vietnamese voice."""
import json
import queue
import sys
import threading
import time


def emit(state, **fields):
    print(json.dumps({"state": state, **fields}, ensure_ascii=False), flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    try:
        voice = comtypes.client.CreateObject("SAPI.SpVoice", dynamic=True)
        voices = voice.GetVoices()
        vietnamese = []
        for i in range(voices.Count):
            token = voices.Item(i)
            locales = token.GetAttribute("Language").split(";")
            if any((int(code, 16) & 0x3FF) == 0x2A for code in locales):
                vietnamese.append(token)
        if not vietnamese:
            emit("no_vi_voice", message="Chưa có giọng tiếng Việt SAPI trên Windows. OCR vẫn hoạt động.")
            return
        voice.Voice = vietnamese[0]
        emit("ready", voice=voice.Voice.GetDescription())
        commands = queue.Queue()

        def listen():
            for line in sys.stdin:
                commands.put(json.loads(line))
            commands.put({"action": "quit"})

        threading.Thread(target=listen, daemon=True).start()
        speaking = False
        while True:
            try:
                command = commands.get(timeout=.025)
                if command["action"] in {"stop", "quit"}:
                    voice.Speak("", 3)
                    speaking = False
                    emit("ready")
                    if command["action"] == "quit":
                        return
                elif command["action"] == "speak":
                    # Async + purge + literal text (never interpret recognized XML).
                    voice.Speak(command["text"][:3000], 1 | 2 | 16)
                    speaking = True
                    emit("speaking")
            except queue.Empty:
                if speaking and voice.Status.RunningState != 2:
                    speaking = False
                    emit("ready")
    except Exception as exc:
        emit("error", message=str(exc))
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    main()
