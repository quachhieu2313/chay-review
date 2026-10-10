# -*- coding: utf-8 -*-
"""
Tải báo cáo tài chính (kết quả kinh doanh, cân đối kế toán, lưu chuyển tiền tệ) của các cổ phiếu trong
assets/data/co_phieu.json từ API công khai của Vietcap (iq.vietcap.com.vn), ghi ra assets/data/bctc/<MÃ>.json
và mục lục assets/data/bctc/muc_luc.json cho tab "Báo cáo tài chính" của trang Cổ phiếu khuyến nghị.

Vì sao dùng Vietcap mà không dùng KBS: API tài chính theo quý của KBS trả cột giá trị lệch thứ tự so với nhãn kỳ
(đối chiếu FPT với FiinQuant và TCBS thì sai kỳ); Vietcap khớp hoàn toàn cả doanh thu lẫn lợi nhuận từng quý.

Đơn vị: tỷ đồng (số gốc là đồng chia 1e9), riêng dòng "Lãi cơ bản trên cổ phiếu (VND)" giữ nguyên đồng.
Lưu chuyển tiền tệ theo quý là số riêng từng quý (cộng 4 quý ≈ số cả năm).

Chạy:   python scripts/bao_cao_tai_chinh.py              # chỉ tải lại mã có kỳ báo cáo mới (nhanh)
        python scripts/bao_cao_tai_chinh.py --all        # tải lại tất cả
        python scripts/bao_cao_tai_chinh.py FPT ACB      # chỉ các mã chỉ định
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nguon  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
OUT = DATA / "bctc"
FS = f"{nguon.VCI_IQ}/v1/company"
SO_QUY, SO_NAM = 12, 6
SECTIONS = {"kqkd": "INCOME_STATEMENT", "cdkt": "BALANCE_SHEET", "lctt": "CASH_FLOW"}
# mã chỉ tiêu tổng hợp ổn định giữa các loại hình doanh nghiệp (doanh thu thì mỗi loại một mã)
TOM_TAT = {"lnst": ("isa22", "isa20"), "ts": ("bsa53",), "vcsh": ("bsa78",), "cfo": ("cfa18",), "eps": ("isa23",)}
DOANH_THU = ("isa3", "isb27", "isi103")      # doanh thu thuần | thu nhập lãi thuần (ngân hàng) | doanh thu phí bảo hiểm


def loai_hinh(metrics):
    ma = {x.get("field") for x in metrics.get("INCOME_STATEMENT", []) if x.get("field")}
    # thứ tự quan trọng: tập đoàn bảo hiểm (BVH) có cả mã của mảng ngân hàng nên phải xét bảo hiểm/chứng khoán trước
    if any(f.startswith("isi") for f in ma):
        return "Bảo hiểm"
    if any(f.startswith("iss") for f in ma):
        return "Chứng khoán"
    if any(f.startswith("isb") for f in ma):
        return "Ngân hàng"
    return "Doanh nghiệp"


def lay_bao_cao(ma, section):
    d = nguon._goi("GET", f"{FS}/{ma}/financial-statement", nguon.H_VCI, params={"section": section}) or {}
    return d.get("data") or {}


def cac_ky(ds, so):
    """Bản ghi kỳ mới nhất trước, bỏ kỳ trùng; lengthReport 1-4 là quý, 5 là năm."""
    seen, out = set(), []
    for x in sorted(ds, key=lambda r: (r.get("yearReport") or 0, r.get("lengthReport") or 0), reverse=True):
        k = (x.get("yearReport"), x.get("lengthReport"))
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
        if len(out) >= so:
            break
    return out


def moc_cua(bao_cao_kqkd):
    q = cac_ky(bao_cao_kqkd.get("quarters") or [], 1)
    return f"{q[0]['yearReport']}-{q[0]['lengthReport']}|{(q[0].get('publicDate') or '')[:10]}" if q else ""


def so(v, giu_dong):
    if v is None:
        return None
    return round(v) if giu_dong else round(v / 1e9, 2)


def dung_bang(metrics_sec, qs, ns):
    rows = []
    for m in metrics_sec:
        f = m.get("field")
        tieu_de = (m.get("titleVi") or "").strip()
        giu_dong = "(vnd)" in tieu_de.lower()
        q = [so(x.get(f), giu_dong) if f else None for x in qs]
        n = [so(x.get(f), giu_dong) if f else None for x in ns]
        co_so = any(v not in (None, 0) for v in q + n)
        # dòng tiêu đề nhóm (không có mã) giữ lại để giữ cấu trúc; dòng số liệu rỗng ở cấp con thì bỏ cho gọn
        if f and not co_so and (m.get("level") or 1) > 1:
            continue
        row = {"f": f, "t": tieu_de, "c": m.get("level") or 1, "q": q, "n": n}
        if giu_dong:
            row["dv"] = "VND"
        rows.append(row)
    return rows


def tai_mot_ma(ma, ten, nganh, cu=None, tat_ca=False):
    kqkd = lay_bao_cao(ma, SECTIONS["kqkd"])
    moc = moc_cua(kqkd)
    if not moc:
        return None, "không có dữ liệu"
    if cu and not tat_ca and cu.get("moc") == moc:
        return cu, "giữ nguyên"
    metrics = nguon._goi("GET", f"{FS}/{ma}/financial-statement/metrics", nguon.H_VCI)["data"]
    bao = {"kqkd": kqkd, "cdkt": lay_bao_cao(ma, SECTIONS["cdkt"]), "lctt": lay_bao_cao(ma, SECTIONS["lctt"])}
    quy = cac_ky(kqkd.get("quarters") or [], SO_QUY)
    nam = cac_ky(kqkd.get("years") or [], SO_NAM)
    by = {k: {(r["yearReport"], r["lengthReport"]): r for r in (v.get("quarters") or []) + (v.get("years") or [])} for k, v in bao.items()}
    out = {
        "ma": ma, "ten": ten, "nganh": nganh, "loai": loai_hinh(metrics), "don_vi": "tỷ đồng", "cap_nhat": date.today().isoformat(), "moc": moc, "nguon": "Vietcap (iq.vietcap.com.vn)",
        "quy": [{"k": f"Q{r['lengthReport']}/{r['yearReport']}", "nam": r["yearReport"], "q": r["lengthReport"], "cb": (r.get("publicDate") or "")[:10]} for r in quy],
        "nam": [{"k": str(r["yearReport"]), "nam": r["yearReport"], "cb": (r.get("publicDate") or "")[:10]} for r in nam],
        "bc": {},
    }
    for k, sec in SECTIONS.items():
        qs = [by[k].get((r["yearReport"], r["lengthReport"]), {}) for r in quy]
        ns = [by[k].get((r["yearReport"], r["lengthReport"]), {}) for r in nam]
        out["bc"][k] = dung_bang(metrics.get(sec, []), qs, ns)
    co = {r["f"] for rows in out["bc"].values() for r in rows if r["f"]}
    tt = {k: next((f for f in cands if f in co), None) for k, cands in TOM_TAT.items()}
    tt["dt"] = next((f for f in DOANH_THU if f in co), None)
    out["tt"] = tt
    return out, "đã tải"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ma", nargs="*")
    ap.add_argument("--all", action="store_true", help="tải lại tất cả, kể cả mã chưa có kỳ mới")
    args = ap.parse_args()
    ds = json.loads((DATA / "co_phieu.json").read_text(encoding="utf-8")).get("co_phieu") or []
    if args.ma:
        chon = {m.upper() for m in args.ma}
        ds = [x for x in ds if x["ma"] in chon]
    OUT.mkdir(parents=True, exist_ok=True)
    muc_luc, loi = [], []
    for i, x in enumerate(ds, 1):
        ma = x["ma"]
        f = OUT / f"{ma}.json"
        cu = None
        if f.exists():
            try:
                cu = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                cu = None
        try:
            kq, tt = tai_mot_ma(ma, x.get("ten"), x.get("nganh"), cu, args.all)
        except Exception as e:
            kq, tt = cu, f"LỖI: {str(e)[:80]}"
            loi.append(ma)
        if kq and tt == "đã tải":
            f.write_text(json.dumps(kq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[{i}/{len(ds)}] {ma}: {tt}", flush=True)
        if kq:
            q = (kq.get("quy") or [{}])[0]
            muc_luc.append({"ma": ma, "ten": kq.get("ten"), "nganh": kq.get("nganh"), "loai": kq.get("loai"), "ky": q.get("k"), "cb": q.get("cb")})
    if not args.ma:                                   # chạy một phần thì không ghi đè mục lục đầy đủ
        (OUT / "muc_luc.json").write_text(json.dumps({"cap_nhat": date.today().isoformat(), "ds": muc_luc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Xong: {len(muc_luc)}/{len(ds)} mã có báo cáo" + (f", lỗi: {', '.join(loi)}" if loi else ""))
    if loi and len(loi) > len(ds) * 0.3:
        sys.exit(1)               # quá nhiều mã lỗi mới coi là lượt chạy hỏng; vài mã lỗi lẻ thì giữ dữ liệu cũ


if __name__ == "__main__":
    main()
