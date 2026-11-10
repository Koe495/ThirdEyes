# ThirdEyes — camera, cảnh báo vật cản và đọc văn bản ngoại tuyến

Project: `E:\ThirdEyes`. Kinect for Windows model 1517, SDK/Runtime 1.8.

## Dùng nhanh

Mở `run.bat`. Cảnh báo vật cản luôn xử lý depth; đọc chữ chỉ chạy khi yêu cầu.

| Phím trong cửa sổ camera | Thao tác |
|---|---|
| O | Chụp ảnh RGB hiện tại và đọc chữ; không nhận thêm yêu cầu khi đang bận |
| R | Đọc lại kết quả thành công gần nhất, nếu có giọng tiếng Việt ngoại tuyến |
| X | Hủy OCR đang chạy và dừng đọc thành tiếng |
| M | Tắt/bật toàn bộ âm thanh |
| T | Thử một âm báo ngắn |
| Q/Esc | Thoát và giải phóng camera, OCR, âm thanh |

Khi kết quả OCR xuất hiện, có cửa sổ chữ tiếng Việt và ảnh chụp với khung vùng chữ. Khung chữ thuộc **ảnh chụp tại thời điểm bấm O**, không được vẽ đè lên ảnh camera đang thay đổi. Bấm phím điều khiển trong cửa sổ camera; cửa sổ kết quả hỗ trợ chọn/copy văn bản.

Máy hiện chỉ có giọng SAPI tiếng Anh. `no_vi_voice` nghĩa là **OCR vẫn đọc được chữ**, nhưng chưa đọc thành tiếng tiếng Việt. Sau khi cài một giọng **tiếng Việt có hỗ trợ SAPI** trên Windows, khởi động lại chương trình. Gói ngôn ngữ/giọng OneCore không nhất thiết được SAPI nhìn thấy. Không dùng giọng Anh để giả lập đọc tiếng Việt, không dùng Edge TTS/Google Speech/LLM trực tuyến.

## Môi trường đã cài

- `.venv`: Python 3.14, NumPy 2.5.4, OpenCV 5.0 — camera/hiển thị/vật cản.
- `.ocr-venv`: Python 3.10.22, NumPy 1.26.4, OpenCV contrib 4.6, Paddle 2.6.2, PaddleOCR 2.7.3, VietOCR 0.3.13, Torch CPU 2.2.2 — đọc chữ trong tiến trình riêng.
- `.runtimes`: Python 3.10 riêng của project; không thay đổi Python/PATH toàn máy.
- `models/ocr`: model và cấu hình cục bộ; OCR không tải model khi đang chạy.

Nếu cài lại: `setup.bat` cho phần chính, `setup_ocr.bat` cho OCR. **Bước cài đặt cần Internet để tải thư viện/model; hoạt động OCR và TTS sau đó là ngoại tuyến.** Không cài `requirements.txt` của module gốc vào `.venv` chính. File `requirements-ocr.lock.txt` là bộ phụ thuộc suy luận đã khóa; script dùng `--no-deps` để tránh kéo phần huấn luyện/xuất tài liệu và các bản OpenCV trùng nhau.

## Các lệnh

```powershell
cd E:\ThirdEyes
# Demo vật cản
.\.venv\Scripts\python.exe main.py --demo

# Đọc ảnh kiểm thử, không mở camera, không phát giọng, trả JSON
.\.venv\Scripts\python.exe main.py --ocr-image tests\assets\ocr_sample.png

# Tắt riêng giọng đọc, vẫn giữ âm báo vật cản
.\.venv\Scripts\python.exe main.py --no-speech

# Chụp đọc một lần khi camera bắt đầu có RGB
.\.venv\Scripts\python.exe main.py --read-once

# Chẩn đoán Kinect
.\.venv\Scripts\python.exe main.py --diagnose

# Toàn bộ kiểm thử, gồm kiểm thử kết quả nhận dạng cần Pillow
.\.ocr-venv\Scripts\python.exe -m unittest discover -s tests -v
```

OCR thực tế mất vài giây trên CPU. Lần đầu cần nạp model nên lâu hơn. Có thể hủy bằng X; sau khi hủy, lần tiếp theo sẽ nạp lại model. Lần đọc đầu không chặn camera hay phát hiện vật cản.

## Bảy module

| Module | Vị trí | Trạng thái |
|---|---|---|
| Thu nhận | `thirdeyes/capture/` | RGB/depth Kinect 640×480, SDK 1.8 |
| Xử lý depth | `thirdeyes/depth_processing.py` | Lọc cụm depth; chưa ánh xạ RGB–depth |
| Vật cản | `thirdeyes/obstacle_detection.py` | Khoảng cách, tiến gần, chống lặp |
| OCR | `thirdeyes/ocr.py`, `ocr_runtime/text_reader/` | Chụp theo yêu cầu, Paddle detector + VietOCR ngoại tuyến |
| Tìm vật | `thirdeyes/object_finding.py` | Placeholder |
| Điều phối/âm thanh | `thirdeyes/coordinator_audio.py`, `thirdeyes/speech.py` | Âm báo ưu tiên, dừng giọng đọc khi báo vật cản; SAPI ngoại tuyến |
| UI/log | `thirdeyes/ui_logging.py`, `thirdeyes/ocr_view.py` | Camera, nguy cơ, trạng thái OCR, cửa sổ kết quả tiếng Việt |

## Cấu hình và dữ liệu

- `config/obstacles.json`: cấu hình vật cản hiện hành. Xem `docs/OBSTACLE_MODULE.md`.
- `config/ocr.json`: độ mờ, phóng ảnh, lọc điểm tin cậy, giới hạn số vùng/ký tự, timeout. Xem `docs/OCR_INTEGRATION.md`.
- `logs/thirdeyes.log`: trạng thái, thời gian và sự kiện; không ghi nội dung chữ nhận dạng.
- `logs/ocr_worker.log`: chẩn đoán tiến trình OCR; được ghi mới mỗi lần khởi động worker.
- `runtime/ocr_jobs`: ảnh và kết quả tạm giữa hai tiến trình. Dọn sau tác vụ, hủy và timeout trong quá trình đóng bình thường; hệ điều hành tắt đột ngột có thể để lại file tạm.
- Nội dung OCR giữ trong bộ nhớ và cửa sổ kết quả; không tự tải lên dịch vụ bên ngoài.

## Giới hạn

Độ nét/chữ nhỏ của Kinect 640×480 vẫn là giới hạn thật; phóng ảnh không tạo lại nét chữ đã mất. OCR có thể sai dấu, số và dấu câu; điểm tin cậy không đảm bảo văn bản đúng. Thuật toán thứ tự đọc phù hợp dòng chữ đơn giản, chưa tối ưu trang nhiều cột/bảng. Khi âm báo vật cản ngắt giọng đọc, chương trình không tự đọc tiếp nội dung cũ; bấm R nếu cần.

Đây là nguyên mẫu thử nghiệm có kiểm soát. Cảnh báo vật cản, độ chính xác OCR và khả năng nghe cần kiểm tra trên tình huống thực tế của người dùng.
