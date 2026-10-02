# Hướng dẫn sửa website Kim Chỉ Nam

Web dùng **Jekyll** (GitHub Pages hỗ trợ sẵn). Sửa file nào, lưu lại và đẩy lên GitHub thì sau 1–2 phút web tự cập nhật.

Có 2 cách sửa:

- **Trên máy:** mở thư mục `E:\KimChiNam` bằng VS Code, sửa xong vào Source Control (`Ctrl+Shift+G`), bấm Commit rồi Sync.
- **Trên web GitHub (không cần cài gì):** vào repo, bấm vào file muốn sửa, bấm biểu tượng bút chì ✏️, sửa xong bấm **Commit changes**.

## Mỗi trang nằm ở đâu

| Trang | File | Địa chỉ |
|---|---|---|
| Trang chủ | `index.html` | `/` |
| Công cụ (lãi kép + mục tiêu hôm nay, hai tab) | `cong-cu.html` | `/cong-cu/` |
| Thị trường | `thi-truong.html` | `/thi-truong/` |
| Danh sách ETF | `etf/index.html` | `/etf/` |
| Chi tiết một ETF | `etf/chi-tiet.html` | `/etf/chi-tiet/?ma=E1VFVN30` |
| Quỹ mô phỏng KCN30 | `quy-mo-phong.html` | `/quy-mo-phong/` |
| Danh sách bài viết | `blog/index.html` | `/blog/` |
| Hỏi đáp | `hoi-dap.html` | `/hoi-dap/` |
| Bản tin thị trường | `ban-tin/index.html` (bài tự viết trong `ban-tin/_posts/`) | `/ban-tin/` |
| Giới thiệu | `gioi-thieu.html` | `/gioi-thieu/` |
| Điều khoản & miễn trừ | `dieu-khoan.html` | `/dieu-khoan/` |
| Chính sách bảo mật | `bao-mat.html` | `/bao-mat/` |
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

Không cần sửa tay. Script `scripts/cap_nhat_du_lieu.py` lấy dữ liệu từ bảng giá công khai của Vietcap (VCI) và KBS (mã nguồn trong `scripts/nguon.py`) rồi ghi vào thư mục `assets/data/`. GitHub Actions chạy script này, được **cron-job.org** gọi theo lịch (lịch "schedule" của GitHub chạy trễ hàng giờ nên không dùng):

- **Cronjob 1, `cap-nhat-trong-phien.yml`: 9:00–14:50 thứ Hai đến thứ Sáu, mỗi 10 phút.** Chỉ lấy bảng giá hiện tại, khoảng 30 giây (`--trong-phien`).
- **Cronjob 2, `cap-nhat-du-lieu.yml`: 16:40 thứ Hai đến thứ Sáu, một lần.** Chạy đầy đủ: tải lại lịch sử, chốt giá đóng cửa, tính lại NAV quỹ mô phỏng và chỉ số rủi ro, **tự viết bản tin cuối phiên** vào `ban-tin/_posts/` (chỉ viết sau 15:05).

Cả hai cronjob gọi `POST https://api.github.com/repos/quachhieu2313/chay-review/actions/workflows/<tên file>/dispatches` với header `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` và body `{"ref":"main"}`. Token là fine-grained token, chỉ cấp cho repo này, quyền Actions: Read and write.

Mỗi lần có dữ liệu mới, script ghi `assets/data/phien.json`; trang web đang mở kiểm tra file này 2 phút một lần và tự tải lại.

Không nên chạy dày hơn 10 phút: GitHub Pages chỉ build lại web khoảng 10 lần mỗi giờ.

- Chạy ngay không cần chờ: vào tab **Actions** trên GitHub, chọn **Cập nhật dữ liệu thị trường**, bấm **Run workflow**.
- Chạy trên máy: `python scripts/cap_nhat_du_lieu.py` (cần `pip install requests pandas`), sau đó commit và push thư mục `assets/data`.

### Đổi tên web, câu khẩu hiệu, mô tả

Sửa file `_config.yml` (các dòng `title`, `tagline`, `description`, `slogan`).

## Số liệu cập nhật thủ công

- `scripts/ro_chi_so_he_so.json`: số cổ phiếu free-float và hệ số trần của 6 rổ chỉ số (nguồn FiinQuant). Lấy lại sau mỗi kỳ cơ cấu chỉ số (tháng 1, tháng 7).
- `scripts/xtrackers_vietnam.json`: quy mô quỹ, NAV, tỷ trọng top 5 của Xtrackers Vietnam Swap (chép từ etf.dws.com). Cập nhật khi cần số mới.
- `scripts/etf_danh_ba.json`: tên quỹ và chỉ số tham chiếu của các ETF trong nước. Thêm dòng khi có quỹ ETF mới niêm yết.

## Bật các dịch vụ bên ngoài (chỉ cần điền vào `_config.yml`)

| Dòng trong `_config.yml` | Tác dụng | Lấy ở đâu |
|---|---|---|
| `goatcounter: "ten-cua-ban"` | Thống kê lượt xem, không cookie | Đăng ký miễn phí ở goatcounter.com, tên chọn lúc đăng ký |
| `cloudflare_analytics_token: "..."` | Thống kê lượt xem của Cloudflare | Cloudflare → Web Analytics → Add site → copy token |
| `webmaster_verifications: google: "..."` | Xác minh với Google Search Console | Search Console → Thêm tài sản → Thẻ HTML → copy phần `content="..."` |
| `kenh_ban_tin: "https://t.me/..."` | Hiện nút "Nhận bản tin" ở chân trang và trang Bản tin | Link kênh Telegram/Zalo OA/trang đăng ký email |
| `lien_he: "..."` | Link góp ý ở các trang Giới thiệu/Điều khoản/Bảo mật | Mặc định là trang Issues của repo |

Sau khi xác minh Search Console, gửi sơ đồ trang: `https://<địa-chỉ-web>/sitemap.xml`.

## Đổi tên repo hoặc dùng tên miền riêng

- **Đổi tên repo** (ví dụ thành `kim-chi-nam`): GitHub → Settings → General → Repository name. Sau đó sửa `baseurl: "/kim-chi-nam"` trong `_config.yml`, sửa tên repo trong URL của 2 cronjob trên cron-job.org và dòng `lien_he`.
- **Tên miền riêng** (ví dụ `kimchinam.vn`): mua tên miền, trỏ bản ghi DNS về GitHub Pages (4 bản ghi A: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, hoặc CNAME `www` → `quachhieu2313.github.io`), vào Settings → Pages → Custom domain điền tên miền và bật Enforce HTTPS. Sau đó trong `_config.yml` đổi `url: "https://kimchinam.vn"` và `baseurl: ""`.

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

## Cảnh báo dòng tiền quỹ

Mỗi lần chạy "Cập nhật dữ liệu thị trường", hệ thống so danh mục quỹ ETF ngoại với lần công bố trước. Khi có quỹ mua/bán ròng một mã từ 20 tỷ đồng, hoặc quỹ (như VWO/VT) lần đầu có cổ phiếu Việt Nam, nó:
- ghi vào `assets/data/canh_bao.json` và `canh_bao.atom` (hiện ở trang Radar dòng tiền, có RSS);
- đăng một **Issue** có nhãn `canh-bao` trong kho mã. GitHub sẽ gửi email/thông báo ứng dụng cho bạn (kiểm tra Settings > Notifications);
- gửi **Telegram** nếu bạn tạo hai secret trong Settings > Secrets and variables > Actions: `TELEGRAM_BOT_TOKEN` (tạo bot qua @BotFather) và `TELEGRAM_CHAT_ID` (gửi một tin cho bot rồi mở `https://api.telegram.org/bot<TOKEN>/getUpdates` để lấy `chat.id`).

Đổi ngưỡng: sửa `NGUONG_DONG` trong `scripts/canh_bao.py`. Tổng hợp tuần tự thành bài trong Bản tin vào chiều thứ Sáu; dữ liệu tải về ở trang `/du-lieu/`.
