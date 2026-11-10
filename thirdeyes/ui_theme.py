"""Shared native desktop theme; no additional GUI dependency."""
import base64
import tkinter as tk
import cv2
import numpy as np

BG, SURFACE, CARD, BORDER = '#0b1220', '#111d30', '#18273c', '#2c405a'
TEXT, MUTED, ACCENT, WARNING, DANGER = '#edf4ff', '#aebed4', '#70e1c3', '#ffd08a', '#ff9cab'
FONT = 'Segoe UI'


def label(parent, text='', size=11, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                    font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)


class ImagePane(tk.Canvas):
    """Aspect-preserving RGB preview with bounded refresh controlled by its owner."""
    def __init__(self, parent, placeholder='Đang chờ hình ảnh…'):
        super().__init__(parent, bg='#070d17', highlightthickness=0, width=320, height=240)
        self.frame, self.photo, self.placeholder = None, None, placeholder
        self.bind('<Configure>', lambda _e: self.display(self.frame))

    def display(self, rgb):
        self.frame = rgb
        w, h = max(1, self.winfo_width()), max(1, self.winfo_height())
        self.delete('all')
        if rgb is None:
            self.create_text(w/2, h/2, text=self.placeholder, fill=MUTED, font=(FONT, 12), width=max(1, w-40))
            return
        ih, iw = rgb.shape[:2]
        scale = min(w/iw, h/ih)
        resized = cv2.resize(rgb, (max(1, int(iw*scale)), max(1, int(ih*scale))), interpolation=cv2.INTER_AREA)
        success, png = cv2.imencode('.png', cv2.cvtColor(resized, cv2.COLOR_RGB2BGR))
        if success:
            self.photo = tk.PhotoImage(master=self, data=base64.b64encode(png.tobytes()), format='png')
            self.create_image(w/2, h/2, image=self.photo)


def result_snapshot(rgb, result):
    if rgb is None:
        return None
    snapshot = rgb.copy()
    for index, region in enumerate(result.get('regions', []), 1):
        points = np.asarray(region['box'], np.int32).reshape((-1, 1, 2))
        color = (112, 225, 195) if region.get('accepted', True) else (255, 208, 138)
        cv2.polylines(snapshot, [points], True, color, 2)
        if 'clock_hour' in region:
            hour = region['clock_hour']
            caption = f'{index} | {hour}h' if hour else f'{index} | CENTER'
            depth = region.get('depth', {})
            caption += f" | {depth['distance_m']:.1f} m" if depth.get('status') == 'ok' else ' | ? m'
            if region.get('preferred'):
                caption = '* ' + caption
            x, y = points[0, 0]
            cv2.putText(snapshot, caption, (max(0, int(x)), max(20, int(y)-8)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2)
    return snapshot
