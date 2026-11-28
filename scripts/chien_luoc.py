"""Chiến lược lô lẻ: chạy mô phỏng trên GitHub + đăng tín hiệu cho trang /chien-luoc/ và cho robot DNSE.

Chạy trong workflow trong phiên (10 phút/lần) và lượt chiều. Ra 2 file trong assets/data/chien_luoc/:
  so.json       sổ mô phỏng (lệnh giấy) của 2 chiến lược, cùng logic với app DNSE (chien_luoc_logic.py)
  tin_hieu.json tín hiệu hiện tại: iNAV + sổ lệnh lô lẻ E1VFVN30, rổ VN30 của tháng (đã chốt hoặc dự kiến),
                và `loai_tru` = các mã robot "lỗ 16% mua gấp đôi" phải bỏ qua (app máy tính + APK đọc file này).

Rổ của tháng được CHỐT ở lượt quét đầu tiên trong phiên lô lẻ của tháng; app DNSE mua thật theo đúng rổ đã chốt này.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chien_luoc_logic as cl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data"
OUT = DATA / "chien_luoc"
SO_THANG_LOAI_TRU = 3   # mã trong rổ 3 tháng gần nhất vẫn nằm trong danh sách loại trừ (phòng còn giữ do chưa bán xong)


def log(*a):
    print(*a, flush=True)


def gio_vn():
    return datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)


def doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def ghi(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def phien_lo_le(now):
    t = now.strftime("%H:%M")
    return now.weekday() < 5 and ("09:15" <= t < "11:30" or "13:00" <= t < "14:30")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    now = gio_vn()
    st = doc(OUT / "so.json", None) or cl.new_state()
    for k, v in cl.new_state().items():
        st.setdefault(k, v)
    if not st.get("bat_dau"):
        st["bat_dau"] = now.strftime("%Y-%m-%d")

    diem = cl.chon_diem(doc(DATA / "diem_tai_chinh.json", {}), doc(DATA / "ro_chi_so" / "VN30.json", {}))
    inav = cl.lay_inav(cl.ETF)
    le_etf = cl.lay_so_le(cl.ETF)
    chan_etf = cl.lay_so_chan(cl.ETF)
    log(f"{now:%Y-%m-%d %H:%M} iNAV {inav} | lô lẻ {le_etf and le_etf['ban'][:1]} | điểm {diem[0]} ({len(diem[1])} mã VN30)")

    nhat_ky = []
    if phien_lo_le(now):
        m = cl.buoc_etf(st, now, inav, le_etf)
        if m:
            nhat_ky.append(m)
        nhat_ky += cl.buoc_ro(st, now, diem, cl.lay_so_le, cl.lay_so_chan, le_etf)
        for x in nhat_ky:
            log("  " + x)

    # ---- rổ tháng này: đã chốt (trong sổ) hoặc dự kiến (tính từ điểm hiện tại)
    mid = cl.thang_id(now.date())
    thang = st["ro"]["thang"].get(mid)
    if thang:
        muc_tieu, trang_thai, ngay_diem = thang["muc_tieu"], "da_chot", thang["ngay_diem"]
    else:
        muc_tieu = [x["ma"] for x in cl.chon_ro(diem[1], int(cl.THAM_SO["so_ma"]), int(cl.THAM_SO["toi_da_moi_nganh"]))]
        trang_thai, ngay_diem = "du_kien", diem[0]
    theo_ma = {x["ma"]: x for x in diem[1]}
    chi_tiet = []
    for ma in muc_tieu:
        le, chan = cl.lay_so_le(ma), cl.lay_so_chan(ma)
        g_le = le["ban"][0][0] if le and le["ban"] else None
        g_chan = cl._gia_moc(chan, "ban") or None
        x = theo_ma.get(ma, {})
        chi_tiet.append({"ma": ma, "diem": x.get("diem"), "nganh": x.get("nganh"), "gia_le": g_le, "gia_chan": g_chan,
                         "chenh_le": round((g_le / g_chan - 1) * 100, 2) if g_le and g_chan else None,
                         "khop": (chan or {}).get("khop")})

    # ---- mã robot gấp đôi phải bỏ qua: ETF + rổ các tháng gần đây + rổ tháng này (kể cả dự kiến) + mã sổ còn giữ
    gan = sorted(st["ro"]["thang"])[-SO_THANG_LOAI_TRU:]
    loai_tru = {cl.ETF, *muc_tieu, *st["ro"]["vi_the"]}
    for k in gan:
        loai_tru.update(st["ro"]["thang"][k]["muc_tieu"])

    # ---- giá hiện tại cho báo cáo sổ
    gia = {}
    for ma in {cl.ETF, *st["ro"]["vi_the"]}:
        sc = chan_etf if ma == cl.ETF else cl.lay_so_chan(ma)
        if sc and sc["khop"] > 0:
            gia[ma] = sc["khop"]
    bc = cl.bao_cao(st, gia)

    tran = cl.tron_10(inav["inav"]) if inav else None
    g_ban = le_etf["ban"][0][0] if le_etf and le_etf["ban"] else None
    wid = cl.tuan_id(now.date())
    tuan = st["etf"]["tuan"].get(wid)
    tin_hieu = {
        "cap_nhat": now.strftime("%Y-%m-%d %H:%M"),
        "trong_phien": phien_lo_le(now),
        "tham_so": cl.THAM_SO,
        "A": {"inav": inav, "gia_tran": tran, "so_le": le_etf, "so_chan": chan_etf,
              "chenh_ban_pct": round((g_ban / inav["inav"] - 1) * 100, 2) if g_ban and inav else None,
              "mua_duoc": bool(g_ban and tran and g_ban <= tran),
              "tuan": {"id": wid, "ngan_sach": tuan["ngan_sach"], "da_chi": tuan["da_chi"], "kl": tuan["kl"]} if tuan else None},
        "B": {"thang": mid, "trang_thai": trang_thai, "ngay_diem": ngay_diem, "muc_tieu": muc_tieu, "chi_tiet": chi_tiet},
        "loai_tru": sorted(loai_tru),
        "bao_cao": bc,
        "nhat_ky": nhat_ky,
    }
    ghi(OUT / "so.json", st)
    ghi(OUT / "tin_hieu.json", tin_hieu)
    log(f"Rổ {mid} ({trang_thai}): {', '.join(muc_tieu)} | loại trừ: {', '.join(sorted(loai_tru))} | {len(st['lenh'])} lệnh giấy")


if __name__ == "__main__":
    main()
