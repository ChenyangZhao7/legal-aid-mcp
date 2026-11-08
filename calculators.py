from __future__ import annotations

from datetime import date, timedelta

from holidays import HolidayCalendar

DEADLINE_DAYS = {
    "appeal_judgment": 15,
    "appeal_ruling": 10,
    "answer": 15,
}


def _property_fee(amount: float) -> tuple[float, list[dict]]:
    if amount <= 10000:
        return 50.0, [{"range": "不超过1万元", "rate": "每件50元", "fee": 50.0}]

    fee = 50.0
    lower = 10000.0
    breakdown = [{"range": "不超过1万元", "rate": "每件50元", "fee": 50.0}]
    brackets = [
        (100000.0, 0.025),
        (200000.0, 0.02),
        (500000.0, 0.015),
        (1000000.0, 0.01),
        (2000000.0, 0.009),
        (5000000.0, 0.008),
        (10000000.0, 0.007),
        (20000000.0, 0.006),
        (float("inf"), 0.005),
    ]
    for upper, rate in brackets:
        if amount <= lower:
            break
        portion = min(amount, upper) - lower
        part = portion * rate
        fee += part
        breakdown.append(
            {
                "range": f"{lower:g}-{upper:g}" if upper != float("inf") else f"超过{lower:g}",
                "rate": f"{rate * 100:g}%",
                "fee": round(part, 2),
            }
        )
        lower = upper
    return round(fee, 2), breakdown


def litigation_fee(amount: float | None, case_type: str) -> dict:
    if case_type in {"财产案件"} or (case_type == "知识产权" and amount is not None):
        if amount is None or amount < 0:
            raise ValueError("财产案件需要非负的诉讼请求金额")
        fee, breakdown = _property_fee(float(amount))
        return {
            "case_type": case_type,
            "fee": fee,
            "fee_min": fee,
            "fee_max": fee,
            "breakdown": breakdown,
            "notes": ["按财产案件分段累计计算"],
        }

    if case_type == "劳动争议":
        return {
            "case_type": case_type,
            "fee": 10.0,
            "fee_min": 10.0,
            "fee_max": 10.0,
            "breakdown": [{"range": "劳动争议", "rate": "每件10元", "fee": 10.0}],
        }

    if case_type == "离婚":
        extra = max(float(amount or 0) - 200000, 0) * 0.005
        return {
            "case_type": case_type,
            "fee": round(50 + extra, 2),
            "fee_min": round(50 + extra, 2),
            "fee_max": round(300 + extra, 2),
            "breakdown": [
                {"range": "离婚案件", "rate": "50-300元", "fee": 50.0},
                *(
                    [{"range": "超过20万元部分", "rate": "0.5%", "fee": round(extra, 2)}]
                    if extra
                    else []
                ),
            ],
            "notes": ["幅度型收费，实际金额以当地标准为准"],
        }

    if case_type == "人格权":
        amount = float(amount or 0)
        extra = 0.0
        if amount > 50000:
            extra += (min(amount, 100000) - 50000) * 0.01
        if amount > 100000:
            extra += (amount - 100000) * 0.005
        return {
            "case_type": case_type,
            "fee": round(100 + extra, 2),
            "fee_min": round(100 + extra, 2),
            "fee_max": round(500 + extra, 2),
            "breakdown": [
                {"range": "人格权案件", "rate": "100-500元", "fee": 100.0},
                *(
                    [{"range": "损害赔偿", "rate": "1%/0.5%", "fee": round(extra, 2)}]
                    if extra
                    else []
                ),
            ],
            "notes": ["幅度型收费，实际金额以当地标准为准"],
        }

    if case_type == "知识产权":
        return {
            "case_type": case_type,
            "fee": 500.0,
            "fee_min": 500.0,
            "fee_max": 1000.0,
            "breakdown": [{"range": "无争议金额", "rate": "500-1000元", "fee": 500.0}],
            "notes": ["幅度型收费，实际金额以当地标准为准"],
        }

    if case_type == "行政-商标专利海事":
        return {
            "case_type": case_type,
            "fee": 100.0,
            "fee_min": 100.0,
            "fee_max": 100.0,
            "breakdown": [{"range": "商标、专利、海事行政案件", "rate": "每件100元", "fee": 100.0}],
        }

    if case_type == "行政-其他":
        return {
            "case_type": case_type,
            "fee": 50.0,
            "fee_min": 50.0,
            "fee_max": 50.0,
            "breakdown": [{"range": "其他行政案件", "rate": "每件50元", "fee": 50.0}],
        }

    if case_type == "其他非财产":
        return {
            "case_type": case_type,
            "fee": 50.0,
            "fee_min": 50.0,
            "fee_max": 100.0,
            "breakdown": [{"range": "其他非财产案件", "rate": "50-100元", "fee": 50.0}],
            "notes": ["幅度型收费，实际金额以当地标准为准"],
        }

    raise ValueError(f"不支持的案件类型：{case_type}")


def preservation_fee(amount: float | None) -> dict:
    if amount is None or amount <= 1000:
        return {
            "fee": 30.0,
            "capped": False,
            "breakdown": [{"range": "不超过1000元或不涉及财产数额", "rate": "每件30元", "fee": 30.0}],
        }

    amount = float(amount)
    fee = 30.0
    breakdown = [{"range": "不超过1000元", "rate": "每件30元", "fee": 30.0}]
    first = min(amount, 100000) - 1000
    if first > 0:
        part = first * 0.01
        fee += part
        breakdown.append({"range": "1000元-10万元", "rate": "1%", "fee": round(part, 2)})
    if amount > 100000:
        part = (amount - 100000) * 0.005
        fee += part
        breakdown.append({"range": "超过10万元", "rate": "0.5%", "fee": round(part, 2)})

    capped = fee > 5000
    return {
        "fee": 5000.0 if capped else round(fee, 2),
        "capped": capped,
        "breakdown": breakdown,
        "notes": ["保全费最高不超过5000元"] if capped else [],
    }


def deadline(
    start_date: date,
    days: int,
    day_type: str,
    holiday: HolidayCalendar,
) -> dict:
    if days <= 0:
        raise ValueError("期间天数必须大于 0")
    if day_type not in {"natural", "working"}:
        raise ValueError("day_type 必须是 natural 或 working")

    if day_type == "working":
        original = holiday.add_workdays(start_date, days)
    else:
        original = start_date + timedelta(days=days)

    adjusted = holiday.is_holiday(original)
    end = holiday.next_workday(original) if adjusted else original
    return {
        "start_date": start_date.isoformat(),
        "days": days,
        "day_type": day_type,
        "original_end_date": original.isoformat(),
        "end_date": end.isoformat(),
        "adjusted": adjusted,
        "holiday_source": holiday.source,
    }
