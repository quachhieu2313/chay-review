"""Derived fund-portfolio indicators based on collected public disclosures and price data.

1. Biến động danh mục quỹ ETF nước ngoài: chênh lệch số cổ phiếu nắm giữ giữa hai lần công bố liên tiếp.
2. Biến động danh mục quỹ mở trong nước: mã vào/ra top 10 và thay đổi tỷ trọng giữa hai kỳ công bố.
3. So sánh mẫu top 10 nội - ngoại trên cùng phạm vi công bố; mã không xuất hiện không được xem là tỷ trọng 0.
4. Radar FTSE: dữ liệu nền (giá, free-float, thanh khoản) cho bộ tính áp lực mua thụ động chạy trên trình duyệt.
"""
import json
from pathlib import Path

import canh_bao
import tong_hop_tuan
import xuat_du_lieu

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
GIU_TOI_DA = 150  # số lần chụp lưu lại cho mỗi quỹ
QUY_DAY_DU = {"VNM", "VNAM", "KPHO", "Fubon", "VWO", "VT"}  # holdings được nguồn công bố có số lượng
FX_MAC_DINH = 26300
VON_MAC_DINH_TY_USD = 2.5   # theo công bố của Vanguard (tin vietnam.vn), người dùng chỉnh được
DOT_DAU_PCT = 25            # FTSE chia 4 đợt từ 09/2026 đến 09/2027


def _doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def _chup(ls, ma, ngay, so_cp, pct, audit=None, audit_context=None):
    """Store a new disclosure or record a same-date correction before replacing it."""
    if not ngay:
        return False
    dsach = ls.setdefault(ma, [])
    muc = {"ngay": ngay, "pct": pct}
    if so_cp is not None:
        muc["so_cp"] = so_cp
    chi_so = next((i for i, snapshot in enumerate(dsach) if snapshot["ngay"] == ngay), None)
    if chi_so is not None:
        cu = dsach[chi_so]
        if cu == muc:
            return False
        if audit is not None:
            thay_doi = {}
            for field in ("pct", "so_cp"):
                before, after = cu.get(field), muc.get(field)
                if before == after:
                    continue
                if before is None or after is None:
                    thay_doi[field] = {
                        "co_du_lieu_truoc": before is not None,
                        "co_du_lieu_sau": after is not None,
                    }
                    continue
                for ticker in sorted(set(before) | set(after)):
                    if before.get(ticker) != after.get(ticker):
                        thay_doi.setdefault(field, {})[ticker] = {
                            "truoc": before.get(ticker),
                            "co_truoc": ticker in before,
                            "sau": after.get(ticker),
                            "co_sau": ticker in after,
                        }
            audit.append({
                **(audit_context or {}),
                "ma_quy": ma,
                "ngay_danh_muc": ngay,
                "thay_doi": thay_doi,
            })
            del audit[:-500]
        dsach[chi_so] = muc
        return True
    if dsach and dsach[-1]["ngay"] > ngay:
        return False
    dsach.append(muc)
    del dsach[:-GIU_TOI_DA]
    return True


def _chenh_so_cp(a, b):
    """b - a per ticker; only use for complete holdings feeds within the same filtered universe."""
    return {m: b.get(m, 0.0) - a.get(m, 0.0) for m in set(a) | set(b) if abs(b.get(m, 0.0) - a.get(m, 0.0)) > 0}


def so_sanh_top10(quy_mo, quy_nn, vn100, cty, ngay_vn100=None):
    """Compare disclosed top-10 records only; absence from a top-10 is unknown, not zero."""
    noi = [q for q in quy_mo if q.get("ngay") and q.get("top")]
    ngoai = [q for q in quy_nn if q.get("ngay") and q.get("top")]

    def top10(q):
        return sorted(q["top"], key=lambda row: -row[1])[:10]

    def sample(rows):
        return [{
            "ma": q["ma"],
            "ngay": q["ngay"],
            "loai_quy": q.get("loai_quy") or {
                "STOCK": "Quỹ cổ phiếu",
                "BALANCED": "Quỹ cân bằng",
            }.get(q.get("loai")),
            "ngay_thu_thap": q.get("ngay_thu_thap"),
            "ngay_cong_bo": q.get("ngay_cong_bo"),
            "ngay_cong_bo_trang_thai": q.get("ngay_cong_bo_trang_thai", "nguon_khong_cung_cap"),
            "trang_thai_nguon": q.get("trang_thai_nguon"),
            "trang_thai_doi_chieu": q.get("trang_thai_doi_chieu", "chua_doi_chieu_nguon"),
        } for q in rows]

    def holdings(rows):
        result = {}
        for q in rows:
            per_fund = {}
            for ticker, weight in top10(q):
                per_fund[ticker] = per_fund.get(ticker, 0.0) + float(weight)
            for ticker, weight in per_fund.items():
                result.setdefault(ticker, []).append(weight)
        return result

    noi_holdings = holdings(noi)
    ngoai_holdings = holdings(ngoai)
    lech = []
    for ticker in set(noi_holdings) & set(ngoai_holdings):
        noi_values = noi_holdings[ticker]
        ngoai_values = ngoai_holdings[ticker]
        noi_mean = sum(noi_values) / len(noi_values)
        ngoai_mean = sum(ngoai_values) / len(ngoai_values)
        vn_weight = vn100.get(ticker)
        lech.append({
            "ma": ticker,
            "ten": cty.get(ticker, (ticker, "Khác"))[0],
            "vn100": round(vn_weight, 2) if vn_weight is not None else None,
            "ngay_vn100": ngay_vn100,
            "noi_tb": round(noi_mean, 2),
            "ngoai_tb": round(ngoai_mean, 2),
            "so_noi": len(noi_values),
            "so_ngoai": len(ngoai_values),
            "lech_noi": round(noi_mean - vn_weight, 2) if vn_weight is not None else None,
            "lech_ngoai": round(ngoai_mean - vn_weight, 2) if vn_weight is not None else None,
            "nn_tru_noi": round(ngoai_mean - noi_mean, 2),
            "pham_vi": "top10",
        })
    lech.sort(key=lambda row: (-abs(row["nn_tru_noi"]), row["ma"]))
    ngoai_chua_co_mau = [
        {**entry, "ly_do": "Không có ngày báo cáo hợp lệ hoặc không có mã Việt Nam trong dữ liệu đã lọc"}
        for entry in sample([q for q in quy_nn if not q.get("ngay") or not q.get("top")])
    ]
    return lech, {
        "pham_vi": "top10",
        "ngay_vn100": ngay_vn100,
        "noi_so_quy": len(noi),
        "noi_mau": sample(noi),
        "ngoai_so_quy": len(ngoai),
        "ngoai_mau": sample(ngoai),
        "ngoai_chua_co_mau": ngoai_chua_co_mau,
        "ghi_chu": "Chỉ so mã được công bố trong top 10 ở cả hai nhóm; mã vắng mặt là chưa công bố trong phạm vi này, không phải tỷ trọng 0. Trung bình tính trên các quỹ đã công bố mã đó.",
    }


def tinh(quy_mo, quy_nn, gia, cty, ghi_json, ngay_hom_nay, gio):
    """quy_mo: quỹ mở (Fmarket); quy_nn: quỹ ngoại; gia: {mã: giá VND}; cty: {mã: (tên, ngành)}."""
    ls = _doc(OUT / "lich_su_quy.json", {"nn": {}, "mo": {}})
    audit_path = OUT / "lich_su_dieu_chinh_quy.json"
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được nhật ký điều chỉnh {audit_path.name}") from exc
        if not isinstance(audit, dict) or not isinstance(audit.get("su_kien"), list):
            raise ValueError(f"Nhật ký điều chỉnh {audit_path.name} sai cấu trúc")
    else:
        audit = {
            "schema_version": 1,
            "ghi_chu": "Chỉ ghi nhận thay đổi cùng ngày danh mục kể từ khi cơ chế này được bật; lịch sử cũ không có nhật ký phiên bản.",
            "su_kien": [],
        }
    audit_before = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    thoi_diem_thu_thap = f"{ngay_hom_nay}T{gio}:00+07:00"
    doi = False
    for q in quy_mo:
        q["ngay_thu_thap"] = ngay_hom_nay
        q["trang_thai_nguon"] = "da_lay"
    for q in quy_nn:
        if q.get("trang_thai_nguon") == "loi_nguon":
            continue
        so_cp = q.get("so_cp") if q["ma"] in QUY_DAY_DU else None
        if q["ma"] in QUY_DAY_DU and so_cp is None:
            continue
        doi |= _chup(
            ls["nn"], q["ma"], q["ngay"],
            {m: round(v) for m, v in so_cp.items()} if so_cp is not None else None,
            {m: round(p, 3) for m, p in q["top"]}, audit["su_kien"],
            {"ghi_nhan_luc": thoi_diem_thu_thap, "nguon": q.get("nguon"),
             "pham_vi": q.get("pham_vi") or q.get("loai_quy") or "danh mục quỹ"},
        )
    for q in quy_mo:
        doi |= _chup(
            ls["mo"], q["ma"], q["ngay"], None, {m: round(p, 2) for m, p in q["top"]},
            audit["su_kien"],
            {"ghi_nhan_luc": thoi_diem_thu_thap, "nguon": q.get("nguon"),
             "pham_vi": q.get("pham_vi") or "Top 10 Fmarket"},
        )
    if doi or not (OUT / "lich_su_quy.json").exists():
        ghi_json(OUT / "lich_su_quy.json", ls)
    if json.dumps(audit, ensure_ascii=False, sort_keys=True) != audit_before or not audit_path.exists():
        ghi_json(audit_path, audit)

    # --- 1. biến động số lượng công bố theo từng quỹ ETF ngoại
    tong = {}
    bat_dau = None
    for ma, dsach in ls["nn"].items():
        dsach = [x for x in dsach if x.get("so_cp") is not None]
        if len(dsach) < 2:
            continue
        a, b = dsach[-2], dsach[-1]
        bat_dau = min(bat_dau or dsach[0]["ngay"], dsach[0]["ngay"])
        for m, d in _chenh_so_cp(a["so_cp"], b["so_cp"]).items():
            x = tong.setdefault(m, {"ma": m, "chenh_cp": 0.0, "quy": []})
            x["chenh_cp"] += d
            x["quy"].append({"ma": ma, "chenh_cp": round(d), "tu": a["ngay"], "den": b["ngay"],
                             "moi": a["so_cp"].get(m, 0) == 0, "thoat": b["so_cp"].get(m, 0) == 0})
    dong_nn = []
    for m, x in tong.items():
        g = gia.get(m)
        if not g:
            continue
        x["chenh_gt"] = round(x["chenh_cp"] * g)
        x["chenh_cp"] = round(x["chenh_cp"])
        x["ten"] = cty.get(m, (m, "Khác"))[0]
        dong_nn.append(x)
    dong_nn.sort(key=lambda x: -abs(x["chenh_gt"]))
    tu_ngay = min((v[0]["ngay"] for v in ls["nn"].values() if v), default=None)
    so_ngay_nn = max((len([y for y in v if y.get("so_cp") is not None]) for v in ls["nn"].values()), default=0)

    # --- 2. biến động top 10 và tỷ trọng công bố của quỹ mở nội
    chu_dong = {}
    for ma, dsach in ls["mo"].items():
        if len(dsach) < 2:
            continue
        a, b = dsach[-2], dsach[-1]
        for m in set(a["pct"]) | set(b["pct"]):
            pa, pb = a["pct"].get(m), b["pct"].get(m)
            x = chu_dong.setdefault(m, {"ma": m, "tang": 0, "giam": 0, "moi": 0, "thoat": 0, "chi_tiet": []})
            if pa is None:
                x["moi"] += 1
                kieu = "moi"
            elif pb is None:
                x["thoat"] += 1
                kieu = "thoat"
            elif pb - pa >= 0.3:
                x["tang"] += 1
                kieu = "tang"
            elif pa - pb >= 0.3:
                x["giam"] += 1
                kieu = "giam"
            else:
                continue
            x["chi_tiet"].append({"quy": ma, "kieu": kieu, "tu": pa, "den": pb, "ngay": b["ngay"]})
    ds_cd = []
    for m, x in chu_dong.items():
        x["diem"] = x["tang"] + x["moi"] - x["giam"] - x["thoat"]
        x["ten"] = cty.get(m, (m, "Khác"))[0]
        ds_cd.append(x)
    ds_cd.sort(key=lambda x: (-abs(x["diem"]), x["ma"]))
    so_quy_co_lich_su = sum(1 for v in ls["mo"].values() if len(v) >= 2)

    # --- 3. lệch pha nội - ngoại so với VN100
    vn100 = {x["ma"]: x["ty_trong"] for x in _doc(OUT / "ro_chi_so" / "VN100.json", {}).get("thanh_phan", [])}
    ro_vn100 = _doc(OUT / "ro_chi_so" / "VN100.json", {})
    lech, lech_meta = so_sanh_top10(
        quy_mo, quy_nn, vn100, cty, ro_vn100.get("cap_nhat")
    )

    # --- 4. dữ liệu nền cho Radar FTSE
    he = _doc(ROOT / "scripts" / "ro_chi_so_he_so.json", {})
    ff = he.get("free_float", {})
    cp_ds = _doc(OUT / "co_phieu.json", {}).get("co_phieu", [])
    ftse = []
    for c in cp_ds:
        if "FTSE27" not in c.get("ro", []):
            continue
        m = c["ma"]
        ct = _doc(OUT / "cp" / f"{m}.json", {})
        c_, v_ = ct.get("c", [])[-20:], ct.get("v", [])[-20:]
        adv = sum(a * b for a, b in zip(c_, v_)) / len(c_) if c_ else None
        if not c.get("gia") or not ff.get(m):
            continue
        ftse.append({"ma": m, "ten": c["ten"], "nganh": c["nganh"], "gia": c["gia"], "ff_cp": ff[m], "ff_gt": round(c["gia"] * ff[m]),
                     "adv": round(adv) if adv else None, "nhom6": "FTSE6" in c["ro"]})
    ftse.sort(key=lambda x: -x["ff_gt"])

    moi = {
        "schema_version": 2,
        "dong_tien_nn": {
            "ds": dong_nn[:40], "so_lan_chup": so_ngay_nn, "bat_dau": bat_dau,
            "tu_ngay": tu_ngay, "day_du": sorted(QUY_DAY_DU),
            "ghi_chu": "Biến động số lượng nắm giữ công bố tính theo từng quỹ–mã; giá trị quy đổi dùng giá hiện tại. Ngày chốt khác nhau; đây không phải xác nhận giao dịch hoặc dòng vốn.",
        },
        "dong_tien_mo": {
            "ds": ds_cd[:40], "so_quy": so_quy_co_lich_su,
            "ghi_chu": "Thay đổi top 10 và tỷ trọng được công bố giữa hai kỳ mỗi quỹ; không cho biết thay đổi ở mã ngoài top 10 hoặc số lượng cổ phiếu thực mua.",
        },
        "lech_pha": lech[:60],
        "lech_pha_meta": lech_meta,
        "ftse": {"fx": FX_MAC_DINH, "von_ty_usd": VON_MAC_DINH_TY_USD, "dot_dau_pct": DOT_DAU_PCT, "ds": ftse,
                 "ngay_he_so": he.get("ngay")},
    }
    cu = _doc(OUT / "phan_tich.json", {})
    if {k: v for k, v in cu.items() if k not in ("cap_nhat", "cap_nhat_luc")} != moi:
        moi["cap_nhat"] = ngay_hom_nay
        moi["cap_nhat_luc"] = gio
        ghi_json(OUT / "phan_tich.json", moi)

    # cảnh báo, tổng hợp tuần và xuất dữ liệu: lỗi ở đây không được làm hỏng phần còn lại
    kq = {"mua_ban_nn": len(dong_nn), "chu_dong": len(ds_cd), "lech": len(lech), "ftse": len(ftse)}
    for ten, ham in (("canh_bao", lambda: canh_bao.xu_ly(ls, dong_nn, ghi_json, ngay_hom_nay, gio)),
                     ("tong_hop_tuan", lambda: bool(tong_hop_tuan.xu_ly(ls, gia, cty, ghi_json, ngay_hom_nay, gio))),
                     ("xuat", lambda: xuat_du_lieu.xuat(ls, _doc(OUT / "canh_bao.json", {"ds": []})["ds"], ghi_json, ngay_hom_nay, gio))):
        try:
            kq[ten] = ham()
        except Exception as e:
            print(f"  ! {ten}: {str(e)[:150]}")
    return kq
