# Theo dõi vật và bíp stereo

Cập nhật 11/11/2026. Chọn một trong 29 lớp rồi bấm **F**, hoặc bấm **V** và nói “tìm chai nước”. Hệ thống bắt đầu một phiên theo dõi liên tục. Bấm **X** hoặc nói “dừng lại” để dừng. Bấm F/nói tên khác bắt đầu phiên mới; bấm **O** dừng theo dõi và chuyển sang OCR. **M** tắt/bật âm thanh, **R** đọc lại kết quả gần nhất.

## Hành vi âm thanh

- Đợi hai lượt nhận diện liên tiếp phù hợp về vị trí/kích thước trước khi xác nhận vật.
- Đọc hướng và khoảng cách **một lần trong mỗi phiên**. Nếu depth không hợp lệ, nói rõ chưa đo được khoảng cách; không tự đoán.
- Sau thông báo, phát một bíp 850 Hz dài 80 ms, nhịp mục tiêu **1 giây**, khi có vị trí mới đủ tin cậy. Vật bên trái nghe tai trái lớn hơn, bên phải nghe tai phải lớn hơn; giữa phát đều hai tai. Chuyển âm lượng liên tục theo vị trí ngang, tổng công suất tương đối ổn định.
- Bíp chỉ mã hóa trái/phải theo camera, **không mã hóa độ cao hoặc khoảng cách**. Hướng giờ và khoảng cách được đọc ở thông báo đầu; R để nghe lại kết quả gần nhất.
- Khi mất dấu/không chắc/ảnh nhận diện quá 1,2 giây: ngừng bíp chỉ hướng ngay. Không phát bù những bíp đã bỏ qua.
- Mất dấu liên tục quá 5 giây mới nhắc; nếu chưa từng xác nhận vật, chờ 10 giây. **Tối đa một thông báo mất dấu/chưa thấy trong cả phiên**. Tìm lại được chỉ tiếp tục bíp sau hai lượt xác nhận, không nói “đã tìm lại” và không đọc lại vị trí tự động.
- Cảnh báo vật cản ưu tiên hơn bíp theo dõi. Tạm ngừng bíp khi phát giọng, nghe micro, mute, hoặc có cảnh báo chờ phát. Vì vậy khoảng cách giữa các bíp có thể dài hơn một giây.

Dùng tai nghe stereo và tắt Mono audio của Windows. `--swap-audio-channels` đảo hai kênh nếu cần. Phiên theo dõi là thao tác chủ động nên vật đứng yên vẫn phát bíp mỗi giây; quy tắc chống lặp của module cảnh báo vật cản vẫn riêng biệt.

## Cách triển khai và giới hạn

`object_tracking.py` theo dõi bằng nhận diện lặp lại và ghép khung bao theo độ giao nhau, chuyển động tâm, tỷ lệ kích thước. Lần đầu ưu tiên vật gần nhất trong các vật đo được depth; nếu không đo được, chọn theo confidence. Sau đó giữ đối tượng đã ghép, không đổi sang vật khác chỉ vì nó gần hơn. Trường hợp ghép mơ hồ thì ngừng bíp. Sau mất dấu dài có thể chọn lại vật cùng loại; đây **không phải xác minh danh tính**, có thể nhầm khi các vật giống nhau giao nhau. F bắt đầu lại nếu muốn chọn lại vật gần nhất.

YOLO chạy trong tiến trình riêng đã nạp model; mỗi lần chỉ xử lý một yêu cầu, lấy khung mới sau khi hoàn thành, không xếp hàng video cũ. Giữ đủ 30 ứng viên trước khi ghép, dùng RGB/depth đồng bộ của đúng khung. Không phát hướng từ kết quả khởi động model đã quá hạn. Đây là cập nhật liên tục theo khả năng CPU, **không cam kết 30 FPS**. Bíp 1 Hz không có nghĩa YOLO chạy đúng 1 FPS.

Tab kết quả cập nhật khung đã nhận diện gần nhất, kèm trạng thái chờ/mất vị trí; không vẽ khung cũ như thể là kết quả của ảnh live. OCR vẫn dùng ảnh chụp. Đổi danh sách trên combobox chưa chuyển mục tiêu đang theo dõi cho đến khi bấm F.

```powershell
.\run.bat --track --find-target "Chai nước"
# Giữ chế độ ảnh tĩnh cho kiểm thử trước đây:
.\run.bat --find-once --find-target "Chai nước"
```

## Kiểm thử

Bộ test bao gồm nhịp 1 giây, pan stereo/đảo kênh, ghép vật khi có vật gần hơn, từ chối ghép mơ hồ, ảnh cũ, khung trùng, lỗi backend, dừng, ưu tiên âm thanh, xác nhận hai lượt và không lặp giọng khi nhận diện chập chờn. Xem `tests/test_object_tracking.py`.

Đã chạy Kinect thật ngày 11/11/2026. Lượt đầu xác nhận chuỗi camera → YOLO → depth → bíp nhưng người dùng phản hồi thông báo mất dấu/tìm lại quá nhiều. Đã thay bằng chính sách một thông báo vị trí đầu phiên và tối đa một nhắc mất dấu; kết quả lượt đầu không được xem là kiểm chứng bản sửa cuối. Chi tiết từng lượt nằm trong [tracking_20261111.json](evaluation/20261111/tracking_20261111.json).

Độ ổn định phụ thuộc khả năng detect: chai nhỏ, trong suốt, che khuất hoặc chuyển động nhanh có thể khiến hệ thống im lặng do không đủ hai lượt xác nhận. Không hạ confidence tự động để tạo cảm giác đang theo dõi. Các thử nghiệm hiện tại chưa đo ID-switch, độ chính xác bám vật hay sai số khoảng cách bằng nhãn/thước chuẩn.

Bản cuối: **155/155 test đạt (10,931 giây)**. Lượt Kinect sau sửa chạy đủ 1.000 vòng, chỉ có một yêu cầu đọc “chưa thấy”, không có mục tiêu được xác nhận và không có bíp tracking. Lượt này chưa kiểm chứng bám chai thành công với bản cuối; kiểm thử tự động xác nhận chính sách âm thanh và nhịp bíp khi có mục tiêu hợp lệ.
