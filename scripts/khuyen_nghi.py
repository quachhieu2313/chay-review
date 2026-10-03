"""Build an experimental, transparent stock-ranking dataset."""
import json
import math
import re
from bisect import bisect_right
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
CP_DIR = DATA / "cp"
WEIGHTS = {"dong_luong": 30, "chat_luong": 25, "quy": 20, "dinh_gia": 15, "rui_ro": 10}
HORIZONS = {"3m": 63, "6m": 126}
MIN_HISTORY = 253
MAX_PRICE_AGE_DAYS = 5


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def percentile_scores(values, higher_is_better=True, groups=None):
    """Return tied mid-ranks from 0 to 100; optionally rank within peer groups."""
    groups = groups or {}
    by_group = {}
    for ticker, value in values.items():
        if value is not None:
            by_group.setdefault(groups.get(ticker, ""), []).append((ticker, value))

    result = {}
    global_values = [(ticker, value) for ticker, value in values.items() if value is not None]
    for ticker, value in global_values:
        group = groups.get(ticker, "")
        peers = by_group.get(group, [])
        if len(peers) < 5:
            peers = global_values
        less = sum(1 for _, peer in peers if peer < value)
        equal = sum(1 for _, peer in peers if peer == value)
        score = 100 * (less + 0.5 * equal) / len(peers)
        result[ticker] = score if higher_is_better else 100 - score
    return result


def average(values):
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def price_metrics(record):
    dates = record.get("d") or []
    closes = [number(value) for value in record.get("c") or []]
    volumes = [number(value) for value in record.get("v") or []]
    paired = [(day, close, volumes[i] if i < len(volumes) else None)
              for i, (day, close) in enumerate(zip(dates, closes))
              if close is not None and close > 0]
    if len(paired) < MIN_HISTORY:
        return None

    days = [row[0] for row in paired]
    prices = [row[1] for row in paired]
    current = prices[-1]
    returns = {
        "3m": current / prices[-1 - HORIZONS["3m"]] - 1,
        "6m": current / prices[-1 - HORIZONS["6m"]] - 1,
    }
    daily_returns = [prices[i] / prices[i - 1] - 1 for i in range(max(1, len(prices) - 252), len(prices))]
    mean_return = average(daily_returns)
    variance = average([(value - mean_return) ** 2 for value in daily_returns]) if mean_return is not None else None
    volatility = math.sqrt(variance) * math.sqrt(252) * 100 if variance is not None else None

    year_prices = prices[-253:]
    high_water = year_prices[0]
    max_drawdown = 0.0
    for price in year_prices:
        high_water = max(high_water, price)
        max_drawdown = min(max_drawdown, price / high_water - 1)

    avg_volume = average([row[2] for row in paired[-20:] if row[2] is not None and row[2] >= 0])
    ma50 = average(prices[-50:])
    ma200 = average(prices[-200:])
    return {
        "ngay": days[-1],
        "gia": current,
        "returns": returns,
        "ma50": ma50,
        "ma200": ma200,
        "volatility": volatility,
        "drawdown": max_drawdown * 100,
        "avg_volume": avg_volume,
        "days": days,
        "closes": prices,
    }


def quarter_end(period):
    if not isinstance(period, str):
        return None
    match = re.search(r"(?:(\d{4})\s*Q([1-4])|Q([1-4])\s*(\d{4}))", period, re.I)
    if not match:
        return None
    year = int(match.group(1) or match.group(4))
    quarter = int(match.group(2) or match.group(3))
    month = quarter * 3
    day = (date(year + (month == 12), 1, 1) - date(year, month, 1)).days if month == 12 else (
        date(year, month + 1, 1) - date(year, month, 1)
    ).days
    return date(year, month, day)


def score_universe(rows):
    tickers = [row["ma"] for row in rows]
    groups = {row["ma"]: row["nganh"] for row in rows}
    metric_values = {
        "roe": {row["ma"]: row["roe"] for row in rows},
        "margin": {row["ma"]: row["margin"] for row in rows},
        "pe": {row["ma"]: row["pe"] for row in rows},
        "pb": {row["ma"]: row["pb"] for row in rows},
        "volatility": {row["ma"]: row["volatility"] for row in rows},
        "drawdown": {row["ma"]: abs(row["drawdown"]) if row["drawdown"] is not None else None for row in rows},
        "funds": {row["ma"]: row["so_quy"] for row in rows},
        "etfs": {row["ma"]: row["so_etf"] for row in rows},
        "fund_weight": {row["ma"]: row["fund_weight"] for row in rows},
        "momentum_3m": {row["ma"]: row["returns"]["3m"] for row in rows},
        "momentum_6m": {row["ma"]: row["returns"]["6m"] for row in rows},
    }
    ranked = {
        "roe": percentile_scores(metric_values["roe"], groups=groups),
        "margin": percentile_scores(metric_values["margin"], groups=groups),
        "pe": percentile_scores(metric_values["pe"], higher_is_better=False, groups=groups),
        "pb": percentile_scores(metric_values["pb"], higher_is_better=False, groups=groups),
        "volatility": percentile_scores(metric_values["volatility"], higher_is_better=False),
        "drawdown": percentile_scores(metric_values["drawdown"], higher_is_better=False),
        "funds": percentile_scores(metric_values["funds"]),
        "etfs": percentile_scores(metric_values["etfs"]),
        "fund_weight": percentile_scores(metric_values["fund_weight"]),
        "momentum_3m": percentile_scores(metric_values["momentum_3m"]),
        "momentum_6m": percentile_scores(metric_values["momentum_6m"]),
    }

    for row in rows:
        ticker = row["ma"]
        row["quality"] = average([
            ranked["roe"].get(ticker),
            100.0 if row["eps"] is not None and row["eps"] > 0 else (
                0.0 if row["eps"] is not None else None
            ),
            ranked["margin"].get(ticker),
        ])
        row["value"] = average([ranked["pe"].get(ticker), ranked["pb"].get(ticker)])
        row["fund_score"] = average([
            ranked["funds"].get(ticker),
            ranked["etfs"].get(ticker),
            ranked["fund_weight"].get(ticker),
        ])
        row["risk"] = average([ranked["volatility"].get(ticker), ranked["drawdown"].get(ticker)])
        row["trend"] = 100 * average([
            1 if row["gia"] > row["ma50"] else 0,
            1 if row["gia"] > row["ma200"] else 0,
        ])
        row["momentum"] = {
            "3m": 0.75 * ranked["momentum_3m"][ticker] + 0.25 * row["trend"],
            "6m": 0.75 * ranked["momentum_6m"][ticker] + 0.25 * row["trend"],
        }

    for row in rows:
        for horizon in HORIZONS:
            factors = {
                "dong_luong": row["momentum"][horizon],
                "chat_luong": row["quality"],
                "quy": row["fund_score"],
                "dinh_gia": row["value"],
                "rui_ro": row["risk"],
            }
            available_weight = sum(WEIGHTS[name] for name, score in factors.items() if score is not None)
            if available_weight < 65:
                row.setdefault("scores", {})[horizon] = None
            else:
                row.setdefault("scores", {})[horizon] = sum(
                    WEIGHTS[name] * score for name, score in factors.items() if score is not None
                ) / available_weight
            row.setdefault("components", {})[horizon] = factors
            row.setdefault("coverage", {})[horizon] = available_weight
    return rows


def backtest_momentum(histories, index_dates, index_closes, lookback, horizon, max_periods=36):
    """Walk-forward, price-only baseline. Composite fundamentals/holdings are not tested."""
    if len(index_dates) != len(index_closes) or len(index_dates) <= lookback + horizon:
        return {"so_ky": 0}
    start = max(lookback, len(index_dates) - 756)
    end = len(index_dates) - horizon
    samples = []
    for anchor in range(start, end, 21):
        anchor_date = index_dates[anchor]
        signals = []
        for ticker, history in histories.items():
            days, closes = history
            index = bisect_right(days, anchor_date) - 1
            if index < lookback or index + horizon >= len(closes):
                continue
            if (date.fromisoformat(anchor_date) - date.fromisoformat(days[index])).days > 5:
                continue
            past = closes[index] / closes[index - lookback] - 1
            future = closes[index + horizon] / closes[index] - 1
            signals.append((ticker, past, future))
        if len(signals) < 20:
            continue
        signals.sort(key=lambda row: row[1])
        winners = signals[-10:]
        losers = signals[:10]
        benchmark = index_closes[anchor + horizon] / index_closes[anchor] - 1
        samples.append({
            "date": anchor_date,
            "top": average([row[2] for row in winners]),
            "bottom": average([row[2] for row in losers]),
            "benchmark": benchmark,
        })
    if max_periods and len(samples) > max_periods:
        samples = samples[-max_periods:]
    if not samples:
        return {"so_ky": 0}
    top = average([sample["top"] for sample in samples])
    bottom = average([sample["bottom"] for sample in samples])
    benchmark = average([sample["benchmark"] for sample in samples])
    return {
        "so_ky": len(samples),
        "tu": samples[0]["date"],
        "den": samples[-1]["date"],
        "top_tb_pct": round(top * 100, 2),
        "day_duoi_tb_pct": round(bottom * 100, 2),
        "vnindex_tb_pct": round(benchmark * 100, 2),
        "top_chenh_vnindex_pct": round((top - benchmark) * 100, 2),
        "top_hon_vnindex_pct": round(
            100 * sum(sample["top"] > sample["benchmark"] for sample in samples) / len(samples), 1
        ),
        "top_duong_pct": round(100 * sum(sample["top"] > 0 for sample in samples) / len(samples), 1),
    }


def warnings_for(row, fund_date, price_date):
    warnings = []
    if row["eps"] is not None and row["eps"] <= 0:
        warnings.append("EPS không dương")
    if row["pe"] is not None and row["pe"] > 30:
        warnings.append("P/E cao hơn 30 lần")
    if row["beta"] is not None and row["beta"] > 1.5:
        warnings.append("Beta cao")
    if row["drawdown"] is not None and row["drawdown"] <= -30:
        warnings.append("Sụt giảm tối đa 1 năm vượt 30%")
    if row["gia"] < row["ma50"]:
        warnings.append("Giá dưới MA50")
    if row["avg_volume"] is not None and row["avg_volume"] < 100000:
        warnings.append("Thanh khoản 20 phiên thấp")
    if row["fund_weight_max"] is not None and row["fund_weight_max"] >= 10:
        warnings.append("Tỷ trọng quỹ công bố từ 10% NAV trở lên")
    if row["fund_count"] is None:
        warnings.append("Không có dữ liệu danh mục quỹ")
    elif row["fund_count"] == 0:
        warnings.append("Không thấy trong danh mục quỹ theo dữ liệu hiện có")
    if row["fund_count"] is not None and not fund_date:
        warnings.append("Thiếu ngày chốt danh mục quỹ")
    elif fund_date:
        try:
            age = (date.fromisoformat(price_date) - date.fromisoformat(fund_date)).days
            if age < 0:
                warnings.append("Danh mục quỹ chốt sau ngày giá")
            elif age > 180:
                warnings.append("Dữ liệu danh mục quỹ đã cũ")
        except ValueError:
            warnings.append("Không xác định được độ mới danh mục quỹ")
    if row["period"] is None:
        warnings.append("Thiếu kỳ báo cáo tài chính")
    return warnings


def build_dataset():
    market = read_json(DATA / "co_phieu.json", {})
    funds = read_json(DATA / "quy_nam_giu.json", {})
    index = read_json(DATA / "chi_so" / "VNINDEX.json", {})
    if not isinstance(market, dict) or not isinstance(market.get("co_phieu"), list) or not market["co_phieu"]:
        raise RuntimeError("Thiếu danh sách cổ phiếu hiện tại trong assets/data/co_phieu.json")
    if not isinstance(funds, dict) or not isinstance(funds.get("co_phieu"), list):
        raise RuntimeError("Thiếu dữ liệu danh mục quỹ trong assets/data/quy_nam_giu.json")
    if not isinstance(index, dict) or not isinstance(index.get("d"), list) or not isinstance(index.get("c"), list) or not index["d"]:
        raise RuntimeError("Thiếu lịch sử VN-Index trong assets/data/chi_so/VNINDEX.json")
    fund_by_ticker = {row["ma"]: row for row in funds.get("co_phieu", []) if row.get("ma")}
    market_rows = market.get("co_phieu", [])
    current_index_date = (index.get("d") or [""])[-1] or ""
    funds_available = bool(funds.get("ngay_den") and isinstance(funds.get("co_phieu"), list))
    rows = []
    histories = {}
    excluded = {"thieu_du_lieu_gia": 0, "lich_su_chua_du": 0, "gia_qua_cu": 0, "khong_phai_co_phieu": 0}

    for item in market_rows:
        ticker = item.get("ma")
        if not ticker:
            continue
        source = read_json(CP_DIR / f"{ticker}.json")
        if not source or source.get("loai") != "cp":
            excluded["thieu_du_lieu_gia" if source is None else "khong_phai_co_phieu"] += 1
            continue
        prices = price_metrics(source)
        if not prices:
            excluded["lich_su_chua_du"] += 1
            continue
        if not current_index_date:
            raise RuntimeError("VN-Index không có ngày dữ liệu mới nhất")
        try:
            price_age = (date.fromisoformat(current_index_date) - date.fromisoformat(prices["ngay"])).days
            if price_age < 0 or price_age > MAX_PRICE_AGE_DAYS:
                excluded["gia_qua_cu"] += 1
                continue
        except ValueError:
            excluded["gia_qua_cu"] += 1
            continue

        financial = source.get("co_ban") or {}
        report_period = financial.get("ky")
        report_date = quarter_end(report_period)
        report_age = (date.fromisoformat(prices["ngay"]) - report_date).days if report_date else None
        fundamentals_fresh = report_age is not None and 0 <= report_age <= 180
        eps = number(financial.get("eps")) if fundamentals_fresh else None
        roe = number(financial.get("roe")) if fundamentals_fresh else None
        margin = number(financial.get("bien_ln_rong")) if fundamentals_fresh else None
        bvps = number(financial.get("bvps")) if fundamentals_fresh else None
        pe = prices["gia"] / eps if eps and eps > 0 else None
        pb = prices["gia"] / bvps if bvps and bvps > 0 else None
        holding = fund_by_ticker.get(ticker, {})
        mutual_count = number(holding.get("so_quy")) if funds_available else None
        international_count = number(holding.get("so_quy_nn")) if funds_available else None
        fund_count = max(mutual_count or 0, international_count or 0) if funds_available else None
        etf_count = (number(holding.get("so_etf")) or 0) if funds_available else None
        declared_weights = [
            number(entry.get("pct"))
            for entry in (holding.get("quy_mo") or []) + (holding.get("quy_nn") or [])
            if number(entry.get("pct")) is not None
        ]
        fund_weight = average(declared_weights) if funds_available else None
        fund_weight_max = max(declared_weights) if declared_weights else None
        row = {
            "ma": ticker,
            "ten": item.get("ten") or source.get("ten") or ticker,
            "nganh": item.get("nganh") or source.get("nganh") or "Khác",
            "gia": prices["gia"],
            "ngay_gia": prices["ngay"],
            "returns": prices["returns"],
            "ma50": prices["ma50"],
            "ma200": prices["ma200"],
            "volatility": prices["volatility"],
            "drawdown": prices["drawdown"],
            "avg_volume": prices["avg_volume"],
            "eps": eps,
            "roe": roe,
            "margin": margin,
            "bvps": bvps,
            "pe": pe,
            "pb": pb,
            "beta": number(financial.get("beta")) if fundamentals_fresh else None,
            "period": report_period if fundamentals_fresh else None,
            "so_quy": fund_count,
            "so_etf": etf_count,
            "fund_count": fund_count + etf_count if fund_count is not None and etf_count is not None else None,
            "fund_weight": fund_weight,
            "fund_weight_max": fund_weight_max,
        }
        rows.append(row)
        histories[ticker] = (prices["days"], prices["closes"])

    score_universe(rows)
    if len(rows) < 20:
        raise RuntimeError(f"Chỉ có {len(rows)} mã đủ dữ liệu; cần ít nhất 20 mã để tạo hai danh sách top 10.")
    for row in rows:
        row["warnings"] = warnings_for(row, funds.get("ngay_den"), row["ngay_gia"])
        row["metrics"] = {
            "loi_nhuan_3m_pct": round(row["returns"]["3m"] * 100, 2),
            "loi_nhuan_6m_pct": round(row["returns"]["6m"] * 100, 2),
            "roe_pct": round(row["roe"], 2) if row["roe"] is not None else None,
            "pe": round(row["pe"], 2) if row["pe"] is not None else None,
            "pb": round(row["pb"], 2) if row["pb"] is not None else None,
            "bien_dong_nam_pct": round(row["volatility"], 2) if row["volatility"] is not None else None,
            "sut_giam_toi_da_1n_pct": round(row["drawdown"], 2) if row["drawdown"] is not None else None,
            "so_quy": row["so_quy"],
            "so_etf": row["so_etf"],
            "ty_trong_quy_tb_pct": round(row["fund_weight"], 2) if row["fund_weight"] is not None else None,
            "ty_trong_quy_max_pct": round(row["fund_weight_max"], 2) if row["fund_weight_max"] is not None else None,
        }
        row["ky_tai_chinh"] = row["period"]
        row["components"] = {
            horizon: {name: round(value, 1) if value is not None else None for name, value in values.items()}
            for horizon, values in row["components"].items()
        }
        row["scores"] = {
            horizon: round(value, 1) if value is not None else None
            for horizon, value in row["scores"].items()
        }
        row["coverage"] = row["coverage"]
        row.pop("returns")
        for key in ("gia", "ma50", "ma200", "volatility", "drawdown", "avg_volume", "eps", "roe", "margin", "bvps", "pe", "pb", "beta", "period", "fund_count", "fund_weight", "fund_weight_max", "quality", "fund_score", "risk", "value", "trend", "momentum"):
            row.pop(key, None)

    ranked = {}
    for horizon in HORIZONS:
        eligible = [row for row in rows if row["scores"].get(horizon) is not None]
        if len(eligible) < 20:
            raise RuntimeError(f"Chỉ có {len(eligible)} mã đủ độ bao phủ cho thời hạn {horizon}; cần ít nhất 20.")
        eligible.sort(key=lambda row: (row["scores"][horizon], row["ma"]))
        ranked[horizon] = {
            "mua": list(reversed(eligible[-10:])) if len(eligible) >= 20 else [],
            "ban": eligible[:10] if len(eligible) >= 20 else [],
        }

    backtests = {}
    index_dates = index.get("d") or []
    index_closes = [number(value) for value in index.get("c") or []]
    paired_index = [(day, close) for day, close in zip(index_dates, index_closes) if close is not None and close > 0]
    if len(paired_index) >= 2:
        index_dates, index_closes = map(list, zip(*paired_index))
        for horizon, lookback in HORIZONS.items():
            backtests[horizon] = backtest_momentum(histories, index_dates, index_closes, lookback, lookback)
    else:
        backtests = {horizon: {"so_ky": 0} for horizon in HORIZONS}

    analyzed = len(rows)
    return {
        "cap_nhat": current_index_date,
        "cap_nhat_quy": funds.get("ngay_den"),
        "vung_loc": "VN100 hiện tại",
        "so_ma_trong_ro": len(market_rows),
        "so_ma_phan_tich": analyzed,
        "ma_bi_loai": excluded,
        "nguon": [
            {"ten": "Vietcap (VCI)", "du_lieu": "Lịch sử giá và khối lượng hằng ngày"},
            {"ten": "KBS", "du_lieu": "Chỉ số tài chính quý gần nhất; P/E và P/B được tính từ giá đóng cửa"},
            {"ten": "Kim Chỉ Nam", "du_lieu": "Số quỹ/ETF có mã trong danh mục đã công bố"},
        ],
        "trong_so": WEIGHTS,
        "danh_sach": ranked,
        "backtest": backtests,
        "luu_y": [
            "Điểm tổng hợp là bộ lọc thử nghiệm, chưa được backtest toàn bộ; xếp hạng không phải dự báo chắc chắn hay khuyến nghị cá nhân.",
            "Backtest chỉ kiểm tra động lượng giá quá khứ, không gồm chỉ số tài chính hoặc dữ liệu quỹ lịch sử; universe dùng VN100 hiện tại nên có thiên lệch sống sót.",
            "Lợi nhuận backtest bỏ qua cổ tức, phí, thuế, trượt giá và thay đổi rổ; hiệu suất quá khứ không đảm bảo kết quả tương lai.",
            "Số quỹ nắm giữ không chứng minh quỹ vừa mua; danh mục có độ trễ công bố và độ bao phủ không đồng đều.",
        ],
    }


def cap_nhat():
    payload = build_dataset()
    target = DATA / "co_phieu_khuyen_nghi.json"
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") == content:
        print(f"{target.name} không đổi.")
        return False
    target.write_text(content, encoding="utf-8")
    print(f"Đã ghi {target.name}: {payload['so_ma_phan_tich']} mã; dữ liệu đến {payload['cap_nhat']}")
    return True


if __name__ == "__main__":
    cap_nhat()
