# -*- coding: utf-8 -*-
"""
Cập nhật dữ liệu thị trường cho website Kim Chỉ Nam.

Lấy dữ liệu trực tiếp từ API bảng giá của Vietcap (VCI) và KBS (xem scripts/nguon.py),
rồi ghi ra các file JSON trong assets/data/:
  chi_so/<MÃ>.json   lịch sử từng chỉ số (VN-Index, VN30, chỉ số tham chiếu của ETF...)
  chi_so_ngay.json   diễn biến theo phút trong phiên gần nhất của 4 chỉ số chính
  ban-tin/_posts/    bản tin tổng kết phiên tự viết sau giờ đóng cửa (chế độ đầy đủ)
  co_phieu.json      bảng giá rổ VN100 (gồm cả VN30) cho trang Thị trường
  etf.json           danh sách ETF + hiệu suất (trang ETF)
  etf/<MÃ>.json      lịch sử giá từng ETF (trang chi tiết ETF)
  cp/<MÃ>.json       nến OHLCV (+ chỉ số cơ bản với cổ phiếu) từng mã VN30 và ETF (popup chi tiết mã)
  danh_muc_ma.json   danh sách mã có popup, dùng cho ô tìm kiếm
  quy_nam_giu.json   cổ phiếu được các quỹ mở (Fmarket) và quỹ ETF nắm giữ nhiều nhất (trang Quỹ nắm giữ)
  quy_mo_phong.json  quỹ mô phỏng KCN VN30 (trang Quỹ mô phỏng)

Hai chế độ:
  python scripts/cap_nhat_du_lieu.py               đầy đủ: tải lại toàn bộ lịch sử (~2 phút), chạy sau giờ đóng cửa
  python scripts/cap_nhat_du_lieu.py --trong-phien nhanh: chỉ lấy bảng giá hiện tại (~10 giây), chạy mỗi 10 phút trong phiên
GitHub Actions tự chạy cả hai (.github/workflows/cap-nhat-du-lieu.yml và cap-nhat-trong-phien.yml).
Mã nào lấy lỗi thì giữ dữ liệu cũ của mã đó, không làm hỏng cả web.
"""
import json
import math
import sys

import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nguon  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
(OUT / "etf").mkdir(parents=True, exist_ok=True)
(OUT / "cp").mkdir(parents=True, exist_ok=True)
(OUT / "chi_so").mkdir(parents=True, exist_ok=True)
BAN_TIN = ROOT / "ban-tin" / "_posts"
CHI_SO_CHINH = ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]

SO_PHIEN = 1800  # khoảng 7 năm giao dịch

CHI_SO = {
    "VNINDEX": "VN-Index",
    "HNXINDEX": "HNX-Index",
    "UPCOMINDEX": "UPCoM-Index",
    "VN30": "VN30",
    "VN100": "VN100",
    "VNDIAMOND": "VN Diamond",
    "VNFINLEAD": "VNFIN Lead",
    "VNFINSELECT": "VNFIN Select",
    "VNX50": "VNX50",
}

# từ khoá trong tên quỹ -> chỉ số tham chiếu
THAM_CHIEU = [
    ("VNFIN LEAD", "VNFINLEAD"),
    ("VNFINSELECT", "VNFINSELECT"),
    ("DIAMOND", "VNDIAMOND"),
    ("VN100", "VN100"),
    ("VNX50", "VNX50"),
    ("VN30", "VN30"),
]

NHOM = {
    "VN30": "VN30",
    "VNDIAMOND": "Diamond",
    "VNFINLEAD": "Tài chính",
    "VNFINSELECT": "Tài chính",
    "VN100": "VN100",
    "VNX50": "VNX50",
}

# 6 mã vào chỉ số FTSE All-World khi Việt Nam được FTSE Russell nâng hạng (hiệu lực 21/9/2026)
FTSE_ALLWORLD = ["VCB", "VIC", "VHM", "BID", "HPG", "VPB"]
# 27 mã vào FTSE Global All Cap: 3 Large Cap + 3 Mid Cap (6 mã trên) + 21 Small Cap
FTSE_ALLCAP = FTSE_ALLWORLD + [
    "FPT", "GEX", "HDB", "HCM", "MCH", "MSN", "NVL", "SHB", "STB", "SSB", "SSI", "TCX",
    "VNM", "VCI", "VJC", "MSB", "VRE", "VPL", "VIX", "VND", "VCK",
]

PHI_MO_PHONG = 0.005  # phí quản lý giả định 0,5%/năm của quỹ mô phỏng
NAV_KHOI_DAU = 10000.0
NGAY_KHOI_DAU = "2021-01-04"


def log(*a):
    print(*a, flush=True)


def lich_su(ma, so_phien=SO_PHIEN):
    """DataFrame [time, open, high, low, close, volume] (giá theo đồng, chỉ số theo điểm); None nếu lỗi."""
    try:
        return nguon.lich_su(ma, so_phien)
    except Exception as e:
        log(f"  ! {ma}: {str(e)[:120]}")
        return None


def doc_json(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


DA_GHI = False  # có file dữ liệu nào thay đổi trong lần chạy này không


def ghi_json(path, data):
    global DA_GHI
    DA_GHI = True
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def gio_vn():
    return datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M")


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


def loi_nhuan(dates, closes):
    """% thay đổi theo các kỳ chuẩn, tính theo phiên giao dịch."""
    s = pd.Series(closes, index=pd.to_datetime(dates))
    last = s.iloc[-1]

    def back(n):
        return (last / s.iloc[-1 - n] - 1) * 100 if len(s) > n else None

    nam_truoc = s[s.index.year < s.index[-1].year]
    ytd = (last / nam_truoc.iloc[-1] - 1) * 100 if len(nam_truoc) else None
    out = {"1d": back(1), "1m": back(21), "3m": back(63), "6m": back(126), "ytd": ytd, "1y": back(252), "3y": back(756)}
    if len(s) > 756:
        out["3y_nam"] = ((last / s.iloc[-757]) ** (1 / 3) - 1) * 100  # bình quân năm
    return {k: r(v) for k, v in out.items()}


def rui_ro(closes, n=252):
    s = pd.Series(closes[-(n + 1):])
    ret = s.pct_change().dropna()
    bien_dong = ret.std() * math.sqrt(252) * 100 if len(ret) > 20 else None
    dinh = s.cummax()
    sut_giam = ((s / dinh - 1).min()) * 100 if len(s) else None
    return r(bien_dong), r(sut_giam)


# ---------------------------------------------------------------- chỉ số cơ bản (nguồn KBS)
def chi_so_co_ban(ma):
    """Chỉ số tài chính quý gần nhất. Lỗi thì trả None để giữ số cũ."""
    try:
        return nguon.chi_so_co_ban(ma)
    except Exception as e:
        log(f"  ! chỉ số cơ bản {ma}: {str(e)[:100]}")
        return None


# ---------------------------------------------------------------- chỉ số
def doc_chi_so(ds=None):
    out = {}
    for ma in ds or CHI_SO:
        x = doc_json(OUT / "chi_so" / f"{ma}.json", None)
        if x:
            out[ma] = x
    return out


def cap_nhat_chi_so():
    cu = doc_chi_so()
    out = {}
    for ma, ten in CHI_SO.items():
        log(f"Chỉ số {ma}")
        df = lich_su(ma)
        if df is None:
            if ma in cu:
                out[ma] = cu[ma]
            continue
        out[ma] = {"ma": ma, "ten": ten, "d": df["time"].tolist(), "c": [r(x, 2) for x in df["close"]]}
        ghi_json(OUT / "chi_so" / f"{ma}.json", out[ma])
    ghi_json(OUT / "chi_so" / "danh_sach.json", {k: v["ten"] for k, v in out.items()})
    return out


def cap_nhat_trong_ngay(cs):
    """Diễn biến theo phút của phiên gần nhất cho 4 chỉ số chính."""
    out, ngay = {}, None
    for ma in CHI_SO_CHINH:
        try:
            nen = nguon.lich_su_phut(ma)
        except Exception as e:
            log(f"  ! phút {ma}: {str(e)[:100]}")
            continue
        if not nen:
            continue
        hom = nen[-1][1]
        ngay = ngay or hom
        diem = [(g, c) for g, d, c in nen if d == hom]
        s = cs.get(ma)
        tc = None
        if s and s["d"]:
            tc = s["c"][-2] if s["d"][-1] == hom and len(s["c"]) > 1 else s["c"][-1]
        out[ma] = {"t": [g for g, _ in diem], "c": [r(c, 2) for _, c in diem], "tham_chieu": tc}
    if out:
        cu = doc_json(OUT / "chi_so_ngay.json", {})
        moi = {"ngay": ngay, "chi_so": out}
        if json.dumps(cu.get("chi_so"), sort_keys=True) != json.dumps(out, sort_keys=True):
            moi["cap_nhat_luc"] = gio_vn()
            ghi_json(OUT / "chi_so_ngay.json", moi)
            log("chi_so_ngay.json đổi")


# ---------------------------------------------------------------- ETF
def danh_ba_etf():
    """Tên quỹ và chỉ số tham chiếu đã biết. Dùng khi nguồn trả tên bị hỏng (vd 'FUEVFVND - ETF')."""
    return doc_json(ROOT / "scripts" / "etf_danh_ba.json", {})


def cap_nhat_etf():
    etf = nguon.danh_sach_etf()
    ba = danh_ba_etf()
    cu = {e["ma"]: e for e in doc_json(OUT / "etf.json", {}).get("quy", [])}
    phien = {}
    try:
        for row in nguon.bang_gia([m for m, _ in etf]):
            phien[row["listing_symbol"]] = row
    except Exception as e:
        log(f"  ! bảng giá ETF: {str(e)[:100]}")
    ds = []
    for ma, ten in etf:
        log(f"ETF {ma}")
        if ten.strip().upper().endswith("- ETF") and ma in ba:
            ten = ba[ma]["ten_day_du"]  # nguồn trả tên rút gọn, lấy tên đầy đủ đã lưu
        ten_hoa = ten.upper()
        tc = next((v for k, v in THAM_CHIEU if k in ten_hoa), None) or (ba.get(ma) or {}).get("tham_chieu")
        df = lich_su(ma)
        if df is None or len(df) < 2:
            if ma in cu:
                ds.append(cu[ma])
            continue
        d, c = df["time"].tolist(), [r(x, 0) for x in df["close"]]
        ghi_json(OUT / "etf" / f"{ma}.json", {"ma": ma, "d": d, "c": c})
        ghi_nen(ma, ten, "Quỹ ETF", "etf", df, phien.get(ma, {}), None)
        gtgd = (df["close"] * df["volume"]).tail(20).mean()
        bd, sg = rui_ro(c)
        ds.append({
            "ma": ma,
            "ten": ten.replace("Quỹ ETF ", "").strip(),
            "ten_day_du": ten,
            "tham_chieu": tc,
            "nhom": NHOM.get(tc, "Khác"),
            "gia": c[-1],
            "ngay": d[-1],
            "tu_ngay": d[0],
            "gtgd_20": r(gtgd, 0),
            "loi_nhuan": loi_nhuan(d, c),
            "bien_dong_1y": bd,
            "sut_giam_1y": sg,
            "spark": c[-60:],
        })
    ghi_json(OUT / "etf.json", {"cap_nhat": max((x["ngay"] for x in ds), default=None), "cap_nhat_luc": gio_vn(), "quy": ds})
    return ds


# ---------------------------------------------------------------- thông tin phiên cho bảng giá
def thong_tin_phien(row, gia):
    """Tham chiếu/trần/sàn, giá trị giao dịch, khối ngoại, vốn hoá từ một dòng bảng giá."""
    def so(k):
        v = row.get(k)
        return None if v is None or pd.isna(v) else float(v)
    gt = so("match_accumulated_value")
    nn_mua, nn_ban = so("match_foreign_buy_value"), so("match_foreign_sell_value")
    cp_ny = so("listing_listed_share")
    return {
        "tham_chieu": so("listing_ref_price"),
        "tran": so("listing_ceiling"),
        "san": so("listing_floor"),
        "gtgd": r(gt * 1e6, 0) if gt is not None else None,
        "nn_mua": r(nn_mua, 0) if nn_mua is not None else None,
        "nn_ban": r(nn_ban, 0) if nn_ban is not None else None,
        "von_hoa": r(cp_ny * gia, 0) if cp_ny and gia else None,
    }


# ---------------------------------------------------------------- file nến cho popup
def ghi_nen(ma, ten, nganh, loai, df, ph, co_ban):
    cu = doc_json(OUT / "cp" / f"{ma}.json", {})

    def so(k):
        v = ph.get(k)
        return None if v is None or pd.isna(v) else float(v)

    ghi_json(OUT / "cp" / f"{ma}.json", {
        "ma": ma,
        "ten": ten,
        "nganh": nganh,
        "loai": loai,
        "san": "HOSE",
        "co_phieu_niem_yet": so("listing_listed_share") or cu.get("co_phieu_niem_yet"),
        "tran": so("listing_ceiling"),
        "san_gia": so("listing_floor"),
        "tham_chieu": so("listing_ref_price"),
        "cap_nhat_luc": gio_vn(),
        "co_ban": co_ban if co_ban is not None else cu.get("co_ban"),
        "d": df["time"].tolist(),
        "o": [r(x, 0) for x in df["open"]],
        "h": [r(x, 0) for x in df["high"]],
        "l": [r(x, 0) for x in df["low"]],
        "c": [r(x, 0) for x in df["close"]],
        "v": [int(x) for x in df["volume"]],
    })


def ghi_danh_muc_ma():
    """Danh sách mã có popup (cho ô tìm kiếm): đọc từ co_phieu.json và etf.json."""
    cp = doc_json(OUT / "co_phieu.json", {}).get("co_phieu", [])
    etf = doc_json(OUT / "etf.json", {}).get("quy", [])
    ds = [{"ma": x["ma"], "ten": x["ten"], "loai": "cp", "nhom": x.get("nganh", "")} for x in cp]
    ds += [{"ma": x["ma"], "ten": x.get("ten_day_du") or x["ten"], "loai": "etf", "nhom": "Quỹ ETF"} for x in etf]
    ghi_json(OUT / "danh_muc_ma.json", sorted(ds, key=lambda x: x["ma"]))


# ---------------------------------------------------------------- VN30 + quỹ mô phỏng
def cap_nhat_vn30_va_quy(chi_so):
    ro30 = nguon.ro_chi_so("VN30")
    ro100 = nguon.ro_chi_so("VN100")
    ro = ro100 + [m for m in ro30 + FTSE_ALLCAP if m not in ro100]
    ro = list(dict.fromkeys(ro))
    cty = nguon.thong_tin_cong_ty()
    ten = {k: v[0] for k, v in cty.items()}
    nganh = {k: v[1] for k, v in cty.items()}

    # thông tin phiên: trần, sàn, tham chiếu, số cổ phiếu niêm yết
    phien = {}
    try:
        for row in nguon.bang_gia(ro):
            phien[row["listing_symbol"]] = row
    except Exception as e:
        log(f"  ! bảng giá: {str(e)[:100]}")

    gia = {}
    kl = {}
    for ma in ro:
        log(f"Cổ phiếu {ma}")
        df = lich_su(ma)
        if df is None:
            continue
        gia[ma] = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["time"]))
        kl[ma] = int(df["volume"].iloc[-1])
        ghi_nen(ma, ten.get(ma, ma), nganh.get(ma, "Khác"), "cp", df, phien.get(ma, {}), chi_so_co_ban(ma))

    # ----- bảng theo dõi trang Thị trường
    co_phieu = []
    for ma, s in gia.items():
        co_phieu.append({
            "ma": ma,
            "ten": ten.get(ma, ma),
            "nganh": nganh.get(ma, "Khác"),
            "gia": r(s.iloc[-1], 0),
            "thay_doi": r((s.iloc[-1] / s.iloc[-2] - 1) * 100) if len(s) > 1 else 0,
            "khoi_luong": kl[ma],
            "spark": [r(x, 0) for x in s.tail(20)],
            "ro": (["VN30"] if ma in ro30 else []) + (["VN100"] if ma in ro100 else []) + (["FTSE27"] if ma in FTSE_ALLCAP else []) + (["FTSE6"] if ma in FTSE_ALLWORLD else []),
            **thong_tin_phien(phien.get(ma, {}), float(s.iloc[-1])),
        })
    ngay_cuoi = max(s.index[-1] for s in gia.values()).strftime("%Y-%m-%d") if gia else None
    ghi_json(OUT / "co_phieu.json", {"cap_nhat": ngay_cuoi, "cap_nhat_luc": gio_vn(), "ro": "VN100", "co_phieu": co_phieu})

    # ----- quỹ mô phỏng: chia đều tỷ trọng các mã VN30 hiện tại, tái cân bằng đầu mỗi quý
    bang = pd.DataFrame({m: gia[m] for m in ro30 if m in gia}).sort_index()
    bang = bang[bang.index >= NGAY_KHOI_DAU].ffill()
    if bang.empty:
        return
    ngay = bang.index
    tai_can_bang = {ngay[0]}
    for i in range(1, len(ngay)):
        if ngay[i].quarter != ngay[i - 1].quarter:
            tai_can_bang.add(ngay[i])

    gia_tri = NAV_KHOI_DAU
    so_luong = None
    nav = []
    he_so_phi = 1 - PHI_MO_PHONG / 252
    lan_can_bang = []
    for t in ngay:
        hang = bang.loc[t]
        if so_luong is not None:
            gia_tri = float((so_luong * hang).sum()) * he_so_phi
            so_luong = so_luong * he_so_phi
        if t in tai_can_bang:
            co_gia = hang.dropna()
            so_luong = (gia_tri / len(co_gia)) / co_gia
            so_luong = so_luong.reindex(bang.columns).fillna(0)
            lan_can_bang.append(t.strftime("%Y-%m-%d"))
        nav.append(gia_tri)

    d = [x.strftime("%Y-%m-%d") for x in ngay]
    nav = [r(x, 2) for x in nav]
    hang_cuoi = bang.iloc[-1]
    gt = (so_luong * hang_cuoi)
    tong = gt.sum()
    danh_muc = []
    for ma in bang.columns:
        if gt[ma] <= 0:
            continue
        s = gia[ma]
        danh_muc.append({
            "ma": ma,
            "ten": ten.get(ma, ma),
            "nganh": nganh.get(ma, "Khác"),
            "ty_trong": r(gt[ma] / tong * 100, 2),
            "gia": r(s.iloc[-1], 0),
            "thay_doi": r((s.iloc[-1] / s.iloc[-2] - 1) * 100) if len(s) > 1 else 0,
        })
    danh_muc.sort(key=lambda x: -x["ty_trong"])
    theo_nganh = {}
    for x in danh_muc:
        theo_nganh[x["nganh"]] = theo_nganh.get(x["nganh"], 0) + x["ty_trong"]
    nganh_list = sorted(({"nganh": k, "ty_trong": r(v, 2)} for k, v in theo_nganh.items()), key=lambda x: -x["ty_trong"])

    # beta và sai lệch so với VN30
    beta = sai_lech = None
    if "VN30" in chi_so:
        vn30 = pd.Series(chi_so["VN30"]["c"], index=chi_so["VN30"]["d"])
        q = pd.Series(nav, index=d)
        hop = pd.concat([q, vn30], axis=1, join="inner").tail(253).pct_change().dropna()
        if len(hop) > 20:
            cov = hop.cov().iloc[0, 1]
            beta = cov / hop.iloc[:, 1].var()
            sai_lech = (hop.iloc[:, 0] - hop.iloc[:, 1]).std() * math.sqrt(252) * 100

    bd, sg = rui_ro(nav)
    nam_tu_dau = (len(nav) - 1) / 252
    ghi_json(OUT / "quy_mo_phong.json", {
        "ten": "Quỹ mô phỏng Kim Chỉ Nam VN30 Bình Quyền",
        "ma": "KCN30",
        "cap_nhat": d[-1],
        "ngay_khoi_dau": d[0],
        "nav_khoi_dau": NAV_KHOI_DAU,
        "phi": PHI_MO_PHONG * 100,
        "so_ma": len(danh_muc),
        "tai_can_bang_gan_nhat": lan_can_bang[-1],
        "d": d,
        "nav": nav,
        "loi_nhuan": loi_nhuan(d, nav),
        "tu_dau": r((nav[-1] / nav[0] - 1) * 100),
        "tu_dau_nam": r(((nav[-1] / nav[0]) ** (1 / nam_tu_dau) - 1) * 100) if nam_tu_dau > 0 else None,
        "bien_dong_1y": bd,
        "sut_giam_1y": sg,
        "sut_giam_tu_dau": rui_ro(nav, n=len(nav))[1],
        "beta_1y": r(beta),
        "sai_lech_1y": r(sai_lech),
        "cap_nhat_luc": gio_vn(),
        # mốc để chế độ trong phiên tính NAV tạm tính: tỷ trọng và giá tại phiên gần nhất
        "nen": {
            "ngay": d[-1],
            "nav": nav[-1],
            "ty_trong": {ma: round(float(gt[ma] / tong), 6) for ma in bang.columns if gt[ma] > 0},
            "gia": {ma: float(hang_cuoi[ma]) for ma in bang.columns if gt[ma] > 0},
        },
        "danh_muc": danh_muc,
        "nganh": nganh_list,
    })


# ---------------------------------------------------------------- chế độ trong phiên
def dat_diem(d, c, ngay, gia_tri):
    """Ghi giá của ngày `ngay`: thay điểm cuối nếu đã có ngày đó, ngược lại thêm điểm mới."""
    if d and d[-1] == ngay:
        c[-1] = gia_tri
    elif not d or d[-1] < ngay:
        d.append(ngay)
        c.append(gia_tri)


def trong_phien():
    etf = doc_json(OUT / "etf.json", None)
    cp = doc_json(OUT / "co_phieu.json", None)
    cs = doc_chi_so()
    quy = doc_json(OUT / "quy_mo_phong.json", None)
    if not (etf and cp and cs and quy):
        log("Chưa có dữ liệu nền, hãy chạy chế độ đầy đủ trước.")
        return

    ds_ma = [x["ma"] for x in cp["co_phieu"]] + [x["ma"] for x in etf["quy"]]
    try:
        bang = nguon.bang_gia(ds_ma)
    except Exception as e:
        log(f"Không lấy được bảng giá: {str(e)[:120]}")
        return
    gia, ngay = {}, None
    nen_hom_nay = {}
    dong_bang = {row.get("listing_symbol"): row for row in bang}
    for row in bang:
        p = row.get("match_match_price")
        if p is None or pd.isna(p) or float(p) <= 0:
            continue
        ref = row.get("match_reference_price")
        gia[row["listing_symbol"]] = (
            float(p),
            float(ref) if ref is not None and not pd.isna(ref) and float(ref) > 0 else None,
            int(row.get("match_accumulated_volume") or 0),
        )
        ngay = ngay or str(row.get("listing_trading_date"))[:10]

        def so(k):
            v = row.get(k)
            return None if v is None or pd.isna(v) or float(v) <= 0 else float(v)

        nen_hom_nay[row["listing_symbol"]] = {
            "o": so("match_open_price"), "h": so("match_highest"), "l": so("match_lowest"),
            "c": float(p), "v": int(row.get("match_accumulated_volume") or 0),
            "tran": so("listing_ceiling"), "san_gia": so("listing_floor"), "tham_chieu": so("listing_ref_price"),
        }
    if not gia or not ngay:
        log("Bảng giá chưa có giá khớp, bỏ qua.")
        return
    log(f"Bảng giá ngày {ngay}: {len(gia)} mã")
    luc = gio_vn()

    def luu(path, cu, moi):
        """Chỉ ghi file khi số liệu đổi, để không tạo commit thừa (ví dụ giờ nghỉ trưa)."""
        a = dict(cu); b = dict(moi)
        a.pop("cap_nhat_luc", None); b.pop("cap_nhat_luc", None)
        if json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True):
            return False
        moi["cap_nhat_luc"] = luc
        ghi_json(path, moi)
        return True

    # ----- cổ phiếu VN30
    cu = json.loads(json.dumps(cp))
    hom_nay_da_co = cp.get("cap_nhat") == ngay
    for x in cp["co_phieu"]:
        g = gia.get(x["ma"])
        if not g:
            continue
        p, ref, vol = g
        x["gia"] = r(p, 0)
        if ref:
            x["thay_doi"] = r((p / ref - 1) * 100)
        x["khoi_luong"] = vol
        x.update(thong_tin_phien(dong_bang.get(x["ma"], {}), p))
        if hom_nay_da_co:
            x["spark"][-1] = r(p, 0)
        else:
            x["spark"] = (x["spark"] + [r(p, 0)])[-20:]
    cp["cap_nhat"] = ngay
    log("co_phieu.json", "đổi" if luu(OUT / "co_phieu.json", cu, cp) else "không đổi")

    # ----- nến hôm nay của từng mã (VN30 và ETF)
    for ma_nen in [x["ma"] for x in cp["co_phieu"]] + [q["ma"] for q in etf["quy"]]:
        n = nen_hom_nay.get(ma_nen)
        path = OUT / "cp" / f"{ma_nen}.json"
        h = doc_json(path, None)
        if not n or not h:
            continue
        cu_h = json.loads(json.dumps(h))
        c = r(n["c"], 0)
        o = r(n["o"] or n["c"], 0)
        cao = r(max(n["h"] or c, c, o), 0)
        thap = r(min(n["l"] or c, c, o), 0)
        if h["d"] and h["d"][-1] == ngay:
            h["o"][-1], h["h"][-1], h["l"][-1], h["c"][-1], h["v"][-1] = o, cao, thap, c, n["v"]
        elif not h["d"] or h["d"][-1] < ngay:
            h["d"].append(ngay); h["o"].append(o); h["h"].append(cao); h["l"].append(thap); h["c"].append(c); h["v"].append(n["v"])
        for k in ("tran", "san_gia", "tham_chieu"):
            if n[k]:
                h[k] = n[k]
        luu(path, cu_h, h)

    # ----- ETF
    cu = json.loads(json.dumps(etf))
    for q in etf["quy"]:
        g = gia.get(q["ma"])
        if not g:
            continue
        path = OUT / "etf" / f"{q['ma']}.json"
        h = doc_json(path, None)
        if not h:
            continue
        h_cu = json.dumps(h)
        dat_diem(h["d"], h["c"], ngay, r(g[0], 0))
        if json.dumps(h) != h_cu:
            ghi_json(path, h)
        q["gia"] = r(g[0], 0)
        q["ngay"] = ngay
        q["loi_nhuan"] = loi_nhuan(h["d"], h["c"])
        q["spark"] = h["c"][-60:]
    etf["cap_nhat"] = ngay
    log("etf.json", "đổi" if luu(OUT / "etf.json", cu, etf) else "không đổi")

    # ----- chỉ số chính (bảng giá không có chỉ số nên lấy riêng 4 chỉ số)
    cu = json.loads(json.dumps(cs))
    for ma in ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]:
        if ma not in cs:
            continue
        df = lich_su(ma, 3)
        if df is None or df.empty:
            continue
        cuoi = df.iloc[-1]
        if pd.to_datetime(cuoi["time"]).strftime("%Y-%m-%d") == ngay:
            dat_diem(cs[ma]["d"], cs[ma]["c"], ngay, r(float(cuoi["close"]), 2))
    for ma in CHI_SO_CHINH:
        if ma in cs and json.dumps(cs[ma]) != json.dumps(cu.get(ma)):
            ghi_json(OUT / "chi_so" / f"{ma}.json", cs[ma])
            log(f"chi_so/{ma}.json đổi")
    cap_nhat_trong_ngay(cs)

    # ----- quỹ mô phỏng: NAV tạm tính từ tỷ trọng và giá ở phiên trước
    nen = quy.get("nen")
    if nen and nen["ngay"] < ngay:
        cu = json.loads(json.dumps(quy))
        tong_w, tong = 0.0, 0.0
        moi_w = {}
        for ma, w in nen["ty_trong"].items():
            g = gia.get(ma)
            p0 = nen["gia"].get(ma)
            if not g or not p0:
                continue
            tong_w += w
            tong += w * g[0] / p0
            moi_w[ma] = w * g[0] / p0
        if tong_w > 0:
            nav_moi = nen["nav"] * (tong / tong_w) * (1 - PHI_MO_PHONG / 252)
            dat_diem(quy["d"], quy["nav"], ngay, r(nav_moi, 2))
            tong_moi = sum(moi_w.values())
            for x in quy["danh_muc"]:
                g = gia.get(x["ma"])
                if not g:
                    continue
                x["gia"] = r(g[0], 0)
                if g[1]:
                    x["thay_doi"] = r((g[0] / g[1] - 1) * 100)
                if x["ma"] in moi_w:
                    x["ty_trong"] = r(moi_w[x["ma"]] / tong_moi * 100, 2)
            quy["danh_muc"].sort(key=lambda x: -x["ty_trong"])
            theo_nganh = {}
            for x in quy["danh_muc"]:
                theo_nganh[x["nganh"]] = theo_nganh.get(x["nganh"], 0) + x["ty_trong"]
            quy["nganh"] = sorted(({"nganh": k, "ty_trong": r(v, 2)} for k, v in theo_nganh.items()), key=lambda x: -x["ty_trong"])
            n = quy["nav"]
            quy["cap_nhat"] = ngay
            quy["loi_nhuan"] = loi_nhuan(quy["d"], n)
            quy["tu_dau"] = r((n[-1] / n[0] - 1) * 100)
            nam = (len(n) - 1) / 252
            quy["tu_dau_nam"] = r(((n[-1] / n[0]) ** (1 / nam) - 1) * 100) if nam > 0 else None
            log("quy_mo_phong.json", "đổi" if luu(OUT / "quy_mo_phong.json", cu, quy) else "không đổi")


# ---------------------------------------------------------------- danh mục ước tính của các quỹ ETF
def cap_nhat_ro_etf():
    """Thành phần rổ chỉ số mà các quỹ ETF bám theo, kèm tỷ trọng trong rổ.

    Tỷ trọng = giá x số cổ phiếu free-float x hệ số trần của chỉ số (scripts/ro_chi_so_he_so.json, lấy từ
    FiinQuantX, cần cập nhật tay sau mỗi kỳ cơ cấu chỉ số). Rổ nào chưa có trong file đó thì ước tính theo
    vốn hoá niêm yết (ty_trong_nguon = "von_hoa", kém chính xác hơn).
    Đây KHÔNG phải danh mục chính thức của quỹ: quỹ có thể lệch do mô phỏng, sai số bám đuổi."""
    (OUT / "ro_chi_so").mkdir(parents=True, exist_ok=True)
    etf = doc_json(OUT / "etf.json", {}).get("quy", [])
    ds_ro = sorted({q["tham_chieu"] for q in etf if q.get("tham_chieu")})
    cty = nguon.thong_tin_cong_ty()
    snap = doc_json(ROOT / "scripts" / "ro_chi_so_he_so.json", {})
    thanh_phan = {}
    for ro in ds_ro:
        if ro in snap.get("thanh_phan", {}):
            thanh_phan[ro] = list(snap["thanh_phan"][ro])
            continue
        try:
            thanh_phan[ro] = nguon.thanh_phan_ro(ro)
        except Exception as e:
            log(f"  ! rổ {ro}: {str(e)[:100]}")
    moi = sorted({m for v in thanh_phan.values() for m in v})
    if not moi:
        return
    gia = {}
    try:
        for row in nguon.bang_gia(moi):
            gia[row["listing_symbol"]] = row
    except Exception as e:
        log(f"  ! bảng giá rổ ETF: {str(e)[:100]}")
        return
    for ro, ma_list in thanh_phan.items():
        if not ma_list:
            log(f"Rổ {ro}: không có thành phần")
            continue
        muc = []
        for m in ma_list:
            row = gia.get(m)
            if not row:
                continue

            def so(k):
                v = row.get(k)
                return None if v is None or pd.isna(v) else float(v)
            p = so("match_match_price") or so("listing_ref_price")
            ref = so("listing_ref_price")
            cp = so("listing_listed_share")
            if not p or not cp:
                continue
            muc.append({
                "ma": m,
                "ten": cty.get(m, (m, "Khác"))[0],
                "nganh": cty.get(m, (m, "Khác"))[1],
                "gia": r(p, 0),
                "thay_doi": r((p / ref - 1) * 100) if ref else None,
                "von_hoa": r(p * cp, 0),
            })
        co_he_so = ro in snap.get("thanh_phan", {})
        if co_he_so:
            ff, hs = snap["free_float"], snap["he_so"].get(ro, {})
            gt = {x["ma"]: x["gia"] * ff[x["ma"]] * hs.get(x["ma"], 1) for x in muc if x["ma"] in ff}
            tong = sum(gt.values()) or 1
            for x in muc:
                x["ty_trong"] = r(gt.get(x["ma"], 0) / tong * 100, 2)
        else:
            tong = sum(x["von_hoa"] for x in muc) or 1
            for x in muc:
                x["ty_trong"] = r(x["von_hoa"] / tong * 100, 2)
        muc.sort(key=lambda x: -x["ty_trong"])
        nganh = {}
        for x in muc:
            nganh[x["nganh"]] = nganh.get(x["nganh"], 0) + x["ty_trong"]
        ghi_json(OUT / "ro_chi_so" / f"{ro}.json", {
            "ma": ro,
            "cap_nhat": date_vn(),
            "cap_nhat_luc": gio_vn(),
            "so_ma": len(muc),
            "ty_trong_nguon": "free_float" if co_he_so else "von_hoa",
            "ngay_he_so": snap.get("ngay") if co_he_so else None,
            "thanh_phan": muc,
            "nganh": sorted(({"nganh": k, "ty_trong": r(v, 2)} for k, v in nganh.items()), key=lambda x: -x["ty_trong"]),
        })
        log(f"Rổ {ro}: {len(muc)} mã")


def cap_nhat_quy_nam_giu():
    """Tổng hợp cổ phiếu được các quỹ nắm giữ: quỹ mở (danh mục top 10 thật) + quỹ ETF (theo rổ chỉ số)."""
    try:
        quy = nguon.quy_mo_nam_giu()
    except Exception as e:
        log(f"  ! quỹ mở: {str(e)[:100]}")
        return
    if not quy:
        return
    cty = nguon.thong_tin_cong_ty()
    quy_nn = []
    for ham in (nguon.quy_vaneck_vnm, nguon.quy_globalx_vnam, nguon.quy_fubon_00885):
        try:
            quy_nn.append(ham())
        except Exception as e:
            log(f"  ! quỹ nước ngoài {ham.__name__}: {str(e)[:100]}")
    if not quy_nn:  # lỗi thì giữ danh sách cũ
        cu_nn = doc_json(OUT / "quy_nam_giu.json", {}).get("quy_nn_meta", [])
        log("Không lấy được quỹ nước ngoài, bỏ qua" if not cu_nn else "Giữ dữ liệu quỹ nước ngoài cũ")
    etf = [q for q in doc_json(OUT / "etf.json", {}).get("quy", []) if q.get("tham_chieu")]
    ro = {}
    for q in etf:
        if q["tham_chieu"] not in ro:
            d = doc_json(OUT / "ro_chi_so" / f"{q['tham_chieu']}.json", {})
            ro[q["tham_chieu"]] = {x["ma"] for x in d.get("thanh_phan", [])}

    ma_ds = {m for q in quy for m, _ in q["top"]} | {m for v in ro.values() for m in v} | {m for q in quy_nn for m, _ in q["top"]}
    cp = {}
    for m in ma_ds:
        cp[m] = {"ma": m, "ten": cty.get(m, (m, "Khác"))[0], "nganh": cty.get(m, (m, "Khác"))[1], "quy_mo": [], "etf": [], "quy_nn": []}
    for q in quy:
        for m, pc in q["top"]:
            cp[m]["quy_mo"].append({"ma": q["ma"], "ten": q["ten"], "loai": q["loai"], "pct": r(pc, 2)})
    for q in etf:
        for m in ro[q["tham_chieu"]]:
            cp[m]["etf"].append(q["ma"])
    for q in quy_nn:
        for m, pc in q["top"]:
            cp[m]["quy_nn"].append({"ma": q["ma"], "ten": q["ten"], "pct": r(pc, 2)})
    ds = []
    for m, x in cp.items():
        x["quy_mo"].sort(key=lambda t: -t["pct"])
        n = len(x["quy_mo"])
        pcs = [t["pct"] for t in x["quy_mo"]]
        x["so_quy"] = n
        x["pct_tb"] = r(sum(pcs) / n, 2) if n else None
        x["pct_max"] = max(pcs) if n else None
        x["so_etf"] = len(x["etf"])
        x["quy_nn"].sort(key=lambda t: -t["pct"])
        x["so_quy_nn"] = len(x["quy_nn"])
        ds.append(x)
    ds.sort(key=lambda x: (-x["so_quy"], -(x["pct_tb"] or 0)))
    ngay = [q["ngay"] for q in quy if q["ngay"]]
    moi = {
        "so_quy_mo": len(quy), "so_etf": len(etf),
        "quy_nn_meta": [{"ma": q["ma"], "ten": q["ten"], "ngay": q["ngay"], "nguon": q["nguon"], "so_ma": len(q["top"]),
                         "top": [{"ma": m, "pct": r(p, 2)} for m, p in sorted(q["top"], key=lambda t: -t[1])[:10]]} for q in quy_nn],
        "ngay_tu": min(ngay) if ngay else None, "ngay_den": max(ngay) if ngay else None,
        "co_phieu": ds,
    }
    cu = doc_json(OUT / "quy_nam_giu.json", {})
    if {k: v for k, v in cu.items() if k != "cap_nhat_luc"} != moi:
        moi["cap_nhat_luc"] = gio_vn()
        ghi_json(OUT / "quy_nam_giu.json", moi)
    log(f"Quỹ nắm giữ: {len(quy)} quỹ mở, {len(etf)} quỹ ETF, {len(ds)} mã")


def date_vn():
    return datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- bản tin tổng kết phiên
def vn(x, so_le=2):
    """Định dạng số kiểu Việt Nam: 1.234,56"""
    if x is None:
        return "–"
    s = f"{abs(x):,.{so_le}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("−" if x < 0 else "") + s


def dau(x, so_le=2):
    return ("+" if x and x > 0 else "") + vn(x, so_le)


def viet_ban_tin():
    """Viết bài tổng kết phiên vào ban-tin/_posts/. Chỉ viết sau 15:05 của chính ngày giao dịch đó."""
    bay_gio = datetime.now(timezone(timedelta(hours=7)))
    hom_nay = bay_gio.strftime("%Y-%m-%d")
    cs = doc_chi_so(CHI_SO_CHINH)
    vni = cs.get("VNINDEX")
    if not vni or vni["d"][-1] != hom_nay or bay_gio.hour * 60 + bay_gio.minute < 15 * 60 + 5:
        log("Chưa đến lúc viết bản tin (chỉ viết sau 15:05 ngày có giao dịch).")
        return
    cp = doc_json(OUT / "co_phieu.json", {}).get("co_phieu", [])
    etf = doc_json(OUT / "etf.json", {}).get("quy", [])
    quy = doc_json(OUT / "quy_mo_phong.json", {})
    ngay_vn = bay_gio.strftime("%d/%m/%Y")

    def doi(s):
        c = s["c"]
        return c[-1], c[-1] - c[-2], (c[-1] / c[-2] - 1) * 100

    v, dv, pv = doi(vni)
    xu_huong = "tăng" if dv > 0 else "giảm" if dv < 0 else "đứng yên"
    dong_chi_so = []
    for ma in CHI_SO_CHINH:
        if ma in cs:
            a, b, c = doi(cs[ma])
            dong_chi_so.append(f"| {cs[ma]['ten']} | {vn(a)} | {dau(b)} | {dau(c)}% |")

    def ro(m):
        return [x for x in cp if m in (x.get("ro") or [])]
    vn100 = ro("VN100") or cp
    tang = sum(1 for x in vn100 if x["thay_doi"] > 0)
    giam = sum(1 for x in vn100 if x["thay_doi"] < 0)
    dung = len(vn100) - tang - giam
    tran = sum(1 for x in vn100 if x.get("tran") and x["gia"] >= x["tran"])
    san = sum(1 for x in vn100 if x.get("san") and x["gia"] <= x["san"])
    gtgd = sum(x.get("gtgd") or 0 for x in vn100)
    top_tang = sorted(vn100, key=lambda x: -x["thay_doi"])[:5]
    top_giam = sorted(vn100, key=lambda x: x["thay_doi"])[:5]
    top_gt = sorted(vn100, key=lambda x: -(x.get("gtgd") or 0))[:5]
    nn = [(x, (x.get("nn_mua") or 0) - (x.get("nn_ban") or 0)) for x in vn100]
    nn_rong = sum(r_ for _, r_ in nn)
    nn_mua = sorted([t for t in nn if t[1] > 0], key=lambda t: -t[1])[:5]
    nn_ban = sorted([t for t in nn if t[1] < 0], key=lambda t: t[1])[:5]

    def ds_ma(lst, f):
        return ", ".join(f(x) for x in lst) or "không có"

    etf_top = sorted(etf, key=lambda q: -(q.get("gtgd_20") or 0))[:3]
    tieu_de = f"Bản tin thị trường {ngay_vn}: VN-Index {xu_huong} {vn(abs(dv))} điểm"
    mo_ta = (f"VN-Index {xu_huong} {vn(abs(pv))}% về {vn(v)} điểm; nhóm VN100 có {tang} mã tăng, {giam} mã giảm; "
             f"khối ngoại {'mua' if nn_rong >= 0 else 'bán'} ròng {vn(abs(nn_rong) / 1e9, 1)} tỷ đồng ở nhóm VN100.")
    nav = quy.get("nav") or []
    dong_quy = ""
    if nav and len(nav) > 1:
        dong_quy = (f"\n## Quỹ mô phỏng KCN30\n\nNAV mô phỏng đạt **{vn(nav[-1])} đồng/đơn vị**, "
                    f"{dau((nav[-1] / nav[-2] - 1) * 100)}% trong phiên, {dau(quy.get('tu_dau'), 1)}% từ ngày khởi đầu. "
                    f"[Xem chi tiết quỹ]({{{{ '/quy-mo-phong/' | relative_url }}}}).\n")
    noi_dung = f"""---
title: "{tieu_de}"
description: "{mo_ta}"
chu_de: Bản tin
hinh: sao
phut_doc: 2
image: /assets/img/og-ban-tin.png
tu_dong: true
---

Kết thúc phiên giao dịch ngày {ngay_vn}, **VN-Index {xu_huong} {vn(abs(dv))} điểm ({dau(pv)}%)**, đóng cửa ở mức **{vn(v)} điểm**.

## Các chỉ số chính

| Chỉ số | Đóng cửa | Thay đổi (điểm) | Thay đổi (%) |
|---|---:|---:|---:|
{chr(10).join(dong_chi_so)}

## Độ rộng và thanh khoản nhóm VN100

- **{tang} mã tăng** ({tran} mã tăng trần), **{dung} mã đứng giá**, **{giam} mã giảm** ({san} mã giảm sàn).
- Tổng giá trị giao dịch khớp lệnh của nhóm VN100: **{vn(gtgd / 1e9, 0)} tỷ đồng**.
- Giao dịch sôi động nhất: {ds_ma(top_gt, lambda x: f"**{x['ma']}** ({vn((x.get('gtgd') or 0) / 1e9, 0)} tỷ)")}.

## Cổ phiếu nổi bật

- **Tăng mạnh nhất:** {ds_ma(top_tang, lambda x: f"{x['ma']} ({dau(x['thay_doi'])}%)")}.
- **Giảm mạnh nhất:** {ds_ma(top_giam, lambda x: f"{x['ma']} ({dau(x['thay_doi'])}%)")}.

## Khối ngoại

Khối ngoại **{'mua' if nn_rong >= 0 else 'bán'} ròng {vn(abs(nn_rong) / 1e9, 1)} tỷ đồng** ở nhóm VN100.

- **Mua ròng nhiều nhất:** {ds_ma(nn_mua, lambda t: f"{t[0]['ma']} ({vn(t[1] / 1e9, 1)} tỷ)")}.
- **Bán ròng nhiều nhất:** {ds_ma(nn_ban, lambda t: f"{t[0]['ma']} ({vn(abs(t[1]) / 1e9, 1)} tỷ)")}.

*Số liệu khối ngoại lấy từ bảng giá sau khi đóng cửa, có thể bao gồm các giao dịch thỏa thuận lớn nên có thể chênh so với số khớp lệnh.*

## Quỹ ETF

Ba quỹ ETF có thanh khoản bình quân cao nhất: {ds_ma(etf_top, lambda q: f"**{q['ma']}** ({vn(q['gia'], 0)} đ, {dau(q['loi_nhuan'].get('1d'))}%)")}. [So sánh tất cả ETF]({{{{ '/etf/' | relative_url }}}}).
{dong_quy}
---

*Bản tin được hệ thống tự động tổng hợp lúc {bay_gio.strftime("%H:%M")} từ bảng giá công khai của Vietcap (VCI). Số liệu có thể chậm hoặc sai sót, chỉ mang tính tham khảo, không phải khuyến nghị đầu tư. Xem số liệu chi tiết tại [trang Thị trường]({{{{ '/thi-truong/' | relative_url }}}}).*
"""
    BAN_TIN.mkdir(parents=True, exist_ok=True)
    path = BAN_TIN / f"{hom_nay}-ban-tin-thi-truong-{bay_gio.strftime('%d-%m-%Y')}.md"
    path.write_text(noi_dung, encoding="utf-8")
    log(f"Đã viết bản tin: {path.name}")


def main():
    if "--trong-phien" in sys.argv:
        trong_phien()
    else:
        chi_so = cap_nhat_chi_so()
        cap_nhat_etf()
        cap_nhat_vn30_va_quy(chi_so)
        ghi_danh_muc_ma()
        cap_nhat_ro_etf()
        cap_nhat_quy_nam_giu()
        cap_nhat_trong_ngay(chi_so)
        viet_ban_tin()
    if DA_GHI:
        # file nhỏ để trang web đang mở biết có dữ liệu mới mà tự tải lại
        bay_gio = datetime.now(timezone(timedelta(hours=7)))
        ghi_json(OUT / "phien.json", {"luc": bay_gio.strftime("%Y-%m-%d %H:%M")})
    log("Xong.")


if __name__ == "__main__":
    main()
