# ThirdEyes — hỗ trợ nhận biết môi trường bằng hình ảnh và âm thanh

Project: `E:\DeepLearning\ThirdEyes`. Kinect for Windows model 1517, SDK/Runtime 1.8.


## Cập nhật 10/11/2026

Kinect RGB/depth đã **lật ngang mặc định** trước UI, OCR và phân tích vật cản. Vật vừa xuất hiện gần giới hạn đo rồi đi xa được quan sát hướng và không báo chỉ vì vừa xuất hiện. Nếu dừng gần hoặc quay lại, cảnh báo được đánh giá lại. Chạy `main.py --demo --scenario retreat` để thử. Chi tiết và các thông số mới nằm trong `docs/ORIENTATION_AND_RETREAT.md`.

## Dùng nhanh

Mở `run.bat`. Dashboard một cửa sổ gồm tab Trực tiếp và Kết quả. Cảnh báo vật cản xử lý depth; OCR và tìm vật chạy theo yêu cầu. Giọng Piper và nhận lệnh Vosk hoạt động ngoại tuyến. Xem [hướng dẫn giao diện](docs/INTERFACE.md) và [tìm vật](docs/OBJECT_FINDING.md).

| Phím trong cửa sổ ứng dụng | Thao tác |
|---|---|
| O | Chụp ảnh RGB hiện tại và đọc chữ; không nhận thêm yêu cầu khi đang bận |
| F | Tìm vật đã chọn; ưu tiên vật có khoảng cách hợp lệ gần nhất |
| V | Nghe lệnh tối đa 6 giây, ví dụ “tìm chai nước” |
| S | Đọc trạng thái hệ thống |
| R | Đọc lại kết quả tìm vật/OCR gần nhất |
| X | Hủy OCR/tìm vật đang chạy và dừng đọc thành tiếng |
| M | Tắt/bật toàn bộ âm thanh |
| T | Thử âm báo stereo trái → giữa → phải |
| Q/Esc | Thoát và giải phóng camera, OCR, âm thanh |

Kết quả OCR/tìm vật xuất hiện trong tab Kết quả, gồm ảnh chụp và nội dung tiếng Việt. Khung nhận diện thuộc ảnh chụp tại thời điểm yêu cầu, không vẽ lên ảnh camera đang thay đổi. Micro chỉ mở sau thao tác V.

## Môi trường đã cài

- `.venv`: Python 3.14, NumPy 2.5.4, OpenCV 5.0 — camera/hiển thị/vật cản.
- `.ocr-venv`: Python 3.10.22, NumPy 1.26.4, OpenCV contrib 4.6, Paddle 2.6.2, PaddleOCR 2.7.3, VietOCR 0.3.13, Torch CPU 2.2.2 — đọc chữ trong tiến trình riêng.
- `.object-venv`: Python 3.10.22, Torch CPU 2.2.2, Ultralytics 8.3.40 — YOLO11s trong tiến trình riêng.
- `.audio-venv`: Piper tiếng Việt và Vosk nhận lệnh ngoại tuyến.
- `.runtimes`: Python 3.10 riêng của project; không thay đổi Python/PATH toàn máy.
- `models/ocr`: model và cấu hình cục bộ; OCR không tải model khi đang chạy.

Nếu cài lại: `setup.bat` cho phần chính, `setup_ocr.bat` cho OCR, `setup_objects.bat` cho tìm vật và `setup_audio.bat` cho âm thanh/nhận lệnh. **Bước cài đặt cần Internet để tải thư viện/model; hoạt động OCR và TTS sau đó là ngoại tuyến.** Không cài `requirements.txt` của module gốc vào `.venv` chính. File `requirements-ocr.lock.txt` là bộ phụ thuộc suy luận đã khóa; script dùng `--no-deps` để tránh kéo phần huấn luyện/xuất tài liệu và các bản OpenCV trùng nhau.

## Các lệnh

```powershell
cd E:\DeepLearning\ThirdEyes
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
| Xử lý depth | `thirdeyes/depth_processing.py`, `thirdeyes/rgbd.py` | Lọc depth, ghép timestamp, ánh xạ SDK và đo vùng vật/chữ |
| Vật cản | `thirdeyes/obstacle_detection.py` | Khoảng cách, tiến gần, chống lặp |
| OCR | `thirdeyes/ocr.py`, `ocr_runtime/text_reader/` | Chụp theo yêu cầu, Paddle detector + VietOCR ngoại tuyến |
| Tìm vật | `thirdeyes/object_finding.py`, `ocr_runtime/object_worker.py` | YOLO11s; 30 loại vật, hướng giờ và ưu tiên khoảng cách gần nhất đo được; bút cần model bổ sung |
| Điều phối/âm thanh | `thirdeyes/coordinator_audio.py`, `thirdeyes/speech.py` | Âm báo stereo ưu tiên, Piper tiếng Việt và Vosk nhận lệnh |
| UI/log | `thirdeyes/control_panel.py`, `thirdeyes/ui_theme.py`, `thirdeyes/ui_logging.py` | Dashboard, tab kết quả, trạng thái và log |

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


## Âm báo stereo theo hướng

Mặc định: vật cản trái phát tai trái, phải phát tai phải, phía trước phát đều hai tai. Nhiều hướng phát lần lượt theo mức nguy cơ/khoảng cách. Bấm **T** hoặc chạy `test_stereo.bat` để thử **trái → giữa → phải**. Dùng tai nghe stereo, tắt Mono audio trong Windows. Xem `docs/STEREO_AUDIO.md` để chỉnh âm lượng/đảo kênh và biết giới hạn.

## Tìm vật đã triển khai
Chọn vật trên bảng điều khiển và bấm F. Model mặc định YOLO11s; đọc hướng và khoảng cách khi đo được. Bút cần model custom. Xem docs/OBJECT_FINDING.md. Có thể bấm V rồi nói tên vật; xem giới hạn model và quy ước hướng giờ trong tài liệu.

## Evaluate model và kết quả test

Ngày tổng hợp: **10/11/2026**. Các phép thử dưới đây được phân biệt thành kiểm thử phần mềm, đo model trên mẫu nhỏ và thử thiết bị. **143 test đạt không có nghĩa độ chính xác nhận diện là 100%.** Model tìm vật hiện là YOLO11s pretrained COCO, chưa fine-tune trên dataset riêng.

### 1. Kiểm thử phần mềm — chạy lại ngày 10/11/2026

**143/143 test đạt**, thời gian chạy suite 6,922 giây ở lượt ghi nhận này, dùng `.ocr-venv` Python 3.10.22. [Log kiểm thử](docs/evaluation/20261110/unit_tests.txt).

Các nhóm được kiểm tra gồm:

- Thu nhận ảnh, dữ liệu depth không hợp lệ, ghép timestamp và ánh xạ RGB–depth/lật ngang.
- Cảnh báo theo khoảng cách, tiếp cận nhanh, hạn chế lặp, vật đi ra khỏi vùng dưới 0,8 m và âm báo stereo.
- OCR: cấu hình, tiền/hậu xử lý, tiến trình riêng, hủy yêu cầu và các trạng thái lỗi.
- Object Finder: lọc lớp, khung bao, hướng giờ, đo vùng trung tâm, thiếu khoảng cách và ưu tiên vật gần nhất đo được.
- Lệnh giọng nói: ánh xạ tên vật, từ chối lệnh không rõ, chuyển lệnh tới Object Finder.
- Dashboard: nhãn ảnh cũ/mô phỏng, trạng thái chưa đo được, không sửa ảnh đầu vào và đưa kết quả vào cùng cửa sổ.

Nhiều test sử dụng mock hoặc dữ liệu tổng hợp; suite không thay thế kiểm tra camera, micro, loa và trải nghiệm người dùng thực tế.

Chạy lại:

```powershell
cd E:\DeepLearning\ThirdEyes
.\.ocr-venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

### 2. YOLO11s — kiểm tra ảnh Kinect lưu sẵn và thời gian xử lý

Môi trường: Python 3.10.22, Ultralytics 8.3.40, Torch 2.2.2+cpu, **CPU hai luồng**. Cấu hình: ảnh RGB gốc 640×480, `imgsz=960`, confidence 0,45, IoU 0,45, tìm lớp `bottle`. Phóng kích thước suy luận không tạo thêm chi tiết ảnh gốc.

| Hạng mục | Kết quả |
|---|---|
| Dữ liệu | Một cặp RGB–depth Kinect đã lưu, timestamp lệch 2 ms |
| Đầu ra nhận diện | Một chai, confidence **0,6773** |
| Đo depth trung tâm | **1,083 m**, 142 mẫu hợp lệ |
| Chọn kết quả | `nearest_measured`; ảnh này chỉ có một ứng viên chai |
| Đo tốc độ | Một lượt làm nóng, sau đó năm lượt trên cùng ảnh |
| Thời gian trung vị | **214,64 ms/lượt** |
| Khoảng min–max | **213,93–232,14 ms/lượt** |

Thời gian trên đo lời gọi `detect()`, gồm tiền xử lý, suy luận và hậu xử lý; **không gồm thu ảnh, ánh xạ SDK, giao tiếp tiến trình hay phát giọng**. Đây không phải FPS toàn ứng dụng. Điểm confidence không phải tỷ lệ chính xác. Năm lượt trên cùng một ảnh không phải năm cảnh độc lập.

Depth được tính lại từ các điểm đã chiếu bằng SDK trong lần thu trước; phép thử phát lại này không mở camera mới. Chưa có khoảng cách chuẩn bằng thước nên **chưa tính được MAE/RMSE khoảng cách**. Chưa có tập bounding box độc lập đủ để báo cáo **precision, recall, mAP50 hoặc mAP50–95 của ThirdEyes**.

[Kết quả và thông số đầy đủ](docs/evaluation/20261110/object_snapshot.json) gồm hash trọng số, hash mẫu, phiên bản và thời gian từng lượt. Ảnh/NPZ camera gốc lưu cục bộ, không đưa vào Git; tái lập phép đo ảnh này cần mẫu gốc. Có thể chạy model trên ảnh mới, nhưng thời gian và kết quả không nhất thiết giống bảng.

### 3. OCR — đánh giá lại trên bốn ảnh có nội dung tham chiếu

Model: PaddleOCR `en_PP-OCRv3_det` phát hiện vùng chữ và VietOCR `vgg_transformer` nhận dạng tiếng Việt. Dữ liệu và nội dung chuẩn: [ocr_manifest.json](tests/assets/ocr_manifest.json).

| Ảnh | Nguồn | Trạng thái | CER | WER | Xử lý OCR |
|---|---|---|---:|---:|---:|
| `ocr_sample.png` | Ảnh tổng hợp | `ok` | 2,50% | 13,33% | 2.174 ms |
| `ocr_tilted.png` | Biến thể nghiêng của ảnh tổng hợp | `ok` | 2,50% | 13,33% | 1.523 ms |
| `ocr_blank.png` | Ảnh trống tổng hợp | `blurry`, không sinh chữ | Không áp dụng | Không áp dụng | 2 ms |
| `kinect_text_crop.png` | Ảnh Kinect cắt thủ công, hai dòng chữ | `blurry`, không trả chữ | 100% | 100% | 0 ms theo độ phân giải bộ đếm |

**CER gộp: 23,90% — WER gộp: 31,58%.** Tính bằng tổng số phép sửa chia tổng ký tự/từ tham chiếu, không lấy trung bình các tỷ lệ theo ảnh. Nội dung bị từ chối dù có chữ chuẩn vẫn được tính là lỗi bỏ sót. Ảnh trống không có mẫu số nên CER/WER để null, không quy thành 0%.

CER là tỷ lệ lỗi ký tự; WER là tỷ lệ lỗi từ. Công cụ chuẩn hóa Unicode và khoảng trắng, vẫn tính dấu câu. Hai ảnh tổng hợp bị mất dấu chấm; mẫu Kinect bị bộ lọc độ mờ từ chối. `process_ms` không gồm toàn bộ thời gian khởi động/nạp model/đọc âm thanh. Bộ bốn ảnh quá nhỏ, trong đó hai ảnh liên quan nhau, nên không đại diện chất lượng OCR ngoài thực tế.

[Kết quả OCR chi tiết](docs/evaluation/20261110/ocr_metrics.json). Chạy lại:

```powershell
.\.ocr-venv\Scripts\python.exe -B tools\evaluate_ocr.py tests\assets\ocr_manifest.json --output runtime\evaluation\ocr_metrics.json
```

### 4. Bằng chứng thiết bị và giọng nói từ các lượt trước

Các kết quả này đã được lưu trong ngày 10/11/2026; **không phải lượt đo camera/micro mới trong lần cập nhật README**.

| Phép thử | Kết quả | Giới hạn |
|---|---|---|
| Kinect → Object Finder → ánh xạ depth | Một chai, hướng 10 giờ, **1,350 m**, 96 mẫu, lệch timestamp 2 ms; tổng tác vụ đầu 4.468 ms | Chưa đối chiếu thước; khác ảnh với phép thử phát lại 1,083 m |
| Piper tạo giọng → Vosk → phân tích lệnh | **4/4 câu thử** cho ra đúng loại vật | Giọng tổng hợp, không phải độ chính xác micro/giọng người thật |
| Giao diện | Đã xem demo, tab kết quả, trạng thái chưa hỗ trợ; kiểm tra widget 1050×660 và phím Q từ vùng văn bản | Chưa chứng nhận khả năng tiếp cận với mọi trình đọc màn hình |

Bốn câu giọng tổng hợp: “tìm chai nước”, “tìm điện thoại”, “tìm cái ghế”, “tìm máy tính xách tay”. [Kết quả nhận lệnh](docs/evaluation/20261110/voice_synthetic.json), [kết quả Kinect thật đã lưu](docs/evaluation/20261110/kinect_object_previous.json). Người dùng đã chọn tự thử micro sau; chưa có số liệu đánh giá micro thực tế. Chưa đo chất lượng nghe/độ tự nhiên của Piper bằng người nghe.

### 5. Quy trình evaluate sau khi fine-tune

1. Chốt tập test độc lập, có ảnh Kinect và bounding box được kiểm tra. Chia theo phiên chụp/mẫu vật, tránh khung hình gần trùng giữa train và test.
2. Đánh giá checkpoint `best.pt` với đúng danh sách lớp và ID đã huấn luyện. Báo cáo precision, recall, mAP50, mAP50–95, AP theo từng lớp và số lượng mẫu.
3. So sánh với model pretrained trên cùng tập test. Nếu model gốc dùng 80 ID COCO còn model mới dùng ID 0–4, phải ánh xạ dự đoán theo tên lớp trước khi so sánh; không coi các ID là tương đương.
4. Đo tốc độ trên laptop đích: tách nạp model, suy luận đã làm nóng và độ trễ từ yêu cầu đến phản hồi. Ghi số lượt, cấu hình ảnh và phần cứng; không thay bằng tốc độ trên GPU Kaggle.
5. Kiểm thử tích hợp bằng camera: hướng đúng, khoảng cách hợp lệ, vật gần nhất, không thấy vật và mất depth. Báo cáo cả lỗi, không chỉ ảnh nhận đúng.

`datasets/objects/data.yaml` hiện **được để rỗng theo yêu cầu người dùng**. Chỉ chạy lệnh dưới đây sau khi chuẩn bị dataset có nhãn, điền cấu hình test hợp lệ và đặt checkpoint tương thích vào đường dẫn chỉ định:

```powershell
.\.object-venv\Scripts\python.exe -c "from ultralytics import YOLO; YOLO('models/objects/best.pt').val(data='datasets/objects/data.yaml', split='test', imgsz=960, device='cpu', project='runtime/evaluation', name='objects_test')"
```

Phần cảnh báo vật cản hiện dùng thuật toán depth, không dùng mạng học sâu. Đánh giá phần này bằng tỷ lệ bỏ sót vật cản, cảnh báo sai/phút, số lần lặp gây phiền và độ trễ cảnh báo; không dùng mAP làm chỉ số thay thế. Các con số ngoài thực địa này **chưa được đo đầy đủ**.

### 6. Kế hoạch kiểm thử camera có đối chiếu

- Đặt vật không trong suốt tại các mốc đo bằng thước, ví dụ 1,0 / 1,5 / 2,0 / 3,0 m; thử trái, giữa, phải. Ghi từng lần: loại vật, nhận diện có/không, hướng, depth, khoảng cách chuẩn và trạng thái chưa đo được.
- Đặt hai hoặc ba vật cùng loại ở các khoảng cách khác nhau để kiểm tra lựa chọn gần nhất; có thêm vật thiếu depth để kiểm tra lời thông báo giới hạn.
- Thử vật đứng yên, tiến gần, đi xa từ dưới 0,8 m; kiểm tra cảnh báo lặp. Thực hiện trong môi trường kiểm soát, không dùng đường đi nguy hiểm làm nơi thử.
- Micro: nói từng lệnh nhiều lần với nhiều người và mức ồn, tính tỷ lệ hiểu đúng ý định; chưa có dữ liệu thì để “chưa đánh giá”.

Khi cần ghi phiên camera để phân tích, dùng một thư mục mới:

```powershell
.\run.bat --record-dir captures\evaluation_session_01
```

Lệnh này chủ động lưu ảnh RGB/depth cục bộ; thư mục captures được Git bỏ qua. Kết quả test và các mẫu nhỏ trong README không phải bằng chứng thiết bị đủ an toàn để dẫn đường độc lập.

