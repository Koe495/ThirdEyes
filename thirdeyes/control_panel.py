"""Large keyboard-accessible controls; actions use the same coordinator as OpenCV."""
import queue
from thirdeyes.object_finding import TARGETS

KEYS = {'o': 'read', 'r': 'repeat', 'x': 'cancel', 'm': 'mute', 't': 'test',
        'v': 'listen', 's': 'status', 'q': 'quit', 'Escape': 'quit', 'f': 'find'}


class ControlPanel:
    def __init__(self, demo=False):
        import tkinter as tk
        self.tk = tk
        self.window = tk.Tk()
        self.window.title('ThirdEyes — Điều khiển')
        self.window.geometry('650x680')
        self.window.configure(bg='#111111')
        self.events = queue.Queue()
        self.window.protocol('WM_DELETE_WINDOW', lambda: self.events.put('quit'))
        tk.Label(self.window, text='THIRDEYES — DEMO' if demo else 'THIRDEYES', fg='white', bg='#111111', font=('Arial', 22, 'bold')).pack(pady=10)
        self.buttons = []
        from tkinter import ttk
        tk.Label(self.window, text='Vật cần tìm (chọn bằng phím mũi tên):', fg='white', bg='#111111').pack()
        self.target = tk.StringVar(value='Chai nước')
        self.selector = ttk.Combobox(self.window, textvariable=self.target, values=list(TARGETS), state='readonly', font=('Arial', 14))
        self.selector.pack(fill='x', padx=25, pady=5)
        self.selector.bind('<<ComboboxSelected>>', lambda e: self.events.put(('say', self.target.get())))
        for caption, action in [('Đọc văn bản [O]', 'read'), ('Đọc lại [R]', 'repeat'), ('Dừng đọc [X]', 'cancel'),
                                ('Tìm vật đã chọn [F]', 'find'), ('Nghe lệnh 6 giây [V]', 'listen'), ('Đọc trạng thái [S]', 'status'),
                                ('Bật / tắt âm [M]', 'mute'), ('Thử trái – giữa – phải [T]', 'test'), ('Thoát [Q]', 'quit')]:
            button = tk.Button(self.window, text=caption, command=lambda a=action: self.events.put(a),
                               font=('Arial', 14), bg='#eeeeee', fg='black', takefocus=True)
            button.pack(fill='x', padx=25, pady=3)
            button.bind('<FocusIn>', lambda event, text=caption: self.events.put(('say', text)))
            self.buttons.append((button, caption))
        self.text = tk.StringVar(value='Tab: chuyển nút. Enter hoặc Space: chọn.')
        tk.Label(self.window, textvariable=self.text, fg='white', bg='#111111', wraplength=600,
                 justify='left', font=('Arial', 13)).pack(fill='x', padx=25, pady=10)
        self.window.bind_all('<Key>', self._key)
        self.window.bind_all('<Return>', lambda e: e.widget.invoke() if isinstance(e.widget, tk.Button) else None)
        self.window.update_idletasks()
        # Tk draws its own text. Expose matching native window text to Windows
        # accessibility clients as well as speaking focused button labels.
        import os
        if os.name == 'nt':
            import ctypes as ct
            set_text = ct.windll.user32.SetWindowTextW
            set_text.argtypes = [ct.c_void_p, ct.c_wchar_p]
            set_text.restype = ct.c_int
            for button, caption in self.buttons:
                set_text(button.winfo_id(), caption)

    def _key(self, event):
        if event.widget is self.selector:
            return
        action = KEYS.get(event.keysym.lower()) or KEYS.get(event.keysym)
        if action:
            self.events.put(action)

    def update(self, message):
        self.text.set(message)
        self.window.update_idletasks()
        self.window.update()

    def poll(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.window.destroy()


def describe_status(report, reader, audio):
    directions = {'LEFT': 'bên trái', 'CENTER': 'phía trước', 'RIGHT': 'bên phải'}
    sentences = ['Âm thanh đang tắt.' if audio.muted else 'Âm thanh đang bật.']
    if report.status != 'ok':
        sentences.append('Dữ liệu độ sâu chưa đầy đủ. Không thể kết luận đường trống.')
    for zone in report.zones:
        if zone.level and zone.distance_m is not None and not zone.suppress_audio:
            sentences.append(f'Có vật cản {directions[zone.zone]}, khoảng {zone.distance_m:.1f} mét.')
    sentences.append('Đang nhận dạng văn bản.' if reader.busy else 'Bấm O để đọc văn bản, V để ra lệnh.')
    return ' '.join(sentences)
