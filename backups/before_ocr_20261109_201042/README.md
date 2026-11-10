# ThirdEyes — RGB/depth và cảnh báo vật cản

Project: `E:\ThirdEyes`. Kinect for Windows model 1517, SDK/Runtime 1.8, Python 3.14 x64, NumPy và OpenCV. Không cần thêm model AI hoặc thư viện so với bản trước.

## Chạy

- Mở `run.bat`: camera thật và cảnh báo âm thanh bật mặc định.
- Mở `demo.bat`: chu kỳ giả lập 18 giây, có nhãn rõ ràng.
- **Q/Esc**: thoát; **M**: tắt/bật âm báo; **T**: thử một âm ngắn khi không tắt tiếng.
- Đọc `docs/OBSTACLE_MODULE.md` để xem hành vi, các ngưỡng và giới hạn.

```powershell
cd E:\ThirdEyes
.\.venv\Scripts\python.exe main.py --demo --scenario stationary
.\.venv\Scripts\python.exe main.py --demo --scenario approach
.\.venv\Scripts\python.exe main.py --demo --scenario invalid
.\.venv\Scripts\python.exe main.py --mute
.\.venv\Scripts\python.exe main.py --test-sound
.\.venv\Scripts\python.exe main.py --diagnose
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Có sẵn `.venv`. Nếu cài lại: chạy `setup.bat`, hoặc `python -m venv .venv` rồi `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Không cần kích hoạt venv/đổi ExecutionPolicy.

## Cấu trúc

| Module | File/thư mục | Trạng thái |
|---|---|---|
| 1. Thu nhận | `thirdeyes/capture/` | Kinect RGB/depth 640×480 + timestamp; demo giả lập |
| 2. Xử lý depth | `thirdeyes/depth_processing.py` | Lọc dữ liệu, đo các cụm trong vùng phía trước; chưa ánh xạ RGB–depth |
| 3. Vật cản | `thirdeyes/obstacle_detection.py` | Khoảng cách, tốc độ tiến gần tương đối, xác nhận, hysteresis |
| 4. OCR | `thirdeyes/ocr.py` | Placeholder |
| 5. Tìm vật | `thirdeyes/object_finding.py` | Placeholder |
| 6. Điều phối/âm thanh | `thirdeyes/coordinator_audio.py` | Âm ngắn không chặn camera, chống lặp, ưu tiên, tắt tiếng; chưa có TTS |
| 7. UI/nhật ký | `thirdeyes/ui_logging.py` | RGB/depth, ROI, ba vùng nguy cơ, trạng thái âm thanh, log |

`app.py` nối pipeline; `contracts.py` định nghĩa dữ liệu; `config.py` đọc/kiểm tra cấu hình. Ngưỡng nằm trong `config/obstacles.json`, được đọc lúc khởi động. Sửa file rồi chạy lại. Có thể truyền `--config DUONG_DAN`.

## Dữ liệu và trạng thái

- `FrameBundle.rgb`: uint8 RGB 480×640×3; `depth_mm`: uint16 mm 480×640. Dữ liệu depth gốc không bị sửa để tô màu.
- RGB/depth là hai khung mới nhất độc lập, chưa đồng bộ và chưa ánh xạ pixel. Khung ROI chỉ vẽ lên ảnh depth.
- `DepthObservation` chứa các cụm và chất lượng; `ObstacleReport` chứa nguy cơ trái/giữa/phải; `SoundEvent` chuyển cho bộ âm thanh.
- `MONITORING`: chưa xác nhận vật cản theo các ngưỡng; `NEAR`: gần; `URGENT`: rất gần/tiến nhanh; `LOW CONFIDENCE`: vùng có phần không đo được.
- `Depth: PARTIAL/INVALID/STALE` không có nghĩa là đường trống. Điểm đen có thể là ngoài khoảng đo hoặc dữ liệu không hợp lệ.
- `Audio: ERROR`: đọc log, kiểm tra loa/Windows rồi chạy lại. Chương trình không thể tự xác nhận người dùng nghe được âm thanh.
- Nhật ký `logs/thirdeyes.log`, xoay file 1 MB. Chỉ ghi sự kiện/trạng thái, không tự lưu ảnh camera.

## Khi không nhận camera

Chạy `--diagnose`, kiểm tra nguồn riêng và USB, driver SDK **1.8**, đóng các ứng dụng khác đang dùng Kinect. SDK 2.0 không dành cho model 1517. Không tự chuyển sang dữ liệu giả nếu camera lỗi.

Không có depth mới hơn 0,6 giây: báo trạng thái mất độ tin cậy. Sau 10 giây thiếu RGB hoặc depth: báo lỗi và dừng (đổi bằng `--timeout`). Nhấn Ctrl+C hoặc đóng cửa sổ đều giải phóng camera và luồng âm thanh.

## Tham khảo

- [Kinect SDK 1.8 — Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=40278)
- [Kinect Human Interface Guidelines — Microsoft](https://download.microsoft.com/download/B/0/7/B070724E-52B4-4B1A-BD1B-05CC28D07899/Human_Interface_Guidelines_v1.7.0.pdf)
- [winsound — Python](https://docs.python.org/3/library/winsound.html)
- Khai báo native đối chiếu các header `NuiApi.h`, `NuiImageCamera.h`, `NuiSensor.h` của SDK đã cài.

Đây là nguyên mẫu thử nghiệm có kiểm soát; các ngưỡng chưa được hiệu chuẩn để hỗ trợ di chuyển độc lập.
