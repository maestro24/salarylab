/**
 * salarylab net-salary engine (JavaScript, ES module).
 *
 * Mirror of scripts/salary.py — the two engines MUST behave identically.
 * No DOM, no fetch: rates data is injected via setData(data) or passed per
 * call as the 3rd argument of computeNet(). In the browser, load
 * data/rates.json (inline or fetch at build time) and call setData() once.
 *
 * 계산 규약 (scripts/salary.py와 동일)
 * - 월 급여 = floor(연봉 / 12)
 * - 비과세 식대는 월 한도와 월 급여를 넘지 않게 클램프
 * - 4대보험·지방소득세 10원 미만 절사, 전 곱셈 정수 연산(Number.isSafeInteger 범위)
 * - 소득세 = 간이세액표(소득세법 시행령 별표2, 2026.2.27 개정) 원본 룩업 + 1,000만원
 *   초과 산식, 100% 원천징수 기준. 열 = 공제대상가족 수 + 8~20세 자녀 수.
 */

const RATE_SCALE = 1000000;

let defaultData = null;

function validateData(data) {
  if (!data || typeof data !== "object") {
    throw new Error("rates data must be an object");
  }
  const keys = ["pension", "health", "care", "employment", "incomeTax", "localIncomeTax", "nonTaxable"];
  for (const key of keys) {
    if (!(key in data)) {
      throw new Error(`rates data missing key: ${key}`);
    }
  }
  const itx = data.incomeTax;
  if (!Array.isArray(itx.rows) || itx.rows.length === 0 || itx.rows[0].length !== 12) {
    throw new Error("incomeTax.rows malformed");
  }
  if (!Array.isArray(itx.exactTop) || itx.exactTop.length !== 11) {
    throw new Error("incomeTax.exactTop malformed");
  }
}

/**
 * Inject the rates database (parsed content of data/rates.json).
 * @param {object} data
 */
export function setData(data) {
  validateData(data);
  defaultData = data;
}

function getData(data) {
  if (data !== undefined && data !== null) {
    validateData(data);
    return data;
  }
  if (!defaultData) {
    throw new Error("no rates data: call setData(data) first or pass data");
  }
  return defaultData;
}

function floor10(n) {
  return Math.floor(n / 10) * 10;
}

/** floor(amount * rate) using integer fixed-point math. */
function rateMul(amount, rate) {
  const num = Math.round(rate * RATE_SCALE);
  return Math.floor((amount * num) / RATE_SCALE);
}

function pensionOf(taxable, p) {
  const base = Math.min(Math.max(taxable, p.baseMonthlyMin), p.baseMonthlyMax);
  return floor10(rateMul(base, p.workerRate));
}

function healthOf(taxable, h) {
  const prem = floor10(rateMul(taxable, h.workerRate));
  return Math.min(Math.max(prem, h.workerMonthlyPremiumMin), h.workerMonthlyPremiumMax);
}

function careOf(healthPremium, c) {
  const num = Math.round(c.incomeRate * RATE_SCALE);
  const den = Math.round(c.healthRateRef * RATE_SCALE);
  return floor10(Math.floor((healthPremium * num) / den));
}

function employmentOf(taxable, e) {
  return floor10(rateMul(taxable, e.workerRate));
}

/** cells10: 11 amounts (families 1..11). Extrapolate beyond 11 (별표2 제4호). */
function tableCell(cells10, families) {
  if (families <= 11) {
    return cells10[families - 1];
  }
  const t10 = cells10[9];
  const t11 = cells10[10];
  return Math.max(0, t11 - (t10 - t11) * (families - 11));
}

function incomeTaxOf(taxable, dependents, children, itx) {
  const families = dependents + children;
  const rows = itx.rows;
  let tax;
  if (taxable < rows[0][0] * 1000) {
    tax = 0;
  } else if (taxable < 10000000) {
    let lo = 0;
    let hi = rows.length - 1;
    while (lo < hi) {
      const mid = Math.floor((lo + hi + 1) / 2);
      if (rows[mid][0] * 1000 <= taxable) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }
    tax = tableCell(rows[lo].slice(1), families);
  } else {
    const base = tableCell(itx.exactTop, families);
    if (taxable === 10000000) {
      tax = base;
    } else {
      tax = null;
      for (const br of itx.over10m) {
        if (br.uptoK === null || taxable <= br.uptoK * 1000) {
          const over = taxable - br.overK * 1000;
          const fnum = Math.round(br.factor * 100);
          const rnum = Math.round(br.rate * 100);
          tax = base + br.baseConst + Math.floor((over * fnum * rnum) / 10000);
          break;
        }
      }
      if (tax === null) {
        throw new Error("no over10m bracket matched");
      }
    }
  }
  if (children > 0 && tax > 0) {
    const cd = itx.childDeduction;
    if (children === 1) {
      tax -= cd.one;
    } else {
      tax -= cd.two + cd.perExtraOverTwo * (children - 2);
    }
    if (tax < 0) {
      tax = 0;
    }
  }
  return floor10(tax);
}

function isInt(v) {
  return typeof v === "number" && Number.isSafeInteger(v);
}

/**
 * 연봉(원) → 월/연 실수령액 및 공제 내역. 전 항목 원 단위 정수.
 *
 * @param {number} annual 연봉(원), 세전
 * @param {object} [opts]
 * @param {number} [opts.dependents=1] 본인 포함 공제대상 가족 수 (>=1)
 * @param {number} [opts.children=0] 8~20세 자녀 수 (dependents에 포함되어 있어야 함)
 * @param {number} [opts.mealAllowance=200000] 월 비과세 식대(원), 0이면 미적용
 * @param {object} [data] rates database (defaults to setData() value)
 * @returns {{monthlyGross:number, taxableMonthly:number, pension:number,
 *   health:number, care:number, employment:number, incomeTax:number,
 *   localTax:number, totalDeduction:number, monthlyNet:number, annualNet:number}}
 */
export function computeNet(annual, opts, data) {
  const d = getData(data);
  const o = opts || {};
  const dependents = o.dependents === undefined ? 1 : o.dependents;
  const children = o.children === undefined ? 0 : o.children;
  const mealAllowance = o.mealAllowance === undefined ? 200000 : o.mealAllowance;

  if (!isInt(annual) || annual < 0) {
    throw new Error("annual must be an integer >= 0 (KRW)");
  }
  if (!isInt(dependents) || dependents < 1) {
    throw new Error("dependents must be an integer >= 1 (본인 포함)");
  }
  if (!isInt(children) || children < 0) {
    throw new Error("children must be an integer >= 0");
  }
  if (children > dependents - 1) {
    throw new Error("children must be <= dependents - 1 (자녀도 공제대상가족에 포함)");
  }
  if (!isInt(mealAllowance) || mealAllowance < 0) {
    throw new Error("mealAllowance must be an integer >= 0");
  }

  const monthlyGross = Math.floor(annual / 12);
  const meal = Math.min(mealAllowance, d.nonTaxable.mealMonthlyCap, monthlyGross);
  const taxable = monthlyGross - meal;

  const pension = pensionOf(taxable, d.pension);
  const health = healthOf(taxable, d.health);
  const care = careOf(health, d.care);
  const employment = employmentOf(taxable, d.employment);
  const incomeTax = incomeTaxOf(taxable, dependents, children, d.incomeTax);
  const localTax = floor10(rateMul(incomeTax, d.localIncomeTax.rateOfIncomeTax));

  const totalDeduction = pension + health + care + employment + incomeTax + localTax;
  const monthlyNet = monthlyGross - totalDeduction;

  return {
    monthlyGross,
    taxableMonthly: taxable,
    pension,
    health,
    care,
    employment,
    incomeTax,
    localTax,
    totalDeduction,
    monthlyNet,
    annualNet: monthlyNet * 12,
  };
}

/**
 * 1234567 -> "1,234,567" (원 단위 콤마)
 * @param {number} n
 * @returns {string}
 */
export function fmtKrw(n) {
  const v = Math.trunc(n);
  const sign = v < 0 ? "-" : "";
  const digits = String(Math.abs(v));
  return sign + digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * 45000000 -> "4,500만" / 125000000 -> "1억 2,500만" (만 미만 절사)
 * @param {number} n
 * @returns {string}
 */
export function fmtManwon(n) {
  const v = Math.trunc(n);
  const sign = v < 0 ? "-" : "";
  const man = Math.floor(Math.abs(v) / 10000);
  const eok = Math.floor(man / 10000);
  const rest = man % 10000;
  if (eok && rest) {
    return `${sign}${fmtKrw(eok)}억 ${fmtKrw(rest)}만`;
  }
  if (eok) {
    return `${sign}${fmtKrw(eok)}억`;
  }
  return `${sign}${fmtKrw(man)}만`;
}
