# Đánh giá và tích hợp text_reader vào ThirdEyes

Ngày: 09/11/2026. Nguồn được cung cấp: `C:\Users\FPTSHOP\Downloads\text_reader_module\text_reader_module`. Thư mục gốc được giữ nguyên.

## Kết luận

**Phù hợp về kiến trúc nhận ảnh và hướng nhận dạng tiếng Việt, nhưng không thể ghép trực tiếp vào môi trường ThirdEyes hiện có.** Đã thích nghi phần PaddleOCR phát hiện vùng chữ + VietOCR nhận dạng, chạy thành một dịch vụ con ngoại tuyến theo yêu cầu, dùng RGB từ camera Kinect hiện có.

## Vấn đề của bản bàn giao

| Vấn đề | Ảnh hưởng khi ghép trực tiếp | Xử lý đã thực hiện |
|---|---|---|
| Python 3.10, NumPy 1.26 và Paddle 2.x; ThirdEyes đang dùng Python 3.14/NumPy 2.x | Không dùng được cùng môi trường; có thể phá phần camera đang hoạt động | Môi trường `.ocr-venv` và Python `.runtimes` riêng, trao đổi qua ảnh/JSON tạm |
| Nhiều gói kéo các bản OpenCV khác nhau; VietOCR 0.3.13 khóa Pillow 10.2 | Cài tự do dễ xung đột hoặc ghi đè DLL | Khóa bộ runtime suy luận, chỉ một `opencv-contrib-python` trong OCR, không thay dependency của camera |
| Import/nạp model và `read()` đồng bộ | Có thể đóng băng hiển thị/cảnh báo vật cản | Tiến trình con + luồng điều phối, giới hạn 2 CPU threads, ưu tiên tiến trình thấp hơn |
| Module nhận BGR; `FrameBundle` của ThirdEyes là RGB | Sai màu đầu vào | Chuyển RGB→BGR một lần trên ảnh chụp đã copy |
| Timestamp `time.time()` khác `time.monotonic()` của dự án | Có thể luôn bị coi là dữ liệu cũ nếu truyền trực tiếp | Kiểm tra tuổi khung bằng monotonic ở bên camera; lưu thời điểm chụp dạng wall-clock riêng |
| `KinectV1Source` dùng libfreenect, mới là bản nháp | Trùng nguồn camera/driver với SDK 1.8 | Không dùng nguồn camera của module gốc; dùng chung nguồn Kinect hiện có |
| `PaddleOCR(...)` tạo cả pipeline ngoài detector; dùng cấu hình/tải từ xa | Nạp phần không cần thiết, lần đầu/cấu hình có thể cần mạng | Khởi tạo riêng TextDetector CPU với model local; cấu hình VietOCR đọc local |
| Cắt vùng chữ bằng bounding rectangle; sắp xếp bằng làm tròn Y/15 | Chữ nghiêng bị cắt không phù hợp, thứ tự đọc nhảy giữa các bin | Chỉnh phối cảnh theo tứ giác, nhóm dòng theo chiều cao chữ |
| Chỉ trả chuỗi, thiếu vị trí và điểm nhận dạng | Khó kiểm tra vùng nào đã đọc sai | Trả polygon về tọa độ ảnh gốc, điểm tin cậy từng vùng, đánh dấu vùng bị bỏ |
| `speak(block=False)` vẫn tạo giọng đồng bộ trước khi trả về; không có ưu tiên vật cản | Camera có thể bị chặn; giọng đọc chồng lên âm báo | SAPI bất đồng bộ trong tiến trình riêng; bộ điều phối dừng giọng trước khi gửi âm báo |
| TTS Edge, nhận giọng Google và LLM cần mạng | Không đáp ứng lựa chọn ngoại tuyến của người dùng | Không tích hợp các đường gọi này; không ghi/sử dụng API key |
| Không có hủy/timeout/quản lý kết quả muộn; file TTS tạm không có vòng đời đầy đủ | Tác vụ treo, kết quả cũ phát sau khi đã dừng, rác file | X hủy và dừng worker; timeout; ID tác vụ; một yêu cầu tại một thời điểm; dọn file tạm |

Ngưỡng mờ 100 của bản gốc chưa hiệu chuẩn theo Kinect. Bản thử đặt 35, có thể chỉnh trong cấu hình; đây không phải giá trị đã tối ưu trên bộ ảnh camera thực tế. Không dùng LLM để “làm đẹp” nội dung vì có thể thay tên riêng, số hoặc ý nghĩa.

## Luồng sử dụng

1. `run.bat` mở RGB/depth và tiếp tục cảnh báo vật cản.
2. Bấm **O**: lấy một bản sao ảnh RGB còn mới, trả quyền điều khiển ngay cho vòng camera.
3. Worker OCR xử lý ảnh trong `.ocr-venv`; model được giữ để dùng lại giữa các lượt.
4. Kết quả hiển thị bằng chữ tiếng Việt trong cửa sổ riêng và các khung vùng chữ trên ảnh chụp.
5. Nếu có giọng tiếng Việt SAPI và âm thanh không tắt, bộ điều phối gửi nội dung cần đọc. Âm báo vật cản luôn được ưu tiên; khi bị ngắt, bấm **R** để đọc lại.
6. **X** hủy OCR và dừng giọng đọc; **M** tắt/bật toàn bộ âm thanh. Kết quả đã hủy không được tự phát muộn.

Nếu OCR chưa cài hoặc cấu hình OCR lỗi, giao diện báo `unavailable` và phần camera/vật cản tiếp tục hoạt động. Các trạng thái gồm `working`, `ok`, `blurry`, `no_text`, `low_confidence`, `stale`, `error`, `timeout`, `cancelled`.

## Ngoại tuyến và giọng đọc

Theo lựa chọn của người dùng, **không dùng dịch vụ TTS/ASR/LLM trực tuyến**. Bước cài đặt đã tải model về `models/ocr`; model và cấu hình được lưu nguồn/SHA-256, script cài lại kiểm tra checksum. Khi chạy, thiếu model sẽ báo lỗi, không tự tải từ Internet.

Máy được kiểm tra chỉ có Microsoft David/Zira tiếng Anh trong SAPI. Vì vậy **chưa thể phát tiếng Việt ngoại tuyến trên máy này bằng backend đã chọn**. Hệ thống vẫn OCR và hiển thị đầy đủ, báo `no_vi_voice`; không đọc tiếng Việt bằng giọng Anh. Sau khi có giọng tiếng Việt tương thích SAPI, khởi động lại để tự nhận. TTS thực tế bằng giọng Việt chưa kiểm chứng do chưa có giọng; thứ tự ưu tiên/ngắt âm được kiểm thử bằng bộ phát giả lập.

Nội dung ảnh/chữ không được gửi ra mạng, không có API key và không dùng micro. Ảnh chụp, kết quả JSON chỉ lưu tạm để giao tiếp giữa tiến trình và được dọn khi hoàn tất/hủy/timeout bình thường. Nội dung OCR không được ghi vào log hoạt động.

## Cấu hình OCR

| Khóa trong `config/ocr.json` | Mặc định | Ý nghĩa |
|---|---:|---|
| `blur_threshold` | 35 | Ngưỡng phương sai Laplacian trên ảnh gốc |
| `upscale` | 2,0 | Phóng ảnh; cạnh dài đầu vào model giới hạn 1.280 px |
| `min_confidence` | 0,50 | Bỏ khỏi nội dung đọc các vùng có điểm thấp; vẫn giữ OCR gốc để xem |
| `max_regions` | 40 | Giới hạn số vùng trong một lượt |
| `max_characters` | 3.000 | Giới hạn nội dung đọc, có báo cắt ngắn |
| `frame_max_age_s` | 1,0 | Tuổi tối đa của khung RGB khi người dùng yêu cầu |
| `timeout_s` | 90 | Quá thời gian thì dừng worker, báo timeout |
| `cpu_threads` | 2 | Giới hạn CPU cho OCR |

Điểm tin cậy của VietOCR là điểm nội bộ mô hình, chưa được hiệu chuẩn thành xác suất đúng trên ảnh Kinect. Dữ liệu camera 640×480, chữ quá nhỏ, giấy cong, ánh sáng kém, bố cục nhiều cột/bảng vẫn có thể đọc sai.

## Kết quả kiểm chứng

- **62/62 kiểm thử** bằng Python của `.ocr-venv`, gồm các kiểm thử camera/vật cản cũ và các kiểm thử mới cho OCR, đổi màu, stale, hủy, timeout, worker lỗi, cấu hình lỗi, lọc điểm tin cậy, giới hạn kết quả và ưu tiên âm báo.
- Đọc ảnh kiểm thử 640×480 có 4 dòng tiếng Việt: nhận đúng nội dung chính, dấu tiếng Việt và `125.000`; bỏ 2 dấu chấm cuối câu so với đáp án. Không tuyên bố độ chính xác tổng quát từ ảnh này.
- Ảnh cùng nội dung nghiêng 10°: kết quả tương tự ảnh thẳng.
- Ảnh trắng: trả `blurry`, không sinh/đọc bừa nội dung.
- Lần chạy đo cùng pipeline vật cản: lần đầu khoảng **20,3 giây** (gồm nạp model), suy luận khoảng **5,1 giây**; lượt ảnh nghiêng tiếp theo khoảng **4,6 giây**. Một lần kiểm tra trước đó tải lần đầu khoảng 15,3 giây; thời gian phụ thuộc tải máy.
- Trong lượt đầu, pipeline vật cản vẫn xử lý **528 vòng**; đã ghi nhận các sự kiện gần/khẩn/mất depth đúng chu kỳ demo. Thời gian xử lý một bước vật cản lớn nhất quan sát khoảng **26,3 ms** trong phép thử, không phải cam kết thời gian thực.
- Model chạy được trong phiên shell hạn chế mạng với model local. Không sử dụng dịch vụ trực tuyến để đạt kết quả OCR.
- Bản cài đã chạy đồng thời với Kinect thật **850 vòng hiển thị**, nhận đủ RGB/depth và thoát bình thường. Trong lúc OCR hoạt động vẫn có sự kiện cảnh báo khẩn từ depth. Ảnh RGB đầu tiên được yêu cầu đọc ở lần này trả `blurry` sau khoảng 8,3 giây gồm nạp model; chưa dùng kết quả đó để tuyên bố độ chính xác đọc chữ qua camera. Cửa sổ kết quả được mở, thư mục job tạm trống sau khi hoàn tất.
- Kiểm tra SAPI trực tiếp trả `no_vi_voice`, đúng với hai giọng tiếng Anh được liệt kê. Bản trước khi tích hợp được sao lưu tại `E:\ThirdEyes\backups\before_ocr_20261109_201042`.

Ảnh và dữ liệu kiểm thử nằm tại `tests/assets/`. Có thể chạy:

```powershell
cd E:\ThirdEyes
.\.venv\Scripts\python.exe main.py --ocr-image tests\assets\ocr_sample.png
.\.ocr-venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Phạm vi còn lại

Chưa tích hợp lệnh giọng nói, hiệu chỉnh LLM hay nguồn Kinect libfreenect của gói gốc. Chưa đo CER/WER trên tập ảnh Kinect thật có đáp án; chưa kiểm chứng TTS tiếng Việt do thiếu giọng. Module tìm đồ vật vẫn là placeholder. Các ngưỡng vật cản được giữ theo cấu hình đang có trong project; bộ mốc đề xuất ở trao đổi trước chưa được tự áp dụng trong đợt tích hợp OCR này.

## Nguồn kỹ thuật

- Mã `ocr_reader.py`, `tts.py`, `frame_source.py`, `voice_command.py`, README và requirements của module người dùng cung cấp.
- [PaddlePaddle 2.6.2: bản Windows Python 3.10](https://pypi.org/project/paddlepaddle/2.6.2/)
- [VietOCR — tác giả](https://github.com/pbcquoc/vietocr)
- [PaddleOCR TextDetector — mã nguồn](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/tools/infer/predict_det.py)
- [uv: quản lý Python riêng](https://docs.astral.sh/uv/guides/install-python/)
