"""Gửi các cảnh báo mới (scripts/.canh_bao_moi.json) ra ngoài. Chạy trong GitHub Actions sau khi đã đẩy dữ liệu.

- GitHub Issues: luôn gửi (dùng GITHUB_TOKEN có sẵn); GitHub sẽ báo qua email/ứng dụng điện thoại cho người theo dõi kho mã.
- Telegram: chỉ gửi nếu có hai biến môi trường TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID (đặt trong Settings > Secrets > Actions).
Đặt DRY_RUN=1 để chỉ in nội dung, không gửi.
"""
import json
import os
import sys
from html import escape
from pathlib import Path

import requests

FILE = Path(__file__).resolve().parent / ".canh_bao_moi.json"


def noi_dung(d):
    dong = [f"• <b>{escape(x['tieu_de'])}</b>\n  {escape(x['noi_dung'])}" for x in d["ds"]]
    if d.get("them"):
        dong.append(f"… và {d['them']} cảnh báo khác, xem trên trang web.")
    dong.append(f"Chi tiết: {d['trang']}")
    return "\n\n".join(dong)


def main():
    if not FILE.exists():
        print("Không có cảnh báo mới.")
        return 0
    d = json.loads(FILE.read_text(encoding="utf-8"))
    if not d.get("ds"):
        return 0
    tieu_de = d["ds"][0]["tieu_de"] + (f" (+{len(d['ds']) - 1 + d.get('them', 0)})" if len(d["ds"]) + d.get("them", 0) > 1 else "")
    html = noi_dung(d)
    if os.environ.get("DRY_RUN"):
        print(tieu_de, "\n", html)
        return 0
    loi = 0
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if repo and token:
        body = html.replace("<b>", "**").replace("</b>", "**")
        res = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                            json={"title": "Cảnh báo: " + tieu_de, "body": body, "labels": ["canh-bao"]})
        print("GitHub Issue:", res.status_code)
        loi += res.status_code >= 300
    bot, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if bot and chat:
        res = requests.post(f"https://api.telegram.org/bot{bot}/sendMessage", timeout=30,
                            json={"chat_id": chat, "text": html, "parse_mode": "HTML", "disable_web_page_preview": True})
        print("Telegram:", res.status_code)
        loi += res.status_code >= 300
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
