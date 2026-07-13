# -*- coding: utf-8 -*-
"""Unit + fixture tests for scripts/salary.py (stdlib unittest).

실행: python -m unittest discover tests  (repo root에서)
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import salary  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def floor10(n):
    return (n // 10) * 10


class TestComputeNetCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = salary.load_data()

    def test_known_table_cell_50m(self):
        # 연봉 5,000만, 식대 20만 → 과세 월급여 3,966,666 → 별표2 3,960~3,980 구간 1인 190,620
        r = salary.compute_net(50_000_000)
        self.assertEqual(r["taxableMonthly"], 3_966_666)
        self.assertEqual(r["incomeTax"], 190_620)
        self.assertEqual(r["localTax"], 19_060)

    def test_deduction_sum_and_net(self):
        for annual in (24_000_000, 50_000_000, 88_000_000, 150_000_000):
            r = salary.compute_net(annual)
            parts = (r["pension"] + r["health"] + r["care"] + r["employment"]
                     + r["incomeTax"] + r["localTax"])
            self.assertEqual(r["totalDeduction"], parts)
            self.assertEqual(r["monthlyNet"], r["monthlyGross"] - parts)
            self.assertEqual(r["annualNet"], r["monthlyNet"] * 12)

    def test_pension_upper_cap(self):
        # 과세 월급여가 기준소득월액 상한(659만)을 넘으면 상한 기준: 6,590,000×4.75%=313,025 → 313,020
        r = salary.compute_net(120_000_000, meal_allowance=0)
        self.assertEqual(r["taxableMonthly"], 10_000_000)
        self.assertEqual(r["pension"], 313_020)
        # 상한 바로 아래는 상한 미적용
        r2 = salary.compute_net(6_590_000 * 12, meal_allowance=0)
        self.assertEqual(r2["pension"], 313_020)
        r3 = salary.compute_net((6_590_000 - 100_000) * 12, meal_allowance=0)
        self.assertLess(r3["pension"], 313_020)

    def test_pension_lower_floor(self):
        # 과세 월급여 40만 < 하한 41만 → 410,000×4.75%=19,475 → 19,470
        r = salary.compute_net(4_800_000, meal_allowance=0)
        self.assertEqual(r["taxableMonthly"], 400_000)
        self.assertEqual(r["pension"], 19_470)

    def test_income_tax_zero_low_salary(self):
        # 간이세액표 최저 과세 구간(1,060천원) 미만은 소득세 0
        r = salary.compute_net(12_000_000, meal_allowance=0)  # 월 100만
        self.assertEqual(r["incomeTax"], 0)
        self.assertEqual(r["localTax"], 0)
        # 식대 적용 시 과세 월급여가 더 내려가도 0 유지
        r2 = salary.compute_net(12_000_000)
        self.assertEqual(r2["incomeTax"], 0)

    def test_income_tax_first_taxable_bracket(self):
        # 과세 월급여 1,060,000 → 첫 과세 구간 1인 1,040원
        r = salary.compute_net(1_060_000 * 12, meal_allowance=0)
        self.assertEqual(r["incomeTax"], 1_040)

    def test_exact_10m_row(self):
        r = salary.compute_net(120_000_000, meal_allowance=0)
        self.assertEqual(r["incomeTax"], 1_507_400)  # 별표2 '10,000천원' 행 1인
        # 바로 아래 구간(9,980~10,000천원)
        r2 = salary.compute_net(119_999_988, meal_allowance=0)
        self.assertEqual(r2["taxableMonthly"], 9_999_999)
        self.assertEqual(r2["incomeTax"], 1_503_990)

    def test_over_10m_formula_first_bracket(self):
        # 과세 월급여 12,000,000: 1,507,400 + 25,000 + 2,000,000×98%×35% = 2,218,400
        r = salary.compute_net(144_000_000, meal_allowance=0)
        expected = 1_507_400 + 25_000 + (2_000_000 * 98 * 35) // 10000
        self.assertEqual(r["incomeTax"], floor10(expected))
        self.assertEqual(r["localTax"], floor10(floor10(expected) // 10))

    def test_over_14m_formula_second_bracket(self):
        # 연봉 2억 → 과세 월급여 16,666,666 (식대 0)
        r = salary.compute_net(200_000_000, meal_allowance=0)
        over = 16_666_666 - 14_000_000
        expected = 1_507_400 + 1_397_000 + (over * 98 * 38) // 10000
        self.assertEqual(r["incomeTax"], floor10(expected))

    def test_dependents_reduce_tax(self):
        base = salary.compute_net(50_000_000)
        for dep in (2, 3, 4):
            r = salary.compute_net(50_000_000, dependents=dep)
            self.assertLess(r["incomeTax"], base["incomeTax"])
            base = r

    def test_child_deduction_amounts(self):
        itx = self.data["incomeTax"]
        # 자녀 수만 다르고 간이세액표 열(dependents+children)이 같도록 구성해 공제액만 검증
        r_col3 = salary.compute_net(60_000_000, dependents=3, children=0)
        r_child1 = salary.compute_net(60_000_000, dependents=2, children=1)
        self.assertEqual(r_child1["incomeTax"],
                         floor10(r_col3["incomeTax"] - itx["childDeduction"]["one"]))
        r_col5 = salary.compute_net(60_000_000, dependents=5, children=0)
        r_child2 = salary.compute_net(60_000_000, dependents=3, children=2)
        self.assertEqual(r_child2["incomeTax"],
                         floor10(r_col5["incomeTax"] - itx["childDeduction"]["two"]))

    def test_child_deduction_floors_at_zero(self):
        # 저연봉 + 자녀 2명 → 공제 후 음수 방지
        r = salary.compute_net(26_000_000, dependents=4, children=2, meal_allowance=0)
        self.assertGreaterEqual(r["incomeTax"], 0)

    def test_family_over_11_extrapolation(self):
        # 별표2 제4호: 11명 초과 → 11명 세액 - (10명 세액 - 11명 세액) × 초과 가족 수
        annual = 120_000_000
        r10 = salary.compute_net(annual, dependents=10, meal_allowance=0)
        r11 = salary.compute_net(annual, dependents=11, meal_allowance=0)
        r13 = salary.compute_net(annual, dependents=13, meal_allowance=0)
        expected = max(0, r11["incomeTax"] - (r10["incomeTax"] - r11["incomeTax"]) * 2)
        self.assertEqual(r13["incomeTax"], floor10(expected))

    def test_meal_allowance_clamped(self):
        # 한도(20만) 초과 요청은 한도로 클램프
        a = salary.compute_net(50_000_000, meal_allowance=500_000)
        b = salary.compute_net(50_000_000, meal_allowance=200_000)
        self.assertEqual(a, b)
        # 월급보다 큰 식대는 월급까지만
        c = salary.compute_net(1_200_000, meal_allowance=200_000)
        self.assertEqual(c["taxableMonthly"], 0)
        self.assertGreaterEqual(c["monthlyNet"], 0)

    def test_net_monotonic_in_annual(self):
        prev = None
        for annual in range(10_000_000, 200_000_001, 1_000_000):
            r = salary.compute_net(annual)
            if prev is not None:
                self.assertGreater(r["monthlyNet"], prev,
                                   msg=f"net not increasing at annual={annual}")
            prev = r["monthlyNet"]

    def test_all_values_are_int(self):
        r = salary.compute_net(55_555_555, dependents=3, children=1, meal_allowance=100_000)
        for k, v in r.items():
            self.assertIsInstance(v, int, msg=k)

    def test_input_validation(self):
        with self.assertRaises(TypeError):
            salary.compute_net(50_000_000.5)
        with self.assertRaises(ValueError):
            salary.compute_net(-1)
        with self.assertRaises(ValueError):
            salary.compute_net(50_000_000, dependents=0)
        with self.assertRaises(ValueError):
            salary.compute_net(50_000_000, children=-1)
        with self.assertRaises(ValueError):
            salary.compute_net(50_000_000, dependents=1, children=1)
        with self.assertRaises(ValueError):
            salary.compute_net(50_000_000, meal_allowance=-1)


class TestFormatters(unittest.TestCase):
    def test_fmt_krw(self):
        self.assertEqual(salary.fmt_krw(1234567), "1,234,567")
        self.assertEqual(salary.fmt_krw(0), "0")
        self.assertEqual(salary.fmt_krw(-9876543), "-9,876,543")

    def test_fmt_manwon(self):
        self.assertEqual(salary.fmt_manwon(45_000_000), "4,500만")
        self.assertEqual(salary.fmt_manwon(125_000_000), "1억 2,500만")
        self.assertEqual(salary.fmt_manwon(100_000_000), "1억")
        self.assertEqual(salary.fmt_manwon(9_990_000), "999만")
        self.assertEqual(salary.fmt_manwon(1_234_560_000), "12억 3,456만")
        self.assertEqual(salary.fmt_manwon(0), "0만")


class TestCrossCheckFixture(unittest.TestCase):
    """tests/fixtures/cross_check.json이 현재 엔진 출력과 완전 일치하는지 검증.

    (node 테스트가 같은 파일과 비교 → Python↔JS 완전 일치 보장)
    """

    def test_fixture_matches_engine(self):
        path = os.path.join(FIXTURES, "cross_check.json")
        self.assertTrue(os.path.exists(path),
                        "cross_check.json 없음 — python scripts/salary.py --dump-cross-check tests/fixtures/cross_check.json")
        with open(path, encoding="utf-8") as f:
            fixture = json.load(f)
        points = fixture["points"]
        self.assertEqual(len(points), 191)  # 1,000만~2억, 100만 단위
        for p in points:
            annual = p["annual"]
            for case in p["cases"]:
                o = case["opts"]
                r = salary.compute_net(annual, dependents=o["dependents"],
                                       children=o["children"],
                                       meal_allowance=o["mealAllowance"])
                self.assertEqual(r, case["result"], msg=f"annual={annual} opts={o}")


class TestExternalCrossCheck(unittest.TestCase):
    """외부 공개 2026 실수령액표와 대조 (부양가족 1인, 비과세 미적용, 오차 ±3,000원)."""

    TOLERANCE = 3000

    def test_external_points(self):
        path = os.path.join(FIXTURES, "external_check.json")
        self.assertTrue(os.path.exists(path), "external_check.json 없음")
        with open(path, encoding="utf-8") as f:
            fixture = json.load(f)
        tolerance = fixture.get("tolerance", self.TOLERANCE)
        sources = fixture["sources"]
        failures = []
        checked = 0
        for point in fixture["points"]:
            annual = point["annual"]
            for src_id, external_net in point["values"].items():
                a = sources[src_id]["assumptions"]
                r = salary.compute_net(annual, dependents=a["dependents"],
                                       children=a["children"],
                                       meal_allowance=a["mealAllowance"])
                diff = r["monthlyNet"] - external_net
                checked += 1
                if abs(diff) > tolerance:
                    failures.append(
                        f"annual={annual:,} engine={r['monthlyNet']:,} "
                        f"{src_id}={external_net:,} diff={diff:+,}")
        self.assertGreaterEqual(checked, 20, "외부 교차 지점이 20개 미만")
        self.assertEqual(failures, [],
                         msg="외부 표 대비 오차 초과:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
