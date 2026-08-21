# Ăn Chay Ở Đâu

Website review quán chay tại TP.HCM và các tỉnh thành: xem menu, đọc đánh giá thật kèm hình ảnh món ăn từ thực khách.

Stack: Django 6 + SQLite (dev) / PostgreSQL free-tier (production) + Bootstrap 5 (CDN) + Cloudinary (lưu ảnh free).

## Chạy dự án ở máy local (Windows)

```
venv\Scripts\activate
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Mở http://127.0.0.1:8000 để xem trang chủ, http://127.0.0.1:8000/admin/ để đăng nhập quản trị, duyệt quán (Restaurants) và duyệt/xem đánh giá.

## Cấu trúc app

- `restaurants/` — quán chay, danh mục, món ăn (menu), trang chủ, trang chi tiết quán, form đề xuất quán, trang giới thiệu
- `reviews/` — đánh giá sao + bình luận + ảnh món ăn do khách upload (tối đa 5MB/ảnh)
- `accounts/` — đăng ký tài khoản (đăng nhập/đăng xuất dùng sẵn của Django tại `/accounts/login/`)

## Lấy dữ liệu quán chay thật

**Không nên scrape Google Maps/Foody/TikTok** — vi phạm điều khoản dịch vụ và bản quyền ảnh/bài review của người dùng các nền tảng đó. Ba cách hợp pháp để có dữ liệu thật:

1. **Người dùng tự đề xuất** — nút "+ Đề xuất quán" trên web (`/de-xuat-quan/`), cần đăng nhập. Quán gửi lên ở trạng thái chờ duyệt, vào `/admin/` chọn quán rồi dùng action "Duyệt và hiển thị công khai" để đăng.
2. **Tự thu thập rồi import CSV** — nếu bạn/bạn bè tự đi khảo sát, gọi điện, hoặc xem trang Facebook công khai của quán để lấy tên/địa chỉ/SĐT, điền vào file theo mẫu `data_templates/quan_chay_mau.csv` rồi chạy:
   ```
   python manage.py import_restaurants_csv data_templates/quan_chay_mau.csv
   ```
   Thêm `--publish` nếu muốn đăng công khai luôn (bỏ qua bước duyệt).
3. **Import từ OpenStreetMap** (dữ liệu bản đồ mở, giấy phép ODbL, hợp pháp để tái sử dụng) — lấy sẵn các quán được gắn tag ăn chay/thuần chay trong một khu vực:
   ```
   python manage.py import_osm_restaurants --bbox "10.72,106.62,10.87,106.72" --province hcm
   ```
   `--bbox` là "south,west,north,east" (lấy tọa độ trên [bboxfinder.com](http://bboxfinder.com)), mặc định là khu trung tâm TP.HCM. Quán import về ở trạng thái **chờ duyệt** — dữ liệu OSM có thể thiếu/lỗi thời nên cần kiểm tra lại trước khi công khai. Chạy lần đầu tại đây đã lấy được ~125 quán trung tâm TP.HCM, chất lượng không đều (có quán chỉ có món chay chứ không phải quán chay 100%) nên hãy lọc kỹ khi duyệt.

## Deploy miễn phí (gợi ý) — không cần tự có server Linux

Toàn bộ dịch vụ bên dưới đều chạy trên hạ tầng của họ (Linux trên cloud) — bạn chỉ cần tài khoản free, không cần tự thuê/quản lý server.

1. **Source control**: đẩy code lên GitHub (repo free): `git remote add origin <url-repo-github-cua-ban>` rồi `git push -u origin main`. Code đã được `git init` + commit sẵn ở máy local.
2. **Database**: tạo Postgres free tại [neon.tech](https://neon.tech) hoặc [supabase.com](https://supabase.com), copy connection string vào biến môi trường `DATABASE_URL`.
3. **Lưu ảnh**: tạo tài khoản free tại [cloudinary.com](https://cloudinary.com) (25GB free), set `USE_CLOUDINARY=True` và `CLOUDINARY_URL` — bắt buộc vì hosting free không giữ file khi redeploy.
4. **Hosting**: vào [render.com](https://render.com) → New → **Blueprint**, trỏ vào repo GitHub — Render sẽ tự đọc file `render.yaml` có sẵn trong repo để tạo Web Service (không cần tự nhập build/start command). Chỉ cần điền thêm 2 biến môi trường còn thiếu trong dashboard: `DATABASE_URL` và `CLOUDINARY_URL`.
5. **Domain**: ban đầu dùng subdomain free `ten-app.onrender.com`, khi có traffic ổn định mới mua domain riêng (~200k-300k/năm).
6. **SEO**: sitemap tự động tại `/sitemap.xml` — submit link này vào [Google Search Console](https://search.google.com/search-console) (free) để được index nhanh.
7. **Thống kê traffic**: tạo tài khoản free tại [analytics.google.com](https://analytics.google.com), lấy Measurement ID (dạng `G-XXXXXXX`) rồi set biến môi trường `GA_MEASUREMENT_ID` — web sẽ tự gắn Google Analytics.
8. **Kiếm tiền**: bắt đầu với Google AdSense (free) khi đã có traffic, sau đó thêm gói "quán nổi bật" trả phí cho chủ quán muốn được ưu tiên hiển thị.

Lưu ý: gói free của Render sẽ "ngủ" sau ~15 phút không có truy cập và mất khoảng 30-50s để "thức dậy" ở lượt truy cập đầu tiên — chấp nhận được ở giai đoạn kiểm chứng ý tưởng, nên nâng cấp gói trả phí khi đã có traffic ổn định.
