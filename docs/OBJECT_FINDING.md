# ThirdEyes — Tìm vật và bổ sung dataset

Đã tích hợp tại `E:\DeepLearning\ThirdEyes`. Model mặc định **YOLO11s / COCO**, chạy CPU trong `.object-venv` riêng, không ảnh hưởng bộ thư viện OCR/TTS. Runtime dùng trọng số local; Internet chỉ cần lúc cài đặt.

## Sử dụng

1. Chạy `run.bat`.
2. Chọn vật trong danh sách phía trên bảng điều khiển; dùng phím mũi tên hoặc chuột.
3. Bấm nút **Tìm vật đã chọn [F]**, hoặc F khi cửa sổ camera/bảng điều khiển có focus. Khi focus đang ở danh sách, Tab ra nút rồi Enter.
4. Xem cửa sổ kết quả và khung trên **ảnh chụp**, nghe hướng theo mặt đồng hồ và khoảng cách ước tính. Khoảng cách chỉ đọc khi phép đo depth đủ tin cậy. X hủy tìm vật/đọc chữ và dừng âm đọc; F chụp lại để tìm tiếp.

Danh sách chọn hỗ trợ **30 loại vật** với model mặc định, dùng chung cho bảng điều khiển và `--find-target`.

| Tên trong giao diện | Lớp model |
| --- | --- |
| Chai nước | `bottle` |
| Điện thoại | `cell phone` |
| Ghế | `chair` |
| Cốc | `cup` |
| Sách | `book` |
| Laptop | `laptop` |
| Chuột máy tính | `mouse` |
| Bàn phím | `keyboard` |
| Điều khiển | `remote` |
| Ba lô | `backpack` |
| Túi xách | `handbag` |
| Kéo | `scissors` |
| Ly rượu có chân | `wine glass` |
| Bát / tô | `bowl` |
| Thìa / muỗng | `spoon` |
| Nĩa | `fork` |
| Dao | `knife` |
| Tivi | `tv` |
| Đồng hồ | `clock` |
| Vali | `suitcase` |
| Ô / dù | `umbrella` |
| Ghế sofa | `couch` |
| Ghế băng | `bench` |
| Bàn ăn | `dining table` |
| Giường | `bed` |
| Chậu cây | `potted plant` |
| Bình hoa | `vase` |
| Tủ lạnh | `refrigerator` |
| Lò vi sóng | `microwave` |
| Bàn chải đánh răng | `toothbrush` |

“Chai nước” ánh xạ tới `bottle`, không xác nhận chai có nước. Ghế, ghế sofa và ghế băng là ba lớp riêng. **Bút chưa có trong model COCO**; lựa chọn thứ 31 này trả `unsupported` nếu model đang dùng không có lớp `pen`, để phân biệt với `not_found`. Không cần tải thêm trọng số để dùng 30 loại trên. Vật nhỏ như thìa, nĩa, bàn chải có thể khó nhận diện nếu chiếm ít pixel; cần đặt đủ gần, rõ và đủ sáng. Việc có lớp trong model không bảo đảm nhận diện mọi mẫu vật; chưa kiểm thử camera thực tế cho toàn bộ 30 loại.

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

Danh sách hiện dùng các tên lớp tiếng Anh. Model custom cần có `pen`, `bottle`, `cell phone`, `chair`… tương ứng. Lớp không có trong model đang chọn sẽ được báo chưa hỗ trợ.

## Hành vi và giới hạn

- Tìm theo yêu cầu trên một ảnh, không phải theo dõi vật liên tục. Lời đọc bắt đầu bằng “Trong ảnh vừa chụp”. Đổi góc hoặc di chuyển vật thì bấm F lại.
- Tối đa ba kết quả, sắp theo điểm tin cậy; không khẳng định kết quả đầu là vật gần nhất. Hướng tính theo tâm vật trong ảnh đã chuẩn hóa lật ngang.
- Quy ước mặt đồng hồ **trên mặt phẳng ảnh**: 12 giờ ở trên, 3 giờ bên phải, 6 giờ ở dưới, 9 giờ bên trái; các hướng chéo được làm tròn đến giờ gần nhất. Vật gần tâm ảnh (bán kính chuẩn hóa 0,20) được báo “chính giữa khung nhìn”, tránh hướng nhảy thất thường. Đây không phải góc phương vị quanh người dùng: camera phía trước không quan sát được mọi hướng xung quanh.
- Ví dụ lời đọc: “Trong ảnh vừa chụp: Tìm thấy chai nước ở hướng 3 giờ, khoảng cách ước tính 2 mét.” Nhãn trên ảnh có hướng giờ và số mét; khung nhỏ màu vàng là vùng lấy mẫu depth.
- Khi có cặp RGB–depth lệch tối đa 20 ms, dùng ánh xạ SDK để chiếu các điểm depth sang ảnh màu (đã xử lý lật ngang). Object Finder lấy mẫu depth mỗi 2 pixel, đo vùng trung tâm bằng 50% chiều rộng và chiều cao khung vật. Chỉ nhận depth 0,8–4 m, ít nhất 6 mẫu, chênh lệch percentile 10–90 không quá 250 mm; lấy trung vị và đọc làm tròn 0,1 m. OCR vẫn dùng phép đo vùng chữ riêng.
- Nếu vùng trung tâm thiếu depth hoặc lẫn nhiều bề mặt, không lấy khoảng cách nền ở mép khung để thay thế. Kết quả nêu rõ thiếu mẫu, depth chưa ổn định, ảnh chưa đồng bộ hoặc lỗi ánh xạ; log `FIND measurement` ghi trạng thái, số mẫu, khoảng cách và độ lệch thời gian.
- Khoảng cách là độ sâu theo trục camera, chưa hiệu chỉnh thành cự ly đường thẳng 3D. Khung bao không phải mặt nạ phân đoạn: vật trong suốt, có lỗ, phản chiếu hoặc tâm khung nằm trên nền vẫn có thể cho depth nền; cách lấy vùng trung tâm chỉ giảm ảnh hưởng này. Chưa chứng nhận sai số bằng thước.
- Tiến trình suy luận riêng, không chặn vòng cảnh báo depth. OCR và tìm vật không nhận yêu cầu mới đồng thời để giảm tải CPU. Cảnh báo được ưu tiên hơn giọng kết quả; lời đọc kết quả bị trì hoãn quá năm giây sẽ bỏ, kết quả vẫn còn trên màn hình.
- `config/objects.json`: confidence 0.45, IoU 0.45, kích thước suy luận 960, tối đa ba kết quả, hai luồng CPU. Tăng kích thước là nội suy ảnh, không tạo chi tiết camera mới.
- Lần đầu cần nạp model. Ảnh tối, phản sáng, vật trong suốt, che khuất hoặc nhỏ có thể bị bỏ sót/nhận nhầm. Không dùng “chưa thấy” để kết luận vật không tồn tại.
- Chưa thêm tên từng vật vào lệnh giọng nói; chọn vật qua bảng điều khiển hoặc tham số chạy.

## Tạo dataset cho bút và các đồ dùng riêng

Mẫu YAML: `datasets/objects/data.yaml`, gồm bốn lớp `bottle`, `cell phone`, `chair`, `pen`.

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
