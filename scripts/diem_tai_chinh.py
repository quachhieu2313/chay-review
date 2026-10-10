# -*- coding: utf-8 -*-
"""
Điểm định giá từ báo cáo tài chính (assets/data/bctc/<MÃ>.json do bao_cao_tai_chinh.py tải) kết hợp giá cổ phiếu.

Mô hình: cổ phiếu có lợi suất lợi nhuận cao (E/P = lợi nhuận sau thuế 4 quý / vốn hóa) và giá trị sổ sách cao so với vốn hóa (B/P) thì điểm cao,
tức là "rẻ" so với báo cáo tài chính; đắt thì điểm thấp. Điểm là thứ hạng tương đối (0-100) trong nhóm cổ phiếu đang phân tích,
KHÔNG phải dự báo giá hay xác suất sinh lời. Kiểm chứng bằng backtest: scripts/backtest_tai_chinh.py.

Vì sao chỉ chấm điểm bằng định giá: backtest 2020-2026 cho thấy tăng trưởng lợi nhuận, ROE, chất lượng dòng tiền KHÔNG dự báo được lợi nhuận cổ phiếu
(IC gần 0, không có ý nghĩa thống kê), còn E/P và B/P thì có (IC +0,12 đến +0,16, ổn định ở cả hai nửa giai đoạn). Các yếu tố kia vẫn được tính để hiển thị
làm thông tin tham khảo nhưng không tính vào điểm.

Chống nhìn trước tương lai: chỉ dùng các quý đã được công bố tại ngày xét. Ngày có thể dùng số liệu của một quý = muộn hơn của
(ngày công bố lần đầu theo Vietcap, cuối quý + TRE_NGAY ngày). Vốn hóa = giá tại ngày xét x số cổ phiếu hiện tại (vốn góp / mệnh giá 10.000 đồng);
giá đã điều chỉnh chia tách/cổ phiếu thưởng nên cách này gần đúng, sai lệch khi doanh nghiệp phát hành thêm gần đây.

Chạy:  python scripts/diem_tai_chinh.py            # chấm điểm hiện tại, ghi assets/data/diem_tai_chinh.json (giữ nguyên phần backtest đã có)
"""
import calendar
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
TRE_NGAY = 30                      # số liệu quý có thể dùng sau khi quý kết thúc tối thiểu bấy nhiêu ngày (hạn công bố quý của doanh nghiệp là 20-30 ngày)
NHOM_TOI_THIEU = 8                 # nhóm loại hình (ngân hàng, chứng khoán...) có ít hơn bấy nhiêu mã thì ROE xếp hạng chung với toàn bộ
DO_PHU_TOI_THIEU = 0.99            # cả hai yếu tố định giá phải có dữ liệu mới chấm điểm
MENH_GIA = 10000                   # đồng/cổ phiếu

# điểm = định giá (đã kiểm chứng qua backtest). Trọng số cố định, không tối ưu theo kết quả.
TRONG_SO = {"loi_suat_ln": 50, "gia_tri_so_sach": 50}
# yếu tố chỉ để tham khảo và đánh giá trong backtest, KHÔNG tính vào điểm
THAM_KHAO = ["tang_truong_ttm", "tang_truong_quy", "tang_toc", "doanh_thu", "roe", "dong_tien"]
NHAN = {"loi_suat_ln": "Lợi suất lợi nhuận (E/P)", "gia_tri_so_sach": "Giá trị sổ sách / vốn hóa (B/P)",
        "tang_truong_ttm": "Tăng trưởng lợi nhuận 4 quý", "tang_truong_quy": "Tăng trưởng lợi nhuận quý gần nhất", "tang_toc": "Tăng tốc lợi nhuận",
        "doanh_thu": "Tăng trưởng doanh thu 4 quý", "roe": "ROE (4 quý)", "dong_tien": "Chất lượng dòng tiền"}
CAP_TANG_TRUONG = (-1.0, 2.0)      # chặn tăng trưởng trong [-100%, +200%] để số nhỏ ở mẫu không áp đảo thứ hạng
CAP_LOI_SUAT = (-0.5, 0.5)


def _hang(d, bc, f):
    return next((r for r in d.get("bc", {}).get(bc, []) if r["f"] == f), None) if f else None


def _cuoi_quy(nam, q):
    m = q * 3
    return date(nam, m, calendar.monthrange(nam, m)[1])


def ngay_co_the_dung(p, tre=TRE_NGAY):
    qe = _cuoi_quy(p["nam"], p["q"])
    cb = date.fromisoformat(p["cb"]) if p.get("cb") else qe
    return max(cb, qe + timedelta(days=tre))


def so_co_phieu(d):
    """Số cổ phiếu ước tính = vốn góp của chủ sở hữu (mã bsa80, bảng cân đối quý mới nhất) / mệnh giá 10.000 đồng. None nếu không có (ví dụ bảo hiểm)."""
    r = _hang(d, "cdkt", "bsa80")
    v = r["q"][0] if r and r["q"] else None
    return v * 1e9 / MENH_GIA if v and v > 0 else None


def _tong4(arr, i):
    v = arr[i:i + 4]
    return sum(v) if len(v) == 4 and all(x is not None for x in v) else None


def _tang(a, b):
    if a is None or b is None or b == 0:
        return None
    return max(CAP_TANG_TRUONG[0], min(CAP_TANG_TRUONG[1], (a - b) / abs(b)))


def dac_trung(d, den_ngay=None, tre=TRE_NGAY, gia=None):
    """Các chỉ số thô của một mã tại ngày xét (None = dùng toàn bộ quý hiện có). gia = giá cổ phiếu (đồng) tại ngày xét để tính định giá.
    None nếu chưa đủ 8 quý đã công bố."""
    quy = d.get("quy") or []
    i0 = next((i for i, p in enumerate(quy) if den_ngay is None or ngay_co_the_dung(p, tre) <= den_ngay), None)
    if i0 is None or len(quy) - i0 < 8:
        return None
    tt = d.get("tt") or {}
    ln, dt, ve, cf = (_hang(d, "kqkd", tt.get("lnst")), _hang(d, "kqkd", tt.get("dt")), _hang(d, "cdkt", tt.get("vcsh")), _hang(d, "lctt", tt.get("cfo")))
    if not ln:
        return None
    l = ln["q"]
    ttm0, ttm1 = _tong4(l, i0), _tong4(l, i0 + 4)
    gq0, gq1 = _tang(l[i0], l[i0 + 4]), _tang(l[i0 + 1], l[i0 + 5])
    f = {"tang_truong_ttm": _tang(ttm0, ttm1), "tang_truong_quy": gq0, "tang_toc": (gq0 - gq1) if gq0 is not None and gq1 is not None else None}
    f["doanh_thu"] = _tang(_tong4(dt["q"], i0), _tong4(dt["q"], i0 + 4)) if dt else None
    roe = None
    if ve and ttm0 is not None and ve["q"][i0] is not None and ve["q"][i0 + 4] is not None:
        tb = (ve["q"][i0] + ve["q"][i0 + 4]) / 2
        roe = ttm0 / tb if tb > 0 else None
    f["roe"] = roe
    dong_tien = None
    if d.get("loai") == "Doanh nghiệp" and cf and ttm0 is not None and ttm0 > 0 and _tong4(cf["q"], i0) is not None:   # dòng tiền kinh doanh chỉ có nghĩa với doanh nghiệp phi tài chính
        dong_tien = max(-1.0, min(2.0, _tong4(cf["q"], i0) / ttm0))
    f["dong_tien"] = dong_tien
    von_hoa = None
    sh = so_co_phieu(d)
    if gia and sh:
        von_hoa = gia * sh / 1e9                                      # tỷ đồng
    f["loi_suat_ln"] = max(CAP_LOI_SUAT[0], min(CAP_LOI_SUAT[1], ttm0 / von_hoa)) if von_hoa and ttm0 is not None else None
    f["gia_tri_so_sach"] = ve["q"][i0] / von_hoa if von_hoa and ve and ve["q"][i0] is not None else None
    return {"ky": quy[i0]["k"], "loai": d.get("loai"), "f": f, "ln_4q": ttm0, "ln_4q_truoc": ttm1, "von_hoa": von_hoa}


def _phan_vi(gia_tri):
    """{mã: giá trị} -> {mã: phân vị 0-100}, đồng hạng lấy trung bình."""
    ds = sorted(gia_tri.items(), key=lambda kv: kv[1])
    n = len(ds)
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and ds[j + 1][1] == ds[i][1]:
            j += 1
        for k in range(i, j + 1):
            out[ds[k][0]] = 100.0 * ((i + j) / 2 + 0.5) / n
        i = j + 1
    return out


def xep_hang(dac_trung_theo_ma):
    """{mã: dac_trung(...)} -> {mã: {"diem": 0-100, "pv": {yếu tố: phân vị}, "phu": độ phủ trọng số}}.
    pv gồm cả yếu tố tham khảo (để đánh giá trong backtest); điểm chỉ tính từ TRONG_SO. Mã không đủ độ phủ có diem None."""
    pv = {}
    for k in list(TRONG_SO) + THAM_KHAO:
        theo = {m: x["f"][k] for m, x in dac_trung_theo_ma.items() if x and x["f"].get(k) is not None}
        if k == "roe":                                      # ROE so trong cùng loại hình khi nhóm đủ lớn
            nhom = {}
            for m in theo:
                nhom.setdefault(dac_trung_theo_ma[m]["loai"], []).append(m)
            chung, rieng = _phan_vi(theo), {}
            for loai, ms in nhom.items():
                if len(ms) >= NHOM_TOI_THIEU:
                    rieng.update(_phan_vi({m: theo[m] for m in ms}))
            pv[k] = {m: rieng.get(m, chung[m]) for m in theo}
        else:
            pv[k] = _phan_vi(theo)
    tong_w = sum(TRONG_SO.values())
    out = {}
    for m, x in dac_trung_theo_ma.items():
        if not x:
            continue
        co = {k: pv[k][m] for k in pv if m in pv[k]}
        w = sum(TRONG_SO[k] for k in TRONG_SO if k in co)
        out[m] = {"diem": (sum(TRONG_SO[k] * co[k] for k in TRONG_SO if k in co) / w) if w / tong_w >= DO_PHU_TOI_THIEU else None, "pv": co, "phu": w / tong_w}
    return out


def tai_bctc():
    out = {}
    for p in sorted((DATA / "bctc").glob("*.json")):
        if p.name in ("muc_luc.json", "kiem_tra.json"):
            continue
        try:
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
    return out


def gia_moi_nhat(ma):
    p = DATA / "cp" / f"{ma}.json"
    try:
        x = json.loads(p.read_text(encoding="utf-8"))
        return x["c"][-1], x["d"][-1]
    except (OSError, ValueError, KeyError, IndexError):
        return None, None


def main():
    bc = tai_bctc()
    gia = {m: gia_moi_nhat(m) for m in bc}
    dt = {m: dac_trung(d, None, TRE_NGAY, gia[m][0]) for m, d in bc.items()}
    xh = xep_hang({m: x for m, x in dt.items() if x})
    ngay_gia = max((g[1] for g in gia.values() if g[1]), default=None)
    ds = []
    for m, r in xh.items():
        d, x = bc[m], dt[m]
        if r["diem"] is None:
            continue
        kt = d.get("kt") or {}
        f = x["f"]
        ds.append({"ma": m, "ten": d.get("ten"), "nganh": d.get("nganh"), "loai": d.get("loai"), "ky": x["ky"], "diem": round(r["diem"], 1),
                   "gia": gia[m][0], "von_hoa": round(x["von_hoa"], 0) if x["von_hoa"] else None,
                   "pe": round(1 / f["loi_suat_ln"], 1) if f.get("loi_suat_ln") and f["loi_suat_ln"] > 0 else None,
                   "pb": round(1 / f["gia_tri_so_sach"], 2) if f.get("gia_tri_so_sach") and f["gia_tri_so_sach"] > 0 else None,
                   "pv": {k: round(v, 0) for k, v in r["pv"].items()}, "f": {k: (None if v is None else round(v, 4)) for k, v in f.items()},
                   "ln_4q": None if x["ln_4q"] is None else round(x["ln_4q"], 1), "ln_4q_truoc": None if x["ln_4q_truoc"] is None else round(x["ln_4q_truoc"], 1),
                   "canh_bao_du_lieu": bool(kt.get("lech"))})
    ds.sort(key=lambda r: -r["diem"])
    target = DATA / "diem_tai_chinh.json"
    cu = {}
    if target.exists():
        try:
            cu = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            cu = {}
    kq = {"cap_nhat": date.today().isoformat(), "gia_den": ngay_gia, "so_ma": len(ds), "trong_so": TRONG_SO, "nhan": NHAN, "tham_khao": THAM_KHAO, "tre_ngay": TRE_NGAY,
          "ds": ds, "backtest": cu.get("backtest")}
    target.write_text(json.dumps(kq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Đã chấm điểm {len(ds)}/{len(bc)} mã (giá đến {ngay_gia}). Điểm cao nhất (rẻ nhất): " + ", ".join(f"{r['ma']} {r['diem']}" for r in ds[:6]) +
          " | thấp nhất (đắt nhất): " + ", ".join(f"{r['ma']} {r['diem']}" for r in ds[-6:]))


if __name__ == "__main__":
    sys.exit(main())
