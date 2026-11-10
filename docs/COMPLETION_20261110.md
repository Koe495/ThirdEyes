# ThirdEyes — Cập nhật ngày 10/11/2026

Dự án: `E:\DeepLearning\ThirdEyes`. Module tìm đồ vật vẫn là placeholder, không cài model phát hiện đồ vật.

## Những phần đã thực hiện

1. **Khôi phục môi trường sau khi chuyển thư mục.** Đã tạo lại cấu hình/launcher môi trường OCR bằng Python đóng gói trong dự án, giữ các thư viện đã cài. `run.bat` chạy `repair_environment.py` để sửa đường dẫn môi trường OCR/âm thanh khi di chuyển dự án lần sau. Dùng `python -m pip` thay vì gọi launcher pip cũ trực tiếp.
2. **Ghép RGB–depth theo timestamp.** Bộ đệm giữ tối đa sáu khung mỗi luồng, chọn cặp lệch không quá 20 ms, không dùng cặp quá 300 ms. Depth phục vụ cảnh báo vẫn xử lý độc lập, không chờ RGB. Đây là ghép gần thời điểm bằng phần mềm, không phải đồng bộ phần cứng tuyệt đối.
3. **Ánh xạ vùng ảnh màu sang depth.** Dùng hàm chiếu điểm của Kinect SDK 1.8, chuyển đúng tọa độ trước/sau lật ngang. Lấy mẫu depth cách bốn pixel, xử lý trùng tọa độ theo bề mặt gần hơn. Sau OCR, các vùng chữ được bổ sung khoảng cách khi đủ dữ liệu. Ít hơn 12 mẫu hoặc khoảng phân vị 10–90 chênh trên 250 mm thì trả trạng thái chưa đo được. Không nội suy lấp vùng depth mất.
4. **Theo dõi cụm vật cản hình học.** Gom các ô depth liền kề có khoảng cách tương tự, gán ID tạm thời và hiển thị trên ảnh depth. Giữ ID khi liên kết đủ rõ, cấp ID mới khi mơ hồ; không dùng ID để vô hiệu cảnh báo. Chưa nhận diện loại vật, danh tính thật hoặc bù chuyển động của người đeo.
5. **Giọng tiếng Việt ngoại tuyến.** Đã cài Piper và model VAIS1000 medium vào môi trường `.audio-venv` riêng. Có thể đọc OCR, trạng thái và nhãn nút được chọn bằng bàn phím. Luồng phát có thể nhận yêu cầu dừng; cảnh báo vật cản tiếp tục được ưu tiên. Không gửi văn bản lên dịch vụ TTS. Nếu thiếu Piper, cầu nối SAPI cũ vẫn chỉ chọn giọng tiếng Việt phù hợp.
6. **Nhận lệnh tiếng Việt ngoại tuyến.** Vosk dùng model local. Bấm V để mở micro trong tối đa sáu giây sau khi model nạp xong. Chỉ nhận lệnh trong danh sách cho phép và vượt ngưỡng tin cậy; không dùng lệnh giọng nói để tắt cảnh báo hoặc thoát. Không lưu âm thanh micro.
7. **Bảng điều khiển.** Nút lớn, tương phản cao, Tab/Enter/Space, phím tắt, nhãn nút được xuất ra Windows accessibility và phản hồi giọng khi chọn nút. Có nhãn DEMO rõ ràng. Chưa xác nhận tương thích toàn diện với mọi trình đọc màn hình.
8. **Công cụ đánh giá.** Đã thêm CER/WER, manifest ảnh có đáp án, ghi RGB/depth theo yêu cầu và chạy lại phiên vật cản với các khoảng thời gian gán nhãn.

## Cách dùng

Mở `E:\DeepLearning\ThirdEyes\run.bat`.

| Phím | Chức năng |
|---|---|
| O | Chụp và đọc văn bản |
| R | Đọc lại kết quả gần nhất |
| X | Hủy OCR và dừng đọc |
| V | Nghe một lệnh trong sáu giây; tín hiệu ngắn báo micro sẵn sàng nếu âm đang bật |
| S | Đọc trạng thái hiện tại |
| M | Bật/tắt âm |
| T | Thử trái–giữa–phải |
| Q / Esc | Thoát |

Lệnh hỗ trợ: **đọc văn bản / đọc chữ**, **đọc lại / lặp lại**, **dừng đọc / dừng lại**, **trạng thái / kiểm tra**. Chờ micro báo đang nghe rồi nói. Khi không nhận được lệnh, dùng nút hoặc phím tắt. Giọng nói hiện là tính năng thử nghiệm; chưa đo độ chính xác trên nhiều người nói và môi trường ồn.

```powershell
cd E:\DeepLearning\ThirdEyes
# Cài lại phần âm thanh; cần Internet ở bước cài, không cần khi sử dụng:
.\setup_audio.bat
# Đánh giá OCR, dấu câu vẫn được tính là ký tự/từ sai:
.\.ocr-venv\Scripts\python.exe tools\evaluate_ocr.py tests\assets\ocr_manifest.json --output runtime\ocr_metrics.json
# Ghi ảnh và depth cục bộ để đánh giá: phải dùng thư mục chưa tồn tại:
.\run.bat --record-dir runtime\session_01
# Chạy lại dữ liệu, không mở camera hay phát âm:
.\.venv\Scripts\python.exe tools\replay_obstacles.py runtime\session_01 --output runtime\replay.json
```

Ghi phiên là tùy chọn, có lưu hình ảnh môi trường thực tế và tăng tải CPU/ổ đĩa; không bật mặc định. Mẫu ghi cách nhau ít nhất 0,1 giây, không phải bản sao mọi khung hình. Công cụ replay nhận `--labels` là JSON có `start_s`, `end_s`, `zone`, `expect_alert`; kết quả kiểm tra sự xuất hiện cảnh báo trong từng khoảng, chưa phải chứng nhận an toàn điều hướng.

## Kết quả kiểm chứng

- **112/112 kiểm thử phần mềm đạt**, bao gồm các kiểm thử trước đây về stereo, vật đi xa và chống báo lặp, cùng ghép timestamp, phép chiếu, từ chối đo không tin cậy, theo dõi cụm, lệnh giọng và công cụ đánh giá.
- Đã kiểm tra GUI thật: các nút hiển thị đầy đủ; Windows accessibility đọc được tên nút; Tab chọn được nút. Đã mở micro qua phím V và thấy phiên nghe tự kết thúc sau thời hạn.
- Kinect thật: lần đầu cặp OCR lệch **2 ms**, OCR/cảnh báo chạy đồng thời **755 vòng**. Thời gian bước xử lý depth lớn nhất quan sát khoảng **26,3 ms**, không phải cam kết thời gian thực. OCR đọc đúng hai dòng tên trường, nhưng nhận logo thành “INHU”. Các vùng chữ không đủ depth và được báo chưa đo được.
- Lần hai cặp OCR lệch **4 ms**; chữ trên vật nhỏ và tối không được nhận đúng, OCR còn nhận nhầm họa tiết/chữ trên áo. Không tuyên bố đã giải quyết hoàn toàn OCR trong ánh sáng khó.
- Kiểm tra ánh xạ riêng: cặp lệch **1 ms**, có **199.336 pixel depth hợp lệ** và **12.463 mẫu chiếu hợp lệ**. Vùng thử giữa ảnh có nhiều độ sâu nên trả `mixed_depth`; chưa có phép đối chiếu sai số khoảng cách bằng thước chuẩn.
- Đã tạo WAV tiếng Việt, phát qua Windows và kiểm tra tiến trình Piper nhận lệnh dừng. Thời gian xác nhận dừng không đồng nghĩa độ trễ âm thanh thực tế bằng không.
- Kiểm thử Vosk bằng giọng tổng hợp: lần thử cuối đạt hành động mong đợi ở **6/8 câu**. Đây không phải độ chính xác với giọng người dùng; các câu không đủ tin cậy bị bỏ qua.
- Bộ OCR bốn mẫu gồm hai ảnh tổng hợp, một ảnh trắng và một vùng chữ Kinect cắt thủ công. Hai ảnh tổng hợp có CER **2,5%** mỗi ảnh (thiếu dấu câu); ảnh trắng không sinh chữ; ảnh cắt thật bị đánh dấu mờ. CER gộp **23,9%**, WER **31,6%** chỉ mô tả bộ mẫu rất nhỏ này, không đại diện môi trường sử dụng.

## Phần vẫn cần thử nghiệm thực tế

Cần thu thêm ảnh Kinect có đáp án ở nhiều khoảng cách/ánh sáng, đo sai số bằng thước chuẩn, thử người nói thật và tai nghe đúng hướng, cùng kiểm thử bàn phím/trình đọc màn hình với người dùng. Chưa có mô hình nhận diện danh tính/loại vật, bù chuyển động camera, đồng bộ phần cứng hoặc bảo đảm đọc đúng bố cục bảng/nhiều cột. Module tìm đồ vật được giữ nguyên theo yêu cầu.

## Nguồn và giấy phép

- [Piper](https://github.com/OHF-Voice/piper1-gpl): bộ máy TTS chạy local; phiên bản cài 1.8.0, giấy phép GPL-3.0.
- [Model giọng VAIS1000](https://huggingface.co/rhasspy/piper-voices/tree/main/vi/vi_VN/vais1000/medium): model card được lưu tại `models/speech/MODEL_CARD`, ghi nguồn dữ liệu VAIS-1000 và CC BY 4.0.
- [Model Vosk của tác giả](https://alphacephei.com/vosk/models): `vosk-model-small-vn-0.4`, nhận dạng tiếng Việt ngoại tuyến; danh mục tác giả ghi Apache 2.0.
- Khai báo phép chiếu được đối chiếu với `NuiImageCamera.h` trong Kinect SDK 1.8 đã cài trên máy.

Thư viện âm thanh được khóa trong `requirements-audio.lock.txt`; checksum model đã tải nằm ở `models/audio_manifest.json`. Các bản sao lưu thay đổi nằm trong `backups/before_completion_*`.
