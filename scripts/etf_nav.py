"""NAV, chênh lệch giá/NAV và tín hiệu điểm mua cho các quỹ ETF của Dragon Capital.

Nguồn: trang sản phẩm của Dragon Capital (dragoncapital.com.vn) gọi API công khai cho khách
(Salesforce Apex, chế độ asGuest). Không cần đăng nhập. Mỗi quỹ ghi ra assets/data/etf_nav/<MÃ>.json.

Cách tính (chi tiết trong docstring từng hàm):
  - NAV/ccq phiên t = giá đóng cửa − chênh lệch Dragon Capital công bố cho phiên t.
  - Chênh lệch % = (giá đóng cửa / NAV − 1) × 100.
  - Vùng thị trường dựa trên NAV: % cách đỉnh 52 tuần và % cách trung bình 200 phiên.
  - Thống kê lịch sử: lợi nhuận theo giá sàn 1/3/6/12 tháng sau mỗi phiên, nhóm theo tín hiệu.

Chạy: python scripts/etf_nav.py
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "etf_nav"

API = "https://www.dragoncapital.com.vn/individual/vi/webruntime/api/apex/execute?language=vi&asGuest=true&htmlEncode=false"
SITE = "0DMJ2000000oLukOAE"
H = {"User-Agent": "Mozilla/5.0 (KimChiNam data bot)", "Content-Type": "application/json"}

# mã trên sàn -> (fundCode, fundReportCode, trang sản phẩm)
QUY = {
    "E1VFVN30": ("VFMVN30", "DCVFMVN30", "https://www.dragoncapital.com.vn/individual/vi/product/a0eJ2000001X9zhIAC/vn30"),
    "FUEVFVND": ("VFMVND", "DCVFMVN DIAMOND", "https://www.dragoncapital.com.vn/individual/vi/product/a0eJ2000001XA0ZIAW/vndiamond"),
    "FUEDCMID": ("VFMMID", "VFMMID", "https://www.dragoncapital.com.vn/individual/vi/product/a0eJ2000001XA1XIAW/vnmidcap"),
}

# Vùng thị trường theo NAV. Ngưỡng chọn từ phân tích 2014-2026 của E1VFVN30 (xem thong_ke.vung):
# chỉ vùng "giảm sâu" cho lợi nhuận 12 tháng sau tốt hơn hẳn mức nền; các vùng giữa không hơn.
VUNG = [
    ("giam_sau", "Giảm sâu", lambda dd, ma: dd <= -30 or ma <= -15),
    ("dieu_chinh_manh", "Điều chỉnh mạnh", lambda dd, ma: dd <= -20),
    ("dieu_chinh", "Điều chỉnh", lambda dd, ma: dd <= -10),
    ("gan_dinh", "Gần đỉnh", lambda dd, ma: True),
]
NHOM_CL = [(-100, -1, "< −1%"), (-1, -0.5, "−1% … −0,5%"), (-0.5, 0, "−0,5% … 0%"),
           (0, 0.5, "0% … +0,5%"), (0.5, 1, "+0,5% … +1%"), (1, 100, "> +1%")]


def log(*a):
    print(*a, flush=True)


def r(x, n=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, n)


def apex(cls, method, params):
    body = {"namespace": "", "classname": cls, "method": method, "isContinuation": False, "params": params, "cacheable": False}
    for lan in range(3):
        try:
            res = requests.post(API, headers=H, json=body, timeout=60)
            res.raise_for_status()
            return res.json().get("returnValue")
        except Exception as e:
            if lan == 2:
                raise
            log(f"  thử lại {method}: {str(e)[:80]}")


def doc_json(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def lay(ma):
    fc, frc, _ = QUY[ma]
    hom_nay = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    pricing = apex("@udd/01pJ2000000DF0h", "getFundPricingData", {"fundCode": fc, "fundReportCode": frc, "navDate": hom_nay + "T00:00:00"})

    def thu(cls, method, params):
        try:
            return apex(cls, method, params)
        except Exception as e:
            log(f"  ! {method}: {str(e)[:100]}")
            return None

    return {
        "pricing": pricing,
        "risk": thu("@udd/01pJ2000000CgSo", "getLatestFundFundamentalRiskData", {"fundCode": fc}),
        "portfolio": thu("@udd/01pJ2000000CgSq", "getLatestFundPortfolioData", {"fundCode": fc}),
        "te": thu("@udd/01pJ2000000CgSw", "getLatestFundTrackingErrorsByReportCode", {"fundCode": fc}),
        "exp": thu("@udd/01pJ2000000CgSm", "getLatestFundExpenseRatioByReportCode", {"fundCode": fc}),
    }


def bang_gia(pricing):
    """DataFrame theo phiên: gia (đóng cửa), nav (NAV/ccq), cl (% chênh lệch giá/NAV)."""
    rows = []
    for x in pricing.get("fundPricingList") or []:
        g, dlt = x.get("closePrice__c"), x.get("deltaChangeWithNav__c")
        if g is None or dlt is None or not x.get("date__c"):
            continue
        g, dlt = float(g), float(dlt)
        nav = g - dlt
        if nav <= 0:
            continue
        rows.append({"ngay": x["date__c"][:10], "gia": g, "nav": nav, "cl": (g / nav - 1) * 100})
    df = pd.DataFrame(rows).drop_duplicates("ngay", keep="last")
    df["ngay"] = pd.to_datetime(df["ngay"])
    return df.set_index("ngay").sort_index()


def them_tin_hieu(df):
    s = df["nav"]
    df["dd52"] = (s / s.rolling(252, min_periods=120).max() - 1) * 100   # % cách đỉnh 52 tuần
    df["ma200"] = (s / s.rolling(200, min_periods=150).mean() - 1) * 100  # % cách trung bình 200 phiên
    for k, n in (("f1m", 21), ("f3m", 63), ("f6m", 126), ("f12m", 252)):
        df[k] = (df["gia"].shift(-n) / df["gia"] - 1) * 100            # lợi nhuận theo giá sàn sau n phiên
    df["vung"] = [vung(dd, ma) for dd, ma in zip(df["dd52"], df["ma200"])]
    return df


def vung(dd, ma):
    if pd.isna(dd) or pd.isna(ma):
        return None
    return next(k for k, _, f in VUNG if f(dd, ma))


def thong_ke_nhom(x, cot="f12m"):
    v = x[cot].dropna()
    if not len(v):
        return {"so_phien": int(len(x))}
    return {"so_phien": int(len(x)), "so_phien_do": int(len(v)),
            "f3m": r(x["f3m"].mean(), 1), "f6m": r(x["f6m"].mean(), 1), "f12m": r(v.mean(), 1),
            "f12m_duong": r((v > 0).mean() * 100, 0), "f12m_xau": r(v.quantile(.1), 1), "f12m_tot": r(v.quantile(.9), 1)}


def so_dot(mask):
    """Số đợt liên tiếp (cách nhau > 60 phiên coi là đợt mới)."""
    idx = [i for i, m in enumerate(mask) if m]
    return sum(1 for i, j in zip([-999] + idx, idx) if j - i > 60)


def dca(df, nam_tu, chon):
    """Mua 1 triệu mỗi tháng. chon(list vị trí phiên trong tháng) -> vị trí phiên mua. Trả giá vốn bình quân, % lãi."""
    x = df[df.index >= f"{nam_tu}-01-01"]
    gia, cl = x["gia"].values, x["cl"].values
    cc = gop = 0.0
    for _, idx in pd.Series(range(len(x)), index=x.index.to_period("M")).groupby(level=0):
        i = chon(list(idx.values), cl)
        cc += 1e6 / gia[i]; gop += 1e6
    return {"gop": gop, "gia_von": gop / cc, "lai": (cc * gia[-1] / gop - 1) * 100}


def dau_thang(idx, cl):
    return idx[0]


def cho_nav(idx, cl, toi_da=10):
    for j in idx[:toi_da]:
        if cl[j] <= 0:
            return j
    return idx[min(toi_da, len(idx)) - 1]


def thong_ke(df):
    out = {"tu_ngay": df.index[0].strftime("%Y-%m-%d"), "so_phien": int(len(df))}
    co = df.dropna(subset=["f12m"])
    out["nen"] = thong_ke_nhom(df)
    out["nen"]["f1m"] = r(df["f1m"].mean(), 2)

    ds = []
    for k, ten, _ in VUNG:
        x = df[df["vung"] == k]
        t = thong_ke_nhom(x)
        t.update({"ma": k, "ten": ten, "so_dot": so_dot((df["vung"] == k).tolist())})
        ds.append(t)
    out["vung"] = ds

    ds = []
    df2 = df.copy()
    df2["cl_5"] = df2["cl"].shift(-5)
    for a, b, ten in NHOM_CL:
        x = df2[(df2["cl"] > a) & (df2["cl"] <= b)]
        ds.append({"ten": ten, "so_phien": int(len(x)), "cl_tb": r(x["cl"].mean(), 2), "cl_5": r(x["cl_5"].mean(), 2),
                   "f1m": r(x["f1m"].mean(), 2), "f3m": r(x["f3m"].mean(), 1)})
    out["chenh_lech"] = ds

    nam = df[df.index >= df.index[-1] - pd.Timedelta(days=365)]["cl"]
    out["cl_1n"] = {"p10": r(nam.quantile(.1)), "p50": r(nam.median()), "p90": r(nam.quantile(.9)),
                    "tb": r(nam.mean()), "ty_le_duoi_nav": r((nam <= 0).mean() * 100, 0), "so_phien": int(len(nam))}

    bt = []
    nam_dau = df.index[0].year + 1
    for y in range(nam_dau, df.index[-1].year + 1):
        a, b = dca(df, y, dau_thang), dca(df, y, cho_nav)
        bt.append({"tu_nam": y, "gop": r(a["gop"], 0), "gia_von_thuong": r(a["gia_von"], 0), "lai_thuong": r(a["lai"], 1),
                   "gia_von_cho": r(b["gia_von"], 0), "lai_cho": r(b["lai"], 1),
                   "re_hon": r((a["gia_von"] / b["gia_von"] - 1) * 100, 2)})
    out["backtest"] = bt
    return out


def gon_danh_muc(pf):
    if not pf:
        return None
    vi = lambda t, k: ((t or {}).get("vi") or {}).get(k)
    top = [{"ma": x.get("assetId"), "ty_trong": r(x.get("weight"), 2), "nganh": vi(x.get("translation"), "sectorLevel") or x.get("sectorLevel"),
            "gia_tri": r(x.get("marketValue"), 0), "so_cp": x.get("holdingVolume")} for x in pf.get("top10Holding") or []]
    nganh = []
    for x in pf.get("allocationBySectors") or []:
        w = next(iter((x.get("fundWeight") or {}).values()), None)
        nganh.append({"ten": vi(x.get("translation"), "industryLevel2") or x.get("industryLevel2"), "ty_trong": r(w, 2)})
    nganh.sort(key=lambda z: -(z["ty_trong"] or 0))
    tai_san = [{"ten": vi(x.get("translation"), "sourceName") or x.get("sourceName"), "ty_trong": r(x.get("valueAssetType"), 2)}
               for x in pf.get("allocationByAssetTypes") or []]
    return {"ngay": (pf.get("tradingDate") or "")[:10], "top10": top, "nganh": nganh, "tai_san": tai_san}


def ccq_luu_hanh(pricing):
    """Số chứng chỉ quỹ lưu hành theo phiên (thay đổi = tiền vào/ra quỹ qua hoán đổi)."""
    out = {}
    for x in pricing.get("fundTradingList") or []:
        v = x.get("lastIssuedShare__c")
        d = (x.get("lastDate__c") or x.get("dateTime__c") or "")[:10]
        if v and d:
            out[d] = float(v)
    return out


def chay_mot(ma):
    log(f"ETF {ma}")
    raw = lay(ma)
    p = raw["pricing"]
    df = them_tin_hieu(bang_gia(p))
    if len(df) < 300:
        raise RuntimeError(f"quá ít phiên: {len(df)}")
    cuoi = df.iloc[-1]
    path = OUT / f"{ma}.json"
    cu = doc_json(path, {})

    rk = raw["risk"] or {}
    dinh_gia = None
    if rk:
        dinh_gia = {"ngay": (rk.get("tradingDate") or "")[:10],
                    "pe": r(rk.get("peOfFund")), "pb": r(rk.get("pbOfFund")), "roe": r(rk.get("roeOfFund")),
                    "co_tuc": r(rk.get("divYldOfFund")), "beta": r(rk.get("betaOfFund")),
                    "sharpe": r(rk.get("sharpeRatioOfFund")), "do_lech": r(rk.get("standardDeviationOfFund")),
                    "so_ma": r(rk.get("numberOfHoldingOfFund"), 0),
                    "pe_vni": r(rk.get("peOfVnindex")), "pb_vni": r(rk.get("pbOfVnindex")), "roe_vni": r(rk.get("roeOfVnindex")),
                    "co_tuc_vni": r(rk.get("divYldOfVnindex"))}
    # lịch sử P/E, P/B: API chỉ trả kỳ mới nhất nên tự tích lũy mỗi tháng
    ls = {x["ngay"]: x for x in cu.get("dinh_gia_ls") or []}
    if dinh_gia and dinh_gia["ngay"]:
        ls[dinh_gia["ngay"]] = {"ngay": dinh_gia["ngay"], "pe": dinh_gia["pe"], "pb": dinh_gia["pb"],
                                "pe_vni": dinh_gia["pe_vni"], "pb_vni": dinh_gia["pb_vni"]}

    te = (raw["te"] or [None])[0] or {}
    ex = (raw["exp"] or [None])[0] or {}
    tai_co_cau = [{"ngay": x.get("Date__c"), "ghi_chu": x.get("Remark_VI__c") or x.get("Remark_EN__c")}
                  for x in (p.get("fundRebalanceList") or []) if x.get("Date__c")]
    tai_co_cau.sort(key=lambda z: z["ngay"], reverse=True)
    ccq = ccq_luu_hanh(p)
    ngay_ccq = sorted(ccq)[-260:]

    ln = p.get("latestFundNav") or {}
    n250 = df.tail(260)
    out = {
        "ma": ma, "quy": QUY[ma][1], "nguon": QUY[ma][2],
        "cap_nhat": df.index[-1].strftime("%Y-%m-%d"),
        "lay_luc": datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M"),
        "phien": {"ngay": df.index[-1].strftime("%Y-%m-%d"), "gia": r(cuoi["gia"], 0), "nav": r(cuoi["nav"], 2),
                  "cl": r(cuoi["cl"], 2), "dd52": r(cuoi["dd52"], 1), "ma200": r(cuoi["ma200"], 1),
                  "vung": cuoi["vung"], "dinh_52t": r(df["nav"].tail(252).max(), 2),
                  "tb_200": r(df["nav"].tail(200).mean(), 2)},
        "nav_moi": {"nav": r(ln.get("navPerShare__c"), 2), "tong": r(ln.get("totalNav__c"), 0),
                    "thay_doi": r(ln.get("lastNavChange__c"), 2), "ytd": r(ln.get("ytdReturn__c"), 2),
                    "1y": r(ln.get("navChangeIn1Year__c"), 2), "3y": r(ln.get("navChangeIn3Years__c"), 2),
                    "5y": r(ln.get("fiveYearsReturn__c"), 2)},
        "dinh_gia": dinh_gia,
        "dinh_gia_ls": sorted(ls.values(), key=lambda z: z["ngay"])[-120:],
        "bam_duoi": {"ngay": (te.get("date__c") or "")[:10], "sai_so": r(te.get("trackingError__c")),
                     "chenh_lech": r(te.get("excessReturn__c"))} if te else None,
        "chi_phi": {"ngay": (ex.get("periodOfReportEndDate__c") or "")[:10], "ty_le": r(ex.get("expenseRatioIn12M__c"))} if ex else None,
        "tai_co_cau": tai_co_cau[:10],
        "danh_muc": gon_danh_muc(raw["portfolio"]),
        "ccq": {"d": ngay_ccq, "v": [ccq[d] for d in ngay_ccq]},
        # chuỗi 260 phiên gần nhất cho biểu đồ
        "d": [x.strftime("%Y-%m-%d") for x in n250.index],
        "gia": [r(x, 0) for x in n250["gia"]],
        "nav": [r(x, 2) for x in n250["nav"]],
        "cl": [r(x, 2) for x in n250["cl"]],
        "thong_ke": thong_ke(df),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  {out['cap_nhat']}: giá {out['phien']['gia']:,.0f} · NAV {out['phien']['nav']:,.2f} · chênh {out['phien']['cl']}% · vùng {out['phien']['vung']}")
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ds =[a.upper() for a in sys.argv[1:]] or list(QUY)
    loi = 0
    for ma in ds:
        try:
            chay_mot(ma)
        except Exception as e:
            loi += 1
            log(f"  ! {ma}: {str(e)[:200]}")
    if loi == len(ds):
        sys.exit(1)


if __name__ == "__main__":
    main()
