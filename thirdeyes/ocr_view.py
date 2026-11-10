"""Unicode result window and boxes on the captured snapshot, never on live RGB."""
import cv2
import numpy as np


class OCRView:
    def __init__(self, title='ThirdEyes - Kết quả đọc văn bản (ảnh chụp)', snapshot_title='ThirdEyes | OCR captured snapshot'):
        self.title = title
        self.snapshot_title = snapshot_title
        self.window = None
        self.widget = None
        self.closed = False

    def show(self, result, rgb):
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText
        if self.window is None:
            self.window = tk.Tk()
            self.window.title(self.title)
            self.window.geometry("720x480")
            self.window.protocol("WM_DELETE_WINDOW", self.close)
            self.widget = ScrolledText(self.window, wrap=tk.WORD, font=("Arial", 14), padx=15, pady=15)
            self.widget.pack(fill=tk.BOTH, expand=True)
        content = f"Trạng thái: {result['status']}\nThời gian: {result.get('total_ms', 0)} ms\n\n"
        content += result.get("text") or result.get("speak", "Chưa có kết quả.")
        content += f"\n\nRGB–depth: {result.get('rgbd_status', 'unpaired')}"
        if result.get('rgbd_skew_ms') is not None:
            content += f" (lệch {result['rgbd_skew_ms']} ms)"
        for i, region in enumerate(result.get('regions', []), 1):
            depth = region.get('depth', {})
            region_name = 'Vật' if 'target_label' in result else 'Vùng chữ'
            if depth.get('status') == 'ok':
                content += f"\n{region_name} {i}: khoảng {depth['distance_m']:.2f} m"
            elif depth:
                content += f"\n{region_name} {i}: chưa đo được ({depth['status']})"
            if 'clock_hour' in region:
                content += f" | {region['clock_hour']} giờ" if region['clock_hour'] else ' | Chính giữa'
        if result.get("rejected_regions"):
            content += "\n\nMột số vùng chữ bị bỏ qua do điểm tin cậy thấp."
        if result.get("truncated"):
            content += ("\n\nCòn các vật cùng loại khác trong ảnh." if 'target_label' in result else
                        "\n\nNội dung đã giới hạn độ dài; hãy chia thành đoạn nhỏ hơn.")
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
                if 'clock_hour' in region:
                    hour = region['clock_hour']
                    label = f'{hour}h' if hour else 'CENTER'
                    depth = region.get('depth', {})
                    label += f" | {depth['distance_m']:.1f} m" if depth.get('status') == 'ok' else ' | depth ?'
                    x, y = points[0, 0]
                    cv2.putText(snapshot, label, (max(0, int(x)), max(18, int(y)-8)),
                                cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
                    if depth.get('roi'):
                        roi = np.asarray(depth['roi'], np.int32).reshape((-1, 1, 2))
                        cv2.polylines(snapshot, [roi], True, (0, 220, 255), 1)
            cv2.imshow(self.snapshot_title, snapshot)
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
