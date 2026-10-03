"""Tổng hợp tuần về biến động danh mục ETF ngoại và các thay đổi top 10 quỹ mở trong nước.
Ghi assets/data/tong_hop_tuan.json (cho trang Radar) và một bài trong ban-tin/_posts/ (dùng làm bản tin, gửi Zalo/Telegram...).
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data"
BAN_TIN = ROOT / "ban-tin" / "_posts"
SITE = "https://quachhieu2013.github.io/chay-review"
SO_NGAY = 7


def _vn(n, d=0):
    s = f"{abs(n):,.{d}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if n < 0 else "") + s


def _doc(path, mac_dinh):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return mac_dinh


def _d(s):
    return date.fromisoformat(s)


def tinh(ls, gia, cty, canh_bao, hom_nay):
    """Trả dict tổng hợp tuần, hoặc None nếu chưa đủ lịch sử (cần hai bản công bố cách nhau ít nhất 7 ngày)."""
    tong, theo_quy, tu_ngay, den_ngay = {}, [], None, None
    for ma, dsach in ls["nn"].items():
        dsach = [x for x in dsach if x.get("so_cp") is not None]
        if len(dsach) < 2:
            continue
        b = dsach[-1]
        # quỹ công bố hằng tháng (Vanguard) cách nhau quá xa nên không đưa vào tổng hợp tuần; chúng đã có trong mục cảnh báo
        a = next((x for x in reversed(dsach[:-1]) if SO_NGAY <= (_d(b["ngay"]) - _d(x["ngay"])).days <= 2 * SO_NGAY), None)
        if not a or (_d(hom_nay) - _d(b["ngay"])).days > 35:
            continue
        gt_quy = 0.0
        for m in set(a["so_cp"]) | set(b["so_cp"]):
            dcp = b["so_cp"].get(m, 0) - a["so_cp"].get(m, 0)
            g = gia.get(m)
            if not dcp or not g:
                continue
            x = tong.setdefault(m, {"ma": m, "ten": cty.get(m, (m, ""))[0], "gt": 0.0, "quy": []})
            x["gt"] += dcp * g
            x["quy"].append(ma)
            gt_quy += dcp * g
        theo_quy.append({"quy": ma, "tu": a["ngay"], "den": b["ngay"], "rong": round(gt_quy)})
        tu_ngay = min(tu_ngay or a["ngay"], a["ngay"])
        den_ngay = max(den_ngay or b["ngay"], b["ngay"])
    if not theo_quy:
        return None
    ds = sorted(tong.values(), key=lambda x: -x["gt"])
    mua = [{"ma": x["ma"], "ten": x["ten"], "gt": round(x["gt"]), "quy": x["quy"]} for x in ds if x["gt"] > 0][:8]
    ban = [{"ma": x["ma"], "ten": x["ten"], "gt": round(x["gt"]), "quy": x["quy"]} for x in reversed(ds) if x["gt"] < 0][:8]

    # quỹ mở nội: các quỹ vừa công bố danh mục mới trong tuần
    dau_tuan = (_d(hom_nay) - timedelta(days=SO_NGAY)).isoformat()
    cd = {}
    for q, dsach in ls["mo"].items():
        if len(dsach) < 2 or dsach[-1]["ngay"] < dau_tuan:
            continue
        a, b = dsach[-2], dsach[-1]
        for m in set(a["pct"]) | set(b["pct"]):
            pa, pb = a["pct"].get(m), b["pct"].get(m)
            diem = 0
            if pa is None:
                diem = 1
            elif pb is None:
                diem = -1
            elif pb - pa >= 0.3:
                diem = 1
            elif pa - pb >= 0.3:
                diem = -1
            if diem:
                cd[m] = cd.get(m, 0) + diem
    tang = sorted(((m, v) for m, v in cd.items() if v > 0), key=lambda t: -t[1])[:6]
    giam = sorted(((m, v) for m, v in cd.items() if v < 0), key=lambda t: t[1])[:6]
    so_quy_mo = sum(1 for dsach in ls["mo"].values() if len(dsach) >= 2 and dsach[-1]["ngay"] >= dau_tuan)
    ds_cb = [x for x in canh_bao if x["ngay"] >= dau_tuan][:10]
    return {"tu": tu_ngay, "den": den_ngay, "tong_mua": round(sum(x["gt"] for x in ds if x["gt"] > 0)),
            "tong_ban": round(sum(x["gt"] for x in ds if x["gt"] < 0)), "mua": mua, "ban": ban, "theo_quy": theo_quy,
            "mo_tang": [{"ma": m, "diem": v} for m, v in tang], "mo_giam": [{"ma": m, "diem": v} for m, v in giam],
            "so_quy_mo_moi": so_quy_mo, "canh_bao": [{"tieu_de": x["tieu_de"], "ngay": x["ngay"]} for x in ds_cb]}


def van_ban(t):
    """Bản tin dạng chữ thuần, dán được vào Zalo/Telegram/email."""
    ng = lambda s: f"{s[8:]}/{s[5:7]}"
    dong = [f"BIẾN ĐỘNG DANH MỤC QUỸ TUẦN {ng(t['tu'])}–{ng(t['den'])}", ""]
    dong.append(f"ETF ngoại: giá trị quy đổi của lượng nắm giữ công bố tăng là {_vn(t['tong_mua'] / 1e9, 1)} tỷ đồng; giảm là {_vn(abs(t['tong_ban']) / 1e9, 1)} tỷ đồng (dùng giá hiện tại, các quỹ có ngày chốt khác nhau).")
    if t["mua"]:
        dong.append("Mức tăng quy đổi lớn nhất: " + ", ".join(f"{x['ma']} {_vn(x['gt'] / 1e9, 1)} tỷ" for x in t["mua"][:5]) + ".")
    if t["ban"]:
        dong.append("Mức giảm quy đổi lớn nhất: " + ", ".join(f"{x['ma']} {_vn(abs(x['gt']) / 1e9, 1)} tỷ" for x in t["ban"][:5]) + ".")
    if t["mo_tang"] or t["mo_giam"]:
        dong.append(f"Quỹ mở trong nước ({t['so_quy_mo_moi']} quỹ vừa cập nhật danh mục): "
                    + ("tăng hiện diện/tỷ trọng công bố " + ", ".join(x["ma"] for x in t["mo_tang"]) if t["mo_tang"] else "")
                    + ("; " if t["mo_tang"] and t["mo_giam"] else "")
                    + ("giảm hiện diện/tỷ trọng công bố " + ", ".join(x["ma"] for x in t["mo_giam"]) if t["mo_giam"] else "") + ".")
    for x in t["canh_bao"][:4]:
        dong.append("• " + x["tieu_de"])
    dong += ["", f"Chi tiết: {SITE}/phan-tich/", "Chênh lệch danh mục không xác nhận giao dịch, dòng vốn hay động cơ; không phải khuyến nghị đầu tư."]
    return "\n".join(dong)


def ban_tin_md(t):
    ng = lambda s: f"{s[8:]}/{s[5:7]}"
    bang = lambda ds: "\n".join(f"| {x['ma']} | {x['ten']} | {_vn(x['gt'] / 1e9, 1)} | {', '.join(x['quy'])} |" for x in ds) or "| – | – | – | – |"
    quy = "\n".join(f"- **{q['quy']}**: {_vn(q['rong'] / 1e9, 1)} tỷ đồng ròng ({ng(q['tu'])} → {ng(q['den'])})" for q in t["theo_quy"])
    cb = "\n".join(f"- {x['tieu_de']} ({ng(x['ngay'])})" for x in t["canh_bao"]) or "- Không có cảnh báo nào trong tuần."
    mo = ""
    if t["mo_tang"] or t["mo_giam"]:
        mo = (f"\n## Quỹ mở trong nước\n\n{t['so_quy_mo_moi']} quỹ vừa cập nhật danh mục. "
              + ("**Mã mới xuất hiện trong top 10 hoặc tăng tỷ trọng công bố:** " + ", ".join(x["ma"] for x in t["mo_tang"]) + ". " if t["mo_tang"] else "")
              + ("**Mã không còn trong top 10 hoặc giảm tỷ trọng công bố:** " + ", ".join(x["ma"] for x in t["mo_giam"]) + "." if t["mo_giam"] else "") + "\n")
    return f"""Giá trị quy đổi theo giá hiện tại của lượng cổ phiếu Việt Nam được ETF ngoại công bố tăng là **{_vn(t['tong_mua'] / 1e9, 1)} tỷ đồng**, lượng công bố giảm là **{_vn(abs(t['tong_ban']) / 1e9, 1)} tỷ đồng** trong các kỳ so sánh gần nhất. Khoảng ngày cụ thể khác nhau theo từng quỹ (xem mục bên dưới), vì vậy không diễn giải đây là dòng tiền tuần hay giá trị giao dịch.

## Mã có lượng công bố tăng quy đổi lớn nhất

| Mã | Tên | Giá trị (tỷ đồng) | Quỹ |
|---|---|---:|---|
{bang(t['mua'])}

## Mã có lượng công bố giảm quy đổi lớn nhất

| Mã | Tên | Giá trị (tỷ đồng) | Quỹ |
|---|---|---:|---|
{bang(t['ban'])}

## Kỳ so sánh theo từng quỹ

{quy}
{mo}
## Cảnh báo trong tuần

{cb}

[Xem Radar biến động danh mục]({{{{ '/phan-tich/' | relative_url }}}}).

---

*Tính từ chênh lệch số lượng nắm giữ từng quỹ–mã, quy đổi theo giá hiện tại. Ngày chốt khác nhau; chia/tách, hoán đổi hoặc sự kiện doanh nghiệp có thể ảnh hưởng số lượng. Không xác nhận giao dịch hoặc dòng vốn; không phải khuyến nghị đầu tư.*
"""


def xu_ly(ls, gia, cty, ghi_json, hom_nay, gio):
    """Ghi tong_hop_tuan.json và bài bản tin (từ chiều thứ Sáu). Trả tổng hợp hoặc None."""
    canh_bao = _doc(OUT / "canh_bao.json", {"ds": []})["ds"]
    t = tinh(ls, gia, cty, canh_bao, hom_nay)
    if t is None:
        return None
    t["van_ban"] = van_ban(t)
    cu = _doc(OUT / "tong_hop_tuan.json", {})
    if {k: v for k, v in cu.items() if k not in ("cap_nhat", "cap_nhat_luc")} != t:
        ghi_json(OUT / "tong_hop_tuan.json", {**t, "cap_nhat": hom_nay, "cap_nhat_luc": gio})
    bay_gio = datetime.now(timezone(timedelta(hours=7)))
    thu6 = (date.fromisoformat(hom_nay) + timedelta(days=4 - date.fromisoformat(hom_nay).weekday()))
    if date.fromisoformat(hom_nay).weekday() >= 4 and (bay_gio.weekday() > 4 or bay_gio.hour >= 16):
        tuan = thu6.isocalendar()[1]
        path = BAN_TIN / f"{thu6.isoformat()}-bien-dong-danh-muc-quy-tuan-{tuan:02d}.md"
        ng = lambda s: f"{s[8:]}/{s[5:7]}/{s[:4]}"
        noi_dung = f"""---
title: "Biến động danh mục quỹ tuần {tuan}: cập nhật ETF ngoại và quỹ mở"
description: "Tổng hợp biến động lượng nắm giữ công bố của ETF ngoại và tỷ trọng top 10 quỹ mở; kỳ danh mục khác nhau theo từng quỹ."
chu_de: Bản tin
hinh: sao
phut_doc: 2
image: /assets/img/og-ban-tin.png
tu_dong: true
---

""" + ban_tin_md(t)
        BAN_TIN.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != noi_dung:
            path.write_text(noi_dung, encoding="utf-8")
            ghi_json.__globals__["DA_GHI"] = True
    return t
