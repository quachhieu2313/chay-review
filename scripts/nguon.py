# -*- coding: utf-8 -*-
"""
Lấy dữ liệu thị trường trực tiếp từ các API công khai mà website Vietcap (VCI) và KB Securities (KBS)
dùng cho bảng giá của họ. Chỉ cần `requests` + `pandas`, không phụ thuộc thư viện bên thứ ba khác.

Đơn vị: giá cổ phiếu/ETF tính bằng đồng, chỉ số tính bằng điểm, khối lượng tính bằng cổ phiếu.
"""
import json
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


def lich_su(ma, so_phien=2000):
    """Nến ngày gần nhất: DataFrame [time, open, high, low, close, volume]; None nếu không có dữ liệu."""
    body = {"timeFrame": "ONE_DAY", "symbols": [ma], "to": int(time.time()) + 86400, "countBack": so_phien}
    data = _goi("POST", f"{VCI}/chart/OHLCChart/gap-chart", H_VCI, data=json.dumps(body))
    if not data or not data[0].get("t"):
        return None
    x = data[0]
    df = pd.DataFrame({
        "time": pd.to_datetime([int(t) for t in x["t"]], unit="s").strftime("%Y-%m-%d"),
        "open": x["o"], "high": x["h"], "low": x["l"], "close": x["c"], "volume": x["v"],
    })
    return df.dropna(subset=["close"]).drop_duplicates("time", keep="last").reset_index(drop=True)


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
            })
    return out


def danh_sach_etf():
    """[(mã, tên quỹ)] các ETF đang niêm yết."""
    data = _goi("GET", f"{VCI}/price/symbols/getAll", H_VCI)
    return sorted((x["symbol"], x.get("organName") or x["symbol"]) for x in data if x.get("type") == "ETF")


def ro_chi_so(nhom="VN30"):
    data = _goi("GET", f"{VCI}/price/symbols/getByGroup", H_VCI, params={"group": nhom})
    return [x["symbol"] for x in data]


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
