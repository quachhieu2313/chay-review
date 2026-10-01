# Hướng dẫn sửa website Kim Chỉ Nam

Web dùng **Jekyll** (GitHub Pages hỗ trợ sẵn). Sửa file nào, lưu lại và đẩy lên GitHub thì sau 1–2 phút web tự cập nhật.

Có 2 cách sửa:

- **Trên máy:** mở thư mục `E:\KimChiNam` bằng VS Code, sửa xong vào Source Control (`Ctrl+Shift+G`), bấm Commit rồi Sync.
- **Trên web GitHub (không cần cài gì):** vào repo, bấm vào file muốn sửa, bấm biểu tượng bút chì ✏️, sửa xong bấm **Commit changes**.

## Mỗi trang nằm ở đâu

| Trang | File | Địa chỉ |
|---|---|---|
| Trang chủ | `index.html` | `/` |
| Mục tiêu hôm nay | `muc-tieu.html` | `/muc-tieu/` |
| Máy tính lãi kép | `lai-kep.html` | `/lai-kep/` |
| Thị trường | `thi-truong.html` | `/thi-truong/` |
| Danh sách ETF | `etf/index.html` | `/etf/` |
| Chi tiết một ETF | `etf/chi-tiet.html` | `/etf/chi-tiet/?ma=E1VFVN30` |
| Quỹ mô phỏng KCN30 | `quy-mo-phong.html` | `/quy-mo-phong/` |
| Danh sách bài viết | `blog/index.html` | `/blog/` |
| Hỏi đáp | `hoi-dap.html` | `/hoi-dap/` |
| Trang lỗi 404 | `404.html` | |

Đầu trang (menu, logo) và chân trang chỉ nằm ở **một chỗ**: `_layouts/default.html`. Sửa ở đó là mọi trang đổi theo.

## Việc hay làm (không cần biết code)

### Viết bài blog mới

1. Tạo file mới trong thư mục `_posts`, đặt tên theo mẫu `NĂM-THÁNG-NGÀY-ten-khong-dau.md`, ví dụ `2026-10-15-dau-tu-dinh-ky.md`.
2. Dán khung sau vào đầu file rồi viết nội dung bên dưới:

```markdown
---
title: Tiêu đề bài viết
description: Một câu tóm tắt, hiện ở thẻ bài viết và khi chia sẻ Facebook/Zalo.
chu_de: Đầu tư
phut_doc: 5
hinh: tron
---

Đoạn mở đầu...

## Tiêu đề mục

Nội dung. **In đậm**, *in nghiêng*, [chữ có link](https://...).

- Gạch đầu dòng
- Gạch đầu dòng
```

- `hinh` là hình trang trí trên thẻ bài viết, chọn một trong: `tron`, `vuong`, `tam-giac`, `sao`.
- Bài mới tự động hiện ở trang chủ (3 bài mới nhất), trang Blog và chân trang.
- Muốn có khung ghi chú màu vàng, dùng:

```markdown
<div class="callout" markdown="1">
**Lưu ý:** nội dung ghi chú.
</div>
```

Lưu ý: bài có ngày ở tương lai sẽ **chưa hiện** cho tới đúng ngày đó.

### Sửa / thêm câu hỏi ở trang Hỏi đáp

Sửa file `_data/hoi_dap.yml`. Mỗi câu gồm 2 dòng `hoi:` và `dap:`, thụt lề đúng 2 dấu cách như các câu có sẵn.

### Sửa menu

Sửa file `_data/menu.yml`: đổi `ten` để đổi chữ hiển thị, đổi thứ tự các khối để đổi thứ tự menu.

### Số liệu thị trường, ETF, quỹ mô phỏng

Không cần sửa tay. Script `scripts/cap_nhat_du_lieu.py` lấy dữ liệu qua vnstock và ghi vào thư mục `assets/data/`. GitHub Actions tự chạy script này lúc **16:30 thứ Hai đến thứ Sáu**.

- Chạy ngay không cần chờ: vào tab **Actions** trên GitHub, chọn **Cập nhật dữ liệu thị trường**, bấm **Run workflow**.
- Chạy trên máy: `python scripts/cap_nhat_du_lieu.py` (cần `pip install vnstock pandas`), sau đó commit và push thư mục `assets/data`.

### Đổi tên web, câu khẩu hiệu, mô tả

Sửa file `_config.yml` (các dòng `title`, `tagline`, `description`, `slogan`).

## Muốn bỏ một phần của web

Xoá file trang tương ứng, rồi xoá mục đó khỏi `_data/menu.yml` và các link trỏ tới nó ở trang chủ (`index.html`) và chân trang (`_layouts/default.html`). Cách nhanh nhất là nhắn Claude "bỏ phần ...".

## Nếu web bị lỗi sau khi sửa

GitHub sẽ gửi email báo build lỗi, và web vẫn giữ bản cũ đang chạy. Lỗi thường gặp:

- Thụt lề sai trong file `.yml` (phải dùng dấu cách, không dùng Tab).
- Trong file `.yml`, nội dung có dấu `:` thì phải bọc cả câu trong ngoặc kép `"..."`.
- Thiếu dòng `---` ở đầu hoặc cuối phần khai báo của bài blog.

Xem chi tiết lỗi tại tab **Actions** của repo trên GitHub.

## Phần giao diện và tính năng (cần biết code)

- Màu sắc, kiểu chữ, bố cục: `assets/style.css` (bảng màu nằm ở đầu file).
- Tính năng chạy được: `assets/app.js` (menu, giao diện tối, bảng mục tiêu, máy tính lãi kép) và `assets/data-pages.js` (ETF, quỹ mô phỏng, thị trường, biểu đồ).
