# ThirdEyes — Âm báo stereo theo hướng vật cản

Đã tích hợp vào `E:\ThirdEyes`, mặc định bật khi chạy `run.bat`.

| Tình huống | Âm thanh |
|---|---|
| Vật cản bên trái | Chỉ kênh trái |
| Vật cản phía trước | Hai kênh bằng nhau |
| Vật cản bên phải | Chỉ kênh phải |
| Cảnh báo gần | 1.000 Hz, 100 ms mỗi hướng |
| Cảnh báo khẩn | 1.600 Hz, 150 ms mỗi hướng |
| Depth không khả dụng | 500 Hz, 100 ms ở cả hai kênh |

Hướng âm báo là **hướng có vật cản**, không phải hướng khuyên người dùng di chuyển. Hướng lấy từ depth đã lật ngang; không lật lại khi phát âm. Đây là định hướng ba vùng, chưa phải âm thanh không gian 3D/HRTF hoặc góc liên tục.

## Nhiều vật cản và chống lặp

Mỗi lượt chọn các hướng đang cần thông báo có mức cảnh báo cao nhất. Trong cùng mức, hướng gần nhất phát trước; nếu bằng khoảng cách, ưu tiên phía trước. Mỗi hướng có một âm riêng, cách nhau 60 ms; tối đa ba âm, tổng tối đa 570 ms. Không trộn trái và phải đồng thời vì dễ nhầm với vật cản phía trước.

Hướng có mức cảnh báo thấp hơn chưa được đánh dấu là đã thông báo; hệ thống xét lại từ dữ liệu hiện tại sau thời gian chờ hiện hành. Các cơ chế chống lặp khi đứng yên, phát lại khi nguy cơ tăng, quan sát vật mới xuất hiện và bỏ âm báo khi vật đang đi xa vẫn được giữ. Báo lỗi depth vẫn độc lập. Âm báo ngắt giọng OCR như trước.

Một luồng nền phát âm, không chặn camera và không tích hàng đợi âm báo cũ. Khi đang phát, yêu cầu mới được xét lại ở các khung sau nếu nguy cơ còn tồn tại; không ngắt giữa một chuỗi ngắn. Vì vậy, cảnh báo mới có thể phải chờ chuỗi đang phát kết thúc. Lỗi phát âm hiển thị trên giao diện và ghi log; không thay âm stereo bằng một tiếng beep chung.

## Cách thử

Đeo tai nghe stereo đúng bên L/R, chọn đúng thiết bị phát mặc định trong Windows và tắt chế độ Mono audio. Loa laptop hoặc một tai nghe đơn sẽ khó phân biệt hướng bằng cách này. Chương trình không tự xác nhận được cách đeo tai nghe hay việc Windows/thiết bị đang gộp hai kênh.

Chạy `E:\ThirdEyes\test_stereo.bat`, hoặc bấm **T** trong cửa sổ camera: nghe lần lượt **trái → giữa → phải**, mỗi âm 100 ms, cách nhau 120 ms. M vẫn bật/tắt âm như trước.

```powershell
cd E:\ThirdEyes
.\run.bat --test-sound
# Nếu tai nghe đang đảo trái/phải:
.\run.bat --swap-audio-channels
# Chỉnh biên độ âm báo (mặc định 0.25, lớn hơn 0 và không quá 1):
.\run.bat --audio-volume 0.15
```

Tùy chọn áp dụng cho lần chạy đó. Mức 0.25 là biên độ tín hiệu, không phải mức âm lượng vật lý hoặc phần trăm âm lượng Windows. Âm phía trước chia đều năng lượng cho hai kênh. Có đoạn tăng/giảm biên độ 5 ms để giảm tiếng tách ở đầu/cuối âm. Không thêm thư viện, không kết nối mạng, không thay cấu hình ngưỡng khoảng cách.

## Kiểm chứng

- **93/93 kiểm thử đạt**, gồm 14 kiểm thử mới cho stereo, thứ tự hướng, ưu tiên, trạng thái đã thông báo, đảo kênh, biên độ, kết thúc luồng và chế độ thử âm.
- Đã gọi phát chuỗi thử thật qua Windows bằng môi trường `.venv` của dự án; hoàn tất, mã thoát 0.
- Việc phân kênh được kiểm tra trực tiếp trên mẫu PCM. Chưa xác nhận bằng tai nghe của người dùng hoặc đối chiếu vị trí vật thật trước Kinect trong lần cập nhật này.

Mã chính: `thirdeyes/stereo_audio.py`, `thirdeyes/coordinator_audio.py`, `thirdeyes/app.py`. Phát WAV trong bộ nhớ bằng PlaySound đồng bộ trong luồng nền, theo [tài liệu winsound của Python](https://docs.python.org/3.14/library/winsound.html); không dùng SND_ASYNC với SND_MEMORY.
