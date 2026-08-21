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

Mở http://127.0.0.1:8000 để xem trang chủ, http://127.0.0.1:8000/admin/ để đăng nhập quản trị và thêm quán chay đầu tiên (Restaurants > Add).

## Cấu trúc app

- `restaurants/` — quán chay, danh mục, món ăn (menu), trang chủ + trang chi tiết quán
- `reviews/` — đánh giá sao + bình luận + ảnh món ăn do khách upload
- `accounts/` — đăng ký tài khoản (đăng nhập/đăng xuất dùng sẵn của Django tại `/accounts/login/`)

## Deploy miễn phí (gợi ý)

1. **Source control**: đẩy code lên GitHub (repo free).
2. **Database**: tạo Postgres free tại [neon.tech](https://neon.tech) hoặc [supabase.com](https://supabase.com), copy connection string vào biến môi trường `DATABASE_URL`.
3. **Lưu ảnh**: tạo tài khoản free tại [cloudinary.com](https://cloudinary.com) (25GB free), set `USE_CLOUDINARY=True` và `CLOUDINARY_URL` — bắt buộc vì hosting free không giữ file khi redeploy.
4. **Hosting**: tạo Web Service free tại [render.com](https://render.com), trỏ vào repo GitHub:
   - Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - Start command: `gunicorn core.wsgi`
   - Thêm các biến môi trường ở trên (SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DATABASE_URL, USE_CLOUDINARY, CLOUDINARY_URL) trong phần Environment của Render.
5. **Domain**: ban đầu dùng subdomain free `ten-app.onrender.com`, khi có traffic ổn định mới mua domain riêng (~200k-300k/năm).
6. **SEO**: sitemap tự động tại `/sitemap.xml` — submit link này vào [Google Search Console](https://search.google.com/search-console) (free) để được index nhanh.
7. **Kiếm tiền**: bắt đầu với Google AdSense (free) khi đã có traffic, sau đó thêm gói "quán nổi bật" trả phí cho chủ quán muốn được ưu tiên hiển thị.

Lưu ý: gói free của Render sẽ "ngủ" sau ~15 phút không có truy cập và mất khoảng 30-50s để "thức dậy" ở lượt truy cập đầu tiên — chấp nhận được ở giai đoạn kiểm chứng ý tưởng, nên nâng cấp gói trả phí khi đã có traffic ổn định.
