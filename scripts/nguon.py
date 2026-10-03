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
    top, so_cp = [], {}
    for _, row in d.iterrows():
        m = _ma_vn(row["Ticker"])
        if m and str(row["Asset Class"]).strip() == "Stock":
            top.append((m, float(str(row["% of Net Assets"]).replace("%", "").replace(",", ""))))
            so_cp[m] = float(str(row["Shares"]).replace(",", ""))
    time.sleep(NGHI)
    return {"ma": "VNM", "ten": "VanEck Vietnam ETF (VNM, Mỹ)", "loai": "ETF_NN", "ngay": ngay, "top": top, "so_cp": so_cp,
            "nguon": "https://www.vaneck.com/us/en/investments/vietnam-etf-vnm/holdings/",
            "tep_nguon": res.url}


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
    top, so_cp = [], {}
    for _, row in df.iterrows():
        m = _ma_vn(row["Ticker"])
        if m:
            top.append((m, float(row["% of Net Assets"])))
            so_cp[m] = float(str(row["Shares Held"]).replace(",", ""))
    time.sleep(NGHI)
    return {"ma": "VNAM", "ten": "Global X MSCI Vietnam ETF (VNAM, Mỹ)", "loai": "ETF_NN", "ngay": ngay, "top": top, "so_cp": so_cp,
            "nguon": "https://www.globalxetfs.com/funds/vnam/", "tep_nguon": link.group(0)}


def quy_kraneshares_kpho():
    """KraneShares Dragon Capital Vietnam ETF (KPHO, Mỹ): file CSV danh mục hằng ngày trên kraneshares.com."""
    page = _phien.get("https://kraneshares.com/etf/kpho/", headers=H_WEB, timeout=40).text
    link = re.search(r"https://kraneshares\.com/csv/\d{2}_\d{2}_\d{4}_kpho_holdings\.csv", page)
    if not link:
        raise RuntimeError("không thấy link danh mục KPHO")
    res = _phien.get(link.group(0), headers=H_WEB, timeout=40)
    res.raise_for_status()
    dong = res.text.splitlines()
    ngay = re.search(r"As of (\d{4}-\d{2}-\d{2})", dong[0])
    df = pd.read_csv(io.StringIO(chr(10).join(dong[1:])))
    top, etf_pct, so_cp = [], 0.0, {}
    for _, row in df.iterrows():
        t = str(row["Ticker"]).strip()
        pc = float(row["% of Net Assets"])
        if re.fullmatch(r"[A-Z0-9]{3} VN", t) or re.fullmatch(r"[A-Z0-9]{3,4}", t):
            top.append((t.split()[0], pc))
            so_cp[t.split()[0]] = float(str(row["Shares Held"]).replace(",", ""))
        elif t.endswith(" VN"):  # chứng chỉ quỹ ETF nội (vd FUEVFVND), không phải cổ phiếu
            etf_pct += pc
    if not ngay or len(top) < 10:
        raise RuntimeError(f"danh mục KPHO bất thường ({len(top)} mã)")
    time.sleep(NGHI)
    them = {"loai_quy": "ETF Mỹ do Dragon Capital chọn rổ, bám chỉ số tăng trưởng"}
    if etf_pct:
        them["loai_quy"] += f"; {etf_pct:.2f}".replace(".", ",") + "% tài sản nằm trong chứng chỉ quỹ DCVFMVN Diamond ETF (không tính vào bảng cổ phiếu)"
    return {"ma": "KPHO", "ten": "KraneShares Dragon Capital Vietnam ETF (KPHO, Mỹ)", "loai": "ETF_NN", "ngay": ngay.group(1), "top": top, "so_cp": so_cp,
            "them": them, "nguon": "https://kraneshares.com/etf/kpho/", "tep_nguon": link.group(0)}


TEN_VEIL = {"vingroup": "VIC", "vinhomes": "VHM", "mobile world": "MWG", "bidv": "BID", "vietcombank": "VCB", "vp bank": "VPB",
            "vpbank": "VPB", "techcombank": "TCB", "vietinbank": "CTG", "hoa phat group": "HPG", "hoa phat": "HPG", "asia com. bank": "ACB",
            "acb": "ACB", "fpt corp": "FPT", "fpt": "FPT", "masan group": "MSN", "mb bank": "MBB", "mbbank": "MBB", "ssi securities": "SSI",
            "vinamilk": "VNM", "stb": "STB", "sacombank": "STB", "hdbank": "HDB", "tpbank": "TPB", "vietjet": "VJC", "vix securities": "VIX"}


def quy_veil():
    """Vietnam Enterprise Investments (VEIL, London): top 10 trong factsheet PDF hằng tháng của Dragon Capital."""
    from pypdf import PdfReader
    page = _phien.get("https://www.veil.uk/the-fund/", headers=H_WEB, timeout=40).text
    ds = sorted(set(re.findall(r"https://[^\"' ]*VEIL_Factsheet_(\d{6})\.pdf", page)))
    if not ds:
        raise RuntimeError("không thấy factsheet VEIL")
    url = re.search(r"https://[^\"' ]*VEIL_Factsheet_" + ds[-1] + r"\.pdf", page).group(0)
    pdf = _phien.get(url, headers=H_WEB, timeout=60)
    pdf.raise_for_status()
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf.content)).pages)
    mo = re.search(r"Top Ten Holdings(.*?)(?:T \+84|https://www\.veil\.uk|\Z)", txt, flags=re.S)
    top = []
    for dong in (mo.group(1).splitlines() if mo else []):
        m = re.match(r"(.+?)\s+(?:Real Estate|Consumer \w+|Financials[^\d]*|Materials|Industrials|Technology|Information Technology|Energy|Utilities|Health Care|Communication[^\d]*)\s+(\d+\.\d)\s+\$", dong.strip())
        if m:
            ten = m.group(1).strip().lower()
            ma = TEN_VEIL.get(ten)
            if not ma:
                raise RuntimeError(f"VEIL: chưa biết mã của '{m.group(1)}'")
            top.append((ma, float(m.group(2))))
    ngay = re.search(r"(?:Data as of|as of)\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", txt)
    if len(top) < 8 or not ngay:
        raise RuntimeError(f"factsheet VEIL bất thường ({len(top)} mã)")
    tna = re.search(r"Total Net Assets\s+US\$\s*([\d\.]+)bn", txt)
    cl = re.search(r"Premium / Discount\s+(-?[\d\.]+)%", txt) or re.search(r"(-?[\d\.]+)%\s*\(GBP\)", txt)
    loai = "Quỹ đóng niêm yết London (FTSE 250) của Dragon Capital"
    if tna:
        loai += f"; tổng tài sản ròng {tna.group(1).replace('.', ',')} tỷ USD"
    if cl:
        loai += f"; giá cổ phiếu {cl.group(1).replace('.', ',').replace('-', 'chiết khấu ')}% so với NAV" if cl.group(1).startswith("-") else ""
    time.sleep(NGHI)
    return {"ma": "VEIL", "ten": "Vietnam Enterprise Investments (VEIL, Luân Đôn)", "loai": "QUY_NN",
            "ngay": pd.to_datetime(ngay.group(1), format="%d %B %Y").strftime("%Y-%m-%d"), "top": top,
            "them": {"loai_quy": loai, "chi_top": 10}, "nguon": url}


TEN_STOXX = [("VINGROUP", "VIC"), ("VINHOMES", "VHM"), ("SAIGON TREASURE", "STB"), ("SAIGON THUONG TIN", "STB"), ("HOA PHAT", "HPG"),
             ("SAI GON - HANOI", "SHB"), ("FPT", "FPT"), ("SSI", "SSI"), ("VIX", "VIX"), ("MASAN GROUP", "MSN"),
             ("VIETJET", "VJC"), ("GELEX", "GEX"), ("VIETNAM DAIRY", "VNM"), ("VPS", "VCK"), ("VPBANK", "VPB"), ("TECHCOM", "TCB")]


def stoxx_vietnam():
    """STOXX Vietnam Total Market Liquid (STCVNLL): mức chỉ số và top 10 thành phần (không có tỷ trọng) từ stoxx.com."""
    html = _phien.get("https://stoxx.com/index/stcvnll/", headers=H_WEB, timeout=40).text
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " | ", txt)
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"(\| ?)+", "| ", txt)
    gia_tri = re.search(r"Last Value \| ([\d,\.]+) \|", txt)
    top10 = re.search(r"Top 10 Components(.*?)Zoom", txt)
    if not gia_tri or not top10:
        raise RuntimeError("không đọc được trang STOXX")
    ten = [t.strip() for t in top10.group(1).split("|") if t.strip() and t.strip() != "VN"]
    top = []
    for t in ten:
        ma = next((m for k, m in TEN_STOXX if k in t.upper()), None)
        top.append({"ten": t, "ma": ma})
    time.sleep(NGHI)
    return {"gia_tri": float(gia_tri.group(1).replace(",", "")), "top": top, "nguon": "https://stoxx.com/index/stcvnll/"}


def dws_ro_swap():
    """Rổ cổ phiếu thế chấp của Xtrackers Vietnam Swap (quỹ swap nên danh mục thật là cổ phiếu ngoài Việt Nam)."""
    url = "https://etf.dws.com/api/pdp/en-lu/etf/LU0322252924-vietnam-swap-ucits-etf-1c/holdings"
    d = _goi("GET", url, {"User-Agent": UA, "Accept": "application/json", "client-id": "passive-frontend",
                          "Referer": "https://etf.dws.com/en-lu/LU0322252924-vietnam-swap-ucits-etf-1c/"})
    rows = (d.get("tables") or [{}])[0].get("values") or []
    ds = []
    for r_ in rows:
        try:
            ds.append({"ten": r_["column_0"]["value"], "pct": round(float(r_["column_1"]["sortValue"]), 3), "nuoc": r_["column_3"]["value"]})
        except Exception:
            continue
    ds.sort(key=lambda x: -x["pct"])
    return {"so_ma": len(ds), "top": ds[:5], "tong_my_pct": round(sum(x["pct"] for x in ds if x["nuoc"] == "United States"), 1)}


def quy_thien_hoang():
    """Thiên Hoằng Việt Nam (天弘越南市场股票发起 QDII, mã 008763): quỹ mở của Trung Quốc đầu tư riêng vào Việt Nam.
    Danh mục top 20 theo quý và quy mô quỹ lấy từ Thiên Thiên Cơ Kim (Eastmoney)."""
    H = {"User-Agent": UA, "Referer": "https://fundf10.eastmoney.com/", "Accept-Language": "zh-CN,zh;q=0.9"}
    res = _phien.get("https://fundf10.eastmoney.com/FundArchivesDatas.aspx",
                     params={"type": "jjcc", "code": "008763", "topline": "20", "year": "", "month": "", "rt": "0.1"}, headers=H, timeout=40)
    res.raise_for_status()
    box = re.search(r"<div class='box'>(.*?)</table>", res.text, flags=re.S)
    if not box:
        raise RuntimeError("không đọc được danh mục Thiên Hoằng")
    box = box.group(1)
    ngay = re.search(r"截止至：?\s*<font[^>]*>(\d{4}-\d{2}-\d{2})", box)
    top = []
    for tr in re.findall(r"<tr>(.*?)</tr>", box, flags=re.S)[1:]:
        c = [re.sub(r"<[^>]+>", "", x).replace("&nbsp;", "").strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        pct_i = next((i for i, x in enumerate(c) if x.endswith("%")), None)
        if pct_i is None or len(c) < pct_i + 3 or not c[1].startswith("VN"):
            continue
        ma = c[1][8:-1]  # VN000000HPG4 -> HPG
        if re.fullmatch(r"[A-Z0-9]{3,4}", ma):
            top.append((ma, float(c[pct_i].rstrip("%")), float(c[pct_i + 1].replace(",", "")) * 1e4, float(c[pct_i + 2].replace(",", "")) * 1e4))
    if len(top) < 10 or not ngay:
        raise RuntimeError(f"danh mục Thiên Hoằng bất thường ({len(top)} mã)")
    pz = _phien.get("https://fund.eastmoney.com/pingzhongdata/008763.js", headers=H, timeout=40).text
    quy_mo = re.search(r"Data_fluctuationScale\s*=\s*(\{.*?\});", pz, flags=re.S)
    phan_bo = re.search(r"Data_assetAllocation\s*=\s*(\{.*?\});", pz, flags=re.S)
    them = {"chi_top": 20, "tien_te": "NDT", "loai_quy": "Quỹ mở QDII (Trung Quốc), bám VN30 90%", "ma_quy": "008763 / 008764 / 022524"}
    try:
        q = json.loads(quy_mo.group(1))
        them["quy_mo_ty_ndt"] = [{"ngay": d, "gia_tri": s["y"]} for d, s in zip(q["categories"], q["series"])]
        a = json.loads(phan_bo.group(1))
        them["co_phieu_pct"] = a["series"][0]["data"][-1]
        them["tien_mat_pct"] = a["series"][2]["data"][-1]
    except Exception:
        pass
    time.sleep(NGHI)
    return {"ma": "Tianhong", "ten": "Thiên Hoằng Việt Nam (天弘越南 QDII, Trung Quốc)", "loai": "QUY_NN", "ngay": ngay.group(1),
            "top": [(m, p) for m, p, _, _ in top], "so_cp": {m: sl for m, _, sl, _ in top}, "chi_tiet": [{"ma": m, "pct": p, "so_cp": sl, "gia_tri_ndt": gt} for m, p, sl, gt in top],
            "them": them, "nguon": "https://fundf10.eastmoney.com/ccmx_008763.html"}


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
    top, so_cp = [], {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        if len(c) == 5:
            m = _ma_vn(c[0])
            if m:
                top.append((m, float(c[4].replace(",", ""))))
                so_cp[m] = float(c[2].replace(",", ""))
    if len(top) < 20:
        raise RuntimeError(f"danh mục Fubon quá ít mã ({len(top)})")
    time.sleep(NGHI)
    return {"ma": "Fubon", "ten": "Fubon FTSE Vietnam ETF (00885, Đài Loan)", "loai": "ETF_NN",
            "ngay": ngay.group(1).replace("/", "-"), "top": top, "so_cp": so_cp,
            "nguon": "https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId=00885&lan=EN"}


def _quy_vanguard(ma, ten, url):
    """Quỹ ETF Vanguard bám chỉ số FTSE (GEIS): danh mục đầy đủ công bố hằng tháng. Chỉ giữ cổ phiếu Việt Nam (ISIN bắt đầu bằng VN)."""
    H = {"User-Agent": UA, "Accept": "application/json", "Referer": "https://investor.vanguard.com/"}
    vn, so_cp, ngay, bat_dau, tong = [], {}, None, 1, 0
    while True:
        d = _goi("GET", f"https://investor.vanguard.com/vmf/api/{ma}/portfolio-holding/stock.json", H,
                 params={"start": bat_dau, "count": 500})
        ngay = (d.get("asOfDate") or "")[:10] or ngay
        tong = int(d.get("size") or 0)
        ds = d.get("fund", {}).get("entity") if "fund" in d else d.get("entity")
        for e in ds or []:
            if str(e.get("isin", "")).startswith("VN"):
                m = _ma_vn(str(e.get("ticker", "")).strip() + " VN")
                if m:
                    vn.append((m, float(e.get("percentWeight") or 0)))
                    so_cp[m] = float(e.get("sharesHeld") or 0)
        bat_dau += 500
        if not ds or bat_dau > tong:
            break
    return {"ma": ma, "ten": ten, "loai": "ETF_NN", "ngay": ngay, "top": vn, "so_cp": so_cp, "nguon": url, "tong_ma_quy": tong}


def quy_vanguard_vwo():
    return _quy_vanguard("VWO", "Vanguard FTSE Emerging Markets ETF (VWO, Mỹ) - bám FTSE Emerging, thuộc GEIS",
                         "https://investor.vanguard.com/investment-products/etfs/profile/vwo")


def quy_vanguard_vt():
    return _quy_vanguard("VT", "Vanguard Total World Stock ETF (VT, Mỹ) - bám FTSE Global All Cap, thuộc GEIS",
                         "https://investor.vanguard.com/investment-products/etfs/profile/vt")


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
            "top": top, "nguon": f"{FMARKET}/{q['id']}",
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
