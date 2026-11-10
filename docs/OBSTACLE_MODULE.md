# Báo cáo bổ sung module cảnh báo vật cản — ThirdEyes

## Phần đã triển khai

Đã nối luồng **Kinect → xử lý depth → nhận biết nguy cơ → điều phối → âm báo ngắn**, đồng thời bổ sung trạng thái lên giao diện và nhật ký. Module OCR, tìm đồ vật vẫn là placeholder. Không cần nhận dạng tên ghế/tường để cảnh báo độ sâu phía trước.

## Hành vi và ngưỡng mặc định

| Tình huống | Phản hồi |
|---|---|
| Cụm vật cản trong vùng quan sát cách ≤1,50 m | Một âm 1.000 Hz, dài 100 ms sau khi xác nhận |
| Cách ≤1,00 m | Một âm khẩn cao hơn: 1.600 Hz, dài 150 ms |
| Tiến gần ≥0,80 m/s khi cách ≤3 m | Âm khẩn, kể cả chưa vào ngưỡng 1,50 m |
| Tiến gần ≥0,30 m/s và d/v ≤2 giây, trong 3 m | Cũng được xếp mức khẩn |
| Vật đứng yên trước bàn/người đối diện | Giữ cảnh báo hình ảnh, không phát âm nhắc định kỳ |
| Vật đã báo nhưng gần thêm ≥25 cm | Được phép báo lại, có giới hạn tần suất |
| Tăng từ mức gần lên mức khẩn | Được phép báo lại sớm hơn |
| Đã dừng tiến gần ≥1 giây, sau đó tiến nhanh trở lại | Được phép báo lại cho đợt chuyển động mới |
| Đã có dữ liệu xác nhận thông thoáng liên tục ≥1 giây, rồi có vật mới | Mở lại một lượt cảnh báo |
| Depth thiếu/không đủ tin cậy kéo dài ≥1 giây | Một âm trầm 500 Hz, dài 100 ms; không kêu lặp liên tục |

Các ngưỡng là lựa chọn kỹ thuật ban đầu cho demo trong nhà, chưa phải khoảng cách an toàn đã được kiểm chứng. `d/v` chỉ là chỉ số thời gian tương đối từ depth; không phải dự đoán va chạm chính xác.

## Cơ chế chống báo phiền

- Theo dõi riêng trái/giữa/phải, gộp những nguy cơ cùng lúc thành một âm.
- Lưu mức và khoảng cách đã báo của từng đợt. Vật đứng yên, kể cả rất gần, không bị nhắc định kỳ.
- Khoảng cách phải tăng quá ngưỡng gần +25 cm (mặc định 1,75 m), không còn tiến gần nhanh và có đủ dữ liệu liên tục ít nhất 1 giây mới xác nhận hết nguy cơ gần. Mức rất gần có biên nhả riêng +12,5 cm.
- Cảnh báo thường xác nhận ≥0,18 giây; khẩn ≥0,10 giây; đều cần ít nhất 3 khung depth mới. Bỏ qua khung hình lặp của vòng vẽ giao diện.
- Giãn cách âm thông thường ≥0,8 giây. Khi tăng mức so với âm gần nhất, cho phép rút xuống ≥0,25 giây. Đây là giới hạn tần suất, không phải lịch phát lặp.
- Nếu bộ phát âm đang bận, chỉ thử lại khi nguy cơ hiện tại còn tồn tại; không xếp hàng dài các cảnh báo cũ.
- Dữ liệu mất/không hợp lệ không xóa trạng thái vật cản đã báo. Cảnh báo chất lượng depth chỉ được mở lại sau ít nhất 2 giây dữ liệu tốt.
- **M** tắt/bật tiếng; bật lại sẽ đánh giá và báo nguy cơ hiện tại một lần. **T** thử loa; không phát khi đang tắt tiếng.

## Lọc nhiễu và đo tốc độ

Vùng quan sát mặc định: ngang 20–80%, dọc 18–78% ảnh depth. Chia thành lưới 6×3 (18 ô), gộp thành trái/giữa/phải. Việc bỏ mép và phần thấp giúp giảm ảnh hưởng của sàn; đây chưa phải thuật toán nhận biết mặt sàn.

Chỉ sử dụng depth 800–4.000 mm của chế độ thường. Mỗi ô cần ≥30% pixel hợp lệ. Tìm các cụm liên thông ở các phân vị thấp; cụm phải chiếm ≥8% ô và ít nhất 25 pixel. Khoảng cách đại diện dùng trung vị của cụm, tránh để một vài điểm nhiễu rất gần gây báo động. Một vùng chỉ đủ tin cậy để xóa nguy cơ khi cả sáu ô của nó có số đo.

Tốc độ lấy từ lịch sử tối đa 0,55 giây của cùng ô ảnh, cần trải ít nhất 0,25 giây. Yêu cầu ít nhất 3 bước giảm và tổng giảm ≥12 cm, loại chuỗi dao động nhiều hoặc chuỗi bị chi phối bởi một bước nhảy. Đặt lại lịch sử sau mất dữ liệu, gián đoạn hoặc timestamp lùi. Cơ chế này giảm báo nhầm do một vật đột ngột che khuất ảnh, nhưng không loại được mọi chuyển động camera.

## Cấu hình

Sửa `E:\ThirdEyes\config\obstacles.json`, sau đó khởi động lại. Các khóa chính:

| Khóa | Mặc định | Ý nghĩa |
|---|---:|---|
| `near_m` / `critical_m` | 1,50 / 1,00 | Ngưỡng gần/rất gần (m) |
| `release_margin_m` | 0,25 | Biên tránh dao động quanh ngưỡng; mức khẩn dùng nửa biên |
| `approach_mps` / `approach_max_m` | 0,80 / 3,00 | Tốc độ và khoảng xét tiến nhanh |
| `ttc_s` / `ttc_min_speed_mps` | 2,00 / 0,30 | Nhánh d/v và tốc độ tối thiểu |
| `confirm_s` / `urgent_confirm_s` | 0,18 / 0,10 | Thời gian xác nhận tăng mức |
| `clear_s` | 1,00 | Thời gian xác nhận giảm mức/mở lại đợt chuyển động |
| `progress_m` | 0,25 | Gần thêm bao nhiêu mới nhắc lại |
| `cooldown_s` | 0,80 | Khoảng cách thời gian tối thiểu giữa các âm thông thường |
| `history_s` / `speed_min_span_s` | 0,55 / 0,25 | Cửa sổ và khoảng quan sát tối thiểu cho tốc độ |
| `stale_s` | 0,60 | Depth quá cũ |
| `min_valid_fraction` / `min_blob_fraction` | 0,30 / 0,08 | Tỷ lệ pixel hợp lệ/cụm hỗ trợ |
| `fault_delay_s` / `fault_recover_s` | 1,00 / 2,00 | Xác nhận lỗi và mở lại cảnh báo lỗi |
| `roi_left/right/top/bottom` | 0,20 / 0,80 / 0,18 / 0,78 | Vùng quan sát theo tỷ lệ kích thước ảnh |

File cấu hình có kiểm tra kiểu, giới hạn và tên khóa; giá trị lỗi sẽ dừng với thông báo thay vì âm thầm dùng sai ngưỡng. Biên depth 0,8–4 m, lưới 6×3, các tiêu chí tốc độ và thông số âm là hằng số triển khai; không tự thay đổi chế độ near-mode của Kinect.

## Demo và thử nghiệm

Chạy từ `E:\ThirdEyes`:

```powershell
.\.venv\Scripts\python.exe main.py --demo --scenario stationary
.\.venv\Scripts\python.exe main.py --demo --scenario approach
.\.venv\Scripts\python.exe main.py --demo --scenario invalid
.\.venv\Scripts\python.exe main.py --test-sound
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`demo.bat` dùng kịch bản `cycle`: thông thoáng → vật đứng yên → thông thoáng → tiến nhanh → rất gần đứng yên → mất depth → phục hồi, chu kỳ 18 giây. Dữ liệu luôn ghi rõ là giả lập.

Đã qua **41 bài kiểm thử**: gồm 7 bài biên thu nhận có sẵn và 34 bài mới về lọc depth, vật đứng yên, tiến nhanh, lùi xa, bước nhảy giả, nhiễu, tái xuất hiện, ngưỡng, mất depth, timestamp (kể cả timestamp cảm biến bị đứng nhưng thời điểm nhận vẫn thay đổi), âm thanh bận/lỗi, tắt tiếng và đóng tài nguyên khi camera lỗi.

Kiểm tra tích hợp ngày 08/11/2026 trên máy hiện tại:

- Chạy Kinect thật 220 vòng hiển thị: nhận đủ RGB 640×480×3 và depth 640×480, thoát bình thường. Cảnh thật có vùng thiếu depth, báo `PARTIAL` và phát một cảnh báo chất lượng dữ liệu, không nhắc liên tục. Đây chưa phải phép thử thực địa vật tiến gần với tốc độ đã đo.
- Chạy bản cài tại `E:\ThirdEyes` qua 400 vòng demo, khoảng 18,4 giây: một âm gần ở vật đứng yên; âm khẩn khi tiến nhanh và gần thêm; một âm trầm khi mất depth; phục hồi và xóa trạng thái sau khoảng thông thoáng. Không có lỗi phát âm được API Windows báo trong lần thử này.
- Bản trước khi thay đổi được giữ tại `E:\ThirdEyes\backups\before_obstacles_20261108_203233` (các file đã tồn tại trước bản cập nhật).

Đo riêng xử lý depth + nhận biết trên ảnh giả lập 640×480, 100 khung: trung bình khoảng **5,3 ms**, phân vị 95 khoảng **6,1 ms** trên máy hiện tại. Không bao gồm thu camera, dựng giao diện hay âm thanh; không phải cam kết hiệu năng trong mọi cảnh.

Âm thử ngoài sandbox đã được API Windows thực hiện không trả lỗi. Điều này không xác nhận âm lượng loa thực tế hoặc khả năng nghe của người dùng. Khi phát âm lỗi, giao diện hiện `Audio: ERROR`, log ghi lỗi và phần nhận biết/hình ảnh vẫn hoạt động.

## Giới hạn cần giữ khi trình diễn

- Đây là tốc độ **tương đối giữa bề mặt và camera**. Người đeo camera đi tới tường cũng tạo nguy cơ tiến gần; hệ thống chưa phân biệt người di chuyển, vật di chuyển hay camera xoay.
- Không theo dõi danh tính vật thể; vật khác đi vào cùng ô có thể tạo thay đổi depth. Bộ lọc chỉ giảm sai báo.
- Với chế độ depth hiện tại, vùng dưới khoảng 0,8 m có thể không đo được. Khi đó báo chất lượng dữ liệu, không khẳng định đó là vật cực gần hay đường trống.
- Vật mảnh/nhỏ hơn cụm tối thiểu, ngoài ROI, bậc thang/hố, bề mặt phản xạ/trong suốt và cảnh không có depth hợp lệ có thể bị bỏ sót. Chưa có loại bỏ mặt sàn, bù nghiêng hoặc nhận biết hướng di chuyển.
- RGB–depth chưa ánh xạ; ROI và hướng cảnh báo chỉ dựa vào ảnh depth. Âm không mã hóa hướng stereo; hướng hiển thị và lưu log.
- Không có nhắc định kỳ cho vật đứng yên: đây là lựa chọn cố ý theo yêu cầu chống phiền. Cảnh báo hình ảnh vẫn giữ, và thay đổi nguy cơ sẽ mở lại âm báo.

Chỉ sử dụng bản này để thử nghiệm trong môi trường có kiểm soát; cần hiệu chuẩn tư thế camera và thử với các vật, khoảng cách, tốc độ thực tế trước bước phát triển tiếp theo.
