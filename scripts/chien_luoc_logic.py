"""BẢN SAO logic thử nghiệm lô lẻ từ app DNSE (E:/Tool_FY/Code_Stock/thu_nghiem.py) - sửa một bên thì chép sang bên kia.
scripts/chien_luoc.py dùng file này để chạy mô phỏng trên GitHub và đăng rổ tháng + danh sách mã cho robot bỏ qua."""
"""
THỬ NGHIỆM 2 CHIẾN LƯỢC BẰNG LÔ LẺ (từ 28/11/2026) - TÁCH RIÊNG khỏi công thức gấp đôi của Robot DCA
=====================================================================================================
Logic THUẦN (không Qt, gọi mạng qua hàm truyền vào) để kiểm thử được. Tab thu_nghiem_tab.py chạy vòng quét.

Giai đoạn 1 = CHẠY THỬ: chỉ ghi LỆNH GIẤY (không đặt lệnh thật), khớp giả lập theo sổ lệnh lô lẻ thật lúc đó
(chỉ ăn đúng các mức giá + khối lượng đang chào). Sổ ghi riêng file thu_nghiem_state.json, không đụng tài khoản.

A. ETF E1VFVN30 ≤ iNAV  (mỗi tuần một khoản tiền)
   - Trong phiên lô lẻ, mỗi lượt quét: lấy iNAV (Dragon Capital) + sổ lệnh lô lẻ (SSI).
   - Giá trần mua = iNAV làm tròn XUỐNG bước 10 đ. Chỉ mua các mức giá chào bán ≤ giá trần.
   - Hạn chót: ngày giao dịch cuối tuần (thứ Sáu) từ 14:00 chấp nhận cao hơn iNAV tối đa `chenh_han_chot_pct` (mặc định 0,3%).
   - Tiền chưa tiêu hết chuyển sang tuần sau (cộng dồn tối đa thêm 1 tuần).
   - Đối chứng: "mua ngay đầu tuần" = giá chào bán lô lẻ tốt nhất ở lượt quét đầu tiên của tuần.
     So giá vốn A với giá đối chứng = lợi ích thật của việc chờ giá ≤ iNAV sau khi tính chênh lệch lô lẻ.

B. Rổ VN30 điểm tài chính cao nhất  (mỗi tháng một khoản tiền)
   - Đầu tháng: lấy điểm tài chính (Kim Chỉ Nam, assets/data/diem_tai_chinh.json, điểm = 50% E/P + 50% B/P),
     chỉ xét mã đang trong rổ VN30, bỏ mã có cảnh báo dữ liệu, chọn `so_ma` mã điểm cao nhất.
   - Mã đang giữ mà rớt khỏi top -> bán hết (giá chào mua lô lẻ). Tiền bán + tiền tháng chia đều cho các mã top.
   - Mua trong `so_ngay_mua` ngày giao dịch đầu tháng. Không trả giá lô lẻ cao hơn giá chào bán bảng chính quá `chenh_le_toi_da_pct`.
   - Đối chứng: mỗi đồng chi cho rổ cũng "mua" E1VFVN30 lô lẻ cùng lúc -> rổ có thắng được ETF không.

Phí/thuế lấy từ vn_market_rules (mặc định phí 0,15%/chiều, thuế bán 0,1%).
"""
import json
import math
import urllib.request
from datetime import datetime

class rules:  # phí/thuế giống vn_market_rules.py của app DNSE
    BROKER_FEE_RATE = 0.0015   # phí giao dịch mỗi chiều
    SELL_TAX_RATE = 0.001      # thuế TNCN khi bán

ETF = "E1VFVN30"
STATE_FILE = "thu_nghiem_state.json"   # thư mục chạy app (E:\Tool_FY), giống robot_memory.json
URL_INAV = "https://api.dragoncapital.com.vn/iindex/getLatestIIndex.php?index="
URL_SSI = "https://iboard-query.ssi.com.vn/stock/"
URL_KCN = "https://quachhieu2313.github.io/chay-review/assets/data/"
UA = "Mozilla/5.0 (DNSE-Terminal ThuNghiem)"

THAM_SO = {
    "tien_tuan_etf": 600_000,       # A: tiền mỗi tuần (~2,6 triệu/tháng)
    "chenh_han_chot_pct": 0.3,      # A: hạn chót cuối tuần chấp nhận cao hơn iNAV tối đa bao nhiêu %
    "tien_thang_ro": 2_400_000,     # B: tiền mỗi tháng
    "so_ma": 5,                     # B: số mã trong rổ
    "toi_da_moi_nganh": 2,          # B: mỗi ngành tối đa bao nhiêu mã (0 = không giới hạn)
    "so_ngay_mua": 5,               # B: số ngày giao dịch đầu tháng được mua
    "chenh_le_toi_da_pct": 0.5,     # B: giá lô lẻ không cao hơn giá chào bán bảng chính quá bao nhiêu %
}


# =============================================================================
# DỮ LIỆU (gọi mạng; trả None khi lỗi để vòng quét bỏ qua lượt đó)
# =============================================================================
def _get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def lay_inav(ma=ETF):
    """-> {'inav': float, 'luc': 'YYYY-MM-DD HH:MM:SS'} hoặc None."""
    try:
        x = _get_json(URL_INAV + ma).get(ma) or {}
        v = float(x.get("value") or 0)
        return {"inav": v, "luc": str(x.get("trade_date") or "")} if v > 0 else None
    except Exception:
        return None


def _so_lenh(d):
    lv = lambda k: [(float(d.get(f"best{i}{k}") or 0), int(d.get(f"best{i}{k}Vol") or 0)) for i in (1, 2, 3)]
    ngay = str(d.get("tradingDate") or "")
    return {
        "ngay": f"{ngay[:4]}-{ngay[4:6]}-{ngay[6:8]}" if len(ngay) == 8 else "",
        "khop": float(d.get("matchedPrice") or 0),
        "mua": [x for x in lv("Bid") if x[0] > 0 and x[1] > 0],      # giá chào MUA, cao -> thấp
        "ban": [x for x in lv("Offer") if x[0] > 0 and x[1] > 0],    # giá chào BÁN, thấp -> cao
    }


def lay_so_le(ma):
    """Sổ lệnh LÔ LẺ (SSI iboard). DNSE /chart-api/v2/markets/.../depth?board=ODD đã ngừng (404 từ 11/2026)."""
    try:
        return _so_lenh(_get_json(f"{URL_SSI}{ma}?boardId=ODD_LOT")["data"])
    except Exception:
        return None


def lay_so_chan(ma):
    """Sổ lệnh bảng chính (lô chẵn) để đối chiếu giá lô lẻ."""
    try:
        return _so_lenh(_get_json(f"{URL_SSI}{ma}")["data"])
    except Exception:
        return None


def lay_diem_vn30():
    """-> (ngày cập nhật, [{'ma','diem','gia'}] mã VN30 xếp điểm giảm dần) hoặc None."""
    try:
        diem = _get_json(URL_KCN + "diem_tai_chinh.json", 20)
        ro = _get_json(URL_KCN + "ro_chi_so/VN30.json", 20)
        return chon_diem(diem, ro)
    except Exception:
        return None


def chon_diem(diem, ro):
    vn30 = {x["ma"] for x in ro.get("thanh_phan") or []}
    ds = [{"ma": x["ma"], "diem": float(x["diem"]), "gia": x.get("gia"), "nganh": x.get("nganh") or ""} for x in diem.get("ds") or []
          if x.get("ma") in vn30 and x.get("diem") is not None and not x.get("canh_bao_du_lieu")]
    ds.sort(key=lambda x: (-x["diem"], x["ma"]))
    return diem.get("cap_nhat"), ds


def chon_ro(ds, so_ma, toi_da_moi_nganh):
    """Lấy so_ma mã điểm cao nhất, mỗi ngành tối đa toi_da_moi_nganh mã (điểm E/P + B/P hay dồn hết vào ngân hàng)."""
    out, dem = [], {}
    for x in ds:
        n = x.get("nganh") or x["ma"]
        if toi_da_moi_nganh and dem.get(n, 0) >= toi_da_moi_nganh:
            continue
        out.append(x)
        dem[n] = dem.get(n, 0) + 1
        if len(out) >= so_ma:
            break
    return out


# =============================================================================
# TIỆN ÍCH
# =============================================================================
def tuan_id(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def thang_id(d):
    return d.strftime("%Y-%m")


def tron_10(x):
    return int(math.floor(float(x) / 10 + 1e-9) * 10)


def phi_mua(tien):
    return tien * rules.BROKER_FEE_RATE


def tien_ban_rong(tien):
    return tien * (1 - rules.BROKER_FEE_RATE - rules.SELL_TAX_RATE)


def khop_giay_mua(ban, gia_tran, kl_toi_da, tien_toi_da):
    """Khớp giả lập lệnh MUA: ăn lần lượt các mức chào bán ≤ gia_tran, không vượt số CP / số tiền.
    Lô lẻ: tối đa 99 CP/lệnh. -> (kl, tiền khớp chưa phí, giá TB)."""
    kl = 0
    tien = 0.0
    for gia, vol in ban:
        if gia > gia_tran + 1e-9:
            break
        con_tien = tien_toi_da - tien * (1 + rules.BROKER_FEE_RATE)  # phí của các mức đã ăn cũng tính vào ngân sách
        q = min(vol, kl_toi_da - kl, int(con_tien // (gia * (1 + rules.BROKER_FEE_RATE))))
        if q <= 0:
            break
        kl += q
        tien += q * gia
    return kl, tien, (tien / kl if kl else 0.0)


def khop_giay_ban(mua, gia_san, kl_can):
    """Khớp giả lập lệnh BÁN: ăn các mức chào mua ≥ gia_san. -> (kl, tiền khớp, giá TB)."""
    kl = 0
    tien = 0.0
    for gia, vol in mua:
        if gia < gia_san - 1e-9:
            break
        q = min(vol, kl_can - kl)
        if q <= 0:
            break
        kl += q
        tien += q * gia
    return kl, tien, (tien / kl if kl else 0.0)


def _gia_moc(sc, ben):
    """Giá đối chiếu ở bảng chính: giá chào tốt nhất phía `ben` ('mua'/'ban'), không có thì giá khớp. 0 = không dùng được."""
    if not sc:
        return 0.0
    if sc[ben]:
        return sc[ben][0][0]
    return sc.get("khop") or 0.0


def new_state():
    return {
        "che_do": "GIAY",           # GIAY = chạy thử, chỉ ghi sổ. (THAT: chưa làm, bật sau giai đoạn chạy thử)
        "bat_dau": None,
        "etf": {"tuan": {}, "vi_the": {"kl": 0, "von": 0.0}},
        "ro": {"thang": {}, "vi_the": {}, "tien_mat": 0.0, "ss_etf": {"kl": 0, "von": 0.0}},
        "lenh": [],                 # sổ lệnh giấy: {luc, cl, ma, ben, kl, gia, tien, phi, ly_do}
    }


def _ghi_lenh(st, now, cl, ma, ben, kl, gia, tien, phi, ly_do):
    st["lenh"].append({"luc": now.strftime("%Y-%m-%d %H:%M:%S"), "cl": cl, "ma": ma, "ben": ben, "kl": int(kl),
                       "gia": round(gia, 2), "tien": round(tien), "phi": round(phi), "ly_do": ly_do})


# =============================================================================
# A. ETF ≤ iNAV
# =============================================================================
def buoc_etf(st, now, inav, so_le, ts=None):
    """Một lượt quét chiến lược A (gọi trong phiên lô lẻ, khi dữ liệu đúng ngày hôm nay).
    inav: {'inav','luc'}; so_le: sổ lệnh lô lẻ E1VFVN30. -> chuỗi nhật ký (hoặc '' nếu không làm gì)."""
    ts = ts or THAM_SO
    if not inav or not so_le or not so_le["ban"] or so_le["ngay"] != now.strftime("%Y-%m-%d"):
        return ""  # thiếu dữ liệu hoặc sổ lệnh không phải của hôm nay (ngày nghỉ lễ)
    if inav["luc"][:10] != now.strftime("%Y-%m-%d"):
        return ""  # iNAV chưa cập nhật phiên hôm nay
    a = st["etf"]
    wid = tuan_id(now.date())
    if wid not in a["tuan"]:
        cu = [a["tuan"][k] for k in sorted(a["tuan"]) if k < wid]
        du = 0.0
        if cu:
            du = max(0.0, min(ts["tien_tuan_etf"], cu[-1]["ngan_sach"] - cu[-1]["da_chi"]))  # dồn tối đa thêm 1 tuần
        a["tuan"][wid] = {"ngan_sach": ts["tien_tuan_etf"] + du, "da_chi": 0.0, "kl": 0, "doi_chung": None, "luot": []}
    w = a["tuan"][wid]
    if w["doi_chung"] is None:  # mua ngay ở lượt đầu tiên của tuần thì trả giá này
        w["doi_chung"] = {"gia": so_le["ban"][0][0], "inav": inav["inav"], "luc": now.strftime("%Y-%m-%d %H:%M")}

    con = w["ngan_sach"] - w["da_chi"]
    if con < so_le["ban"][0][0] * (1 + rules.BROKER_FEE_RATE):
        return ""
    tran = tron_10(inav["inav"])
    ly_do = f"giá ≤ iNAV {inav['inav']:,.2f}"
    han_chot = now.weekday() == 4 and now.strftime("%H:%M") >= "14:00"
    if han_chot and so_le["ban"][0][0] > tran:
        tran = tron_10(inav["inav"] * (1 + ts["chenh_han_chot_pct"] / 100))
        ly_do = f"hạn chót cuối tuần, chấp nhận ≤ iNAV +{ts['chenh_han_chot_pct']:g}% ({inav['inav']:,.2f})"
    kl, tien, gia_tb = khop_giay_mua(so_le["ban"], tran, 99, con)
    if kl <= 0:
        return ""
    phi = phi_mua(tien)
    w["da_chi"] += tien + phi
    w["kl"] += kl
    a["vi_the"]["kl"] += kl
    a["vi_the"]["von"] += tien + phi
    _ghi_lenh(st, now, "A", ETF, "MUA", kl, gia_tb, tien, phi, ly_do)
    chenh = (gia_tb / inav["inav"] - 1) * 100
    return f"🧪 A | MUA GIẤY {ETF} {kl} ccq @ {gia_tb:,.0f} ({chenh:+.2f}% so với iNAV {inav['inav']:,.2f}) - {ly_do}"


# =============================================================================
# B. RỔ VN30 ĐIỂM CAO NHẤT
# =============================================================================
def buoc_ro(st, now, diem, lay_le, lay_chan, so_le_etf, ts=None):
    """Một lượt quét chiến lược B. diem = (ngày, [{'ma','diem'}]) từ lay_diem_vn30(); lay_le/lay_chan(ma) -> sổ lệnh.
    so_le_etf: sổ lô lẻ E1VFVN30 để ghi đối chứng. -> list chuỗi nhật ký."""
    ts = ts or THAM_SO
    b = st["ro"]
    log = []
    hom_nay = now.strftime("%Y-%m-%d")
    mid = thang_id(now.date())
    if mid not in b["thang"]:
        if not b["thang"] and now.day > 7:
            # lần đầu chạy giữa/cuối tháng: chờ đầu tháng sau, tránh mua 2 tháng tiền trong vài ngày
            if b.get("cho") != mid:
                b["cho"] = mid
                log.append(f"🧪 B | Rổ VN30 bắt đầu từ phiên đầu tháng sau (hôm nay đã ngày {now.day}); tuần này chỉ chạy A.")
            return log
        if not diem or not diem[1]:
            return log
        chon = chon_ro(diem[1], int(ts["so_ma"]), int(ts.get("toi_da_moi_nganh", 0) or 0))
        top = [x["ma"] for x in chon]
        b["thang"][mid] = {"muc_tieu": top, "ngay_diem": diem[0], "diem": {x["ma"]: x["diem"] for x in chon},
                           "ngay_mua": [], "da_ban": False, "phan_bo": None, "da_chi": {}}
        b["tien_mat"] += ts["tien_thang_ro"]
        log.append(f"🧪 B | Tháng {mid}: rổ mục tiêu {', '.join(top)} (điểm tài chính KCN ngày {diem[0]}); thêm {ts['tien_thang_ro']:,.0f} đ.")
    m = b["thang"][mid]
    if hom_nay not in m["ngay_mua"]:
        if len(m["ngay_mua"]) >= int(ts["so_ngay_mua"]):
            return log  # hết cửa sổ mua đầu tháng
        m["ngay_mua"].append(hom_nay)

    # 1. Bán mã rớt khỏi top (một lần đầu tháng; mua trước đó >= 3 ngày để chắc chắn đã về T+2)
    if not m["da_ban"]:
        con_ban = False
        for ma, vt in list(b["vi_the"].items()):
            if ma in m["muc_tieu"] or vt["kl"] <= 0:
                continue
            if (now - datetime.strptime(vt["mua_cuoi"], "%Y-%m-%d")).days < 3:
                con_ban = True
                continue
            sl, sc = lay_le(ma), lay_chan(ma)
            moc = _gia_moc(sc, "mua")
            if not sl or not sl["mua"] or sl["ngay"] != hom_nay or moc <= 0:
                con_ban = True
                continue
            # không bán lô lẻ rẻ hơn giá chào mua bảng chính quá ngưỡng
            kl, tien, gia_tb = khop_giay_ban(sl["mua"], moc * (1 - ts["chenh_le_toi_da_pct"] / 100), vt["kl"])
            if kl <= 0:
                con_ban = True
                continue
            von = vt["von"] * kl / vt["kl"]
            nhan = tien_ban_rong(tien)
            vt["kl"] -= kl
            vt["von"] -= von
            b["tien_mat"] += nhan
            _ghi_lenh(st, now, "B", ma, "BÁN", kl, gia_tb, tien, tien - nhan, f"rớt khỏi top {int(ts['so_ma'])}")
            log.append(f"🧪 B | BÁN GIẤY {ma} {kl} CP @ {gia_tb:,.0f} (rớt khỏi rổ), lãi/lỗ {nhan - von:+,.0f} đ.")
            if vt["kl"] > 0:
                con_ban = True
            else:
                del b["vi_the"][ma]
        m["da_ban"] = not con_ban

    # 2. Mua: chia đều tiền mặt cho các mã mục tiêu (chia một lần, sau khi đã bán xong hoặc hết ngày đầu)
    if m["phan_bo"] is None and (m["da_ban"] or len(m["ngay_mua"]) > 1):
        moi = b["tien_mat"] / max(1, len(m["muc_tieu"]))
        m["phan_bo"] = {ma: moi for ma in m["muc_tieu"]}
    if not m["phan_bo"]:
        return log
    for ma in m["muc_tieu"]:
        con = m["phan_bo"][ma] - m["da_chi"].get(ma, 0.0)
        sl = lay_le(ma)
        if not sl or not sl["ban"] or sl["ngay"] != hom_nay or con < sl["ban"][0][0] * (1 + rules.BROKER_FEE_RATE):
            continue
        moc = _gia_moc(lay_chan(ma), "ban")
        if moc <= 0:
            continue
        tran = moc * (1 + ts["chenh_le_toi_da_pct"] / 100)
        kl, tien, gia_tb = khop_giay_mua(sl["ban"], tran, 99, min(con, b["tien_mat"]))
        if kl <= 0:
            continue
        phi = phi_mua(tien)
        vt = b["vi_the"].setdefault(ma, {"kl": 0, "von": 0.0, "mua_cuoi": hom_nay})
        vt["kl"] += kl
        vt["von"] += tien + phi
        vt["mua_cuoi"] = hom_nay
        b["tien_mat"] -= tien + phi
        m["da_chi"][ma] = m["da_chi"].get(ma, 0.0) + tien + phi
        _ghi_lenh(st, now, "B", ma, "MUA", kl, gia_tb, tien, phi, f"top {int(ts['so_ma'])} điểm tài chính (bảng chính {moc:,.0f})")
        # đối chứng: cùng số tiền mua E1VFVN30 lô lẻ lúc đó (giá chào bán tốt nhất, không giới hạn khối lượng)
        if so_le_etf and so_le_etf["ban"]:
            g = so_le_etf["ban"][0][0]
            b["ss_etf"]["kl"] += (tien + phi) / (g * (1 + rules.BROKER_FEE_RATE))
            b["ss_etf"]["von"] += tien + phi
        log.append(f"🧪 B | MUA GIẤY {ma} {kl} CP @ {gia_tb:,.0f} (lô lẻ {(gia_tb / moc - 1) * 100:+.2f}% so với bảng chính).")
    return log


# =============================================================================
# BÁO CÁO
# =============================================================================
def bao_cao(st, gia):
    """gia: {ma: giá hiện tại (đ)}. -> dict tóm tắt cho giao diện; giá trị đã trừ phí + thuế nếu bán hết."""
    out = {}
    a = st["etf"]
    ge = gia.get(ETF, 0)
    vt = a["vi_the"]
    gt = tien_ban_rong(vt["kl"] * ge) if ge else 0.0
    # đối chứng A: mỗi tuần mua ở giá lượt quét đầu tuần với đúng số tiền A đã chi tuần đó
    dc_kl = sum(w["da_chi"] / (w["doi_chung"]["gia"] * (1 + rules.BROKER_FEE_RATE)) for w in a["tuan"].values()
                if w["doi_chung"] and w["da_chi"] > 0)
    gia_von = vt["von"] / vt["kl"] if vt["kl"] else 0.0
    gia_dc = vt["von"] / dc_kl if dc_kl else 0.0
    out["A"] = {"kl": vt["kl"], "von": vt["von"], "gia_tri": gt, "lai": gt - vt["von"],
                "gia_von": gia_von, "gia_von_doi_chung": gia_dc,
                "re_hon_pct": (gia_dc / gia_von - 1) * 100 if gia_von and gia_dc else None,
                "so_tuan": len(a["tuan"]), "tuan_chua_mua": sum(1 for w in a["tuan"].values() if w["kl"] == 0)}
    b = st["ro"]
    ds = []
    tong_von = tong_gt = 0.0
    for ma, x in sorted(b["vi_the"].items()):
        g = gia.get(ma, 0)
        v = tien_ban_rong(x["kl"] * g) if g else 0.0
        ds.append({"ma": ma, "kl": x["kl"], "von": x["von"], "gia": g, "gia_tri": v, "lai": v - x["von"]})
        tong_von += x["von"]
        tong_gt += v
    ss = b["ss_etf"]
    ss_gt = tien_ban_rong(ss["kl"] * ge) if ge else 0.0
    da_ban = sum((l["tien"] - l["phi"]) for l in st["lenh"] if l["cl"] == "B" and l["ben"] == "BÁN")
    tong_chi = sum((l["tien"] + l["phi"]) for l in st["lenh"] if l["cl"] == "B" and l["ben"] == "MUA")
    out["B"] = {"ds": ds, "von": tong_von, "gia_tri": tong_gt, "tien_mat": b["tien_mat"],
                "lai": tong_gt + da_ban - tong_chi,
                "lai_pct": (tong_gt + da_ban - tong_chi) / tong_chi * 100 if tong_chi else None,
                "ss_von": ss["von"], "ss_gia_tri": ss_gt,
                "ss_lai_pct": (ss_gt / ss["von"] - 1) * 100 if ss["von"] else None}
    return out


def doc(path=STATE_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            st = json.load(f)
        for k, v in new_state().items():
            st.setdefault(k, v)
        return st
    except Exception:
        return new_state()


def ghi(st, path=STATE_FILE):
    import os
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
