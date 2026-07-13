# -*- coding: utf-8 -*-
"""salarylab net-salary engine (Python, stdlib only).

Mirror of js/salary.js — the two engines MUST behave identically.
Single source of truth: data/rates.json (2026 rates + 간이세액표 원본).

계산 규약
- 월 급여 = 연봉 // 12 (원 단위 절사)
- 비과세 식대는 월 한도(rates.nonTaxable.mealMonthlyCap)와 월 급여를 넘지 않는 범위로 클램프
- 4대보험·지방소득세는 10원 미만 절사, 곱셈은 전부 정수 연산(부동소수점 오차 배제)
- 소득세는 근로소득 간이세액표(소득세법 시행령 별표2, 2026.2.27 개정) 원본 룩업,
  월급여 1,000만원 초과 구간은 별표2의 초과 산식, 100% 원천징수 기준
- 간이세액표 열 = 공제대상가족 수(본인 포함) + 8~20세 자녀 수, 11명 초과는 별표2 제4호 외삽
- 8~20세 자녀가 있으면 자녀수별 공제액 차감(음수면 0원)
"""
import json
import os

_RATE_SCALE = 1_000_000  # fixed-point scale for rate arithmetic

_default_data = None


def _data_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "data", "rates.json")


def load_data(path=None):
    """Load rates.json (defaults to the repo copy) and cache it."""
    global _default_data
    with open(path or _data_path(), encoding="utf-8") as f:
        data = json.load(f)
    _validate_data(data)
    _default_data = data
    return data


def _validate_data(data):
    if not isinstance(data, dict):
        raise ValueError("rates data must be an object")
    for key in ("pension", "health", "care", "employment", "incomeTax",
                "localIncomeTax", "nonTaxable"):
        if key not in data:
            raise ValueError(f"rates data missing key: {key}")
    itx = data["incomeTax"]
    if not itx.get("rows") or len(itx["rows"][0]) != 12:
        raise ValueError("incomeTax.rows malformed")
    if len(itx.get("exactTop", [])) != 11:
        raise ValueError("incomeTax.exactTop malformed")


def _get_data(data):
    if data is not None:
        _validate_data(data)
        return data
    if _default_data is None:
        load_data()
    return _default_data


def _floor10(n):
    return (int(n) // 10) * 10


def _rate_mul(amount, rate):
    """floor(amount * rate) using integer fixed-point math."""
    num = round(rate * _RATE_SCALE)
    return (amount * num) // _RATE_SCALE


def _pension(taxable, p):
    base = min(max(taxable, p["baseMonthlyMin"]), p["baseMonthlyMax"])
    return _floor10(_rate_mul(base, p["workerRate"]))


def _health(taxable, h):
    prem = _floor10(_rate_mul(taxable, h["workerRate"]))
    return min(max(prem, h["workerMonthlyPremiumMin"]), h["workerMonthlyPremiumMax"])


def _care(health_premium, c):
    num = round(c["incomeRate"] * _RATE_SCALE)
    den = round(c["healthRateRef"] * _RATE_SCALE)
    return _floor10((health_premium * num) // den)


def _employment(taxable, e):
    return _floor10(_rate_mul(taxable, e["workerRate"]))


def _table_cell(cells10, families):
    """cells10: list of 11 amounts (families 1..11). Extrapolate beyond 11 (별표2 제4호)."""
    if families <= 11:
        return cells10[families - 1]
    t10, t11 = cells10[9], cells10[10]
    return max(0, t11 - (t10 - t11) * (families - 11))


def _income_tax(taxable, dependents, children, itx):
    families = dependents + children  # 간이세액표 열: 공제대상가족 수 + 8~20세 자녀 수
    rows = itx["rows"]
    if taxable < rows[0][0] * 1000:
        tax = 0
    elif taxable < 10_000_000:
        # binary search: greatest row with lowerK*1000 <= taxable
        lo, hi = 0, len(rows) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if rows[mid][0] * 1000 <= taxable:
                lo = mid
            else:
                hi = mid - 1
        tax = _table_cell(rows[lo][1:], families)
    else:
        base = _table_cell(itx["exactTop"], families)
        if taxable == 10_000_000:
            tax = base
        else:
            tax = None
            for br in itx["over10m"]:
                upto = br["uptoK"]
                if upto is None or taxable <= upto * 1000:
                    over = taxable - br["overK"] * 1000
                    fnum = round(br["factor"] * 100)
                    rnum = round(br["rate"] * 100)
                    tax = base + br["baseConst"] + (over * fnum * rnum) // 10000
                    break
            if tax is None:  # pragma: no cover - last bracket is open-ended
                raise ValueError("no over10m bracket matched")
    if children > 0 and tax > 0:
        cd = itx["childDeduction"]
        if children == 1:
            tax -= cd["one"]
        else:
            tax -= cd["two"] + cd["perExtraOverTwo"] * (children - 2)
        if tax < 0:
            tax = 0
    return _floor10(tax)


def compute_net(annual, dependents=1, children=0, meal_allowance=200000, data=None):
    """연봉(원) → 월/연 실수령액 및 공제 내역. 전 항목 원 단위 int.

    annual: 연봉(원), 세전. dependents: 본인 포함 공제대상 가족 수(>=1).
    children: 8~20세 자녀 수(공제대상가족에 포함되어 있어야 함).
    meal_allowance: 월 비과세 식대(원). 0이면 미적용, 한도 초과분은 한도로 클램프.
    """
    d = _get_data(data)

    if not isinstance(annual, int) or isinstance(annual, bool):
        raise TypeError("annual must be an int (KRW)")
    if annual < 0:
        raise ValueError("annual must be >= 0")
    if not isinstance(dependents, int) or dependents < 1:
        raise ValueError("dependents must be an int >= 1 (본인 포함)")
    if not isinstance(children, int) or children < 0:
        raise ValueError("children must be an int >= 0")
    if children > dependents - 1:
        raise ValueError("children must be <= dependents - 1 (자녀도 공제대상가족에 포함)")
    if not isinstance(meal_allowance, int) or meal_allowance < 0:
        raise ValueError("meal_allowance must be an int >= 0")

    monthly_gross = annual // 12
    meal = min(meal_allowance, d["nonTaxable"]["mealMonthlyCap"], monthly_gross)
    taxable = monthly_gross - meal

    pension = _pension(taxable, d["pension"])
    health = _health(taxable, d["health"])
    care = _care(health, d["care"])
    employment = _employment(taxable, d["employment"])
    income_tax = _income_tax(taxable, dependents, children, d["incomeTax"])
    local_tax = _floor10(_rate_mul(income_tax, d["localIncomeTax"]["rateOfIncomeTax"]))

    total = pension + health + care + employment + income_tax + local_tax
    monthly_net = monthly_gross - total

    return {
        "monthlyGross": monthly_gross,
        "taxableMonthly": taxable,
        "pension": pension,
        "health": health,
        "care": care,
        "employment": employment,
        "incomeTax": income_tax,
        "localTax": local_tax,
        "totalDeduction": total,
        "monthlyNet": monthly_net,
        "annualNet": monthly_net * 12,
    }


def fmt_krw(n):
    """1234567 -> '1,234,567' (원 단위 콤마)."""
    return f"{int(n):,}"


def fmt_manwon(n):
    """45000000 -> '4,500만' / 125000000 -> '1억 2,500만' (만 미만 절사)."""
    n = int(n)
    sign = "-" if n < 0 else ""
    man = abs(n) // 10000
    eok, rest = divmod(man, 10000)
    if eok and rest:
        return f"{sign}{eok:,}억 {rest:,}만"
    if eok:
        return f"{sign}{eok:,}억"
    return f"{sign}{man:,}만"


def _dump_cross_check(out_path):
    """Python 기준값 덤프 — node 엔진(tests/salary.test.mjs)이 완전 일치 비교."""
    points = []
    for annual in range(10_000_000, 200_000_001, 1_000_000):
        points.append({
            "annual": annual,
            "cases": [
                {"opts": {"dependents": 1, "children": 0, "mealAllowance": 200000},
                 "result": compute_net(annual)},
                {"opts": {"dependents": 4, "children": 2, "mealAllowance": 0},
                 "result": compute_net(annual, dependents=4, children=2, meal_allowance=0)},
            ],
        })
    payload = {"generatedBy": "scripts/salary.py --dump-cross-check", "points": points}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"wrote {out_path} ({len(points)} annual points x 2 cases)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--dump-cross-check":
        _dump_cross_check(sys.argv[2])
    elif len(sys.argv) == 2:
        r = compute_net(int(sys.argv[1]))
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("usage: salary.py <annual>  |  salary.py --dump-cross-check <out.json>")
