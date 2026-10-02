"""Cảnh báo dòng tiền quỹ: phát hiện sự kiện mới, lưu lịch sử (canh_bao.json + canh_bao.atom) và chuẩn bị tin cần gửi.

Tin cần gửi được ghi vào scripts/.canh_bao_moi.json; bước "Gửi cảnh báo" của workflow (scripts/gui_canh_bao.py) đọc file này
và đăng lên GitHub Issues (có email/thông báo điện thoại của GitHub) và Telegram nếu đã cấu hình.
"""
import json
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
FILE_MOI = ROOT / "scripts" / ".canh_bao_moi.json"
SITE = "https://quachhieu2313.github.io/chay-review"
NGUONG_DONG = 20e9     # mua/bán ròng một mã từ 20 tỷ đồng (khoảng 0,76 triệu USD) trở lên mới cảnh báo
TOI_DA_TIN = 6         # số cảnh báo tối đa trong một tin gửi đi, phần còn lại gộp thành "và N cảnh báo khác"
GIU = 300


def _vn(n, d=0):
    s = f"{abs(n):,.{d}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if n < 0 else "") + s


def _doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def phat_hien(ls, dong_nn):
    """Trả danh sách cảnh báo từ hai lần công bố gần nhất của mỗi quỹ ngoại."""
    ds = []
    for ma, dsach in ls["nn"].items():
        if len(dsach) < 2:
            continue
        a, b = dsach[-2], dsach[-1]
        if not a["pct"] and b["pct"]:
            top = sorted(b["pct"].items(), key=lambda t: -t[1])[:3]
            tong = sum(b["pct"].values())
            ds.append({
                "id": f"vn_lan_dau|{ma}|{b['ngay']}", "loai": "vn_lan_dau", "ma": ma, "quy": ma, "ngay": b["ngay"], "muc": 100,
                "tieu_de": f"{ma} lần đầu nắm giữ cổ phiếu Việt Nam",
                "noi_dung": (f"Danh mục {ma} chốt ngày {b['ngay'][8:]}/{b['ngay'][5:7]}/{b['ngay'][:4]} có {len(b['pct'])} cổ phiếu Việt Nam, "
                             f"chiếm {_vn(tong, 2)}% quỹ. Lớn nhất: " + ", ".join(f"{m} {_vn(p, 2)}%" for m, p in top) + "."),
            })
    for x in dong_nn:
        if abs(x["chenh_gt"]) < NGUONG_DONG:
            continue
        mua = x["chenh_gt"] > 0
        den = max(q["den"] for q in x["quy"])
        chi_tiet = ", ".join(f"{q['ma']} {'+' if q['chenh_cp'] > 0 else '−'}{_vn(abs(q['chenh_cp']))} cp" + (" (mua mới)" if q["moi"] else " (bán hết)" if q["thoat"] else "") for q in x["quy"])
        ds.append({
            "id": f"{'mua_manh' if mua else 'ban_manh'}|{x['ma']}|{den}", "loai": "mua_manh" if mua else "ban_manh", "ma": x["ma"],
            "quy": ",".join(q["ma"] for q in x["quy"]), "ngay": den, "muc": abs(x["chenh_gt"]) / 1e9,
            "tieu_de": f"Quỹ ETF ngoại {'mua' if mua else 'bán'} ròng {x['ma']} khoảng {_vn(abs(x['chenh_gt']) / 1e9, 1)} tỷ đồng",
            "noi_dung": f"{x['ma']} ({x['ten']}): {chi_tiet}. Giá trị tính theo giá hiện tại.",
        })
    ds.sort(key=lambda t: -t["muc"])
    return ds


def _atom(ds, luc):
    muc = []
    for x in ds[:50]:
        muc.append(
            "<entry>"
            f"<id>{escape(SITE)}/phan-tich/#{escape(x['id'].replace('|', '-'))}</id>"
            f"<title>{escape(x['tieu_de'])}</title>"
            f"<updated>{x['ngay']}T00:00:00+07:00</updated>"
            f"<link href=\"{SITE}/phan-tich/\"/>"
            f"<summary>{escape(x['noi_dung'])}</summary>"
            "</entry>")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            "<title>Kim Chỉ Nam - Cảnh báo dòng tiền quỹ</title>"
            f"<id>{SITE}/assets/data/canh_bao.atom</id>"
            f"<link href=\"{SITE}/phan-tich/\"/><link rel=\"self\" href=\"{SITE}/assets/data/canh_bao.atom\"/>"
            f"<updated>{luc}</updated>" + "".join(muc) + "</feed>\n")


def xu_ly(ls, dong_nn, ghi_json, ngay_hom_nay, gio):
    """Phát hiện cảnh báo mới, ghi lịch sử và file tin cần gửi. Trả số cảnh báo mới."""
    FILE_MOI.unlink(missing_ok=True)  # tránh gửi lại tin của lần chạy trước
    cu = _doc(OUT / "canh_bao.json", {"ds": []})
    da_co = {x["id"] for x in cu["ds"]}
    moi = [x for x in phat_hien(ls, dong_nn) if x["id"] not in da_co]
    if not moi:
        if not (OUT / "canh_bao.json").exists():
            ghi_json(OUT / "canh_bao.json", {"cap_nhat": ngay_hom_nay, "cap_nhat_luc": gio, "ds": []})
        return 0
    for x in moi:
        x["phat_hien_luc"] = f"{ngay_hom_nay} {gio}"
    ds = (moi + cu["ds"])[:GIU]
    ghi_json(OUT / "canh_bao.json", {"cap_nhat": ngay_hom_nay, "cap_nhat_luc": gio, "ds": ds})
    luc = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%dT%H:%M:%S+07:00")
    (OUT / "canh_bao.atom").write_text(_atom(ds, luc), encoding="utf-8")
    FILE_MOI.write_text(json.dumps({"ds": moi[:TOI_DA_TIN], "them": max(0, len(moi) - TOI_DA_TIN), "trang": f"{SITE}/phan-tich/"},
                                   ensure_ascii=False), encoding="utf-8")
    return len(moi)
