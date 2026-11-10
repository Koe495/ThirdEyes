# ThirdEyes — Tìm vật và bổ sung dataset

Đã tích hợp tại `E:\DeepLearning\ThirdEyes`. Model mặc định **YOLO11s / COCO**, chạy CPU trong `.object-venv` riêng, không ảnh hưởng bộ thư viện OCR/TTS. Runtime dùng trọng số local; Internet chỉ cần lúc cài đặt.

## Sử dụng

**Chế độ hiện tại:** F/lệnh tìm vật bắt đầu phiên theo dõi liên tục, không chỉ chụp một ảnh. X dừng; O chuyển sang OCR. Đọc vị trí đầu phiên rồi bíp stereo mỗi giây; xem [OBJECT_TRACKING.md](OBJECT_TRACKING.md). `--find-once` giữ cách kiểm thử ảnh tĩnh. Các mục kết quả kiểm thử cũ bên dưới là lịch sử trước khi có tracking.

1. Chạy `run.bat`.
2. Chọn vật trong danh sách phía trên bảng điều khiển; dùng phím mũi tên hoặc chuột.
3. Bấm nút **Tìm vật đã chọn [F]**, hoặc F khi cửa sổ camera/bảng điều khiển có focus. Khi focus đang ở danh sách, Tab ra nút rồi Enter.
4. Xem cửa sổ kết quả và khung trên **ảnh chụp**, nghe hướng theo mặt đồng hồ và khoảng cách ước tính. Khoảng cách chỉ đọc khi phép đo depth đủ tin cậy. X hủy tìm vật/đọc chữ và dừng âm đọc; F bắt đầu lại phiên theo dõi và chọn lại vật.

Danh sách chọn hỗ trợ **29 loại vật** với model mặc định, dùng chung cho bảng điều khiển và `--find-target`.

| Thứ tự | Lựa chọn | Lớp model |
|---:|---|---|
| 0 | Người | `person` |
| 1 | Xe buýt | `bus` |
| 2 | Ghế băng | `bench` |
| 3 | Mèo | `cat` |
| 4 | Chó | `dog` |
| 5 | Ba lô | `backpack` |
| 6 | Ô / dù | `umbrella` |
| 7 | Túi xách | `handbag` |
| 8 | Vali | `suitcase` |
| 9 | Chai nước | `bottle` |
| 10 | Cốc | `cup` |
| 11 | Nĩa | `fork` |
| 12 | Dao | `knife` |
| 13 | Thìa / muỗng | `spoon` |
| 14 | Bát / tô | `bowl` |
| 15 | Ghế | `chair` |
| 16 | Ghế sofa | `couch` |
| 17 | Chậu cây | `potted plant` |
| 18 | Bàn ăn | `dining table` |
| 19 | Điện thoại | `cell phone` |
| 20 | Lò vi sóng | `microwave` |
| 21 | Lò nướng | `oven` |
| 22 | Máy nướng bánh mì | `toaster` |
| 23 | Bồn rửa | `sink` |
| 24 | Tủ lạnh | `refrigerator` |
| 25 | Bình hoa | `vase` |
| 26 | Kéo | `scissors` |
| 27 | Máy sấy tóc | `hair drier` |
| 28 | Bàn chải đánh răng | `toothbrush` |

Danh sách cập nhật ngày 11/11/2026 gồm đúng 29 lớp theo yêu cầu. Số 0–28 là thứ tự lựa chọn, không phải ID COCO gốc. Detector tra ID theo `model.names`, nên vẫn chạy đúng với YOLO11s pretrained và model custom có tên lớp tương ứng. “Chai nước” ánh xạ tới `bottle`, không xác nhận chai có nước. Chưa kiểm thử camera cho toàn bộ danh sách mới.

```powershell
cd E:\DeepLearning\ThirdEyes
.\run.bat --find-target "Điện thoại"
# Tìm một lần tự động sau khi camera có ảnh:
.\run.bat --find-target "Chai nước" --find-once
# Model tự huấn luyện:
.\run.bat --object-model "E:\DeepLearning\ThirdEyes\models\objects\best.pt"
# Cài lại:
.\setup_objects.bat
```

Danh sách hiện dùng các tên lớp tiếng Anh. Model custom cần có tên lớp tương ứng với bảng trên. Lớp không có trong model đang chọn sẽ được báo chưa hỗ trợ.

## Tìm vật bằng giọng nói ngoại tuyến

1. Bấm **V** hoặc nút **Nghe lệnh 6 giây**. Chờ tiếng bíp báo micro sẵn sàng rồi nói, ví dụ **“tìm chai nước”**.
2. Hệ thống tự chọn loại vật và chụp ảnh để tìm; không cần chọn danh sách hoặc bấm F. Có lời xác nhận “Đang tìm …” khi âm thanh có thể phát.
3. Nghe kết quả ưu tiên, gồm hướng giờ và khoảng cách ước tính. Nói **“đọc lại”** trong phiên nghe tiếp theo (hoặc bấm R) để nghe lại kết quả gần nhất của tìm vật/OCR.

Hỗ trợ câu ngắn `tìm <tên vật>` và `tìm cái <tên vật>` cho danh sách trên. Ví dụ: tìm người, tìm xe buýt, tìm mèo, tìm chai nước, tìm điện thoại, tìm máy sấy tóc. Các tên tương đương gồm chai/chai nước, ly/cốc/ca, bát/tô, thìa/muỗng, ô/dù, vali/va li, bồn rửa/chậu rửa. Các vật đã bỏ như bút, sách, laptop không còn là lệnh tìm hợp lệ.

Micro chỉ mở trong phiên nghe tối đa 6 giây, xử lý bằng Vosk đã cài trên máy, không gửi âm thanh lên mạng và không lưu bản ghi. Đây là chế độ bấm để nghe, chưa phải luôn nghe hoặc có từ đánh thức. Lệnh không rõ, tên không hỗ trợ hay câu ghép không được suy đoán; bấm V để nói lại bằng câu ngắn. Nếu bộ tìm vật/OCR đang bận, hệ thống báo thử lại. Cảnh báo vật cản tiếp tục hoạt động; giọng kết quả chờ hết phiên nghe để tránh micro thu lại tiếng đọc của hệ thống.

### Ưu tiên vật gần camera

- Model giữ tối đa 30 ứng viên cùng loại sau lọc nhận diện, rồi ánh xạ depth cho tất cả trước khi chọn. Không loại sớm chỉ vì vật gần có điểm nhận diện thấp hơn ba vật khác.
- Ưu tiên khoảng cách hợp lệ nhỏ nhất trong khoảng 0,8–4 m; khi bằng nhau dùng điểm nhận diện. Giới hạn ba vật trên giao diện chỉ áp dụng sau bước sắp xếp; vật đầu có dấu `*` và nhãn “ưu tiên”. Giọng nói chỉ đọc vật ưu tiên để tránh quá nhiều thông tin.
- Vật chưa đo được depth được xếp sau. Nếu có vật chưa đo được, lời đọc nói rõ chưa thể so sánh đầy đủ; không khẳng định vật được chọn gần hơn vật chưa đo được.
- Nếu tất cả đều thiếu khoảng cách, báo chưa xác định được vật gần nhất rồi đọc vị trí vật có điểm nhận diện cao nhất. “Gần nhất” chỉ trong các ứng viên nhận diện và đo được của ảnh chụp, theo độ sâu ước tính; không phải xác nhận tất cả vật trong môi trường.

## Hành vi và giới hạn

- Tìm theo yêu cầu trên một ảnh, không phải theo dõi vật liên tục. Lời đọc bắt đầu bằng “Trong ảnh vừa chụp”. Đổi góc hoặc di chuyển vật thì bấm F lại.
- Tối đa ba kết quả hiển thị, ưu tiên khoảng cách hợp lệ gần nhất sau khi đo các ứng viên. Hướng tính theo tâm vật trong ảnh đã chuẩn hóa lật ngang.
- Quy ước mặt đồng hồ **trên mặt phẳng ảnh**: 12 giờ ở trên, 3 giờ bên phải, 6 giờ ở dưới, 9 giờ bên trái; các hướng chéo được làm tròn đến giờ gần nhất. Vật gần tâm ảnh (bán kính chuẩn hóa 0,20) được báo “chính giữa khung nhìn”, tránh hướng nhảy thất thường. Đây không phải góc phương vị quanh người dùng: camera phía trước không quan sát được mọi hướng xung quanh.
- Ví dụ lời đọc: “Trong ảnh vừa chụp: Tìm thấy chai nước ở hướng 3 giờ, khoảng cách ước tính 2 mét.” Nhãn trên ảnh có hướng giờ và số mét; khung nhỏ màu vàng là vùng lấy mẫu depth.
- Khi có cặp RGB–depth lệch tối đa 20 ms, dùng ánh xạ SDK để chiếu các điểm depth sang ảnh màu (đã xử lý lật ngang). Object Finder lấy mẫu depth mỗi 2 pixel, đo vùng trung tâm bằng 50% chiều rộng và chiều cao khung vật. Chỉ nhận depth 0,8–4 m, ít nhất 6 mẫu, chênh lệch percentile 10–90 không quá 250 mm; lấy trung vị và đọc làm tròn 0,1 m. OCR vẫn dùng phép đo vùng chữ riêng.
- Nếu vùng trung tâm thiếu depth hoặc lẫn nhiều bề mặt, không lấy khoảng cách nền ở mép khung để thay thế. Kết quả nêu rõ thiếu mẫu, depth chưa ổn định, ảnh chưa đồng bộ hoặc lỗi ánh xạ; log `FIND measurement` ghi trạng thái, số mẫu, khoảng cách và độ lệch thời gian.
- Khoảng cách là độ sâu theo trục camera, chưa hiệu chỉnh thành cự ly đường thẳng 3D. Khung bao không phải mặt nạ phân đoạn: vật trong suốt, có lỗ, phản chiếu hoặc tâm khung nằm trên nền vẫn có thể cho depth nền; cách lấy vùng trung tâm chỉ giảm ảnh hưởng này. Chưa chứng nhận sai số bằng thước.
- Tiến trình suy luận riêng, không chặn vòng cảnh báo depth. OCR và tìm vật không nhận yêu cầu mới đồng thời để giảm tải CPU. Cảnh báo được ưu tiên hơn giọng kết quả; lời đọc bị trì hoãn quá mười giây sẽ bỏ, kết quả vẫn còn trên màn hình và có thể yêu cầu đọc lại.
- `config/objects.json`: confidence 0.45, IoU 0.45, kích thước suy luận 960, tối đa ba kết quả, hai luồng CPU. Tăng kích thước là nội suy ảnh, không tạo chi tiết camera mới.
- Lần đầu cần nạp model. Ảnh tối, phản sáng, vật trong suốt, che khuất hoặc nhỏ có thể bị bỏ sót/nhận nhầm. Không dùng “chưa thấy” để kết luận vật không tồn tại.
- Danh sách vật và câu lệnh dùng chung giữa các môi trường Python, không cần tải thêm model giọng nói cho cập nhật này.

## Tham khảo: tạo dataset mở rộng ngoài danh sách hiện tại

Ví dụ mở rộng trong tương lai (không thuộc danh sách hiện tại): bốn lớp `bottle`, `cell phone`, `chair`, `pen`.

```text
datasets/objects/
  data.yaml
  images/train/   images/val/   images/test/
  labels/train/   labels/val/   labels/test/
```

**Thu ảnh:** bắt đầu khoảng 300–500 ảnh đa dạng mỗi lớp nếu có thể; đây là mục tiêu ban đầu, không bảo đảm chất lượng. Chụp bằng chính Kinect, nhiều mẫu bút/chai/điện thoại/ghế, nền bàn/kệ/sàn, nhiều góc, sáng/tối, cầm tay/đặt xuống, che khuất một phần. Với bút cần có ảnh gần đủ nét: vật chỉ vài pixel không thể giải quyết bằng model lớn hơn. Thêm ảnh không có vật mục tiêu và các vật dễ nhầm như đũa, thước, dây điện.

**Gán nhãn:** dùng CVAT hoặc LabelImg xuất định dạng YOLO. Vẽ box sát từng vật, đánh dấu tất cả vật thuộc bốn lớp trong ảnh; không chỉ đánh dấu bút rồi bỏ qua chai. Với vật che khuất, dùng cùng một quy ước box trên toàn dataset, không đoán phần không nhìn thấy một cách tùy ý.

Mỗi ảnh có file `.txt` cùng tên; mỗi dòng:

```text
class_id center_x center_y width height
3 0.50 0.60 0.20 0.04
```

Tọa độ chuẩn hóa 0–1 theo kích thước ảnh, không phải pixel. Ví dụ trên là một box bút; không dùng làm nhãn thật cho ảnh khác. Ảnh âm tính có file nhãn rỗng.

**Chia dữ liệu:** khoảng 70% train, 20% validation, 10% test. Chia theo phiên quay và mẫu vật; không đưa các khung sát nhau của cùng video vào cả train và test. Giữ một tập phòng/ánh sáng/mẫu bút chưa thấy để kiểm tra tổng quát hóa.

**Huấn luyện:** CPU chạy được nhưng chậm; ưu tiên máy có GPU cho bước này. Không tự chạy huấn luyện khi chưa có ảnh gán nhãn.

```powershell
cd E:\DeepLearning\ThirdEyes
.\.object-venv\Scripts\yolo.exe detect train model=models/objects/yolo11s.pt data=datasets/objects/data.yaml epochs=80 imgsz=960 batch=2 device=cpu workers=0 project=runs/objects name=custom4
.\.object-venv\Scripts\yolo.exe detect val model=runs/objects/custom4/weights/best.pt data=datasets/objects/data.yaml split=test imgsz=960 device=cpu
.\run.bat --object-model runs/objects/custom4/weights/best.pt
```

Sau huấn luyện bốn lớp, model mới chỉ có bốn lớp đó; các lớp khác của COCO không tự được giữ lại. Muốn giữ toàn bộ lớp, phải thiết kế lại danh sách lớp và dataset đầy đủ, hoặc dùng thêm model riêng. Kiểm tra precision/recall và ảnh sai theo từng lớp, đặc biệt bút; sau đó thử toàn chuỗi camera → hướng → depth → âm thanh. Không đánh giá chỉ bằng loss train.

## Kiểm chứng giọng nói và ưu tiên vật gần — 10/11/2026

- **139/139 kiểm thử đạt** trên bản đã triển khai. Có kiểm thử lệnh giọng nói đi tới ObjectFinder trong vòng lặp ứng dụng không có bảng điều khiển, các tên tương đương, từ chối lệnh mơ hồ, và vật thứ tư theo điểm nhận diện vẫn được ưu tiên nếu có depth gần nhất.
- Dùng Piper tạo âm thanh thử, đưa trực tiếp vào model Vosk đang cài: nhận đúng bốn câu “tìm chai nước”, “tìm điện thoại”, “tìm cái ghế”, “tìm máy tính xách tay”. Đây là kiểm tra giọng tổng hợp, chưa thay thế kiểm tra giọng người dùng qua micro và tiếng ồn thực tế.
- Đã nối kết quả Vosk với tiến trình ObjectFinder thật trên cặp RGB–depth Kinect lưu từ lần thử trước: nhận diện chai, chọn `nearest_measured`, đo **1,083 m**, tạo câu đọc khoảng **1,1 m**. Phép thử phát lại này có một chai; trường hợp nhiều vật được kiểm chứng bằng dữ liệu kiểm thử, chưa đo đối chiếu nhiều vật thật bằng thước.
- Không cài thêm thư viện/model, không lưu bản ghi micro. Các file sửa được sao lưu trong `backups/before_voice_find_*`.

## Kiểm chứng cập nhật khoảng cách và hướng giờ — 10/11/2026

- **128/128 kiểm thử đạt**, trong đó 10 kiểm thử bổ sung cho hướng giờ, vùng trung tâm, nền phía sau, thiếu mẫu, giới hạn 0,8–4 m, hủy phép đo và lời đọc khi chưa có khoảng cách.
- Trên một cặp RGB–depth Kinect đã lưu: model tìm thấy chai, đo toàn khung bị `mixed_depth`; đo vùng trung tâm có 142 mẫu hợp lệ, trung vị **1,083 m**. Đây là phép so sánh trên cùng ảnh và cùng dữ liệu depth.
- Đã chạy bản tích hợp trên Kinect thật qua tiến trình ObjectFinder: chai có điểm nhận diện 0,778; **hướng 10 giờ**, **1,350 m**, 96 mẫu, RGB–depth lệch 2 ms, tổng thời gian lần đầu khoảng 4,47 giây (gồm nạp model). Chuỗi lời đọc tạo ra: “Trong ảnh vừa chụp: Tìm thấy chai nước ở hướng 10 giờ, khoảng cách ước tính 1.4 mét.”
- Lần kiểm tra tự động này xác nhận kết quả và chuỗi đưa vào bộ đọc, không đánh giá bằng nghe thực tế. Chưa có khoảng cách đo bằng thước để tính sai số, chưa kiểm chứng đủ 30 loại vật.

## Kiểm chứng đợt tích hợp ban đầu (trước cập nhật khoảng cách)

- **118/118 kiểm thử đạt**, bao gồm sáu kiểm thử mới cho lọc lớp, hướng, giới hạn số vật, hộp ảnh, trạng thái chưa hỗ trợ, lời đọc khoảng cách và yêu cầu không hợp lệ.
- Đã chạy model thật trên ảnh Kinect: YOLO11n 640 có chai khoảng 0.337; YOLO11s 960 khoảng 0.773 trên cùng ảnh, thời gian suy luận đo riêng khoảng 230 ms với hai luồng CPU. Đây là một phép thử, không đại diện tốc độ/độ chính xác mọi cảnh.
- Đã chạy tiến trình tìm vật cùng vòng xử lý depth trên Kinect; kết quả không tìm thấy khi ảnh chụp tiếp theo không còn chai ở vị trí cầm trước camera. Chưa kiểm chứng được toàn chuỗi nhận diện chai dương tính + khoảng cách chuẩn trong cùng lần chụp.
- Demo tích hợp trả `unsupported` cho bút trong lúc cảnh báo vật cản vẫn chạy. Chưa huấn luyện model bút hoặc tạo ảnh gán nhãn thay người dùng.

## Nguồn

- [YOLO11 — Ultralytics](https://docs.ultralytics.com/models/yolo11/): model detect pretrained COCO 80 lớp.
- [Trọng số chính thức](https://huggingface.co/Ultralytics/YOLO11): tải YOLO11s.
- [Định dạng dataset YOLO](https://docs.ultralytics.com/datasets/detect/): box chuẩn hóa và YAML.
- [Huấn luyện detection](https://docs.ultralytics.com/tasks/detect/): train/val và model custom.

Ultralytics dùng AGPL-3.0 hoặc giấy phép Enterprise; cần xem điều khoản phù hợp nếu phân phối sản phẩm. Các file cũ được sao lưu trong `backups/before_objects_*`.
