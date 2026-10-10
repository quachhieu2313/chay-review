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
import re
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
    # mốc gồm cả ngày cập nhật: báo cáo quý được soát xét/kiểm toán sau đó sẽ đổi mốc và kích hoạt tải lại số liệu mới
    return f"{q[0]['yearReport']}-{q[0]['lengthReport']}|{ngay_cap_nhat(q[0])}" if q else ""


def _ngay(x, *khoa, dung=min):
    ds = [str(x.get(k))[:10] for k in khoa if x.get(k)]
    return dung(ds) if ds else ""


def ngay_cong_bo(r):
    """Ngày công bố LẦN ĐẦU (ước tính): sớm nhất trong ngày hệ thống Vietcap tạo bản ghi và publicDate.
    publicDate/updateDate bị đẩy sang ngày cập nhật gần nhất khi báo cáo được soát xét/kiểm toán (trung vị chậm ~30 ngày so với lần đầu), không phải ngày công bố."""
    return _ngay(r, "createDate", "publicDate")


def ngay_cap_nhat(r):
    return _ngay(r, "createDate", "updateDate", "publicDate", dung=max)


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


# ---------------------------------------------------------------- đối chiếu chéo cả năm với KBS
# API KBS theo QUÝ trả cột lệch kỳ nên không dùng; theo NĂM (termtype=1) thì đúng nên dùng làm nguồn kiểm tra độc lập cho số liệu Vietcap.
DUNG_SAI_TUYET_DOI, DUNG_SAI_TUONG_DOI = 1.0, 0.005       # lệch ≤ 1 tỷ hoặc ≤ 0.5% thì coi là khớp (làm tròn, đơn vị nguồn)
LOAI_TRU_LNST = ("shareholders", "attribut", "parent", "non-contr", "taken", "before", "minority")


def _kbs_nam(ma, loai):
    return nguon._goi("GET", f"{nguon.KBS}/stock/finance-info/{ma}", nguon.H_KBS,
                      params={"page": 1, "pageSize": 4, "type": loai, "unit": 1000, "termtype": 1, "languageid": 1})


def _dong_kbs(data):
    """(danh sách năm theo cột, các dòng); None nếu cột năm trùng/thiếu (không tin được thứ tự cột)."""
    nam = [h.get("YearPeriod") for h in (data or {}).get("Head") or []]
    if not nam or len(set(nam)) != len(nam):
        return None, []
    return nam, [r for v in ((data or {}).get("Content") or {}).values() for r in v]


def _gia_tri_kbs(nam, rows, khop):
    for r in rows:
        ten = (r.get("NameEn") or "").strip().lower()
        if khop(ten):
            v = {y: r.get(f"Value{i + 1}") / 1e6 for i, y in enumerate(nam) if r.get(f"Value{i + 1}") is not None}   # nghìn đồng -> tỷ
            if v:
                return v
    return {}


CHI_TIEU_KT = (
    # (tên hiển thị, báo cáo, mã Vietcap, hàm nhận dòng KBS theo tên tiếng Anh, chỉ áp cho loại hình)
    ("Tổng tài sản", "cdkt", "bsa53", lambda t: t == "total assets", None),
    ("Vốn chủ sở hữu", "cdkt", "bsa78", lambda t: re.match(r"^[a-z]\.\s*owner'?s equity", t) is not None, None),
    ("Lợi nhuận sau thuế", "kqkd", "isa20", lambda t: "profit after tax" in t and not any(x in t for x in LOAI_TRU_LNST), None),
    ("Dòng tiền kinh doanh", "lctt", "cfa18", lambda t: t == "net cash flows from operating activities", None),
    ("Doanh thu thuần", "kqkd", "isa3", lambda t: re.fullmatch(r"(\d+\.\s*)?net revenue", t) is not None, ("Doanh nghiệp",)),
)


def _khop(a, b):
    return abs(a - b) <= max(DUNG_SAI_TUYET_DOI, DUNG_SAI_TUONG_DOI * abs(a))


def _hang(d, bc, f):
    return next((r for r in d["bc"].get(bc, []) if r["f"] == f), None)


def _tu_quy(d, bc, hang, y):
    """Số cả năm tính lại từ các quý của CHÍNH Vietcap: số cuối năm (cân đối kế toán) = quý 4; số phát sinh = tổng 4 quý. None nếu thiếu quý."""
    q_idx = {x["k"]: i for i, x in enumerate(d.get("quy") or [])}
    if bc == "cdkt":
        j = q_idx.get(f"Q4/{y}")
        return hang["q"][j] if j is not None else None
    ks = [f"Q{k}/{y}" for k in (1, 2, 3, 4)]
    if not all(k in q_idx for k in ks):
        return None
    vals = [hang["q"][q_idx[k]] for k in ks]
    return None if any(v is None for v in vals) else sum(vals)


def kiem_tra_cheo(ma, d):
    """So số liệu cả năm của Vietcap (đã lưu trong d) với KBS: tối đa 2 năm gần nhất, 5 chỉ tiêu. Trả {ngay, nguon, so_sanh, lech, khong_doi_chieu}."""
    kq = {"ngay": date.today().isoformat(), "nguon": "KBS (báo cáo cả năm)", "so_sanh": 0, "lech": [], "khong_doi_chieu": []}
    nam_vc = [x["nam"] for x in d.get("nam") or []]
    kbs = {}
    for loai in ("KQKD", "CDKT", "LCTT"):
        kbs[loai] = _dong_kbs(_kbs_nam(ma, loai))
    for ten, bc, f, khop, ap_dung in CHI_TIEU_KT:
        if ap_dung and d.get("loai") not in ap_dung:
            continue
        hang = next((r for r in d["bc"].get(bc, []) if r["f"] == f), None)
        nam_kbs, rows = kbs[{"kqkd": "KQKD", "cdkt": "CDKT", "lctt": "LCTT"}[bc]]
        v_kbs = _gia_tri_kbs(nam_kbs, rows, khop) if nam_kbs else {}
        if ten == "Vốn chủ sở hữu" and not v_kbs:             # ngân hàng không có dòng vốn chủ sở hữu riêng: = tổng tài sản − tổng nợ
            nam_c, rows_c = kbs["CDKT"]
            ts = _gia_tri_kbs(nam_c, rows_c, lambda t: t == "total assets") if nam_c else {}
            no = _gia_tri_kbs(nam_c, rows_c, lambda t: t == "total liabilities") if nam_c else {}
            v_kbs = {y: ts[y] - no[y] for y in ts if y in no}
        if not hang or not v_kbs:
            kq["khong_doi_chieu"].append(ten)
            continue
        chung = [y for y in nam_vc if y in v_kbs][:2]
        if not chung:
            kq["khong_doi_chieu"].append(ten)
            continue
        for y in chung:
            vc = hang["n"][nam_vc.index(y)]
            if vc is None:
                continue
            kq["so_sanh"] += 1
            lech = abs(vc - v_kbs[y])
            if lech > max(DUNG_SAI_TUYET_DOI, DUNG_SAI_TUONG_DOI * abs(vc)):
                m = {"ct": ten, "nam": y, "vietcap": round(vc, 1), "kbs": round(v_kbs[y], 1)}
                tq = _tu_quy(d, bc, hang, y)
                # Gợi ý nguồn nào có vẻ đúng: nếu KBS khớp số tính lại từ các quý của chính Vietcap (quý 4 hoặc tổng 4 quý) thì nghi số "cả năm" của Vietcap.
                # Chỉ dùng làm gợi ý khi hai nguồn đã lệch nhau: số cả năm đã kiểm toán khác số quý ban đầu là điều chỉnh bình thường, không tự nó là lỗi.
                if tq is not None and _khop(tq, v_kbs[y]):
                    m["goi_y"] = "kbs_khop_quy"
                    m["tu_quy"] = round(tq, 1)
                kq["lech"].append(m)
    return kq


def tai_mot_ma(ma, ten, nganh, cu=None, tat_ca=False, so_quy=SO_QUY, so_nam=SO_NAM, kiem_tra=True):
    kqkd = lay_bao_cao(ma, SECTIONS["kqkd"])
    moc = moc_cua(kqkd)
    if not moc:
        return None, "không có dữ liệu"
    if cu and not tat_ca and cu.get("moc") == moc:
        return cu, "giữ nguyên"
    metrics = nguon._goi("GET", f"{FS}/{ma}/financial-statement/metrics", nguon.H_VCI)["data"]
    bao = {"kqkd": kqkd, "cdkt": lay_bao_cao(ma, SECTIONS["cdkt"]), "lctt": lay_bao_cao(ma, SECTIONS["lctt"])}
    quy = cac_ky(kqkd.get("quarters") or [], so_quy)
    nam = cac_ky(kqkd.get("years") or [], so_nam)
    by = {k: {(r["yearReport"], r["lengthReport"]): r for r in (v.get("quarters") or []) + (v.get("years") or [])} for k, v in bao.items()}
    out = {
        "ma": ma, "ten": ten, "nganh": nganh, "loai": loai_hinh(metrics), "don_vi": "tỷ đồng", "cap_nhat": date.today().isoformat(), "moc": moc, "nguon": "Vietcap (iq.vietcap.com.vn)",
        "quy": [{"k": f"Q{r['lengthReport']}/{r['yearReport']}", "nam": r["yearReport"], "q": r["lengthReport"], "cb": ngay_cong_bo(r), "cn": ngay_cap_nhat(r)} for r in quy],
        "nam": [{"k": str(r["yearReport"]), "nam": r["yearReport"], "cb": ngay_cong_bo(r), "cn": ngay_cap_nhat(r)} for r in nam],
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
    if not kiem_tra:                            # dùng cho backtest (lịch sử dài): không cần đối chiếu KBS
        return out, "đã tải"
    try:
        out["kt"] = kiem_tra_cheo(ma, out)
    except Exception as e:                     # KBS lỗi thì không chặn việc lưu báo cáo; ghi nhận là chưa đối chiếu được
        out["kt"] = {"ngay": date.today().isoformat(), "nguon": "KBS (báo cáo cả năm)", "so_sanh": 0, "lech": [], "khong_doi_chieu": ["lỗi kết nối KBS"]}
    return out, "đã tải"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ma", nargs="*")
    ap.add_argument("--all", action="store_true", help="tải lại tất cả, kể cả mã chưa có kỳ mới")
    ap.add_argument("--chi-kiem-tra", action="store_true", help="chỉ chạy lại đối chiếu với KBS trên dữ liệu đã lưu, không tải lại từ Vietcap")
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
            if args.chi_kiem_tra:
                if not cu:
                    raise RuntimeError("chưa có dữ liệu để đối chiếu")
                cu["kt"] = kiem_tra_cheo(ma, cu)
                kq, tt = cu, "đã tải"
            else:
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
    # tổng hợp đối chiếu: mã nào số liệu cả năm lệch giữa Vietcap và KBS thì cảnh báo (GitHub Actions hiện thành annotation)
    tong = {"cap_nhat": date.today().isoformat(), "so_ma": 0, "khop": 0, "lech": [], "chua_doi_chieu": []}
    for x in muc_luc:
        try:
            kt = json.loads((OUT / f"{x['ma']}.json").read_text(encoding="utf-8")).get("kt") or {}
        except (OSError, ValueError):
            continue
        tong["so_ma"] += 1
        if kt.get("lech"):
            tong["lech"].append({"ma": x["ma"], "chi_tiet": kt["lech"]})
            print(f"::warning::BCTC {x['ma']}: số liệu cả năm lệch giữa Vietcap và KBS: " + "; ".join(f"{c['ct']} {c['nam']} (Vietcap {c['vietcap']} / KBS {c['kbs']})" for c in kt["lech"]))
        elif kt.get("so_sanh"):
            tong["khop"] += 1
        else:
            tong["chua_doi_chieu"].append(x["ma"])
    if not args.ma:
        (OUT / "kiem_tra.json").write_text(json.dumps(tong, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Đối chiếu KBS: khớp {tong['khop']}/{tong['so_ma']} mã, lệch {len(tong['lech'])}, chưa đối chiếu được {len(tong['chua_doi_chieu'])}")
    print(f"Xong: {len(muc_luc)}/{len(ds)} mã có báo cáo" + (f", lỗi: {', '.join(loi)}" if loi else ""))
    if loi and len(loi) > len(ds) * 0.3:
        sys.exit(1)               # quá nhiều mã lỗi mới coi là lượt chạy hỏng; vài mã lỗi lẻ thì giữ dữ liệu cũ


if __name__ == "__main__":
    main()
