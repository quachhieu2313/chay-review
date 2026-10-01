# -*- coding: utf-8 -*-
"""
Cập nhật dữ liệu thị trường cho website Kim Chỉ Nam.

Lấy dữ liệu bằng vnstock (nguồn VCI) rồi ghi ra các file JSON trong assets/data/:
  chi_so.json        lịch sử các chỉ số (VN-Index, VN30, chỉ số tham chiếu của ETF...)
  co_phieu.json      bảng theo dõi cổ phiếu rổ VN30 (trang Thị trường)
  etf.json           danh sách ETF + hiệu suất (trang ETF)
  etf/<MÃ>.json      lịch sử giá từng ETF (trang chi tiết ETF)
  quy_mo_phong.json  quỹ mô phỏng KCN VN30 (trang Quỹ mô phỏng)

Hai chế độ:
  python scripts/cap_nhat_du_lieu.py               đầy đủ: tải lại toàn bộ lịch sử (~4 phút), chạy sau giờ đóng cửa
  python scripts/cap_nhat_du_lieu.py --trong-phien nhanh: chỉ lấy bảng giá hiện tại (~20 giây), chạy mỗi 10 phút trong phiên
GitHub Actions tự chạy cả hai (.github/workflows/cap-nhat-du-lieu.yml và cap-nhat-trong-phien.yml).
Mã nào lấy lỗi thì giữ dữ liệu cũ của mã đó, không làm hỏng cả web.
"""
import json
import math
import sys
import time
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from vnstock import Listing, Quote, Trading  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
(OUT / "etf").mkdir(parents=True, exist_ok=True)

START = "2020-01-01"
TODAY = date.today().isoformat()
PAUSE = 3.2  # giây giữa hai lần gọi, để không vượt giới hạn 20 lần/phút của vnstock bản miễn phí

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

PHI_MO_PHONG = 0.005  # phí quản lý giả định 0,5%/năm của quỹ mô phỏng
NAV_KHOI_DAU = 10000.0
NGAY_KHOI_DAU = "2021-01-04"


def log(*a):
    print(*a, flush=True)


def lich_su(ma):
    """Trả về DataFrame [time, close, volume] hoặc None nếu lỗi."""
    for lan in range(3):
        try:
            df = Quote(symbol=ma, source="VCI").history(start=START, end=TODAY, interval="1D")
            time.sleep(PAUSE)
            if df is None or df.empty:
                return None
            df = df[["time", "close", "volume"]].copy()
            df["time"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
            return df.dropna(subset=["close"]).drop_duplicates("time").reset_index(drop=True)
        except Exception as e:  # mạng chập chờn, bị giới hạn tần suất...
            log(f"  ! {ma} lỗi lần {lan + 1}: {str(e)[:120]}")
            time.sleep(PAUSE * (lan + 2))
    return None


def doc_json(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def ghi_json(path, data):
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


# ---------------------------------------------------------------- chỉ số
def cap_nhat_chi_so():
    cu = doc_json(OUT / "chi_so.json", {})
    out = {}
    for ma, ten in CHI_SO.items():
        log(f"Chỉ số {ma}")
        df = lich_su(ma)
        if df is None:
            if ma in cu:
                out[ma] = cu[ma]
            continue
        out[ma] = {
            "ten": ten,
            "d": df["time"].tolist(),
            "c": [r(x, 2) for x in df["close"]],
        }
    ghi_json(OUT / "chi_so.json", out)
    return out


# ---------------------------------------------------------------- ETF
def cap_nhat_etf():
    lst = Listing(source="VCI").symbols_by_exchange()
    time.sleep(PAUSE)
    etf = lst[lst["type"] == "ETF"][["symbol", "organ_name"]].drop_duplicates("symbol")
    cu = {e["ma"]: e for e in doc_json(OUT / "etf.json", {}).get("quy", [])}
    ds = []
    for ma, ten in sorted(etf.itertuples(index=False), key=lambda x: x[0]):
        log(f"ETF {ma}")
        ten_hoa = ten.upper()
        tc = next((v for k, v in THAM_CHIEU if k in ten_hoa), None)
        df = lich_su(ma)
        if df is None or len(df) < 2:
            if ma in cu:
                ds.append(cu[ma])
            continue
        d, c = df["time"].tolist(), [r(x * 1000, 0) for x in df["close"]]
        ghi_json(OUT / "etf" / f"{ma}.json", {"ma": ma, "d": d, "c": c})
        gtgd = (df["close"] * 1000 * df["volume"]).tail(20).mean()
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


# ---------------------------------------------------------------- VN30 + quỹ mô phỏng
def cap_nhat_vn30_va_quy(chi_so):
    lst = Listing(source="VCI")
    ro = list(lst.symbols_by_group("VN30"))
    time.sleep(PAUSE)
    ten = dict(lst.all_symbols()[["symbol", "organ_name"]].values)
    time.sleep(PAUSE)
    nganh_df = lst.symbols_by_industries()
    time.sleep(PAUSE)
    nganh = dict(nganh_df[nganh_df["icb_level"] == 2][["symbol", "icb_name"]].values)

    gia = {}
    kl = {}
    for ma in ro:
        log(f"Cổ phiếu {ma}")
        df = lich_su(ma)
        if df is None:
            continue
        gia[ma] = pd.Series((df["close"] * 1000).values, index=pd.to_datetime(df["time"]))
        kl[ma] = int(df["volume"].iloc[-1])

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
        })
    ngay_cuoi = max(s.index[-1] for s in gia.values()).strftime("%Y-%m-%d") if gia else None
    ghi_json(OUT / "co_phieu.json", {"cap_nhat": ngay_cuoi, "cap_nhat_luc": gio_vn(), "ro": "VN30", "co_phieu": co_phieu})

    # ----- quỹ mô phỏng: chia đều tỷ trọng các mã VN30 hiện tại, tái cân bằng đầu mỗi quý
    bang = pd.DataFrame(gia).sort_index()
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
    cs = doc_json(OUT / "chi_so.json", None)
    quy = doc_json(OUT / "quy_mo_phong.json", None)
    if not (etf and cp and cs and quy):
        log("Chưa có dữ liệu nền, hãy chạy chế độ đầy đủ trước.")
        return

    ds_ma = [x["ma"] for x in cp["co_phieu"]] + [x["ma"] for x in etf["quy"]]
    bang = Trading(source="VCI").price_board(ds_ma)
    bang.columns = ["_".join(c) if isinstance(c, tuple) else c for c in bang.columns]
    gia, ngay = {}, None
    for row in bang.to_dict("records"):
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
        if hom_nay_da_co:
            x["spark"][-1] = r(p, 0)
        else:
            x["spark"] = (x["spark"] + [r(p, 0)])[-20:]
    cp["cap_nhat"] = ngay
    log("co_phieu.json", "đổi" if luu(OUT / "co_phieu.json", cu, cp) else "không đổi")

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
    bat_dau = (date.fromisoformat(ngay) - timedelta(days=10)).isoformat()
    for ma in ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]:
        if ma not in cs:
            continue
        try:
            df = Quote(symbol=ma, source="VCI").history(start=bat_dau, end=ngay, interval="1D")
            time.sleep(PAUSE)
        except Exception as e:
            log(f"  ! {ma}: {str(e)[:120]}")
            continue
        if df is None or df.empty:
            continue
        cuoi = df.iloc[-1]
        if pd.to_datetime(cuoi["time"]).strftime("%Y-%m-%d") == ngay:
            dat_diem(cs[ma]["d"], cs[ma]["c"], ngay, r(float(cuoi["close"]), 2))
    if json.dumps(cs, sort_keys=True) != json.dumps(cu, sort_keys=True):
        ghi_json(OUT / "chi_so.json", cs)
        log("chi_so.json đổi")

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


def main():
    if "--trong-phien" in sys.argv:
        trong_phien()
    else:
        chi_so = cap_nhat_chi_so()
        cap_nhat_etf()
        cap_nhat_vn30_va_quy(chi_so)
    log("Xong.")


if __name__ == "__main__":
    main()
