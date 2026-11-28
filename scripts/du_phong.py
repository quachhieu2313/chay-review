# -*- coding: utf-8 -*-
"""
Dự phóng báo cáo tài chính bằng mô hình L1 của Phòng Phân tích ACBS (thư viện acbs-quick-model,
https://github.com/phucdh-acbs/acbs_quick_model), cho tab "Dự phóng BCTC" của trang Cổ phiếu khuyến nghị.

Mô hình đọc BCTC thô theo đúng tên bảng và mã khoản mục của FiinX/GBQ (ISA…, BSA…, CFA…, ghi chú NOC…/NOB…).
API Vietcap (cùng nguồn với scripts/bao_cao_tai_chinh.py) trả đúng các mã đó (viết thường) nên chỉ cần đổi tên cột
và dựng thêm các cột metadata (LENGTH_SERIES, START_DATE, END_DATE, STATUS…). Đối chiếu với dữ liệu mẫu GBQ đi
kèm thư viện (HPG, TCB): trùng trên 99% ô; chỗ lệch là vài kỳ được trình bày lại và 18 dòng mới theo Thông tư 99
mà Vietcap chưa có (để trống).

Phạm vi: doanh nghiệp phi tài chính (trừ bất động sản) và ngân hàng. Bỏ qua bất động sản, chứng khoán, bảo hiểm,
dịch vụ tài chính vì mô hình chưa hỗ trợ.

Ghi ra assets/data/du_phong/<MÃ>.json và assets/data/du_phong/muc_luc.json. Đơn vị: tỷ đồng (số gốc là đồng chia 1e9),
riêng dòng có đơn vị khác đồng (EPS, %, ngày…) giữ nguyên.

Chạy:   python scripts/du_phong.py              # chỉ chạy lại mã có kỳ báo cáo mới hoặc phiên bản mô hình mới
        python scripts/du_phong.py --all        # chạy lại tất cả
        python scripts/du_phong.py HPG TCB      # chỉ các mã chỉ định
"""
import argparse
import json
import math
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nguon  # noqa: E402

from quick_model import service as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
OUT = DATA / "du_phong"
FS = f"{nguon.VCI_IQ}/v1/company"
NAM_DU_PHONG = 3
CHI_GHI_KHI_CONG_BO = True
BO_QUA_NGANH = {"Bất động sản", "Dịch vụ tài chính", "Bảo hiểm"}

# bảng GBQ -> (section Vietcap, cột ID, kiểu tên cột metadata)
BANG = {
    "INCOME_STATEMENT": ("INCOME_STATEMENT", "INCOME_STATEMENT_ID", "upper"),
    "BALANCE_SHEET": ("BALANCE_SHEET", "BALANCE_SHEET_ID", "upper"),
    "CASH_FLOW": ("CASH_FLOW", "CASH_FLOW_ID", "upper"),
    "STX_FSC_NOTECOMPANY": ("NOTE", "NoteCompanyId", "camel"),
    "STX_FSC_NOTEBANK": ("NOTE", "NoteBankId", "camel"),
}
META = ["ORGAN_CODE", "TICKER", "YEAR_REPORT", "LENGTH_REPORT", "LENGTH_SERIES", "START_DATE", "END_DATE",
        "PUBLIC_DATE", "IS_AUDIT", "REPORT_FORM_TYPE_CODE", "SOURCE_NAME", "STATUS", "CREATE_DATE", "UPDATE_DATE"]
CAMEL = {"ORGAN_CODE": "OrganCode", "TICKER": "Ticker", "YEAR_REPORT": "YearReport", "LENGTH_REPORT": "LengthReport",
         "LENGTH_SERIES": "LengthSeries", "START_DATE": "StartDate", "END_DATE": "EndDate", "PUBLIC_DATE": "PublicDate",
         "IS_AUDIT": "IsAudit", "REPORT_FORM_TYPE_CODE": "ReportFormTypeCode", "SOURCE_NAME": "SourceName",
         "STATUS": "Status", "CREATE_DATE": "CreateDate", "UPDATE_DATE": "UpdateDate"}
THANG_CUOI = {1: 3, 2: 6, 3: 9, 4: 12, 5: 12}


def ho(loai, nganh):
    """Nhóm mô hình của một mã, hoặc None nếu mô hình chưa hỗ trợ."""
    if nganh in BO_QUA_NGANH:
        return None
    if loai == "Ngân hàng":
        return "bank"
    if loai == "Doanh nghiệp":
        return "nonfinancial"
    return None


def _ky(nam, kr):
    """Ngày đầu/cuối kỳ: quý 1–4 là 3 tháng, 5 là cả năm."""
    t = THANG_CUOI[kr]
    dau = date(nam, 1 if kr == 5 else t - 2, 1)
    cuoi = (date(nam + 1, 1, 1) if t == 12 else date(nam, t + 1, 1)) - timedelta(days=1)
    return dau.isoformat(), cuoi.isoformat()


def _ngay(v):
    return str(v)[:19].replace("T", " ") if v else None


def khung(ma, bang, ban_ghi, ma_khoan):
    """Bản ghi Vietcap (quý + năm) -> DataFrame đúng cột GBQ của bảng."""
    _, cot_id, kieu = BANG[bang]
    dong = []
    for i, r in enumerate(ban_ghi):
        nam, kr = r.get("yearReport"), r.get("lengthReport")
        if nam is None or kr not in THANG_CUOI:
            continue
        dau, cuoi = _ky(int(nam), int(kr))
        m = {"ORGAN_CODE": r.get("organCode") or ma, "TICKER": ma, "YEAR_REPORT": int(nam), "LENGTH_REPORT": int(kr),
             "LENGTH_SERIES": 12 if kr == 5 else 3, "START_DATE": dau, "END_DATE": cuoi,
             "PUBLIC_DATE": _ngay(r.get("publicDate")), "IS_AUDIT": None, "REPORT_FORM_TYPE_CODE": None,
             "SOURCE_NAME": "Vietcap", "STATUS": 1, "CREATE_DATE": _ngay(r.get("createDate")),
             "UPDATE_DATE": _ngay(r.get("updateDate") or r.get("createDate"))}
        x = {(CAMEL[k] if kieu == "camel" else k): v for k, v in m.items()}
        x[cot_id] = i + 1
        for c in ma_khoan:
            v = r.get(c.lower())
            x[c] = None if v is None or (isinstance(v, float) and math.isnan(v)) else v
        if bang == "BALANCE_SHEET":
            bu_tt99(x)
        dong.append(x)
    return pd.DataFrame(dong)


# Thông tư 99 (từ 2026) thêm tài sản sinh học: tổng ngắn hạn BSA290, tổng dài hạn BSA294. Vietcap đã cộng chúng vào
# BSA1/BSA23 nhưng chưa trả dòng riêng, nên suy ra bằng phần còn lại. Đối chiếu HPG Q2/2026 với GBQ: khớp từng đồng.
TT99 = {"BSA290": ("BSA1", ["BSA2", "BSA5", "BSA8", "BSA15", "BSA18"]),
        "BSA294": ("BSA23", ["BSA24", "BSA29", "BSA163", "BSA40", "BSA43", "BSA48", "BSA49"])}


def bu_tt99(x):
    if x["YEAR_REPORT"] < 2026:
        return
    for dich, (tong, con) in TT99.items():
        if dich not in x or x.get(dich) is not None or x.get(tong) is None:
            continue
        con_lai = x[tong] - sum(x.get(c) or 0 for c in con)
        if abs(con_lai) >= 1e6:
            x[dich] = con_lai


def lay_frames(ma, family):
    hd = S.data_contract(family)
    cache, frames = {}, {}
    for bang, info in hd.items():
        sec = BANG[bang][0]
        if sec not in cache:
            d = nguon._goi("GET", f"{FS}/{ma}/financial-statement", nguon.H_VCI, params={"section": sec}) or {}
            d = d.get("data") or {}
            cache[sec] = (d.get("quarters") or []) + (d.get("years") or [])
        if not cache[sec]:
            if info["required"]:
                raise S.ServiceError(f"Vietcap không trả bảng {sec}")
            continue
        frames[bang] = khung(ma, bang, cache[sec], info["item_columns"])
    return frames


def _so(v, don_vi):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    if don_vi == "VND":
        return round(v / 1e9, 2)
    return round(v, 4) if abs(v) < 100 else round(v, 1)


def bang_gon(df, ty_le=False):
    """DataFrame dòng × kỳ -> {cot: [...], dong: [{id, ten, bc, dv, v: [...]}]}.
    Bảng tỷ lệ (đơn vị %) lấy tên chỉ tiêu từ chỉ mục của DataFrame."""
    ky = [c for c in df.columns if c not in ("line_id", "label", "statement", "unit")]
    dong = []
    for idx, r in df.iterrows():
        if ty_le:
            dong.append({"id": str(idx), "ten": str(idx), "bc": "", "dv": "%", "v": [_so(r[c], "%") for c in ky]})
            continue
        dv = r.get("unit", "")
        dong.append({"id": r.get("line_id"), "ten": r.get("label"), "bc": r.get("statement", ""),
                     "dv": "tỷ đồng" if dv == "VND" else (dv or ""), "v": [_so(r[c], dv) for c in ky]})
    return {"cot": ky, "dong": dong}


def chay_mot_ma(ma, family, ten, nganh):
    t0 = time.time()
    frames = lay_frames(ma, family)
    out = S.forecast(ma, family, frames=frames, years=NAM_DU_PHONG)
    st = out.status
    kq = {"ma": ma, "ten": ten, "nganh": nganh, "family": family, "chay_luc": datetime.now().isoformat(timespec="minutes"),
          "nguon": "BCTC: Vietcap. Mô hình: ACBS Quick Model (Phòng Phân tích ACBS)",
          "meta": out.meta, "status": st, "issues": out.issues.to_dict("records") if hasattr(out.issues, "to_dict") else out.issues}
    # README của mô hình: "Chỉ đưa ra ngoài khi status.publishable = true". Trang web là công khai nên mã chưa đạt
    # chỉ ghi trạng thái và lý do, không ghi số dự phóng.
    if st.get("ok") and (st.get("publishable") or not CHI_GHI_KHI_CONG_BO):
        kq["nam"] = bang_gon(out.annual)
        kq["quy"] = bang_gon(out.quarterly)
        kq["ty_le"] = {"nam": bang_gon(out.ratios["annual"], True), "quy": bang_gon(out.ratios["quarterly"], True)}
        a = out.assumptions
        kq["gia_dinh"] = a.to_dict("records") if hasattr(a, "to_dict") else a
        o = out.one_offs
        kq["bat_thuong"] = o.to_dict("records") if hasattr(o, "to_dict") else o
        giai = {}
        for nam in out.meta.get("forecast_years", [])[:2]:
            for line in ("npat_parent", "net_revenue", "nii"):
                try:
                    e = out.explain(line, nam)
                    giai.setdefault(line, {})[nam] = e.get("headline")
                except Exception:
                    pass
        kq["giai_thich"] = giai
    kq["giay"] = round(time.time() - t0, 1)
    return json.loads(json.dumps(_sach(kq), ensure_ascii=False, default=str))


def tom_tat(kq):
    """Doanh thu (ngân hàng: tổng thu nhập hoạt động) và LNST công ty mẹ: năm gốc thực tế + 2 năm dự phóng, tỷ đồng."""
    if "nam" not in kq:
        return None
    cot = kq["nam"]["cot"]
    goc = f"{kq['meta']['origin_year']} A"
    ky = [goc] + [f"{y} F" for y in kq["meta"]["forecast_years"][:2]]
    by = {r["id"]: r for r in kq["nam"]["dong"]}
    out = {"ky": ky}
    for khoa, ids in (("dt", ("net_revenue", "toi")), ("ln", ("npat_parent",))):
        r = next((by[i] for i in ids if i in by), None)
        out[khoa] = [r["v"][cot.index(k)] if r and k in cot else None for k in ky]
    return out


def _sach(x):
    if isinstance(x, dict):
        return {str(k): _sach(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_sach(v) for v in x]
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if hasattr(x, "item"):
        try:
            return _sach(x.item())
        except Exception:
            return str(x)
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ma", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ml = json.loads((DATA / "bctc" / "muc_luc.json").read_text(encoding="utf-8"))["ds"]
    cu = {}
    f_ml = OUT / "muc_luc.json"
    if f_ml.exists():
        cu = {x["ma"]: x for x in json.loads(f_ml.read_text(encoding="utf-8")).get("ds", [])}
    phien_ban = S.MODEL_VERSION
    ds, loi = [], []
    chon = {m.upper() for m in args.ma}
    for x in ml:
        ma, fam = x["ma"], ho(x.get("loai"), x.get("nganh"))
        if chon and ma not in chon:
            if ma in cu:
                ds.append(cu[ma])
            continue
        if not fam:
            continue
        c = cu.get(ma)
        if not (args.all or chon) and c and c.get("ky") == x.get("ky") and c.get("pb") == phien_ban and (OUT / f"{ma}.json").exists():
            ds.append(c)
            continue
        try:
            kq = chay_mot_ma(ma, fam, x.get("ten"), x.get("nganh"))
        except Exception as e:  # một mã lỗi không chặn cả lượt
            loi.append(f"{ma}: {e}")
            print(f"{ma}: LỖI {e}")
            if c:
                ds.append(c)
            continue
        (OUT / f"{ma}.json").write_text(json.dumps(kq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        st = kq["status"]
        dong = {"ma": ma, "ten": x.get("ten"), "nganh": x.get("nganh"), "family": fam, "ky": x.get("ky"), "pb": phien_ban,
                "usable": st.get("usable"), "publishable": st.get("publishable"), "flags": st.get("flags") or [],
                "tom_tat": tom_tat(kq)}
        ds.append(dong)
        print(f"{ma} ({fam}): usable={st.get('usable')} publishable={st.get('publishable')} flags={st.get('flags')} {kq['giay']}s")
    ds.sort(key=lambda r: r["ma"])
    f_ml.write_text(json.dumps({"cap_nhat": date.today().isoformat(), "phien_ban": phien_ban, "ds": ds, "loi": loi},
                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Xong {len(ds)} mã, {len(loi)} lỗi")


if __name__ == "__main__":
    main()
