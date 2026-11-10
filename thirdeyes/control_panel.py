"""Single-window accessible dashboard driven by the existing application loop."""
import queue
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import cv2
from thirdeyes.object_catalog import TARGETS
from thirdeyes.ui_logging import colorize_depth
from thirdeyes.ui_theme import (BG, SURFACE, CARD, BORDER, TEXT, MUTED, ACCENT,
                               WARNING, DANGER, FONT, ImagePane, label, result_snapshot)

KEYS = {'o': 'read', 'r': 'repeat', 'x': 'cancel', 'm': 'mute', 't': 'test',
        'v': 'listen', 's': 'status', 'q': 'quit', 'Escape': 'quit', 'f': 'find'}
STATES = {'idle': 'Sẵn sàng', 'working': 'Đang xử lý', 'ok': 'Hoàn tất',
          'not_found': 'Chưa tìm thấy', 'unsupported': 'Chưa hỗ trợ', 'error': 'Cần kiểm tra',
          'timeout': 'Xử lý quá lâu', 'cancelled': 'Đã dừng', 'unavailable': 'Chưa sẵn sàng',
          'no_frame': 'Chưa có ảnh', 'stale': 'Ảnh đã cũ', 'blurry': 'Ảnh chưa rõ',
          'no_text': 'Chưa thấy chữ', 'ready': 'Sẵn sàng', 'speaking': 'Đang đọc',
          'starting': 'Đang khởi động', 'listening': 'Đang nghe', 'result': 'Đã nghe xong'}


def stream_status(received, now, demo=False):
    if received is None:
        return 'CHỜ KẾT NỐI', WARNING
    if now-received > 2:
        return 'ẢNH ĐÃ CŨ', DANGER
    return ('MÔ PHỎNG', WARNING) if demo else ('TRỰC TIẾP', ACCENT)


def zone_status(zone):
    if not zone.known or zone.distance_m is None:
        return 'Chưa đo được', '—', WARNING
    distance = f'{zone.distance_m:.2f} m'
    if zone.suppress_audio:
        return 'Đang theo dõi', distance, WARNING
    return ('Đang quan sát', 'Vật ở gần', 'Cần chú ý ngay')[zone.level], distance, (ACCENT, WARNING, DANGER)[zone.level]


class ControlPanel:
    def __init__(self, demo=False):
        self.demo = demo
        self.window = tk.Tk()
        self.window.title('ThirdEyes — Trợ lý thị giác')
        width, height = min(1380, self.window.winfo_screenwidth()-60), min(860, self.window.winfo_screenheight()-90)
        self.window.geometry(f'{width}x{height}+20+20')
        self.window.minsize(1050, 660)
        self.window.configure(bg=BG)
        self.events, self.buttons = queue.Queue(), []
        self.closed, self._last_preview = False, -float('inf')
        self.window.protocol('WM_DELETE_WINDOW', lambda: self.events.put('quit'))
        self._style()
        header = tk.Frame(self.window, bg=BG)
        header.pack(fill='x', padx=24, pady=(18, 16))
        logo = label(header, 'TE', 16, BG, True, padx=10, pady=7)
        logo.configure(bg=ACCENT)
        logo.pack(side='left')
        brand = tk.Frame(header, bg=BG)
        brand.pack(side='left', padx=12)
        label(brand, 'ThirdEyes', 22, bold=True).pack(anchor='w')
        label(brand, 'Trợ lý thị giác · Nhận biết bằng âm thanh', 10, MUTED).pack(anchor='w')
        self.connection = label(header, 'Đang kết nối camera', 11, WARNING, True, padx=14, pady=9)
        self.connection.configure(bg=SURFACE)
        self.connection.pack(side='right')
        self.alert = label(header, '', 10, WARNING, True)
        self.alert.pack(side='right', padx=12)
        footer = tk.Frame(self.window, bg=BG)
        footer.pack(side='bottom', fill='x', padx=24, pady=(10, 12))
        label(footer, 'Tab  Chuyển nút     Enter / Space  Chọn     Esc  Thoát', 10, MUTED).pack(side='left')
        label(footer, 'BẢN THỬ NGHIỆM  /  NGOẠI TUYẾN', 9, MUTED).pack(side='right')
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=24)
        side_host = tk.Frame(body, bg=SURFACE, width=264)
        side_host.pack(side='left', fill='y', padx=(0, 18))
        side_host.pack_propagate(False)
        self.side_canvas = tk.Canvas(side_host, bg=SURFACE, highlightthickness=0, width=252)
        scroll = ttk.Scrollbar(side_host, orient='vertical', command=self.side_canvas.yview, style='ThirdEyes.Vertical.TScrollbar')
        scroll.pack(side='right', fill='y')
        self.side_canvas.pack(side='left', fill='both', expand=True)
        self.side_canvas.configure(yscrollcommand=scroll.set)
        sidebar = tk.Frame(self.side_canvas, bg=SURFACE, padx=12, pady=16)
        self.sidebar = sidebar
        side_id = self.side_canvas.create_window(0, 0, window=sidebar, anchor='nw')
        sidebar.bind('<Configure>', lambda _e: self.side_canvas.configure(scrollregion=self.side_canvas.bbox('all')))
        self.side_canvas.bind('<Configure>', lambda e: self.side_canvas.itemconfigure(side_id, width=e.width))
        self.window.bind('<MouseWheel>', self._scroll_sidebar)
        label(sidebar, 'THAO TÁC', 10, MUTED, True).pack(anchor='w', pady=(0, 12))
        self._button(sidebar, 'Ra lệnh bằng giọng nói   V', 'listen', primary=True)
        label(sidebar, 'Chờ tiếng bíp rồi nói\n“tìm chai nước”', 10, MUTED, justify='left').pack(anchor='w', pady=(6, 16))
        self._button(sidebar, 'Đọc văn bản                         O', 'read')
        self._separator(sidebar)
        label(sidebar, 'VẬT CẦN TÌM', 10, MUTED, True).pack(anchor='w', pady=(0, 8))
        self.target = tk.StringVar(value='Chai nước')
        self.selector = ttk.Combobox(sidebar, textvariable=self.target, values=list(TARGETS),
                                     state='readonly', font=(FONT, 12), style='ThirdEyes.TCombobox')
        self.selector.pack(fill='x', pady=(0, 8), ipady=5)
        self.selector.bind('<<ComboboxSelected>>', lambda _e: self.events.put(('say', self.target.get())))
        self.selector.bind('<FocusIn>', lambda _e: self._reveal(self.selector))
        self._button(sidebar, 'Tìm vật đã chọn                   F', 'find')
        self._separator(sidebar)
        row = tk.Frame(sidebar, bg=SURFACE)
        row.pack(fill='x')
        self._button(row, 'Đọc lại  R', 'repeat', side='left')
        self._button(row, 'Dừng  X', 'cancel', side='right', danger=True)
        self.mute_button = self._button(sidebar, 'Âm thanh: đang bật              M', 'mute')
        row = tk.Frame(sidebar, bg=SURFACE)
        row.pack(fill='x', pady=(6, 0))
        self._button(row, 'Trạng thái  S', 'status', side='left', small=True)
        self._button(row, 'Thử âm  T', 'test', side='right', small=True)
        self._button(sidebar, 'Thoát ứng dụng                  Q', 'quit', small=True)
        content = tk.Frame(body, bg=BG)
        content.pack(side='left', fill='both', expand=True)
        self.tabs = ttk.Notebook(content, style='ThirdEyes.TNotebook', takefocus=True)
        self.tabs.pack(fill='both', expand=True)
        self.live, self.results = tk.Frame(self.tabs, bg=BG), tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.live, text='  Trực tiếp  ')
        self.tabs.add(self.results, text='  Kết quả  ')
        self._build_live()
        self._build_results()
        # Run shortcuts before Text/Button class bindings. Disabled text widgets
        # otherwise swallow letters such as Q/R while displaying a result.
        self._shortcut_tag = 'ThirdEyesKeys' + str(id(self))
        self.window.bind_class(self._shortcut_tag, '<Key>', self._key)
        self.window.bind_class(self._shortcut_tag, '<Return>', self._enter)
        self._install_shortcuts(self.window)
        self.window.update_idletasks()
        self._native_captions()

    def _install_shortcuts(self, widget):
        widget.bindtags((self._shortcut_tag,) + widget.bindtags())
        for child in widget.winfo_children():
            self._install_shortcuts(child)

    def _style(self):
        style = ttk.Style(self.window)
        style.theme_use('clam')
        style.configure('ThirdEyes.TNotebook', background=BG, borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure('ThirdEyes.TNotebook.Tab', background=SURFACE, foreground=MUTED,
                        font=(FONT, 12, 'bold'), padding=(16, 11), bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure('ThirdEyes.Vertical.TScrollbar', background=BORDER, troughcolor=SURFACE,
                        bordercolor=SURFACE, arrowcolor=MUTED, lightcolor=SURFACE, darkcolor=SURFACE, width=10)
        style.map('ThirdEyes.Vertical.TScrollbar', background=[('active', MUTED), ('!active', BORDER)])
        style.map('ThirdEyes.TNotebook.Tab', lightcolor=[('selected', CARD), ('!selected', SURFACE)],
                  darkcolor=[('selected', CARD), ('!selected', SURFACE)], bordercolor=[('selected', CARD), ('!selected', SURFACE)])
        style.map('ThirdEyes.TNotebook.Tab', background=[('selected', CARD)], foreground=[('selected', ACCENT)])
        style.configure('ThirdEyes.TCombobox', fieldbackground=CARD, background=CARD,
                        foreground=TEXT, arrowcolor=ACCENT, bordercolor=BORDER, padding=4)
        style.map('ThirdEyes.TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', TEXT)],
                  selectbackground=[('readonly', CARD)], selectforeground=[('readonly', TEXT)])
        for key, value in [('background', CARD), ('foreground', TEXT), ('selectBackground', '#244c61'),
                           ('selectForeground', TEXT), ('font', (FONT, 12))]:
            self.window.option_add('*TCombobox*Listbox.'+key, value)

    def _button(self, parent, caption, action, primary=False, danger=False, side=None, small=False):
        background, foreground = (ACCENT, BG) if primary else (CARD, DANGER if danger else TEXT)
        button = tk.Button(parent, text=caption, command=lambda: self.events.put(action),
                           font=(FONT, 10 if small else 11, 'bold'), bg=background, fg=foreground,
                           activebackground='#a0f0dc' if primary else '#28435d', activeforeground=BG if primary else TEXT,
                           relief='flat', bd=0, highlightthickness=2, highlightbackground=background,
                           highlightcolor=ACCENT, cursor='hand2', takefocus=True, pady=9 if small else 11, padx=4)
        if side:
            button.pack(side=side, fill='x', expand=True, padx=(0, 3) if side == 'left' else (3, 0))
        else:
            button.pack(fill='x', pady=(0, 7))
        button.bind('<FocusIn>', lambda _e: self._focus_button(button))
        self.buttons.append((button, caption))
        return button

    def _reveal(self, widget):
        height = max(1, self.sidebar.winfo_height())
        top = widget.winfo_rooty()-self.sidebar.winfo_rooty()
        bottom = top+widget.winfo_height()
        first, last = self.side_canvas.yview()
        if top < first*height:
            self.side_canvas.yview_moveto(max(0, (top-8)/height))
        elif bottom > last*height:
            self.side_canvas.yview_moveto(max(0, (bottom-self.side_canvas.winfo_height()+8)/height))

    def _focus_button(self, button):
        self._reveal(button)
        self.events.put(('say', button.cget('text')))

    def _scroll_sidebar(self, event):
        if str(event.widget).startswith(str(self.sidebar)) or event.widget is self.side_canvas:
            self.side_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return 'break'

    def _separator(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill='x', pady=(10, 16))

    def _build_live(self):
        self.live.grid_columnconfigure(0, weight=1)
        self.live.grid_rowconfigure(1, weight=1)
        intro = tk.Frame(self.live, bg=BG)
        intro.grid(row=0, column=0, sticky='ew', pady=(10, 8))
        label(intro, 'Không gian quan sát', 17, bold=True).pack(anchor='w')
        self.overview = label(intro, 'Đang chờ dữ liệu từ camera', 11, MUTED)
        self.overview.pack(anchor='w', pady=(4, 0))
        cameras = tk.Frame(self.live, bg=BG)
        cameras.grid(row=1, column=0, sticky='nsew')
        cameras.grid_columnconfigure((0, 1), weight=1, uniform='camera')
        cameras.grid_rowconfigure(0, weight=1)
        self.previews, self.stream_labels = [], []
        for i, (name, subtitle) in enumerate((('Ảnh màu', 'Nhận diện vật thể và văn bản'), ('Bản đồ độ sâu', 'Phạm vi đo 0,8 – 4,0 mét'))):
            card = tk.Frame(cameras, bg=SURFACE, padx=10, pady=8)
            card.grid(row=0, column=i, sticky='nsew', padx=(0, 6) if i == 0 else (6, 0))
            bar = tk.Frame(card, bg=SURFACE)
            bar.pack(fill='x', pady=(0, 4))
            label(bar, name, 12, bold=True).pack(side='left')
            state = label(bar, 'ĐANG CHỜ', 8, WARNING, True)
            state.pack(side='right')
            label(card, subtitle, 9, MUTED).pack(anchor='w', pady=(0, 6))
            pane = ImagePane(card)
            pane.pack(fill='both', expand=True)
            self.previews.append(pane)
            self.stream_labels.append(state)
        label(self.live, 'Depth: màu nóng = gần · màu lạnh = xa · màu đen = chưa đo được', 9, MUTED).grid(row=2, column=0, sticky='w', pady=(4, 8))
        zone_row = tk.Frame(self.live, bg=BG)
        zone_row.grid(row=3, column=0, sticky='ew')
        zone_row.grid_columnconfigure((0, 1, 2), weight=1, uniform='zone')
        self.zone_widgets = {}
        for i, (key, name) in enumerate((('LEFT', 'BÊN TRÁI'), ('CENTER', 'PHÍA TRƯỚC'), ('RIGHT', 'BÊN PHẢI'))):
            card = tk.Frame(zone_row, bg=CARD, padx=12, pady=8)
            card.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 5, 0 if i == 2 else 5))
            label(card, name, 9, MUTED, True).pack(anchor='w')
            distance = label(card, '—', 20, bold=True)
            distance.pack(anchor='w')
            status = label(card, 'Chưa đo được', 10, WARNING)
            status.pack(anchor='w')
            self.zone_widgets[key] = (distance, status)
        state_card = tk.Frame(self.live, bg=SURFACE, padx=14, pady=8)
        state_card.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        self.task_status = label(state_card, 'Sẵn sàng nhận yêu cầu', 11, bold=True, anchor='w')
        self.task_status.pack(fill='x')
        self.micro_status = label(state_card, 'Bấm V để nói tên vật cần tìm.', 10, MUTED, anchor='w')
        self.micro_status.pack(fill='x', pady=(4, 0))
        state_card.bind('<Configure>', lambda e: [w.configure(wraplength=max(100, e.width-30)) for w in (self.task_status, self.micro_status)])

    def _build_results(self):
        label(self.results, 'Kết quả gần nhất', 19, bold=True).pack(anchor='w', pady=(16, 4))
        self.result_meta = label(self.results, 'Ảnh chụp và nội dung nhận diện sẽ xuất hiện tại đây.', 11, MUTED)
        self.result_meta.pack(anchor='w', pady=(0, 14))
        area = tk.Frame(self.results, bg=BG)
        area.pack(fill='both', expand=True)
        area.grid_columnconfigure(0, weight=3, uniform='result')
        area.grid_columnconfigure(1, weight=2, uniform='result')
        area.grid_rowconfigure(0, weight=1)
        self.result_image = ImagePane(area, 'Chưa có ảnh kết quả\nBấm O để đọc chữ hoặc F để tìm vật.')
        self.result_image.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        self.result_text = ScrolledText(area, bg=SURFACE, fg=TEXT, insertbackground=ACCENT,
                                       selectbackground='#285268', selectforeground=TEXT, wrap='word',
                                       font=(FONT, 14), relief='flat', bd=0, padx=18, pady=18,
                                       width=24, height=10, takefocus=True)
        self.result_text.grid(row=0, column=1, sticky='nsew')
        self.result_text.vbar.configure(bg=CARD, troughcolor=BG, activebackground=BORDER, relief='flat', bd=0)
        self._set_result_text('Chưa có kết quả.\n\nBạn có thể nói “tìm chai nước” sau khi bấm V và nghe tiếng bíp.')
        label(self.results, 'Kết quả thuộc ảnh vừa chụp. Bấm R để nghe lại, O hoặc F để chụp mới.', 10, MUTED).pack(anchor='w', pady=(12, 6))

    def _set_result_text(self, text):
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.insert('1.0', text)
        self.result_text.configure(state='disabled')

    def show_result(self, result, rgb):
        name = 'Tìm vật' if 'target_label' in result else 'Đọc văn bản'
        state = STATES.get(result.get('status'), 'Đã có kết quả')
        self.result_meta.configure(text=f'{name}  /  {state}  /  Ảnh chụp', fg=ACCENT if result.get('status') == 'ok' else WARNING)
        content = result.get('text') or result.get('speak') or 'Chưa có nội dung nhận diện.'
        if 'target_label' in result and result.get('regions'):
            content += '\n\nCÁC VẬT ĐÃ NHẬN DIỆN'
            for i, region in enumerate(result['regions'], 1):
                hour, depth = region.get('clock_hour'), region.get('depth', {})
                direction = f'{hour} giờ' if hour else 'Chính giữa'
                distance = f"{depth['distance_m']:.2f} m" if depth.get('status') == 'ok' else 'Chưa đo được'
                content += f'\n{i}. {direction} · {distance}' + (' · Ưu tiên' if region.get('preferred') else '')
        self._set_result_text(content)
        self.result_image.display(result_snapshot(rgb, result))
        self.tabs.select(self.results)

    def present(self, frames, report, audio, reader, finder, voice, pair, now):
        if self.closed:
            return
        if now-self._last_preview >= .1:
            self._last_preview = now
            states = [stream_status(t, now, self.demo) for t in (frames.color_received_at, frames.depth_received_at)]
            for widget, (text, color) in zip(self.stream_labels, states):
                widget.configure(text=text, fg=color)
            connected = all(t is not None and now-t <= 2 for t in (frames.color_received_at, frames.depth_received_at))
            self.connection.configure(text='DEMO · Dữ liệu mô phỏng' if self.demo else 'Kinect · Đã kết nối' if connected else 'Camera · Đang chờ dữ liệu', fg=WARNING if self.demo or not connected else ACCENT)
            if self.tabs.select() == str(self.live):
                self.previews[0].display(frames.rgb)
                depth = None if frames.depth_mm is None else colorize_depth(frames.depth_mm)
                if depth is not None and report.roi is not None:
                    x0, y0, x1, y1 = report.roi
                    for i, zone in enumerate(report.zones):
                        color = ((195, 225, 112), (138, 208, 255), (171, 156, 255))[zone.level]
                        cv2.rectangle(depth, (x0+(x1-x0)*i//3, y0), (x0+(x1-x0)*(i+1)//3, y1), color, 2)
                self.previews[1].display(None if depth is None else cv2.cvtColor(depth, cv2.COLOR_BGR2RGB))
            for zone in report.zones:
                status, distance, color = zone_status(zone)
                if zone.zone in self.zone_widgets:
                    number, caption = self.zone_widgets[zone.zone]
                    number.configure(text=distance, fg=color)
                    caption.configure(text=status, fg=color)
            urgent = max((z.level for z in report.zones if not z.suppress_audio), default=0)
            self.alert.configure(text=('', 'VẬT Ở GẦN', 'VẬT RẤT GẦN')[urgent], fg=(MUTED, WARNING, DANGER)[urgent])
            self.overview.configure(text=('Đang quan sát phía trước · Cảnh báo theo mức độ tiếp cận', 'Có vật ở gần · Chú ý tín hiệu cảnh báo', 'Vật rất gần · Chú ý tín hiệu cảnh báo')[urgent], fg=(MUTED, WARNING, DANGER)[urgent])
            if report.status != 'ok':
                self.overview.configure(text='Depth chưa đầy đủ · Không thể kết luận đường trống', fg=WARNING)
                self.alert.configure(text='DEPTH CHƯA ĐẦY ĐỦ', fg=WARNING)
            task = 'Tìm vật · Đang nhận diện ảnh chụp' if finder.busy else 'Đọc văn bản · Đang xử lý ảnh chụp' if reader.busy else 'Sẵn sàng · Chọn một thao tác hoặc ra lệnh bằng giọng nói'
            self.task_status.configure(text=task)
            for name, module in (('Tìm vật', finder), ('Đọc văn bản', reader)):
                if not module.busy and module.status in {'error', 'unavailable', 'no_frame', 'stale', 'timeout'}:
                    self.task_status.configure(text=f'{name} · {STATES[module.status]}. Kiểm tra thiết bị hoặc thử lại.', fg=WARNING)
                    break
            else:
                self.task_status.configure(fg=TEXT)
            speech = 'Đã tắt' if audio.speech is None else STATES.get(audio.speech.state, 'Chưa sẵn sàng')
            self.micro_status.configure(text=f"Micro: {STATES.get(voice.state, 'Sẵn sàng')}   ·   Giọng đọc: {speech}", fg=ACCENT if voice.listening else MUTED)
            if voice.state == 'error':
                self.micro_status.configure(text='Micro chưa sẵn sàng · Kiểm tra kết nối rồi bấm V để thử lại.', fg=WARNING)
            if audio.player.error:
                self.micro_status.configure(text='Không phát được âm báo · Kiểm tra thiết bị âm thanh.', fg=DANGER)
            caption = 'Âm thanh: đã tắt                   M' if audio.muted else 'Âm thanh: đang bật              M'
            if self.mute_button.cget('text') != caption:
                self.mute_button.configure(text=caption, fg=WARNING if audio.muted else TEXT)
                self._native_caption(self.mute_button, caption)
        self.window.update_idletasks()
        self.window.update()

    def _key(self, event):
        if event.widget is self.selector:
            return
        action = KEYS.get(event.keysym.lower()) or KEYS.get(event.keysym)
        if action:
            self.events.put(action)
            return 'break'

    def _enter(self, event):
        if isinstance(event.widget, tk.Button):
            event.widget.invoke()
            return 'break'

    def _native_captions(self):
        for button, caption in self.buttons:
            self._native_caption(button, caption)

    def _native_caption(self, button, caption):
        import os
        if os.name == 'nt':
            import ctypes as ct
            set_text = ct.windll.user32.SetWindowTextW
            set_text.argtypes, set_text.restype = [ct.c_void_p, ct.c_wchar_p], ct.c_int
            set_text(button.winfo_id(), caption)

    def poll(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        if not self.closed:
            self.closed = True
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
