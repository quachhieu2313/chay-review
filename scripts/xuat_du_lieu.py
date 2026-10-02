"""Xuất lịch sử tích luỹ ra CSV (mở được bằng Excel) và lập mục lục dữ liệu cho người dùng chuyên nghiệp.
File nằm trong assets/data/xuat/; mục lục ở assets/data/muc_luc_du_lieu.json.
"""
import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
XUAT = OUT / "xuat"


def _doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def _csv(rows, cot):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cot)
    w.writerows(rows)
    return "﻿" + buf.getvalue()  # BOM để Excel đọc đúng tiếng Việt


def _ghi(path, text):
    """Chỉ ghi khi nội dung đổi, tránh tạo commit thừa."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8", newline="")
    return True


def xuat(ls, canh_bao, ghi_json, ngay, gio):
    XUAT.mkdir(parents=True, exist_ok=True)
    doi = False
    r1 = [[s["ngay"], q, m, round(s["so_cp"][m]), s["pct"].get(m, "")]
          for q, ds in ls["nn"].items() for s in ds if s.get("so_cp") for m in sorted(s["so_cp"])]
    r2 = [[s["ngay"], q, m, p] for q, ds in ls["mo"].items() for s in ds for m, p in sorted(s["pct"].items())]
    r3 = [[x["ngay"], x["loai"], x["ma"], x["quy"], x["tieu_de"], x["noi_dung"]] for x in canh_bao]
    r4 = [[q, s["ngay"], m, p] for q, ds in ls["nn"].items() for s in ds if not s.get("so_cp") for m, p in sorted(s["pct"].items())]
    bo = [
        ("lich_su_quy_ngoai.csv", "Số cổ phiếu và tỷ trọng quỹ ETF ngoại nắm giữ theo từng ngày công bố", ["ngay_cong_bo", "quy", "ma_co_phieu", "so_co_phieu", "ty_trong_pct"], r1),
        ("lich_su_quy_mo.csv", "Tỷ trọng top 10 của từng quỹ mở trong nước theo từng kỳ công bố", ["ngay_cong_bo", "quy", "ma_co_phieu", "ty_trong_pct"], r2),
        ("canh_bao.csv", "Cảnh báo dòng tiền quỹ đã phát hiện", ["ngay", "loai", "ma_co_phieu", "quy", "tieu_de", "noi_dung"], r3),
        ("lich_su_quy_khac.csv", "Quỹ công bố một phần danh mục (VEIL top 10, Thiên Hoằng top 20)", ["quy", "ngay_cong_bo", "ma_co_phieu", "ty_trong_pct"], r4),
    ]
    muc = []
    for tep, mo_ta, cot, rows in bo:
        doi |= _ghi(XUAT / tep, _csv(rows, cot))
        muc.append({"tep": f"xuat/{tep}", "mo_ta": mo_ta, "cot": cot, "so_dong": len(rows), "dinh_dang": "csv"})
    json_tep = [
        ("lich_su_quy.json", "Toàn bộ lịch sử danh mục quỹ (JSON thô)"),
        ("canh_bao.json", "Cảnh báo dòng tiền quỹ (JSON)"),
        ("canh_bao.atom", "Cảnh báo dòng tiền quỹ (Atom/RSS, đăng ký bằng trình đọc tin)"),
        ("tong_hop_tuan.json", "Tổng hợp dòng tiền tuần gần nhất"),
        ("phan_tich.json", "Radar dòng tiền: mua/bán ròng, lệch pha nội–ngoại, dữ liệu radar FTSE"),
        ("quy_nam_giu.json", "Cổ phiếu được quỹ mở, quỹ ETF và quỹ ngoại nắm giữ"),
    ]
    for tep, mo_ta in json_tep:
        p = OUT / tep
        if p.exists():
            muc.append({"tep": tep, "mo_ta": mo_ta, "dinh_dang": tep.rsplit(".", 1)[1]})
    moi = {"datasets": muc, "ngay_bat_dau": min((s["ngay"] for ds in ls["nn"].values() for s in ds), default=None),
           "so_quy_ngoai": len(ls["nn"]), "so_quy_mo": len(ls["mo"])}
    cu = _doc(OUT / "muc_luc_du_lieu.json", {})
    if doi or {k: v for k, v in cu.items() if k not in ("cap_nhat", "cap_nhat_luc")} != moi:
        ghi_json(OUT / "muc_luc_du_lieu.json", {**moi, "cap_nhat": ngay, "cap_nhat_luc": gio})
    return len(muc)
