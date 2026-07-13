/**
 * Node tests for js/salary.js — Python 엔진과의 완전 일치 검증.
 *
 * 실행: node tests/salary.test.mjs  (repo root에서, 사전에
 *       python scripts/salary.py --dump-cross-check tests/fixtures/cross_check.json)
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { computeNet, setData, fmtKrw, fmtManwon } from "../js/salary.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");

const rates = JSON.parse(readFileSync(join(ROOT, "data", "rates.json"), "utf-8"));
setData(rates);

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
  } catch (err) {
    failed += 1;
    console.error(`FAIL: ${name}`);
    console.error(`  ${err.message}`);
  }
}

const floor10 = (n) => Math.floor(n / 10) * 10;

// ---- unit tests (Python test_salary.py와 동일 케이스) ----

test("known table cell: 연봉 5,000만 식대 20만", () => {
  const r = computeNet(50000000);
  assert.equal(r.taxableMonthly, 3966666);
  assert.equal(r.incomeTax, 190620);
  assert.equal(r.localTax, 19060);
});

test("pension upper cap 313,020", () => {
  const r = computeNet(120000000, { mealAllowance: 0 });
  assert.equal(r.pension, 313020);
});

test("pension lower floor 19,470", () => {
  const r = computeNet(4800000, { mealAllowance: 0 });
  assert.equal(r.pension, 19470);
});

test("income tax zero at low salary", () => {
  const r = computeNet(12000000, { mealAllowance: 0 });
  assert.equal(r.incomeTax, 0);
  assert.equal(r.localTax, 0);
});

test("exact 10,000천원 row", () => {
  const r = computeNet(120000000, { mealAllowance: 0 });
  assert.equal(r.incomeTax, 1507400);
});

test("over 10m formula", () => {
  const r = computeNet(144000000, { mealAllowance: 0 });
  const expected = floor10(1507400 + 25000 + Math.floor((2000000 * 98 * 35) / 10000));
  assert.equal(r.incomeTax, expected);
});

test("dependents reduce tax", () => {
  const r1 = computeNet(50000000);
  const r2 = computeNet(50000000, { dependents: 2 });
  assert.ok(r2.incomeTax < r1.incomeTax);
});

test("child deduction", () => {
  const rCol3 = computeNet(60000000, { dependents: 3 });
  const rChild = computeNet(60000000, { dependents: 2, children: 1 });
  assert.equal(rChild.incomeTax,
    floor10(rCol3.incomeTax - rates.incomeTax.childDeduction.one));
});

test("family over 11 extrapolation", () => {
  const r10 = computeNet(120000000, { dependents: 10, mealAllowance: 0 });
  const r11 = computeNet(120000000, { dependents: 11, mealAllowance: 0 });
  const r13 = computeNet(120000000, { dependents: 13, mealAllowance: 0 });
  const expected = floor10(Math.max(0, r11.incomeTax - (r10.incomeTax - r11.incomeTax) * 2));
  assert.equal(r13.incomeTax, expected);
});

test("input validation", () => {
  assert.throws(() => computeNet(-1));
  assert.throws(() => computeNet(50000000.5));
  assert.throws(() => computeNet(50000000, { dependents: 0 }));
  assert.throws(() => computeNet(50000000, { children: 1 }));
  assert.throws(() => computeNet(50000000, { mealAllowance: -1 }));
});

test("setData required when no data", () => {
  // data 인자를 넘기면 전역 주입 없이도 동작
  const r = computeNet(50000000, {}, rates);
  assert.equal(r.incomeTax, 190620);
});

test("fmtKrw", () => {
  assert.equal(fmtKrw(1234567), "1,234,567");
  assert.equal(fmtKrw(0), "0");
  assert.equal(fmtKrw(-9876543), "-9,876,543");
});

test("fmtManwon", () => {
  assert.equal(fmtManwon(45000000), "4,500만");
  assert.equal(fmtManwon(125000000), "1억 2,500만");
  assert.equal(fmtManwon(100000000), "1억");
  assert.equal(fmtManwon(9990000), "999만");
  assert.equal(fmtManwon(1234560000), "12억 3,456만");
  assert.equal(fmtManwon(0), "0만");
});

// ---- Python cross-check: 연봉 1,000만~2억 100만 단위 완전 일치 ----

test("python cross-check fixture (191 points x 2 cases)", () => {
  const fixture = JSON.parse(
    readFileSync(join(HERE, "fixtures", "cross_check.json"), "utf-8"));
  assert.equal(fixture.points.length, 191);
  let mismatches = 0;
  for (const p of fixture.points) {
    for (const c of p.cases) {
      const r = computeNet(p.annual, {
        dependents: c.opts.dependents,
        children: c.opts.children,
        mealAllowance: c.opts.mealAllowance,
      });
      try {
        assert.deepEqual(r, c.result);
      } catch (err) {
        mismatches += 1;
        if (mismatches <= 3) {
          console.error(`  mismatch annual=${p.annual} opts=${JSON.stringify(c.opts)}`);
          console.error(`    js=${JSON.stringify(r)}`);
          console.error(`    py=${JSON.stringify(c.result)}`);
        }
      }
    }
  }
  assert.equal(mismatches, 0, `${mismatches} mismatches vs python fixture`);
});

// ---- summary ----

console.log(`salary.test.mjs: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
