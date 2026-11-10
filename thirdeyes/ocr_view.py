"""Unicode result window and boxes on the captured snapshot, never on live RGB."""
import cv2
import numpy as np


class OCRView:
    def __init__(self):
        self.window = None
        self.widget = None
        self.closed = False

    def show(self, result, rgb):
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText
        if self.window is None:
            self.window = tk.Tk()
            self.window.title("ThirdEyes - Kết quả đọc văn bản (ảnh chụp)")
            self.window.geometry("720x480")
            self.window.protocol("WM_DELETE_WINDOW", self.close)
            self.widget = ScrolledText(self.window, wrap=tk.WORD, font=("Arial", 14), padx=15, pady=15)
            self.widget.pack(fill=tk.BOTH, expand=True)
        content = f"Trạng thái: {result['status']}\nThời gian: {result.get('total_ms', 0)} ms\n\n"
        content += result.get("text") or result.get("speak", "Chưa có kết quả.")
        if result.get("rejected_regions"):
            content += "\n\nMột số vùng chữ bị bỏ qua do điểm tin cậy thấp."
        if result.get("truncated"):
            content += "\n\nNội dung đã giới hạn độ dài; hãy chia thành đoạn nhỏ hơn."
        if result.get("error"):
            content += "\n\nChi tiết lỗi: " + result["error"]
        if result.get("text_raw") and result.get("text_raw") != result.get("text"):
            content += "\n\nOCR gốc (có thể chưa đủ tin cậy):\n" + result["text_raw"]
        self.widget.configure(state=tk.NORMAL)
        self.widget.delete("1.0", tk.END)
        self.widget.insert(tk.END, content)
        self.widget.configure(state=tk.DISABLED)
        if rgb is not None:
            snapshot = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            for region in result.get("regions", []):
                points = np.asarray(region["box"], np.int32).reshape((-1, 1, 2))
                color = (0, 220, 0) if region["accepted"] else (0, 150, 255)
                cv2.polylines(snapshot, [points], True, color, 2)
            cv2.imshow("ThirdEyes | OCR captured snapshot", snapshot)
        self.pump()

    def pump(self):
        if self.window is not None:
            try:
                self.window.update_idletasks()
                self.window.update()
            except Exception:
                self.window = None

    def close(self):
        if self.window is not None:
            self.window.destroy()
            self.window = None
