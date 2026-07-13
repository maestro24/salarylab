// 연봉계산소 인터랙티브 위젯 — 허브 계산기 + 협상 시뮬레이터
const ROOT = new URL('..', import.meta.url);

async function engine() {
  const mod = await import(new URL('js/salary.js', ROOT));
  const res = await fetch(new URL('data/rates.json', ROOT), { cache: 'no-cache' });
  const data = await res.json();
  mod.setData(data);
  return mod;
}

const fmt = (n) => Math.round(n).toLocaleString('ko-KR');
const $ = (id) => document.getElementById(id);

const ROWS = [
  ['국민연금', 'pension'], ['건강보험', 'health'], ['장기요양', 'care'],
  ['고용보험', 'employment'], ['소득세', 'incomeTax'], ['지방소득세', 'localTax'],
];
const BAR_COLORS = { net: '#5b6ee8', social: '#94a3c8', tax: '#e5a04f' };

function renderBreakdown(r, $table) {
  let html = `<tr><td>월 세전 급여</td><td style="text-align:right">${fmt(r.monthlyGross)}원</td></tr>`;
  for (const [name, key] of ROWS) {
    html += `<tr><td>${name}</td><td class="minus" style="text-align:right">-${fmt(r[key])}원</td></tr>`;
  }
  html += `<tr class="total"><td>월 실수령액</td><td style="text-align:right">${fmt(r.monthlyNet)}원</td></tr>`;
  $table.innerHTML = html;
}

// ── 허브 계산기 ──
export async function initCalculator() {
  const { computeNet } = await engine();
  const recalc = () => {
    const annual = (parseFloat($('in-annual').value) || 0) * 10000;
    if (annual <= 0) { $('out-net').textContent = '-'; return; }
    const r = computeNet(annual, {
      dependents: parseInt($('in-dep').value, 10),
      children: parseInt($('in-child').value, 10),
      mealAllowance: $('in-meal').checked ? 200000 : 0,
    });
    $('out-net').textContent = `${fmt(r.monthlyNet)}원`;
    $('out-annual').textContent = `연 실수령 ${fmt(r.annualNet)}원`;
    renderBreakdown(r, $('out-table'));

    const social = r.pension + r.health + r.care + r.employment;
    const tax = r.incomeTax + r.localTax;
    const g = r.monthlyGross;
    $('bar').innerHTML =
      `<span style="width:${(r.monthlyNet / g) * 100}%;background:${BAR_COLORS.net}"></span>` +
      `<span style="width:${(social / g) * 100}%;background:${BAR_COLORS.social}"></span>` +
      `<span style="width:${(tax / g) * 100}%;background:${BAR_COLORS.tax}"></span>`;
    $('bar-legend').innerHTML =
      `<span><i style="background:${BAR_COLORS.net}"></i>실수령 ${((r.monthlyNet / g) * 100).toFixed(1)}%</span>` +
      `<span><i style="background:${BAR_COLORS.social}"></i>4대보험 ${((social / g) * 100).toFixed(1)}%</span>` +
      `<span><i style="background:${BAR_COLORS.tax}"></i>세금 ${((tax / g) * 100).toFixed(1)}%</span>`;
  };
  for (const id of ['in-annual', 'in-dep', 'in-child', 'in-meal']) {
    $(id).addEventListener('input', recalc);
    $(id).addEventListener('change', recalc);
  }
  recalc();
}

// ── 협상 시뮬레이터 ──
export async function initNegotiate() {
  const { computeNet } = await engine();
  const recalc = () => {
    const cur = (parseFloat($('n-current').value) || 0) * 10000;
    const rate = parseFloat($('n-rate').value) || 0;
    if (cur <= 0) return;
    const next = Math.round(cur * (1 + rate / 100));
    const r0 = computeNet(cur);
    const r1 = computeNet(next);
    const delta = r1.monthlyNet - r0.monthlyNet;
    $('n-delta').textContent = `+${fmt(delta)}원`;
    const grossDelta = r1.monthlyGross - r0.monthlyGross;
    const keepPct = grossDelta > 0 ? ((delta / grossDelta) * 100).toFixed(1) : '0';
    $('n-detail').textContent = `세전 증가 ${fmt(grossDelta)}원 중 ${keepPct}%가 실제로 들어옵니다`;
    $('n-table').innerHTML = `
      <tr><td>현재 (연봉 ${fmt(cur / 10000)}만)</td><td style="text-align:right">월 ${fmt(r0.monthlyNet)}원</td></tr>
      <tr><td>인상 후 (연봉 ${fmt(next / 10000)}만)</td><td style="text-align:right">월 ${fmt(r1.monthlyNet)}원</td></tr>
      <tr class="total"><td>연간 실수령 증가</td><td style="text-align:right">+${fmt(r1.annualNet - r0.annualNet)}원</td></tr>`;

    // 역방향: 목표 월 증가분 → 필요 인상률
    const goal = (parseFloat($('n-goal').value) || 0) * 10000;
    if (goal > 0) {
      let lo = cur, hi = cur * 3;
      for (let i = 0; i < 40; i++) {
        const mid = (lo + hi) / 2;
        if (computeNet(Math.round(mid)).monthlyNet - r0.monthlyNet < goal) lo = mid;
        else hi = mid;
      }
      const needRate = ((hi - cur) / cur) * 100;
      $('n-reverse').innerHTML = `월 실수령을 <b>${fmt(goal)}원</b> 늘리려면 연봉 <b>약 ${fmt(Math.round(hi / 10000))}만 원</b> — 인상률 <b>${needRate.toFixed(1)}%</b>가 필요합니다.`;
    }
  };
  for (const id of ['n-current', 'n-rate', 'n-goal']) $(id).addEventListener('input', recalc);
  recalc();
}
