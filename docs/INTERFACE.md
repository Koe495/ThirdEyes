# Giao diện ThirdEyes

Bản ngày 10/11/2026 dùng một cửa sổ dashboard làm giao diện mặc định, không cần cài thêm thư viện.

## Bố cục

- Thanh bên: ra lệnh giọng nói, đọc văn bản, chọn và tìm vật, đọc lại, dừng, âm thanh, trạng thái và thoát. Có thể cuộn trên cửa sổ nhỏ; khi dùng Tab, nút được chọn tự cuộn vào vùng nhìn thấy.
- Tab **Trực tiếp**: RGB và depth giữ đúng tỷ lệ ảnh; ba ô khoảng cách trái / trước / phải; trạng thái micro, giọng đọc và tác vụ. Camera hiển thị tối đa 10 lần/giây để giảm tải giao diện, không thay đổi tần suất xử lý cảnh báo.
- Tab **Kết quả**: ảnh chụp có khung nhận diện và nội dung tiếng Việt cạnh nhau. Có kết quả mới thì tự chuyển tab. Không vẽ kết quả ảnh chụp cũ lên camera đang chạy.
- Nhãn kết nối, dữ liệu mô phỏng, ảnh cũ và thiếu depth có chữ rõ ràng. Cảnh báo nổi bật ở đầu cửa sổ kể cả khi đang xem kết quả.

## Cách mở và thao tác

Chạy `run.bat` để dùng Kinect hoặc `demo.bat` để xem dữ liệu mô phỏng. Giữ nguyên các phím V/O/F/R/X/M/S/T/Q; Escape thoát, Tab chuyển nút, Enter hoặc Space chọn nút. Khi đang chọn loại vật, phím mũi tên dành cho danh sách. Phím V mở phiên nghe theo yêu cầu, không tự mở micro khi khởi động.

Nút được focus có viền tương phản và phát yêu cầu đọc nhãn qua bộ điều phối âm thanh hiện có. Nút bật/tắt âm cập nhật cả nhãn Windows và chữ trên giao diện. Chưa chứng nhận tương thích đầy đủ với mọi trình đọc màn hình; cần thử tiếp với người dùng thực tế.

Ảnh preview giữ tỷ lệ khi thay đổi kích thước. Cửa sổ tối thiểu 1050×660; để xem ảnh rõ hơn nên mở rộng cửa sổ. `--headless` vẫn chạy không giao diện; `--no-controls` giữ cửa sổ OpenCV cũ cho việc chẩn đoán.

## Kiểm chứng

- Đã mở demo và kiểm tra trực quan bằng Windows Computer Use: tab trực tiếp, chuyển tab kết quả, kết quả tìm vật chưa hỗ trợ, phím Q đóng ứng dụng.
- Kiểm tra widget thực ở kích thước 1050×660: preview, ô trạng thái và tab kết quả vẫn có kích thước hợp lệ; nhãn tắt âm cập nhật đúng.
- Bộ kiểm thử có các trường hợp ảnh cũ, dữ liệu mô phỏng, khoảng cách chưa biết, không sửa ảnh đầu vào khi vẽ khung, và ứng dụng đưa kết quả vào dashboard mà không mở cửa sổ OpenCV phụ.

Giao diện cũ được sao lưu trong `backups/before_dashboard_*`. Thay đổi này không thay model, thuật toán đo khoảng cách hay quy tắc ưu tiên âm báo.
