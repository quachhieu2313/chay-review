# -*- coding: utf-8 -*-
"""
"Nhiệt kế tin tức": chấm điểm tích cực / tiêu cực từng bài trong assets/data/thoi_su.json bằng bộ từ khoá
tiếng Việt + tiếng Anh, gắn bài vào ngành (theo từ khoá và mã cổ phiếu), rồi
  1) ghi điểm + ngành vào từng bài trong thoi_su.json (trang lọc tin theo ngành),
  2) tính điểm thị trường và từng ngành trong 24 giờ gần nhất,
  3) lưu điểm tin của từng phiên (tin từ 15:00 phiên trước tới 09:00 phiên đó) và khi phiên đóng cửa thì đối chiếu
     với biến động thực tế của VN-Index / cổ phiếu trong ngành -> tỷ lệ "đúng chiều".
Đây là thước đo tâm lý tin tức, KHÔNG phải dự báo. Chạy sau scripts/thoi_su.py.
"""
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))
GOC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "data")
TIN = os.path.join(GOC, "thoi_su.json")
RA = os.path.join(GOC, "nhiet_ke_tin.json")
NGUONG = 0.05          # |điểm| nhỏ hơn mức này = trung tính, không tính đúng/sai
TOI_THIEU_BAI = 5      # ngành cần ít nhất 5 bài trong phiên mới đối chiếu
GIU_PHIEN = 250
TRONG_SO_TG = 0.5      # tin thế giới tính nửa trọng số

# ---------------------------------------------------------------------------------------------------------------
# Bộ từ khoá. Cụm "ưu tiên" xét trước và bị xoá khỏi câu để không bị đếm lại bởi từ đơn (vd "giảm lỗ" không còn chữ "lỗ").
# Mỗi mục: (mẫu regex, điểm thị trường, {ngành: điểm riêng})
# ---------------------------------------------------------------------------------------------------------------
UU_TIEN_VN = [
    (r"giảm lỗ|lỗ giảm|thu hẹp lỗ|lỗ thu hẹp|có lãi trở lại|lãi trở lại|thoát lỗ", 1, {}),
    (r"(không|chưa|ngừng|tạm dừng) (tăng|nâng) lãi suất", 1, {}),
    (r"(giảm|hạ) lãi suất|lãi suất[^.,;:]{0,25}(giảm|hạ)|nới lỏng tiền tệ", 1, {"Bất động sản": 1, "Dịch vụ tài chính": 1}),
    (r"(tăng|nâng) lãi suất|lãi suất[^.,;:]{0,25}(tăng|nhích)", -1, {"Bất động sản": -1, "Dịch vụ tài chính": -1}),
    (r"lạm phát[^.,;:]{0,12}(tăng|nóng|leo thang|vượt)[^.,;:]{0,8}(dự báo|kỳ vọng)?", -1, {}),
    (r"lạm phát[^.,;:]{0,12}(giảm|hạ nhiệt|chậm lại)", 1, {}),
    (r"nợ xấu (tăng|phình)", -1, {"Ngân hàng": -1}),
    (r"(giảm|xử lý) nợ xấu|nợ xấu giảm", 1, {"Ngân hàng": 1}),
    (r"giá (dầu|xăng)[^.,;]{0,15}(tăng|leo|vọt|lập đỉnh)", -0.5, {"Dầu khí": 1}),
    (r"giá (dầu|xăng)[^.,;]{0,15}(giảm|lao|rơi|hạ)", 0.5, {"Dầu khí": -1}),
    (r"giá thép[^.,;]{0,15}(tăng|phục hồi)", 0, {"Tài nguyên Cơ bản": 1}),
    (r"giá thép[^.,;]{0,15}(giảm|lao|rơi)", 0, {"Tài nguyên Cơ bản": -1}),
    (r"tỷ giá[^.,;]{0,15}(tăng|căng|leo)|usd[^.,;]{0,10}(tăng|vọt)", -1, {}),
    (r"khối ngoại[^.,;]{0,25}mua ròng", 1, {}),
    (r"khối ngoại[^.,;]{0,25}bán ròng", -1, {}),
    (r"giảm thuế|miễn thuế|hoãn thuế|gia hạn thuế", 1, {}),
    (r"(áp|tăng) thuế|thuế quan|thuế đối ứng", -1, {}),
    (r"lỗ kỷ lục|giảm kỷ lục", -1.5, {}),
    (r"lãi kỷ lục|lợi nhuận kỷ lục|cao kỷ lục|đỉnh lịch sử", 1.5, {}),
    (r"không (tăng|đạt|có lãi)", -1, {}),
]
UU_TIEN_EN = [
    (r"rate cuts?|cut(s|ting)? (interest )?rates?|dovish", 1, {"Bất động sản": 1, "Dịch vụ tài chính": 1}),
    (r"rate[- ]hikes?|raise[sd]? (interest )?rates?|hawkish|higher (interest |mortgage )?rates|rising rates|"
     r"rates? (rise|rises|rose|climb\w*|jump\w*|reach\w*)", -1, {"Bất động sản": -1}),
    (r"inflation (rises?|rose|jumps?|jumped|accelerat\w*|heats?|hotter|surges?)|hot(ter)? inflation|re-accelerat\w*", -1, {}),
    (r"inflation (eases?|eased|cools?|cooled|slows?|slowed|falls?|fell)", 1, {}),
    (r"oil (prices? )?(rises?|rose|jumps?|surges?|soars?|climbs?|rall\w+)", -0.5, {"Dầu khí": 1}),
    (r"oil (prices? )?(falls?|fell|drops?|slumps?|tumbles?|slides?|sinks?)", 0.5, {"Dầu khí": -1}),
    (r"lay(s|ing)? off|layoffs?|job cuts?", -1, {}),
    (r"beats? (estimates|expectations|forecasts)|tops? (estimates|expectations)", 1, {}),
    (r"miss(es|ed)? (estimates|expectations|forecasts)|revenue miss", -1, {}),
    (r"record high|all-time high", 1.5, {}),
    (r"tariffs?|trade war", -1, {}),
]
TU_VN = [
    # tích cực
    (r"tăng trưởng|tăng mạnh|tăng điểm|tăng trần|kịch trần|bứt phá|khởi sắc|hồi phục|phục hồi|lạc quan|tích cực|thuận lợi|"
     r"vượt kế hoạch|vượt dự báo|lãi lớn|lợi nhuận tăng|doanh thu tăng|lãi tăng|mua ròng|nâng hạng|nâng tín nhiệm|đột phá|"
     r"tháo gỡ|gỡ vướng|giải ngân|thặng dư|xuất siêu|xuất khẩu tăng|thu hút|cổ tức|thắng thầu|trúng thầu|kỷ lục|"
     r"hút dòng tiền|dòng tiền (vào|đổ vào|quay lại)|bùng nổ|sôi động|hưởng lợi|triển vọng|khả quan|ổn định|tăng tốc", 1),
    # tiêu cực
    (r"giảm điểm|giảm mạnh|giảm sàn|nằm sàn|lao dốc|bán tháo|bán ròng|thua lỗ|\blỗ\b|sụt giảm|lỗ ròng|đỏ lửa|chìm trong sắc đỏ|"
     r"call margin|giải chấp|khởi tố|tạm giam|bắt giữ|sai phạm|vi phạm|xử phạt|bị phạt|đình chỉ|phá sản|vỡ nợ|chậm trả|"
     r"chậm thanh toán|thâm hụt|suy thoái|căng thẳng|xung đột|chiến tranh|rủi ro|cảnh báo|bi quan|tháo chạy|huỷ niêm yết|"
     r"hủy niêm yết|hoãn xuất cảnh|tham ô|lừa đảo|thao túng|điều tra|đóng băng|ế ẩm|sụt|lao đao|khó khăn|áp lực|"
     r"giảm sâu|mất giá|trượt giá|tụt|cắt giảm|hụt", -1),
]
TU_EN = [
    (r"surg\w*|soar\w*|jump\w*|rall\w+|gains?|gained|rises?|rose|rising|climb\w*|beat\w*|upgrade\w*|strong\w*|growth|"
     r"optimis\w*|rebound\w*|recover\w*|boost\w*|outperform\w*|bullish|record profit|expan\w+|upbeat|robust", 1),
    (r"falls?|fell|falling|drops?|dropped|slump\w*|plung\w*|tumbl\w*|slid(e|es|ing)?|sinks?|sank|downgrade\w*|recession|"
     r"crisis|default\w*|bankrupt\w*|fined|fines|penalt\w+|probe|lawsuit|sued|warn\w*|fears?|concerns?|sell-?off|"
     r"bearish|weak\w*|loss(es)?|shutdown|war\b|sanction\w*|volatil\w*|slowdown|turmoil|decline\w*|cuts? forecast", -1),
]


def _bien(ds):
    return [(re.compile(p, re.I), a, b) for p, a, b in ds]


UU_TIEN_VN, UU_TIEN_EN = _bien(UU_TIEN_VN), _bien(UU_TIEN_EN)
TU_VN = [(re.compile(p, re.I), d) for p, d in TU_VN]
TU_EN = [(re.compile(p, re.I), d) for p, d in TU_EN]

# Ngành (tên trùng cột "nganh" trong co_phieu.json) -> từ khoá tiếng Việt, tiếng Anh
NGANH_TU = {
    "Ngân hàng": (r"ngân hàng|tín dụng|nợ xấu|lãi suất huy động|lãi suất cho vay", r"\bbanks?\b|banking|lenders?|credit"),
    "Bất động sản": (r"bất động sản|địa ốc|căn hộ|chung cư|nhà ở|đất nền|dự án nhà|khu đô thị|thị trường nhà", r"real estate|property|housing|home sales|mortgage"),
    "Dịch vụ tài chính": (r"công ty chứng khoán|ctck|môi giới|margin|thanh khoản thị trường|giá trị giao dịch|tài khoản chứng khoán|nâng hạng",
                          r"brokerage|investment bank"),
    "Thực phẩm và đồ uống": (r"thực phẩm|đồ uống|sữa|bia|thủy sản|thuỷ sản|cá tra|con tôm|\btôm\b|mía đường|giá đường|chăn nuôi|thịt heo",
                             r"food|beverage|dairy|brewer"),
    "Xây dựng và Vật liệu": (r"ngành xây dựng|nhà thầu|thi công|đầu tư công|xi măng|cao tốc|hạ tầng giao thông|vật liệu xây dựng|ống nhựa",
                             r"construction|infrastructure|cement"),
    "Điện, nước & xăng dầu khí đốt": (r"\bđiện\b|evn|điện gió|điện mặt trời|năng lượng tái tạo|khí đốt|lng|thủy điện|nhiệt điện|cấp nước",
                                      r"utilit\w+|power grid|electricity|natural gas|\blng\b"),
    "Hàng & Dịch vụ Công nghiệp": (r"cảng biển|logistics|vận tải biển|cước vận tải|container|khu công nghiệp|chuyển phát", r"shipping|logistics|freight|container"),
    "Hóa chất": (r"phân bón|urê|ure|cao su|hóa chất|hoá chất", r"fertili[sz]er|rubber|chemical"),
    "Dầu khí": (r"dầu khí|giá dầu|xăng dầu|dầu thô|opec|brent|lọc dầu|khoan dầu", r"\boil\b|crude|opec|brent|refin\w+"),
    "Bán lẻ": (r"bán lẻ|sức mua|tiêu dùng|điện thoại|điện máy|nhà thuốc|siêu thị", r"retail\w*|consumer spending|shoppers"),
    "Tài nguyên Cơ bản": (r"\bthép\b|quặng|tôn mạ|phôi thép", r"\bsteel\b|iron ore|metals?"),
    "Công nghệ Thông tin": (r"công nghệ thông tin|chuyển đổi số|phần mềm|\bai\b|trí tuệ nhân tạo|bán dẫn|\bchip|viễn thông|trung tâm dữ liệu",
                            r"\btech\w*|software|semiconductor|\bchips?\b|\bai\b|nvidia"),
    "Du lịch và Giải trí": (r"hàng không|du lịch|khách quốc tế|chuyến bay|sân bay|hãng bay", r"airlines?|travel|tourism"),
    "Bảo hiểm": (r"bảo hiểm", r"insur\w+"),
    "Hàng cá nhân & Gia dụng": (r"trang sức|vàng bạc|giá vàng", r"jewel\w+|\bgold\b"),
}
NGANH_TU = {k: (re.compile(a, re.I), re.compile(b, re.I)) for k, (a, b) in NGANH_TU.items()}


def _doc(p, mac_dinh=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return mac_dinh


def _ghi(p, d):
    tam = p + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tam, p)


def cham_diem(van_ban, tieng_anh):
    """Trả về (điểm thị trường cộng dồn, số từ khoá trúng, {ngành: điểm riêng})."""
    s = van_ban.lower()
    tong, trung, rieng = 0.0, 0, {}
    for rx, d, ng in (UU_TIEN_EN if tieng_anh else UU_TIEN_VN):
        for _ in rx.finditer(s):
            tong += d
            trung += 1
            for k, v in ng.items():
                rieng[k] = rieng.get(k, 0) + v
        s = rx.sub(" § ", s)
    for rx, d in (TU_EN if tieng_anh else TU_VN):
        n = len(rx.findall(s))
        tong += d * n
        trung += n
    return tong, trung, rieng


def diem_bai(t, ma_nganh, ma_re):
    tieng_anh = t["pham_vi"] == "tg"
    td = t.get("tieu_de_goc") if tieng_anh and t.get("tieu_de_goc") else t["tieu_de"]
    mt = t.get("mo_ta", "") if not tieng_anh else ""   # tóm tắt tin TG đã bị dịch -> chỉ chấm tiêu đề gốc
    a1, n1, r1 = cham_diem(td, tieng_anh)
    a2, n2, r2 = cham_diem(mt, tieng_anh)
    tho = 2 * a1 + a2
    so = 2 * n1 + n2
    diem = max(-1.0, min(1.0, tho / max(2.0, so))) if so else 0.0
    # ngành: theo từ khoá + mã cổ phiếu (mã chỉ xét tin VN, viết hoa đúng mã)
    nd = td + " " + (t.get("mo_ta", "") if not tieng_anh else "")
    nganh = {}
    for ten, (rvn, ren) in NGANH_TU.items():
        if (ren if tieng_anh else rvn).search(nd):
            nganh[ten] = diem
    if not tieng_anh:
        for m in ma_re.findall(t["tieu_de"] + " " + t.get("mo_ta", "")):
            nganh[ma_nganh[m]] = diem
    for k, v in list(r1.items()) + list(r2.items()):   # quy tắc riêng ngành (vd giá dầu tăng: tốt cho Dầu khí)
        nganh[k] = max(-1.0, min(1.0, (nganh.get(k, diem) + v) / 2 if k in nganh else v))
    return round(diem, 3), {k: round(v, 3) for k, v in nganh.items()}


def _tong_hop(ds):
    """ds: list (điểm, trọng số). Trả về điểm trung bình có trọng số, số bài, số bài tích cực, tiêu cực."""
    w = sum(tr for _, tr in ds)
    return {"diem": round(sum(d * tr for d, tr in ds) / w, 3) if w else 0.0, "n": len(ds),
            "duong": sum(1 for d, _ in ds if d >= NGUONG), "am": sum(1 for d, _ in ds if d <= -NGUONG)}


def phien_cua(thoi_diem):
    """Tin đăng lúc `thoi_diem` (giờ VN) thuộc cửa sổ của phiên nào: từ 15:00 ngày làm việc trước tới 09:00 phiên đó.
    Tin trong giờ giao dịch 09:00-15:00 trả None (diễn ra cùng lúc với giá, không dùng để đối chiếu)."""
    d, g = thoi_diem.date(), thoi_diem.time()
    if d.weekday() < 5 and dtime(9, 0) <= g < dtime(15, 0):
        return None
    if d.weekday() < 5 and g < dtime(9, 0):
        return d
    d = d + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _loi_nhuan_phien(d, c, ngay):
    """% thay đổi giá đóng cửa của phiên giao dịch đầu tiên >= ngay so với phiên liền trước; None nếu chưa có."""
    for i, x in enumerate(d):
        if x >= ngay:
            if i == 0 or c[i - 1] in (None, 0) or c[i] is None:
                return None, x
            return round((c[i] / c[i - 1] - 1) * 100, 3), x
    return None, None


def main():
    tin_tat_ca = _doc(TIN)
    if not tin_tat_ca or not tin_tat_ca.get("tin"):
        print("Chưa có thoi_su.json, bỏ qua.")
        return 0
    cp = _doc(os.path.join(GOC, "co_phieu.json"), {}).get("co_phieu", [])
    ma_nganh = {x["ma"]: x["nganh"] for x in cp if x.get("nganh") in NGANH_TU}
    ma_re = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(sorted(ma_nganh, key=len, reverse=True)) + r")(?![A-Za-z0-9])")
    nganh_ma = {}
    for m, n in ma_nganh.items():
        nganh_ma.setdefault(n, []).append(m)

    bay_gio = datetime.now(VN_TZ)
    tin = tin_tat_ca["tin"]
    for t in tin:
        t["diem"], t["nganh"] = diem_bai(t, ma_nganh, ma_re)
    _ghi(TIN, tin_tat_ca)

    # ---- hiện tại: 24 giờ gần nhất ----
    moc = bay_gio - timedelta(hours=24)
    gan = [t for t in tin if datetime.fromisoformat(t["thoi_gian"]) >= moc]

    def tr(t):
        return TRONG_SO_TG if t["pham_vi"] == "tg" else 1.0

    def bai_ngan(t):
        return {"t": t["tieu_de"], "l": t["link"], "d": t["diem"], "s": t["nguon"]}

    tt = _tong_hop([(t["diem"], tr(t)) for t in gan if t["diem"] or t["nganh"]])
    xep = sorted(gan, key=lambda t: t["diem"] * tr(t))
    tt["top_am"] = [bai_ngan(t) for t in xep[:5] if t["diem"] <= -NGUONG]
    tt["top_duong"] = [bai_ngan(t) for t in reversed(xep[-5:]) if t["diem"] >= NGUONG]
    nganh_nay = []
    for ten in NGANH_TU:
        ds = [t for t in gan if ten in t["nganh"]]
        th = _tong_hop([(t["nganh"][ten], tr(t)) for t in ds])
        th.update(ten=ten, ma=sorted(nganh_ma.get(ten, [])))
        nganh_nay.append(th)
    nganh_nay.sort(key=lambda x: (x["n"] < 3, -x["diem"]))   # ngành ít tin (<3 bài) xếp cuối

    # ---- lịch sử theo phiên ----
    cu = _doc(RA, {}) or {}
    lich_su = {p["phien"]: p for p in cu.get("lich_su", [])}
    for t in tin:
        tg = datetime.fromisoformat(t["thoi_gian"])
        ph = phien_cua(tg)
        if ph is None:
            continue
        k = ph.isoformat()
        p = lich_su.setdefault(k, {"phien": k, "xong": False, "_bai": {}})
        if p.get("xong"):
            continue   # đã đối chiếu xong thì không sửa nữa
        kh = hashlib.md5(t["link"].encode("utf-8")).hexdigest()[:10]
        p.setdefault("_bai", {})[kh] = [t["diem"], tr(t), t["nganh"]]
    vni = _doc(os.path.join(GOC, "chi_so", "VNINDEX.json"), {}) or {}
    gia = {}
    for p in lich_su.values():
        bai = list(p.get("_bai", {}).values())
        if not p.get("xong") and bai:
            p["thi_truong"] = _tong_hop([(d, w) for d, w, ng in bai if d or ng])
            p["nganh"] = {}
            for ten in NGANH_TU:
                ds = [(ng[ten], w) for d, w, ng in bai if ten in ng]
                if ds:
                    p["nganh"][ten] = _tong_hop(ds)
        if p.get("xong") or date.fromisoformat(p["phien"]) > bay_gio.date():
            continue
        if p["phien"] == bay_gio.date().isoformat() and bay_gio.time() < dtime(15, 5):
            continue
        r, ngay_gd = _loi_nhuan_phien(vni.get("d", []), vni.get("c", []), p["phien"])
        if r is None:
            continue
        p["thuc_te"] = {"ngay": ngay_gd, "vnindex": r, "nganh": {}}
        for ten in p.get("nganh", {}):
            ds = []
            for m in nganh_ma.get(ten, []):
                if m not in gia:
                    x = _doc(os.path.join(GOC, "cp", m + ".json"), {}) or {}
                    gia[m] = (x.get("d", []), x.get("c", []))
                rr, nn = _loi_nhuan_phien(gia[m][0], gia[m][1], p["phien"])
                if rr is not None and nn == ngay_gd:
                    ds.append(rr)
            if ds:
                p["thuc_te"]["nganh"][ten] = round(sum(ds) / len(ds), 3)
        p["xong"] = True
        p.pop("_bai", None)

    ds_phien = sorted(lich_su.values(), key=lambda p: p["phien"])[-GIU_PHIEN:]

    # ---- độ chính xác ----
    def dung_chieu(diem, thuc):
        return (diem > 0) == (thuc > 0)

    xong = [p for p in ds_phien if p.get("xong") and "thuc_te" in p]
    thi = [(p["thi_truong"]["diem"], p["thuc_te"]["vnindex"]) for p in xong
           if p.get("thi_truong") and abs(p["thi_truong"]["diem"]) >= NGUONG and p["thuc_te"]["vnindex"] != 0]
    phien_tang = [p for p in xong if p["thuc_te"]["vnindex"] > 0]
    chinh_xac = {"thi_truong": {"so_phien": len(thi), "dung": sum(dung_chieu(a, b) for a, b in thi),
                                "ty_le_phien_tang": round(len(phien_tang) / len(xong) * 100, 1) if xong else None,
                                "so_phien_co_gia": len(xong)},
                 "nganh": {}}
    for ten in NGANH_TU:
        cap = [(p["nganh"][ten]["diem"], p["thuc_te"]["nganh"][ten]) for p in xong
               if ten in p.get("nganh", {}) and ten in p["thuc_te"].get("nganh", {})
               and p["nganh"][ten]["n"] >= TOI_THIEU_BAI and abs(p["nganh"][ten]["diem"]) >= NGUONG and p["thuc_te"]["nganh"][ten] != 0]
        if cap:
            chinh_xac["nganh"][ten] = {"so_phien": len(cap), "dung": sum(dung_chieu(a, b) for a, b in cap)}

    du_lieu = {
        "cap_nhat": bay_gio.isoformat(timespec="minutes"),
        "gio": 24,
        "nguong": NGUONG,
        "thi_truong": tt,
        "nganh": nganh_nay,
        "chinh_xac": chinh_xac,
        "lich_su": ds_phien,
    }
    _ghi(RA, du_lieu)
    print("Nhiệt kế tin: 24h điểm %+.3f (%d bài, %d tích cực, %d tiêu cực); %d phiên đã đối chiếu" % (
        tt["diem"], tt["n"], tt["duong"], tt["am"], len(xong)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
