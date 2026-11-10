# ThirdEyes — nguyên mẫu RGB/depth

Mức triển khai hiện tại: lấy ảnh màu và depth từ **Kinect for Windows model 1517 (Kinect v1)**, hiển thị cạnh nhau. Chưa có model AI, OCR, cảnh báo vật cản, tìm đồ vật hoặc giọng nói.

## Chạy nhanh

Project được đặt tại `E:\ThirdEyes`.

1. Kết nối nguồn điện riêng và USB của Kinect với laptop.
2. Nếu chưa có môi trường Python, chạy `setup.bat` một lần.
3. Chạy **`run.bat`** để xem camera thật.
4. Chạy **`demo.bat`** để xem dữ liệu giả lập khi chưa cắm Kinect.
5. Nhấn **Q**, **Esc**, hoặc đóng cửa sổ để thoát.

Chế độ mặc định luôn dùng Kinect thật. Chương trình không tự chuyển sang dữ liệu giả khi kết nối thất bại. Demo có nhãn `DEMO - SYNTHETIC DATA` và `SIMULATED`.

## Môi trường

- Windows, Python **3.14 x64** (phiên bản đang có trên máy và dùng để kiểm thử).
- Microsoft **Kinect for Windows SDK/Runtime 1.8**, cung cấp `Kinect10.dll` và driver. Máy đã có SDK 1.8 tại thời điểm tạo project.
- NumPy và OpenCV, phiên bản cố định trong `requirements.txt`.
- Dùng `ctypes` trong thư viện chuẩn Python để gọi SDK; không cần PyKinect cũ, PyKinect2, CUDA hoặc model tải xuống.
- SDK 1.8 là phần mềm cũ; khả năng hoạt động trên Windows mới phụ thuộc driver, cổng USB và thiết bị. Cần kiểm chứng trên Kinect thực tế.

Nếu cài lại từ đầu:

```powershell
cd E:\ThirdEyes
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Không cần kích hoạt venv hay đổi ExecutionPolicy.

## Lệnh khác

```powershell
# Kiểm tra runtime và số cảm biến (mã thoát 1 nếu không thấy camera)
.\.venv\Scripts\python.exe main.py --diagnose

# Kiểm tra luồng giả lập không mở cửa sổ
.\.venv\Scripts\python.exe main.py --demo --headless --max-frames 30

# Kiểm thử biên dữ liệu native, không cần camera
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Nhật ký nằm trong `logs/thirdeyes.log`, tự xoay file khi đạt 1 MB. Không lưu ảnh camera tự động.

## Bảy module

| # | Vị trí | Trạng thái |
|---|---|---|
| 1 | `thirdeyes/capture/` | Đọc Kinect RGB/depth và timestamp; có nguồn demo riêng |
| 2 | `thirdeyes/depth_processing.py` | Placeholder ánh xạ RGB–depth và tính khoảng cách vùng |
| 3 | `thirdeyes/obstacle_detection.py` | Placeholder cảnh báo vật cản |
| 4 | `thirdeyes/ocr.py` | Placeholder phát hiện/nhận dạng chữ |
| 5 | `thirdeyes/object_finding.py` | Placeholder tìm đồ vật |
| 6 | `thirdeyes/coordinator_audio.py` | Placeholder điều phối và âm thanh |
| 7 | `thirdeyes/ui_logging.py` | Hiển thị RGB/depth và ghi nhật ký; chưa có nút gọi AI |

`app.py` điều khiển vòng lặp và tạo các module; `contracts.py` chứa kiểu dữ liệu chung. Module 2–6 có phương thức `process()` trả `PlaceholderResult(status="not_implemented")`; chúng chưa tham gia xử lý khung hình. Chế độ cảnh báo vật cản chỉ được khai báo là mặc định cho bước phát triển sau.

## Quy ước dữ liệu

- `FrameBundle.rgb`: mảng NumPy `uint8`, kích thước 480×640×3, thứ tự **RGB**. Khi hiển thị bằng OpenCV mới đổi sang BGR.
- `FrameBundle.depth_mm`: mảng `uint16`, kích thước 480×640, đơn vị **mm**, đã bỏ 3 bit player index của texture SDK 1.x.
- Mỗi luồng có timestamp thiết bị (ms) và thời điểm nhận `time.monotonic()` riêng.
- Đây là **hai khung mới nhất của hai luồng độc lập**, chưa ghép đồng bộ và chưa ánh xạ pixel RGB sang depth. Không dùng cùng tọa độ pixel ở hai ảnh để suy ra khoảng cách vật thể.
- Bản đồ màu depth chỉ để hiển thị: khoảng 0,8–4,0 m cố định, màu nóng gần hơn, màu lạnh xa hơn. Điểm không hợp lệ/ngoài khoảng hiển thị màu đen. Mảng depth gốc giữ nguyên các mã 0, 4095, 8191 của SDK.
- `WAITING`: chưa có ảnh; `STALE`: không cập nhật hơn 2 giây. Sau mặc định 10 giây thiếu một trong hai luồng, chương trình báo lỗi và giải phóng camera. Có thể đổi bằng `--timeout 20`.

## Khi không nhận camera

1. Chạy `main.py --diagnose` bằng Python trong `.venv`.
2. Nếu thiếu `Kinect10.dll`, cài SDK/Runtime **1.8**, không dùng SDK 2.0 cho model 1517.
3. Nếu số cảm biến bằng 0, kiểm tra adapter nguồn, cáp USB và driver trong Device Manager.
4. Đóng Kinect Studio hoặc ứng dụng khác đang dùng Kinect; thử cổng USB trực tiếp khác.
5. Nếu thấy HRESULT trong log, giữ nguyên mã đó để chẩn đoán. Không đổi driver bằng Zadig/libfreenect khi đang dùng backend SDK Microsoft này.

## Nguồn tham khảo

- [Kinect for Windows SDK 1.8 — Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=40278)
- [Các dòng Kinect và model 1517 — tài liệu của tác giả Kinect 3D Video](https://www.cs.ucdavis.edu/~okreylos/ResDev/Kinect/MainPage.html)
- Khai báo native đối chiếu với `NuiApi.h`, `NuiImageCamera.h`, `NuiSensor.h` trong thư mục `inc` của SDK 1.8 đã cài trên máy.

Đây là nguyên mẫu để phát triển trong môi trường có kiểm soát; hiện chưa thực hiện chức năng hỗ trợ di chuyển.
