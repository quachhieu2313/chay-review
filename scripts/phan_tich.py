"""Phân tích độc quyền của Kim Chỉ Nam: những con số không có sẵn ở đâu khác vì chúng được tạo ra
bằng cách ghép nhiều nguồn và lưu lịch sử tích luỹ theo ngày.

1. Dòng tiền quỹ ETF nước ngoài theo mã: chênh lệch số cổ phiếu nắm giữ giữa hai lần công bố liên tiếp (mua/bán ròng thật, không lẫn biến động giá).
2. Dòng tiền quỹ mở trong nước: mã vào/ra top 10 và thay đổi tỷ trọng giữa hai kỳ công bố.
3. Lệch pha nội - ngoại: tỷ trọng trung bình quỹ mở nội và quỹ ETF ngoại so với tỷ trọng trong VN100.
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
QUY_DAY_DU = {"VNM", "VNAM", "KPHO", "00885", "VWO", "VT"}  # quỹ công bố đầy đủ danh mục: mới tính được mua/bán ròng
FX_MAC_DINH = 26300
VON_MAC_DINH_TY_USD = 2.5   # theo công bố của Vanguard (tin vietnam.vn), người dùng chỉnh được
DOT_DAU_PCT = 25            # FTSE chia 4 đợt từ 09/2026 đến 09/2027


def _doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def _chup(ls, ma, ngay, so_cp, pct):
    """Thêm một lần chụp vào lịch sử nếu ngày công bố mới hơn lần chụp trước. Trả True nếu có thay đổi."""
    if not ngay:
        return False
    dsach = ls.setdefault(ma, [])
    if dsach and dsach[-1]["ngay"] >= ngay:
        return False
    muc = {"ngay": ngay, "pct": pct}
    if so_cp is not None:
        muc["so_cp"] = so_cp
    dsach.append(muc)
    del dsach[:-GIU_TOI_DA]
    return True


def _chenh_so_cp(a, b):
    """b - a theo từng mã (mã vắng mặt tính 0)."""
    return {m: b.get(m, 0.0) - a.get(m, 0.0) for m in set(a) | set(b) if abs(b.get(m, 0.0) - a.get(m, 0.0)) > 0}


def tinh(quy_mo, quy_nn, gia, cty, ghi_json, ngay_hom_nay, gio):
    """quy_mo: quỹ mở (Fmarket); quy_nn: quỹ ngoại; gia: {mã: giá VND}; cty: {mã: (tên, ngành)}."""
    ls = _doc(OUT / "lich_su_quy.json", {"nn": {}, "mo": {}})
    doi = False
    for q in quy_nn:
        so_cp = q.get("so_cp") if q["ma"] in QUY_DAY_DU else None
        if q["ma"] in QUY_DAY_DU and so_cp is None:
            continue
        doi |= _chup(ls["nn"], q["ma"], q["ngay"], {m: round(v) for m, v in so_cp.items()} if so_cp is not None else None,
                     {m: round(p, 3) for m, p in q["top"]})
    for q in quy_mo:
        doi |= _chup(ls["mo"], q["ma"], q["ngay"], None, {m: round(p, 2) for m, p in q["top"]})
    if doi or not (OUT / "lich_su_quy.json").exists():
        ghi_json(OUT / "lich_su_quy.json", ls)

    # --- 1. dòng tiền quỹ ETF ngoại (mua/bán ròng theo số cổ phiếu)
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

    # --- 2. dòng tiền quỹ mở nội (thay đổi giữa hai kỳ công bố gần nhất của từng quỹ)
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
    quy_co = [q for q in quy_mo if q["loai"] == "STOCK"]
    nn_dd = [q for q in quy_nn if q["ma"] in QUY_DAY_DU and q["top"]]
    ma_xet = set(vn100) | {m for q in quy_co for m, _ in q["top"]} | {m for q in nn_dd for m, _ in q["top"]}
    lech = []
    for m in ma_xet:
        noi = [dict(q["top"]).get(m, 0.0) for q in quy_co]
        ngoai = [dict(q["top"]).get(m, 0.0) for q in nn_dd]
        w = vn100.get(m, 0.0)
        so_noi = sum(1 for v in noi if v > 0)
        so_ngoai = sum(1 for v in ngoai if v > 0)
        if so_noi + so_ngoai == 0:
            continue
        tb_noi = sum(noi) / len(noi) if noi else 0.0
        tb_ngoai = sum(ngoai) / len(ngoai) if ngoai else 0.0
        lech.append({"ma": m, "ten": cty.get(m, (m, "Khác"))[0], "vn100": round(w, 2), "noi_tb": round(tb_noi, 2), "ngoai_tb": round(tb_ngoai, 2),
                     "so_noi": so_noi, "so_ngoai": so_ngoai, "lech_noi": round(tb_noi - w, 2), "lech_ngoai": round(tb_ngoai - w, 2),
                     "nn_tru_noi": round(tb_ngoai - tb_noi, 2)})
    lech.sort(key=lambda x: -abs(x["nn_tru_noi"]))

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
        "dong_tien_nn": {"ds": dong_nn[:40], "so_lan_chup": so_ngay_nn, "bat_dau": bat_dau, "tu_ngay": tu_ngay, "day_du": sorted(QUY_DAY_DU)},
        "dong_tien_mo": {"ds": ds_cd[:40], "so_quy": so_quy_co_lich_su},
        "lech_pha": lech[:60],
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
