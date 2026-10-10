# -*- coding: utf-8 -*-
"""
Backtest điểm tài chính (scripts/diem_tai_chinh.py): nếu mỗi cuối tháng xếp hạng cổ phiếu chỉ bằng báo cáo tài chính ĐÃ CÔNG BỐ tại ngày đó,
nhóm điểm cao có thực sự tăng hơn nhóm điểm thấp trong 1, 3, 6 tháng sau không?

Cách làm (nghiêm ngặt về thời điểm):
- Ngày xét t = cuối mỗi tháng. Chỉ dùng quý có ngày khả dụng <= t (xem diem_tai_chinh.ngay_co_the_dung); trọng số cố định, không tối ưu theo kết quả.
- Vào lệnh tại giá đóng cửa phiên KẾ TIẾP t; lợi nhuận kỳ nắm giữ h phiên (21/63/126). Giá đã điều chỉnh (nguồn Vietcap).
- Mỗi ngày xét: hệ số tương quan hạng (IC) giữa điểm và lợi nhuận sau đó; chia 5 nhóm theo điểm; lợi nhuận trung bình từng nhóm (đều trọng số); cắt đuôi 1%/99%.
- Thống kê t chỉ tính trên các ngày xét KHÔNG chồng lấn (cách nhau >= h phiên) để không thổi phồng mức ý nghĩa.

Giới hạn (ghi trên trang): nhóm cổ phiếu là VN100 HIỆN TẠI (thiên lệch sống sót); không tính phí/thuế/trượt giá; ~6 năm dữ liệu nên chỉ có vài chục kỳ độc lập;
giá và báo cáo lấy từ nguồn công khai có thể chứa sai sót; kết quả quá khứ không bảo đảm tương lai.

Chạy:  python scripts/backtest_tai_chinh.py --tai     # tải lịch sử báo cáo dài (34+ quý) vào .cache/bctc_dai (không commit)
       python scripts/backtest_tai_chinh.py           # chạy backtest và ghi vào assets/data/diem_tai_chinh.json["backtest"]
"""
import argparse
import bisect
import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diem_tai_chinh as dtc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
CACHE = ROOT / ".cache" / "bctc_dai"
HORIZONS = {21: "1 tháng", 63: "3 tháng", 126: "6 tháng"}
NGAY_BAT_DAU = date(2020, 3, 31)
TOI_THIEU_MA = 40                    # ngày xét có ít hơn bấy nhiêu mã đủ dữ liệu thì bỏ


def tai_dai():
    import bao_cao_tai_chinh as b
    CACHE.mkdir(parents=True, exist_ok=True)
    ds = json.loads((DATA / "co_phieu.json").read_text(encoding="utf-8"))["co_phieu"]
    for i, x in enumerate(ds, 1):
        f = CACHE / f"{x['ma']}.json"
        if f.exists():
            continue
        kq, _ = b.tai_mot_ma(x["ma"], x.get("ten"), x.get("nganh"), None, True, so_quy=40, so_nam=10, kiem_tra=False)
        if kq:
            f.write_text(json.dumps(kq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[{i}/{len(ds)}] {x['ma']}: {len(kq['quy']) if kq else 0} quý", flush=True)


def cuoi_thang(tu, den):
    out, y, m = [], tu.year, tu.month
    while date(y, m, 1) <= den:
        out.append(date(y, m, __import__("calendar").monthrange(y, m)[1]))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def chay(tre, bc, gia):
    """Trả DataFrame mỗi dòng = (ngày xét, mã) kèm điểm, phân vị yếu tố và lợi nhuận sau 21/63/126 phiên."""
    ngay_xet = [t for t in cuoi_thang(NGAY_BAT_DAU, date.today()) if t < date.today()]
    rows = []
    for t in ngay_xet:
        dt = {}
        for m, d in bc.items():
            g = None
            if m in gia:                                          # giá đóng cửa phiên cuối cùng <= t (thông tin có sẵn tại ngày xét)
                k = bisect.bisect_right(gia[m][0], t.isoformat()) - 1
                g = gia[m][1][k] if k >= 0 else None
            dt[m] = dtc.dac_trung(d, t, tre, g)
        xh = dtc.xep_hang({m: x for m, x in dt.items() if x})
        for m, r in xh.items():
            if r["diem"] is None or m not in gia:
                continue
            ds, c = gia[m]
            e = bisect.bisect_right(ds, t.isoformat())               # phiên kế tiếp sau t
            if e >= len(c) or not c[e]:
                continue
            row = {"t": t, "ma": m, "loai": dt[m]["loai"], "diem": r["diem"], **{f"pv_{k}": v for k, v in r["pv"].items()}}
            for h in HORIZONS:
                row[f"r{h}"] = (c[e + h] / c[e] - 1) if e + h < len(c) and c[e + h] else None
            rows.append(row)
    return pd.DataFrame(rows)


def thong_ke(df, h, cot="diem"):
    """Theo từng ngày xét: IC, 5 nhóm, trung bình toàn bộ. Trả danh sách dict theo ngày."""
    out = []
    for t, g in df.dropna(subset=[f"r{h}", cot]).groupby("t"):
        if len(g) < TOI_THIEU_MA:
            continue
        r = g[f"r{h}"].clip(g[f"r{h}"].quantile(0.01), g[f"r{h}"].quantile(0.99))
        ic = g[cot].rank().corr(r.rank())
        nhom = pd.qcut(g[cot].rank(method="first"), 5, labels=False)
        q = [float(r[nhom == k].mean()) for k in range(5)]
        out.append({"t": t, "ic": float(ic), "q": q, "tb": float(r.mean()), "n": len(g)})
    return out


def tong_hop(ds, h):
    """Gộp các ngày xét thành chỉ số; t-stat chỉ trên ngày không chồng lấn (cách nhau >= h phiên ~ h/21 tháng)."""
    if not ds:
        return None
    buoc = max(1, math.ceil(h / 21))
    kd = ds[::buoc]
    def tb(x): return sum(x) / len(x) if x else None
    def sd(x):
        m = tb(x)
        return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1)) if len(x) > 1 else None
    ics = [d["ic"] for d in kd if d["ic"] == d["ic"]]
    chen = [d["q"][4] - d["q"][0] for d in kd]
    s = sd(ics)
    nua = len(kd) // 2
    return {"so_ky": len(kd), "so_ky_tat_ca": len(ds), "ic": tb(ics), "ic_t": (tb(ics) / (s / math.sqrt(len(ics)))) if s else None, "ic_duong": sum(1 for v in ics if v > 0) / len(ics),
            "ic_nua_dau": tb(ics[:nua]), "ic_nua_sau": tb(ics[nua:]),
            "nhom": [tb([d["q"][k] for d in kd]) for k in range(5)], "tb": tb([d["tb"] for d in kd]),
            "q5_tru_q1": tb(chen), "q5_tru_q1_t": (tb(chen) / (sd(chen) / math.sqrt(len(chen)))) if sd(chen) else None, "q5_hon_q1": sum(1 for v in chen if v > 0) / len(chen),
            "q5_vuot_tb": tb([d["q"][4] - d["tb"] for d in kd]), "q1_vuot_tb": tb([d["q"][0] - d["tb"] for d in kd]),
            "ic_tat_ca": tb([d["ic"] for d in ds if d["ic"] == d["ic"]]), "q5_tru_q1_tat_ca": tb([d["q"][4] - d["q"][0] for d in ds]), "n_ma_tb": tb([d["n"] for d in ds])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tai", action="store_true", help="chỉ tải lịch sử báo cáo dài vào .cache/bctc_dai")
    args = ap.parse_args()
    if args.tai:
        tai_dai()
        return
    bc = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in CACHE.glob("*.json")}
    if len(bc) < 50:
        sys.exit("Chưa có lịch sử dài: chạy `python scripts/backtest_tai_chinh.py --tai` trước.")
    gia = {}
    for m in bc:
        p = DATA / "cp" / f"{m}.json"
        if p.exists():
            x = json.loads(p.read_text(encoding="utf-8"))
            if x.get("c") and len(x["c"]) > 300:
                gia[m] = (x["d"], x["c"])
    ket_qua = {}
    for tre in (dtc.TRE_NGAY, 60):                       # kịch bản gốc và kịch bản số liệu đến chậm hơn
        df = chay(tre, bc, gia)
        print(f"tre={tre}: {len(df)} dòng, {df['t'].nunique()} ngày xét, từ {df['t'].min()} đến {df['t'].max()}")
        ket_qua[f"tre_{tre}"] = {str(h): tong_hop(thong_ke(df, h), h) for h in HORIZONS}
        if tre == dtc.TRE_NGAY:
            ket_qua["yeu_to"] = {k: tong_hop(thong_ke(df, 63, f"pv_{k}"), 63) for k in list(dtc.TRONG_SO) + dtc.THAM_KHAO}
            ket_qua["phi_tai_chinh"] = {str(h): tong_hop(thong_ke(df[df["loai"] == "Doanh nghiệp"], h), h) for h in HORIZONS}
            ket_qua["thoi_gian"] = {"tu": str(df["t"].min()), "den": str(df["t"].max()), "so_ma": int(df["ma"].nunique())}
    ket_qua["tao_luc"] = date.today().isoformat()
    ket_qua["gia_dinh"] = {"tre_ngay": dtc.TRE_NGAY, "trong_so": dtc.TRONG_SO, "nhom_ngu": "5 nhóm theo điểm, đều trọng số", "nhom_ma": "VN100 hiện tại (thiên lệch sống sót)", "phi": "chưa tính phí, thuế, trượt giá"}
    target = DATA / "diem_tai_chinh.json"
    d = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    d["backtest"] = ket_qua
    target.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for tre in (dtc.TRE_NGAY, 60):
        print(f"\n== Số liệu khả dụng sau {tre} ngày kể từ cuối quý")
        for h, nhan in HORIZONS.items():
            r = ket_qua[f"tre_{tre}"][str(h)]
            if r:
                print(f"  {nhan:<8} kỳ độc lập {r['so_ky']:>3} | IC {r['ic']:+.3f} (t {r['ic_t']:+.2f}, IC>0: {r['ic_duong']*100:.0f}%) | Q5-Q1 {r['q5_tru_q1']*100:+.1f}% (Q5>Q1: {r['q5_hon_q1']*100:.0f}%) | nhóm: " + " ".join(f"{v*100:+.1f}" for v in r["nhom"]) + f" | nửa đầu IC {r['ic_nua_dau']:+.3f}, nửa sau {r['ic_nua_sau']:+.3f}")
    print("\n== Chỉ doanh nghiệp phi tài chính (loại ngân hàng, chứng khoán, bảo hiểm)")
    for h, nhan in HORIZONS.items():
        r = ket_qua["phi_tai_chinh"][str(h)]
        if r:
            print(f"  {nhan:<8} kỳ {r['so_ky']:>3} | IC {r['ic']:+.3f} (t {r['ic_t']:+.2f}) | Q5-Q1 {r['q5_tru_q1']*100:+.1f}% | nhóm: " + " ".join(f"{v*100:+.1f}" for v in r["nhom"]))
    print("\n== IC theo từng yếu tố (3 tháng, kỳ độc lập; hai yếu tố đầu là yếu tố tính điểm)")
    for k, r in ket_qua["yeu_to"].items():
        if r:
            print(f"  {dtc.NHAN[k]:<38} IC {r['ic']:+.3f} (t {r['ic_t']:+.2f}) | nửa đầu {r['ic_nua_dau']:+.3f}, nửa sau {r['ic_nua_sau']:+.3f}")


if __name__ == "__main__":
    main()
