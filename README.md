# Xưởng Dựng Video Tự Động — Lá Số Tử Vi

Công cụ web chạy trên **máy của bạn**: thả kịch bản + ảnh từng cảnh vào, hệ thống tự động:

- Tạo giọng đọc tiếng Việt (giọng nữ ấm áp / nam trầm ấm), miễn phí, không cần API key.
- Tạo hiệu ứng chuyển động Ken Burns (zoom nhẹ) cho từng ảnh, khớp đúng thời lượng giọng đọc.
- Gắn phụ đề **karaoke** — chữ tô sáng đúng lúc giọng đọc đến từ đó (yếu tố tăng retention mạnh nhất trên Shorts).
- Hoà nhạc nền (nếu bạn tải lên) ở âm lượng thấp hơn giọng đọc.
- Xuất video dọc 1080×1920 (chuẩn YouTube Shorts) + 1 thumbnail nháp.
- Tự soạn sẵn **mô tả + hashtag** theo đúng công thức đã đối chiếu với kênh tham khảo thực tế (`#tamlinh #tuvi #huyenhoc #phongthuy` + hashtag chủ đề + hashtag thương hiệu kênh) — copy 1 nút là dán được lên YouTube/TikTok.

Có 2 cách chạy: **cục bộ trên máy bạn** (mục 1-3 bên dưới, dữ liệu không rời máy) hoặc **online qua 1 link web** dùng được trên điện thoại/máy tính bất kỳ (mục 7).

## 1. Cài đặt

Cần có sẵn:
- **Python 3.9+**
- **ffmpeg** đã cài và có trong PATH

Cài ffmpeg:
- Windows: tải tại https://www.gyan.dev/ffmpeg/builds/ (bản "release full"), giải nén, thêm thư mục `bin` vào biến môi trường PATH. Hoặc nếu có Chocolatey: `choco install ffmpeg`.
- macOS: `brew install ffmpeg`
- Linux (Ubuntu/Debian): `sudo apt install ffmpeg`

Kiểm tra đã cài đúng chưa:
```
ffmpeg -version
```

Cài thư viện Python:
```
pip install -r requirements.txt
```

## 2. Chạy

```
python app.py
```

Mở trình duyệt tại: **http://127.0.0.1:8000**

## 3. Cách dùng

1. **Dán kịch bản** — dùng đúng định dạng `SCENE 1: ...`, `SCENE 2: ...` (giống các prompt viết kịch bản trong tài liệu kế hoạch kênh) hoặc đơn giản là mỗi cảnh 1 đoạn, cách nhau 1 dòng trống.
2. **Chọn ảnh** — chọn nhiều ảnh cùng lúc, đúng thứ tự cảnh. Đặt tên file `1.jpg, 2.jpg, 3.jpg...` để chắc chắn đúng thứ tự (hệ thống sắp theo tên file). Nếu ít ảnh hơn số cảnh, ảnh cuối sẽ tự lặp lại cho các cảnh còn thiếu.
3. **Chọn giọng đọc**, đặt **tiêu đề** (dùng để làm thumbnail nháp và sinh hashtag chủ đề), tải lên **nhạc nền** nếu muốn, điền **hashtag thương hiệu kênh** nếu muốn (VD tên kênh không dấu).
4. Bấm **Tạo video** — theo dõi log tiến trình, khi xong sẽ có video xem trước ngay trên trang, nút tải video/thumbnail, và khung mô tả + hashtag đã soạn sẵn để copy.

## 4. Ghi chú quan trọng

- **Cần Internet khi tạo giọng đọc** (dùng dịch vụ Edge TTS miễn phí của Microsoft, không cần đăng ký/API key). Nếu máy không có mạng lúc đó, ứng dụng vẫn xuất được video nhưng audio sẽ câm (im lặng) và có cảnh báo trong log — chạy lại khi có mạng để có giọng đọc thật.
- Thumbnail được tạo tự động chỉ là **bản nháp nhanh** — nên tinh chỉnh lại theo công thức thumbnail trong tài liệu kế hoạch kênh (chữ to, tương phản cao, 1 yếu tố trung tâm gây chú ý).
- Video xuất ra ở độ phân giải 1080×1920, 30fps, để tối ưu thời gian xử lý trên máy cá nhân (không cần GPU).
- Muốn đổi giọng đọc khác/ngôn ngữ khác: xem danh sách giọng Edge TTS bằng lệnh `edge-tts --list-voices` rồi thêm vào `VOICES` trong `pipeline.py`.
- Ứng dụng lưu file tạm trong thư mục `jobs/<job_id>/` — có thể xoá định kỳ để giải phóng dung lượng.

## 5. Cấu trúc mã nguồn

```
app.py           Flask server: nhận form, quản lý job nền, trả trạng thái/tải file
pipeline.py      Lõi xử lý: tách kịch bản, TTS, Ken Burns, phụ đề karaoke (.ass), hoà âm, xuất video
templates/       Giao diện web
static/          CSS + JS giao diện
jobs/            File tạm + video xuất ra (tạo tự động khi chạy)
```

## 6. Hướng mở rộng (nếu muốn tự nâng cấp thêm)

- Thêm bước tự động upload lên YouTube (YouTube Data API v3) sau khi render xong.
- Thêm module tính lá số Tử Vi (an sao) để tự sinh dữ liệu cung Mệnh/đại vận/tiểu hạn, ghép thẳng vào prompt viết kịch bản.
- Chạy nhiều job song song bằng hàng đợi (Celery/RQ) thay vì thread đơn giản, nếu render số lượng lớn.
- Thêm chuyển cảnh mờ dần (crossfade) giữa các clip thay vì cắt cứng.

## 7. Chạy online qua 1 link web (Render.com — miễn phí, không cần thẻ)

Cách này cho ra 1 link dạng `https://ten-cua-ban.onrender.com` mở được trên điện thoại và máy tính bất kỳ, không cần cài gì. Đổi lại: máy chủ miễn phí yếu hơn máy cá nhân và **tự ngủ sau 15 phút không dùng** — lần mở lại đầu tiên sẽ mất khoảng 1 phút để "thức dậy", đây là bình thường, không phải lỗi.

**Bước 1 — Đưa code lên GitHub** (nơi chứa code để Render đọc và build):
1. Tạo tài khoản tại [github.com](https://github.com) nếu chưa có (miễn phí).
2. Bấm nút **+** góc trên phải → **New repository** → đặt tên (VD `tuvi-video-app`) → **Create repository**.
3. Trong repo vừa tạo, bấm **Add file → Upload files**.
4. Giải nén file zip đã tải, kéo **toàn bộ nội dung bên trong** thư mục (app.py, pipeline.py, Dockerfile, requirements.txt, README.md, .dockerignore, .gitignore, thư mục `templates/`, thư mục `static/`) vào khung upload. Bấm **Commit changes**.

**Bước 2 — Tạo Web Service trên Render:**
1. Tạo tài khoản tại [render.com](https://render.com) — chọn **Sign up with GitHub** để không cần đăng ký/thẻ tín dụng và tự liên kết repo luôn.
2. Bấm **New +** → **Web Service** → chọn repo `tuvi-video-app` vừa tạo.
3. Render tự nhận diện `Dockerfile` có sẵn trong repo — để nguyên các tuỳ chọn mặc định.
4. Ở mục **Instance Type**, chọn **Free**.
5. Ở mục **Environment Variables**, thêm 2 biến để khoá mật khẩu (bắt buộc, vì link Render là public, ai có link cũng vào dùng được nếu không khoá):
   - `APP_USERNAME` = tên đăng nhập bạn tự chọn
   - `APP_PASSWORD` = mật khẩu bạn tự chọn
6. Bấm **Create Web Service** — chờ khoảng 3-5 phút để Render build xong (xem log build trực tiếp trên trang).
7. Khi thấy trạng thái **Live**, Render cho 1 link dạng `https://tuvi-video-app-xxxx.onrender.com` — mở link đó trên điện thoại/máy tính, nhập đúng `APP_USERNAME`/`APP_PASSWORD` vừa đặt là dùng được.

**Lưu ý khi dùng bản online:**
- Sau khi đổi file trong repo GitHub, vào lại trang Render và bấm **Manual Deploy → Deploy latest commit** để cập nhật.
- Nếu vừa mở link sau một lúc không dùng, trang có thể load chậm ~1 phút (server đang "thức dậy") — cứ đợi, đừng tắt tab.
- Gói free giới hạn RAM (512MB) — nếu dựng video quá nhiều ảnh/cảnh cùng lúc có thể bị chậm hoặc lỗi hết bộ nhớ; nên dựng từng video một, khoảng 8-14 cảnh là hợp lý.
