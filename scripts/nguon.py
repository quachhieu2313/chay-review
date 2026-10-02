# -*- coding: utf-8 -*-
"""
Lấy dữ liệu thị trường trực tiếp từ các API công khai mà website Vietcap (VCI) và KB Securities (KBS)
dùng cho bảng giá của họ. Chỉ cần `requests` + `pandas`, không phụ thuộc thư viện bên thứ ba khác.

Đơn vị: giá cổ phiếu/ETF tính bằng đồng, chỉ số tính bằng điểm, khối lượng tính bằng cổ phiếu.
"""
import io
import json
import re
import time

import pandas as pd
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
VCI = "https://trading.vietcap.com.vn/api"
VCI_IQ = "https://iq.vietcap.com.vn/api/iq-insight-service"
KBS = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"
H_VCI = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn",
}
H_KBS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
NGHI = 0.4  # giây nghỉ giữa các lần gọi, tránh dồn dập lên máy chủ nguồn

_phien = requests.Session()


def _goi(method, url, headers, lan=3, **kw):
    for i in range(lan):
        try:
            res = _phien.request(method, url, headers=headers, timeout=30, **kw)
            res.raise_for_status()
            time.sleep(NGHI)
            return res.json()
        except Exception as e:
            if i == lan - 1:
                raise
            print(f"  ! {url.split('/')[-1][:40]} lỗi lần {i + 1}: {str(e)[:100]}", flush=True)
            time.sleep(2 * (i + 1))


# Vietcap dùng tên riêng cho chỉ số sàn HNX và UPCoM
MA_VCI = {"HNXINDEX": "HNXIndex", "UPCOMINDEX": "HNXUpcomIndex"}


def lich_su(ma, so_phien=2000):
    """Nến ngày gần nhất: DataFrame [time, open, high, low, close, volume]; None nếu không có dữ liệu."""
    body = {"timeFrame": "ONE_DAY", "symbols": [MA_VCI.get(ma, ma)], "to": int(time.time()) + 86400, "countBack": so_phien}
    data = _goi("POST", f"{VCI}/chart/OHLCChart/gap-chart", H_VCI, data=json.dumps(body))
    if not data or not data[0].get("t"):
        return None
    x = data[0]
    df = pd.DataFrame({
        "time": pd.to_datetime([int(t) for t in x["t"]], unit="s").strftime("%Y-%m-%d"),
        "open": x["o"], "high": x["h"], "low": x["l"], "close": x["c"], "volume": x["v"],
    })
    return df.dropna(subset=["close"]).drop_duplicates("time", keep="last").reset_index(drop=True)


def lich_su_phut(ma, so_nen=300):
    """Nến 1 phút gần nhất: list (giờ 'HH:MM', ngày 'YYYY-MM-DD', giá đóng). Giờ theo giờ Việt Nam."""
    body = {"timeFrame": "ONE_MINUTE", "symbols": [MA_VCI.get(ma, ma)], "to": int(time.time()) + 60, "countBack": so_nen}
    data = _goi("POST", f"{VCI}/chart/OHLCChart/gap-chart", H_VCI, data=json.dumps(body))
    if not data or not data[0].get("t"):
        return []
    x = data[0]
    tg = pd.to_datetime([int(t) for t in x["t"]], unit="s") + pd.Timedelta(hours=7)
    return [(t.strftime("%H:%M"), t.strftime("%Y-%m-%d"), c) for t, c in zip(tg, x["c"])]


def bang_gia(ds_ma):
    """Bảng giá hiện tại, mỗi mã một dict với các khoá phẳng (listing_*, match_*)."""
    out = []
    for i in range(0, len(ds_ma), 50):
        data = _goi("POST", f"{VCI}/price/symbols/getList", H_VCI, data=json.dumps({"symbols": ds_ma[i:i + 50]}))
        for x in data or []:
            li, mp = x.get("listingInfo") or {}, x.get("matchPrice") or {}
            out.append({
                "listing_symbol": li.get("symbol"),
                "listing_trading_date": li.get("tradingDate"),
                "listing_ceiling": li.get("ceiling"),
                "listing_floor": li.get("floor"),
                "listing_ref_price": li.get("refPrice"),
                "listing_listed_share": li.get("listedShare"),
                "match_match_price": mp.get("matchPrice"),
                "match_reference_price": mp.get("referencePrice"),
                "match_accumulated_volume": mp.get("accumulatedVolume"),
                "match_open_price": mp.get("openPrice"),
                "match_highest": mp.get("highest"),
                "match_lowest": mp.get("lowest"),
                "match_accumulated_value": mp.get("accumulatedValue"),  # triệu đồng
                "match_foreign_buy_value": mp.get("foreignBuyValue"),   # đồng
                "match_foreign_sell_value": mp.get("foreignSellValue"),
            })
    return out


def danh_sach_etf():
    """[(mã, tên quỹ)] các ETF đang niêm yết."""
    data = _goi("GET", f"{VCI}/price/symbols/getAll", H_VCI)
    return sorted((x["symbol"], x.get("organName") or x["symbol"]) for x in data if x.get("type") == "ETF")


def ro_chi_so(nhom="VN30"):
    data = _goi("GET", f"{VCI}/price/symbols/getByGroup", H_VCI, params={"group": nhom})
    return [x["symbol"] for x in data]


# mã nhóm của KBS cho các rổ chỉ số mà VCI không trả thành phần
MA_KBS = {"VNDIAMOND": "DIAMOND", "VNFINLEAD": "FINLEAD", "VNFINSELECT": "FINSELECT", "VNX50": "X50"}


def thanh_phan_ro(ma):
    """Danh sách mã thuộc rổ chỉ số: VN30/VN100 từ VCI, các rổ còn lại từ KBS. Rỗng nếu không có."""
    if ma in MA_KBS:
        d = _goi("GET", f"{KBS}/index/{MA_KBS[ma]}/stocks", H_KBS)
        return list((d or {}).get("data") or [])
    return ro_chi_so(ma)


# ---------------------------------------------------------------- quỹ ETF nước ngoài (danh mục đầy đủ, chính thức)
H_WEB = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def _ma_vn(t):
    """'VHM VN' -> 'VHM'; trả None nếu không phải mã cổ phiếu Việt Nam (tiền mặt, quyền mua...)."""
    m = re.fullmatch(r"([A-Z0-9]{3,8}) VN", str(t).strip())
    return m.group(1) if m and not re.search(r"\d.*[A-Z]$", m.group(1)) else None


def quy_vaneck_vnm():
    """VanEck Vietnam ETF (VNM, Mỹ): file danh mục hằng ngày trên vaneck.com."""
    ss = requests.Session()
    res = ss.get("https://www.vaneck.com/us/en/etf/equity/vnm/holdings/download/xlsx/", headers=H_WEB, timeout=40)
    res.raise_for_status()
    df = pd.read_excel(io.BytesIO(res.content), header=None, engine="openpyxl")
    m_ngay = re.search(r"(\d{2}/\d{2}/\d{4})", " ".join(str(x) for x in df.iloc[0].tolist()))
    if not m_ngay:
        raise RuntimeError("không đọc được ngày danh mục VanEck")
    ngay = pd.to_datetime(m_ngay.group(1), format="%m/%d/%Y").strftime("%Y-%m-%d")
    hdr = df.index[df[1].astype(str).str.strip() == "Ticker"][0]
    d = df.iloc[hdr + 1:].copy()
    d.columns = [str(c) for c in df.iloc[hdr]]
    top = []
    for _, row in d.iterrows():
        m = _ma_vn(row["Ticker"])
        if m and str(row["Asset Class"]).strip() == "Stock":
            top.append((m, float(str(row["% of Net Assets"]).replace("%", "").replace(",", ""))))
    time.sleep(NGHI)
    return {"ma": "VNM", "ten": "VanEck Vietnam ETF (VNM, Mỹ)", "loai": "ETF_NN", "ngay": ngay, "top": top,
            "nguon": "https://www.vaneck.com/us/en/investments/vietnam-etf-vnm/holdings/"}


def quy_globalx_vnam():
    """Global X MSCI Vietnam ETF (VNAM, Mỹ): file CSV danh mục hằng ngày trên globalxetfs.com."""
    page = _phien.get("https://www.globalxetfs.com/funds/vnam/", headers=H_WEB, timeout=40).text
    link = re.search(r"https://assets\.globalxetfs\.com/funds/holdings/vnam_full-holdings_(\d{8})\.csv", page)
    if not link:
        raise RuntimeError("không thấy link danh mục VNAM")
    res = _phien.get(link.group(0), headers=H_WEB, timeout=40)
    res.raise_for_status()
    ngay = pd.to_datetime(link.group(1), format="%Y%m%d").strftime("%Y-%m-%d")
    df = pd.read_csv(io.StringIO(res.text), skiprows=2)
    top = []
    for _, row in df.iterrows():
        m = _ma_vn(row["Ticker"])
        if m:
            top.append((m, float(row["% of Net Assets"])))
    time.sleep(NGHI)
    return {"ma": "VNAM", "ten": "Global X MSCI Vietnam ETF (VNAM, Mỹ)", "loai": "ETF_NN", "ngay": ngay, "top": top,
            "nguon": "https://www.globalxetfs.com/funds/vnam/"}


def quy_fubon_00885():
    """Fubon FTSE Vietnam ETF (00885, Đài Loan): bảng danh mục hằng ngày trên website Fubon Asset Management."""
    url = "https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId=00885&lan=EN"
    html = _phien.get(url, headers=H_WEB, timeout=40).text
    ma_quy = re.search(r'hidStkId"[^>]*value="([^"]*)"', html)
    if not ma_quy or ma_quy.group(1) != "00885":
        raise RuntimeError("trang Fubon không trả về quỹ 00885")  # tránh nhầm sang danh mục của quỹ khác
    ngay = re.search(r"Date:\s*(\d{4}/\d{2}/\d{2})", html)
    if not ngay:
        raise RuntimeError("không đọc được ngày danh mục Fubon")
    top = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        if len(c) == 5:
            m = _ma_vn(c[0])
            if m:
                top.append((m, float(c[4].replace(",", ""))))
    if len(top) < 20:
        raise RuntimeError(f"danh mục Fubon quá ít mã ({len(top)})")
    time.sleep(NGHI)
    return {"ma": "00885", "ten": "Fubon FTSE Vietnam ETF (00885, Đài Loan)", "loai": "ETF_NN",
            "ngay": ngay.group(1).replace("/", "-"), "top": top,
            "nguon": "https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId=00885&lan=EN"}


FMARKET = "https://api.fmarket.vn/res/products"
H_FM = {"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json",
        "Referer": "https://fmarket.vn/", "Origin": "https://fmarket.vn"}


def quy_mo_nam_giu():
    """Danh mục top 10 của các quỹ mở cổ phiếu/cân bằng (Fmarket): list dict {ma, ten, loai, ngay, top:[(mã, %NAV)]}."""
    body = {"types": ["NEW_FUND", "TRADING_FUND"], "issuerIds": [], "sortOrder": "DESC", "sortField": "navTo6Months",
            "page": 1, "pageSize": 200, "isIpo": False, "fundAssetTypes": [], "bondRemainPeriods": [],
            "searchField": "", "isBuyByReward": False, "thirdAppIds": []}
    ds = _goi("POST", f"{FMARKET}/filter", H_FM, data=json.dumps(body))["data"]["rows"]
    out = []
    for q in ds:
        loai = (q.get("dataFundAssetType") or {}).get("code")
        if loai not in ("STOCK", "BALANCED"):
            continue
        d = _goi("GET", f"{FMARKET}/{q['id']}", H_FM)["data"]
        th = d.get("productTopHoldingList") or []
        top = [(x["stockCode"], float(x["netAssetPercent"])) for x in th if x.get("stockCode") and x.get("netAssetPercent") is not None]
        if not top:
            continue
        ngay = max((x.get("updateAt") or 0) for x in th)
        out.append({
            "ma": q["shortName"], "ten": q.get("name") or q["shortName"], "loai": loai,
            "ngay": pd.to_datetime(ngay, unit="ms").strftime("%Y-%m-%d") if ngay else None,
            "top": top,
        })
    return out


def thong_tin_cong_ty():
    """{mã: (tên công ty, ngành ICB cấp 2)}"""
    data = _goi("GET", f"{VCI_IQ}/v2/company/search-bar", H_VCI, params={"language": 1})
    out = {}
    for x in data.get("data") or []:
        lv2 = x.get("icbLv2") or {}
        out[x.get("code")] = (x.get("name") or x.get("code"), lv2.get("name") or "Khác")
    return out


# tên tiếng Anh của chỉ tiêu ở KBS -> khoá dùng trên web
_KBS_CHI_TIEU = {
    "Trailing EPS": "eps",
    "Book value per share (BVPS)": "bvps",
    "ROE Trailling": "roe",
    "ROA Trailling": "roa",
    "Net profit margin": "bien_ln_rong",
    "Gross profit margin": "bien_ln_gop",
    "Beta": "beta",
}


def chi_so_co_ban(ma):
    """Chỉ số tài chính quý gần nhất từ KBS; None nếu không lấy được."""
    data = _goi("GET", f"{KBS}/stock/finance-info/{ma}", H_KBS,
                params={"page": 1, "pageSize": 4, "type": "CSTC", "unit": 1000, "termtype": 2, "languageid": 1})
    head = (data or {}).get("Head") or []
    if not head:
        return None
    # cột Value1 ứng với kỳ có ID 1 (kỳ mới nhất)
    h1 = next((h for h in head if h.get("ID") == 1), head[0])
    out = {"ky": f"{h1.get('YearPeriod')} {h1.get('TermCode')}"}
    for nhom in (data.get("Content") or {}).values():
        for row in nhom:
            k = _KBS_CHI_TIEU.get((row.get("NameEn") or "").strip())
            if k and k not in out:
                v = row.get("Value1")
                out[k] = None if v is None else round(float(v), 2)
        for row in nhom:
            # nợ vay / vốn chủ sở hữu: KBS ghi bằng tiếng Việt rõ hơn tiếng Anh
            if "no_vay_vcsh" not in out and (row.get("Name") or "").strip() == "Tỷ số Nợ vay trên Vốn chủ sở hữu":
                v = row.get("Value1")
                out["no_vay_vcsh"] = None if v is None else round(float(v), 2)
    return out
