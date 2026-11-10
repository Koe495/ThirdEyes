# ThirdEyes — lật ngang camera và xử lý vật đi ra khỏi vùng dưới 0,8 m

Cập nhật ngày 10/11/2026.

## Lật ngang

- Kinect RGB và depth được **lật ngang mặc định tại module thu nhận**, trước khi đưa cho UI, OCR và nhận biết vật cản.
- Mỗi khung mới chỉ được lật một lần; khi SDK chưa có khung mới, dùng lại khung đã chuẩn hóa, không lật qua lại.
- Tọa độ trái/phải của module vật cản và ảnh chụp dùng cho OCR cùng theo ảnh đã chuẩn hóa. Đây không phải phép ánh xạ pixel RGB sang depth.
- `--no-flip` chỉ để chẩn đoán nếu cần xem lại ảnh SDK gốc. Ảnh đọc bằng `--ocr-image` không tự lật, vì đó là file đã có hướng riêng; demo được sinh trực tiếp theo tọa độ chuẩn.

## Vật xuất hiện từ phía sát camera rồi đi xa

Không phát âm cảnh báo vật cản chỉ vì depth mới chuyển từ không đo được sang giá trị gần. Hệ thống quan sát hướng thay đổi trước:

1. Một ô depth vừa có số đo gần sau khi không đo được: chờ tối đa **0,4 giây** để nhận biết xu hướng. Cũng áp dụng khi số đo đột ngột chuyển từ nền xa sang vùng **0,8–0,95 m**, vì vật dưới giới hạn đo có thể để lộ một phần nền phía sau.
2. Nếu có bằng chứng khoảng cách tăng liên tục (ít nhất 3 mẫu, khoảng quan sát ≥0,15 giây, tăng tổng ≥2 cm, tốc độ ước lượng ≥0,05 m/s và không dao động qua lại nhiều): trạng thái **RECEDING**, chưa phát âm báo vật cản cho ô đó.
3. Khi vật đi xa qua vùng cảnh báo, không phát âm “vật mới xuất hiện”.
4. Nếu không có tiến triển đi xa trong **0,6 giây**, hoặc vật tiến ngược lại ít nhất **4 cm**, bỏ chế độ giữ im lặng và áp dụng lại xác nhận cảnh báo bình thường.
5. Vật đứng yên mới xuất hiện gần vẫn được cảnh báo sau khoảng quan sát và thời gian xác nhận. Không giữ im lặng vô hạn. Việc xác nhận hướng này làm cảnh báo cho vật gần mới xuất hiện có thêm tối đa khoảng 0,4 giây chờ ban đầu.

Cơ chế được áp dụng **riêng từng ô depth**. Vật khác trong cùng vùng trái/giữa/phải vẫn có thể gây cảnh báo. UI hiện `EMERGING` khi đang xác định hướng, `RECEDING` khi đi xa; không hiển thị tình huống này như xác nhận đường trống.

Âm báo thiếu/mất chất lượng depth là sự kiện riêng, vẫn được xử lý như trước. Chỉ cảnh báo khoảng cách/chuyển động của vật đang xuất hiện và đi xa được trì hoãn hoặc bỏ qua.

## Cấu hình mới

Trong `E:\ThirdEyes\config\obstacles.json`:

| Khóa | Giá trị | Ý nghĩa |
|---|---:|---|
| `emergence_entry_m` | 0,95 | Mép trên của vùng xuất hiện sát giới hạn đo khi nền xa vẫn còn thấy |
| `emergence_observe_s` | 0,40 | Thời gian quan sát ban đầu để xác định hướng |
| `recession_min_mps` | 0,05 | Tốc độ đi xa tối thiểu theo bộ ước lượng |
| `recession_stop_s` | 0,60 | Không đi xa thêm thì bỏ giữ im lặng |
| `recession_reverse_m` | 0,04 | Quay lại gần hơn mức này thì bỏ giữ im lặng |

Các ngưỡng cảnh báo khoảng cách hiện hành không được thay đổi trong cập nhật này.

## Thử lại

```powershell
cd E:\ThirdEyes
# Camera thật: RGB/depth lật ngang mặc định
.\.venv\Scripts\python.exe main.py

# Demo vật xuất hiện từ vùng không đo được rồi đi xa
.\.venv\Scripts\python.exe main.py --demo --scenario retreat

# Các kiểm thử
.\.ocr-venv\Scripts\python.exe -m unittest discover -s tests -v
```

Đã qua **79/79 kiểm thử**, gồm 17 kiểm thử mới: lật cả hai luồng, không lật lại khung cũ, giữ đúng màu/timestamp, hướng vật cản, ảnh cho OCR, từ invalid/nền xa chuyển qua 0,8 m rồi đi xa, đi xa chậm, đứng lại, quay lại, nhiễu tại biên, khung lặp và vật cản khác cùng vùng. Có kiểm thử riêng tránh để trạng thái cảnh báo cũ của vật sát camera biến nền xa hơn thành vật cản mới.

Lần thử Kinect thật ngày 10/11/2026 chưa khởi tạo được: SDK trả `0x8301027F` (thiếu nguồn cho thiết bị). Vì vậy, lần cập nhật này đã kiểm chứng bằng mô phỏng/kiểm thử và kiểm tra giao diện demo; chưa xác nhận lại trái–phải bằng một vật chuẩn đặt trước Kinect thật. Sau khi cấp nguồn/kết nối lại, chạy `run.bat` để kiểm tra.

## Giới hạn của phép suy luận

Depth không hợp lệ **không chứng minh** vật đang dưới 0,8 m. Bản sửa dùng xu hướng của các số đo sau khi vật xuất hiện; chưa có theo dõi danh tính vật thể. Chuyển động quá chậm so với nhiễu, bị mất dữ liệu lâu hoặc đổi ô ảnh có thể không được nhận là cùng một vật đang đi xa. Khi chưa đủ bằng chứng, hệ thống quay lại cảnh báo khoảng cách theo cấu hình thay vì suy ra đường an toàn.
