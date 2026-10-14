# -*- coding: utf-8 -*-
"""
Gom tin thời sự kinh tế - chứng khoán mới nhất từ RSS các báo Việt Nam và thế giới, ghi ra assets/data/thoi_su.json
cho trang /thoi-su/. Chỉ dùng requests + thư viện chuẩn. Nguồn nào lỗi thì bỏ qua, không làm hỏng cả lượt.

Chạy: python scripts/thoi_su.py
"""
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
VN_TZ = timezone(timedelta(hours=7))
GIU_GIO = 48          # chỉ giữ tin trong 48 giờ gần nhất
TOI_DA_MOI_NGUON = 40
TOI_DA_TONG = 500
RA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "data", "thoi_su.json")

# (tên nguồn, phạm vi, chủ đề mặc định, link RSS)
NGUON = [
    ("CafeF", "vn", "chung-khoan", "https://cafef.vn/thi-truong-chung-khoan.rss"),
    ("CafeF", "vn", "vi-mo", "https://cafef.vn/vi-mo-dau-tu.rss"),
    ("CafeF", "vn", "ngan-hang", "https://cafef.vn/tai-chinh-ngan-hang.rss"),
    ("CafeF", "vn", "bat-dong-san", "https://cafef.vn/bat-dong-san.rss"),
    ("CafeF", "vn", "doanh-nghiep", "https://cafef.vn/doanh-nghiep.rss"),
    ("CafeF", "tg", "quoc-te", "https://cafef.vn/tai-chinh-quoc-te.rss"),
    ("Vietstock", "vn", "chung-khoan", "https://vietstock.vn/830/chung-khoan/co-phieu.rss"),
    ("Vietstock", "vn", "vi-mo", "https://vietstock.vn/761/kinh-te/vi-mo.rss"),
    ("Vietstock", "tg", "quoc-te", "https://vietstock.vn/772/the-gioi/tai-chinh-quoc-te.rss"),
    ("VnEconomy", "vn", "chung-khoan", "https://vneconomy.vn/chung-khoan.rss"),
    ("VnEconomy", "vn", "ngan-hang", "https://vneconomy.vn/tai-chinh.rss"),
    ("VnExpress", "vn", "kinh-te", "https://vnexpress.net/rss/kinh-doanh.rss"),
    ("Tuổi Trẻ", "vn", "kinh-te", "https://tuoitre.vn/rss/kinh-doanh.rss"),
    ("Thanh Niên", "vn", "kinh-te", "https://thanhnien.vn/rss/kinh-te.rss"),
    ("Dân trí", "vn", "kinh-te", "https://dantri.com.vn/rss/kinh-doanh.rss"),
    ("VietNamNet", "vn", "kinh-te", "https://vietnamnet.vn/rss/kinh-doanh.rss"),
    ("CNBC", "tg", "kinh-te", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC", "tg", "chung-khoan", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("CNBC", "tg", "vi-mo", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("Bloomberg", "tg", "chung-khoan", "https://feeds.bloomberg.com/markets/news.rss"),
    ("Financial Times", "tg", "chung-khoan", "https://www.ft.com/markets?format=rss"),
    ("MarketWatch", "tg", "chung-khoan", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Investing.com", "tg", "chung-khoan", "https://www.investing.com/rss/news_25.rss"),
    ("BBC", "tg", "kinh-te", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("New York Times", "tg", "kinh-te", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("The Guardian", "tg", "vi-mo", "https://www.theguardian.com/business/economics/rss"),
]

CHU_DE = {
    "chung-khoan": "Chứng khoán",
    "vi-mo": "Vĩ mô",
    "ngan-hang": "Tài chính - Ngân hàng",
    "tien-te": "Tiền tệ - Lãi suất",
    "hang-hoa": "Vàng - Dầu - Hàng hoá",
    "bat-dong-san": "Bất động sản",
    "doanh-nghiep": "Doanh nghiệp",
    "quoc-te": "Quốc tế",
    "kinh-te": "Kinh tế",
}

# Gắn thêm chủ đề theo từ khoá (không phân biệt hoa thường) - tin có thể thuộc nhiều chủ đề
TU_KHOA = [
    ("chung-khoan", r"chứng khoán|cổ phiếu|vn-?index|hnx|upcom|vn30|khối ngoại|tự doanh|niêm yết|cổ tức|trái phiếu|chứng chỉ quỹ|etf|"
                    r"\bstocks?\b|\bshares?\b|equit|s&p|nasdaq|dow jones|wall street|nikkei|hang seng|\bipo\b|earnings|bond"),
    ("vi-mo", r"gdp|cpi|lạm phát|tăng trưởng kinh tế|xuất khẩu|nhập khẩu|fdi|đầu tư công|ngân sách|thuế|thuế quan|"
              r"inflation|recession|economy|economic|tariff|jobs report|payroll|unemployment"),
    ("tien-te", r"lãi suất|tỷ giá|usd|đô la|ngân hàng nhà nước|nhnn|fed\b|ecb|boj|tiền tệ|"
                r"interest rate|rate cut|rate hike|federal reserve|central bank|dollar|yen|yuan|treasury yield"),
    ("ngan-hang", r"ngân hàng|tín dụng|nợ xấu|bảo hiểm|\bbanks?\b|banking|lender|credit"),
    ("hang-hoa", r"giá vàng|vàng miếng|vàng nhẫn|\bvàng\b|giá dầu|\bdầu\b|xăng|dầu thô|cà phê|gạo|thép|phân bón|hàng hoá|hàng hóa|"
                 r"\bgold\b|\boil\b|crude|brent|opec|commodit|copper|bitcoin|crypto"),
    ("bat-dong-san", r"bất động sản|nhà ở|căn hộ|chung cư|đất nền|khu công nghiệp|real estate|property|housing|mortgage"),
]
TU_KHOA = [(k, re.compile(p, re.I)) for k, p in TU_KHOA]

_THE = re.compile(r"<[^>]+>")
_KHOANG = re.compile(r"\s+")


def _sach(s, dai=0):
    s = html.unescape(html.unescape(s or ""))
    s = _THE.sub(" ", s)
    s = _KHOANG.sub(" ", s).strip()
    if dai and len(s) > dai:
        s = s[:dai].rsplit(" ", 1)[0] + "…"
    return s


def _ngay(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d:
            return d if d.tzinfo else d.replace(tzinfo=VN_TZ)
    except Exception:
        pass
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000") if f.endswith("%z") else s, f)
            if f.endswith("Z") or f == "%Y-%m-%d %H:%M:%S":
                return d.replace(tzinfo=timezone.utc)
            return d if d.tzinfo else d.replace(tzinfo=VN_TZ)
        except Exception:
            continue
    return None


def _anh(it, mo_ta_tho):
    for tag in ("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail", "enclosure"):
        e = it.find(tag)
        if e is not None and (e.get("url") or "").startswith("http") and (tag != "enclosure" or "image" in (e.get("type") or "image")):
            return e.get("url")
    m = re.search(r'<img[^>]+src="(https?://[^"]+)"', html.unescape(mo_ta_tho or ""))
    return m.group(1) if m else ""


def lay_nguon(nguon):
    ten, pham_vi, chu_de, url = nguon
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}, timeout=25)
    r.raise_for_status()
    goc = ET.fromstring(r.content)
    ds = goc.findall(".//item") or goc.findall(".//{http://www.w3.org/2005/Atom}entry")
    ra = []
    for it in ds[:TOI_DA_MOI_NGUON]:
        tieu_de = _sach(it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title"))
        link = (it.findtext("link") or "").strip()
        if not link:
            le = it.find("{http://www.w3.org/2005/Atom}link")
            link = le.get("href", "") if le is not None else ""
        mo_ta_tho = it.findtext("description") or it.findtext("{http://www.w3.org/2005/Atom}summary") or ""
        thoi_gian = _ngay(it.findtext("pubDate") or it.findtext("{http://www.w3.org/2005/Atom}updated")
                          or it.findtext("{http://purl.org/dc/elements/1.1/}date"))
        if not tieu_de or not link.startswith("http") or thoi_gian is None:
            continue
        ra.append({
            "tieu_de": tieu_de,
            "link": link,
            "mo_ta": _sach(mo_ta_tho, 260),
            "anh": _anh(it, mo_ta_tho),
            "nguon": ten,
            "pham_vi": pham_vi,
            "chu_de_goc": chu_de,
            "thoi_gian": thoi_gian,
        })
    return ra


def _gan_chu_de(tin):
    noi_dung = tin["tieu_de"] + " " + tin["mo_ta"]
    cd = [tin["chu_de_goc"]]
    for k, rx in TU_KHOA:
        if k not in cd and rx.search(noi_dung):
            cd.append(k)
    if tin["pham_vi"] == "tg" and "quoc-te" not in cd:
        cd.append("quoc-te")
    # tin chỉ mang nhãn chung "kinh-te" mà khớp chủ đề cụ thể thì bỏ nhãn chung
    if len(cd) > 1 and cd[0] == "kinh-te":
        cd = cd[1:]
    return cd


def _khoa_trung(tieu_de):
    t = re.sub(r"[^\w]+", " ", tieu_de.lower()).strip()
    return hashlib.md5(t.encode("utf-8")).hexdigest()[:12]


def main():
    bat_dau = time.time()
    tat_ca, trang_thai = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        kq = {ex.submit(lay_nguon, n): n for n in NGUON}
        for fut, n in kq.items():
            try:
                ds = fut.result()
                tat_ca.extend(ds)
                trang_thai.append({"nguon": n[0], "url": n[3], "so_tin": len(ds), "loi": ""})
            except Exception as e:
                trang_thai.append({"nguon": n[0], "url": n[3], "so_tin": 0, "loi": type(e).__name__ + ": " + str(e)[:120]})
                print("  Lỗi nguồn", n[0], n[3], "->", e, file=sys.stderr)

    bay_gio = datetime.now(timezone.utc)
    moc = bay_gio - timedelta(hours=GIU_GIO)
    da_co, tin = set(), []
    for t in sorted(tat_ca, key=lambda x: x["thoi_gian"], reverse=True):
        if t["thoi_gian"] < moc or t["thoi_gian"] > bay_gio + timedelta(minutes=30):
            continue
        k1, k2 = t["link"].split("?")[0], _khoa_trung(t["tieu_de"])
        if k1 in da_co or k2 in da_co:   # cùng bài đăng ở nhiều chuyên mục / nhiều nguồn
            continue
        da_co.update((k1, k2))
        t["chu_de"] = _gan_chu_de(t)
        t["thoi_gian"] = t["thoi_gian"].astimezone(VN_TZ).isoformat(timespec="minutes")
        del t["chu_de_goc"]
        tin.append(t)
        if len(tin) >= TOI_DA_TONG:
            break

    if not tin:
        print("Không lấy được tin nào, giữ nguyên file cũ.")
        return 1
    du_lieu = {
        "cap_nhat": datetime.now(VN_TZ).isoformat(timespec="minutes"),
        "giu_gio": GIU_GIO,
        "chu_de": CHU_DE,
        "nguon": sorted(trang_thai, key=lambda x: (x["loi"] != "", x["nguon"])),
        "tin": tin,
    }
    os.makedirs(os.path.dirname(RA), exist_ok=True)
    tam = RA + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(du_lieu, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tam, RA)
    loi = sum(1 for x in trang_thai if x["loi"])
    print("Thời sự: %d tin (VN %d, thế giới %d), %d/%d nguồn lỗi, %.1f giây" % (
        len(tin), sum(t["pham_vi"] == "vn" for t in tin), sum(t["pham_vi"] == "tg" for t in tin), loi, len(NGUON), time.time() - bat_dau))
    return 0


if __name__ == "__main__":
    sys.exit(main())
