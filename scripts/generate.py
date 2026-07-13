# -*- coding: utf-8 -*-
"""연봉계산소 정적 사이트 생성기.

rates.json × salary.py 엔진 × 템플릿 → 연봉별/역계산/표/시뮬레이터 페이지.
- 고아 페이지 0 검증, 파일럿 상한 300 강제 (docs/PLAN.md 단계 방출 원칙)
- 광고: 하단 배너 전 페이지, 사이드 레일은 허브성 페이지만
실행: python scripts/generate.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import salary  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SITE_URL = "https://maestro24.github.io/salarylab"
MAX_PAGES = 300
YEAR = 2026

# 연봉 페이지 대상 (만원): 100만 단위 전 구간 + 인기 구간 50만 보강
ANNUAL_MANWON = list(range(1000, 20001, 100)) + list(range(2050, 7951, 100))
# 역계산 대상 (월 실수령 만원)
REVERSE_TARGETS = list(range(150, 441, 10))

DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
TAX_NOTE = f"{YEAR}년 4대보험 요율·근로소득 간이세액표(부양가족 1인, 비과세 미적용) 기준 추정치입니다. 회사별 공제 항목·수당 구성에 따라 실제 금액과 다를 수 있으며, 세무 상담을 대신하지 않습니다."

FAVICON = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='%236E7FF3'/><stop offset='1' stop-color='%233D4FD0'/></linearGradient></defs><rect width='100' height='100' rx='18' fill='url(%23g)'/><text x='50' y='66' font-size='44' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='bold'>₩</text><rect x='24' y='74' width='52' height='7' rx='3.5' fill='white' opacity='.85'/></svg>"

GTAG = """<!-- Google Analytics (GA4) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2P73L29BH7"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-2P73L29BH7');
</script>"""

PROMO = """<aside class="promo" data-coupang>
  <div class="coupang-wrap">
    <a href="https://link.coupang.com/a/flCfhuxEJM" target="_blank" rel="sponsored noopener" referrerpolicy="unsafe-url"><img src="https://ads-partners.coupang.com/banners/1006097?trackingCode=AF8748009&subId=&traceId=V0-301-879dd1202e5c73b2-I1006097&w=728&h=90" alt="쿠팡 파트너스 배너" style="max-width:100%;height:auto" loading="lazy"></a>
  </div>
  <p class="promo-disclosure">""" + DISCLOSURE + """</p>
</aside>
<script>
  setTimeout(function () {
    document.querySelectorAll('[data-coupang]').forEach(function (el) {
      var f = el.querySelector('iframe');
      var m = el.querySelector('img');
      var ok = (f && f.getBoundingClientRect().height >= 10) || (m && m.complete && m.naturalWidth > 0);
      if (!ok) el.hidden = true;
    });
  }, 4000);
</script>"""

RAILS = """<div class="side-rail side-l" data-coupang>
  <script src="https://ads-partners.coupang.com/g.js"></script>
  <script>new PartnersCoupang.G({ id: 1006093, template: "carousel", trackingCode: "AF8748009", width: "160", height: "600", tsource: "" });</script>
</div>
<div class="side-rail side-r" data-coupang>
  <script>new PartnersCoupang.G({ id: 1006093, template: "carousel", trackingCode: "AF8748009", width: "160", height: "600", tsource: "" });</script>
</div>
"""


def shell(*, title, desc, canonical, depth, body, jsonld=None, seo_html="", rails=False, extra_script=""):
    p = "../" * depth
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
{GTAG}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{desc}" />
<link rel="canonical" href="{canonical}" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{desc}" />
<meta property="og:type" content="website" />
<meta property="og:url" content="{canonical}" />
<meta property="og:locale" content="ko_KR" />
<meta name="theme-color" content="#f7f8fc" />
<link rel="icon" href="{FAVICON}" />
{ld}
<link rel="stylesheet" href="{p}css/style.css" />
</head>
<body>
<div id="app">
<header class="header">
  <a class="brand" href="{p}index.html">💰 연봉계산소</a>
  <nav class="nav">
    <a href="{p}table/index.html">실수령액표</a>
    <a href="{p}negotiate/index.html">협상</a>
    <a href="{p}guide/index.html">가이드</a>
  </nav>
</header>
<main class="main">
{body}
</main>
{PROMO}
{seo_html}
<footer class="footer">
  <span>{TAX_NOTE}</span>
  <a href="{p}index.html">계산기</a>
  <a href="{p}table/index.html">실수령액표</a>
  <a href="https://maestro24.github.io/stockcal/">주식달력</a>
</footer>
</div>
{extra_script}
{RAILS if rails else ""}
</body>
</html>"""


class Site:
    def __init__(self):
        self.pages = {}
        self.links = set()

    def emit(self, path, html):
        if path in self.pages:
            raise SystemExit(f"중복 페이지: {path}")
        self.pages[path] = html

    def link(self, src, dst):
        self.links.add((src, dst))

    def verify(self):
        if len(self.pages) > MAX_PAGES:
            raise SystemExit(f"페이지 {len(self.pages)} > 상한 {MAX_PAGES}")
        linked = {d for _, d in self.links}
        orphans = [p for p in self.pages if p != "index.html" and p not in linked]
        if orphans:
            raise SystemExit(f"고아 {len(orphans)}: {orphans[:5]}")

    def write(self):
        for path, html in self.pages.items():
            full = os.path.join(ROOT, path.replace("/", os.sep))
            os.makedirs(os.path.dirname(full) or ROOT, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(html)


def mw(manwon):  # 만원 → 원
    return manwon * 10000


def breakdown_rows(r, hl=None):
    items = [
        ("월 세전 급여", r["monthlyGross"], ""),
        ("국민연금", -r["pension"], "minus"),
        ("건강보험", -r["health"], "minus"),
        ("장기요양보험", -r["care"], "minus"),
        ("고용보험", -r["employment"], "minus"),
        ("소득세", -r["incomeTax"], "minus"),
        ("지방소득세", -r["localTax"], "minus"),
    ]
    rows = "".join(
        f'<tr><td>{name}</td><td class="{cls}">{"-" if v < 0 else ""}{salary.fmt_krw(abs(v))}원</td></tr>'
        for name, v, cls in items
    )
    rows += f'<tr class="total"><td>월 실수령액</td><td>{salary.fmt_krw(r["monthlyNet"])}원</td></tr>'
    return rows


def nearby(values, v, n=5):
    i = values.index(v)
    lo = max(0, i - n)
    return values[lo:i] + values[i + 1:i + 1 + n]


# ── 연봉 페이지 ──────────────────────────────────
def build_salary_page(site, m):
    annual = mw(m)
    r = salary.compute_net(annual)
    path = f"salary/{m}/index.html"
    canonical = f"{SITE_URL}/salary/{m}/"
    label = salary.fmt_manwon(annual)

    sorted_all = sorted(set(ANNUAL_MANWON))
    near_rows = []
    for w in nearby(sorted_all, m):
        rn = salary.compute_net(mw(w))
        site.link(path, f"salary/{w}/index.html")
        near_rows.append(
            f'<tr><td><a href="../{w}/index.html">연봉 {salary.fmt_manwon(mw(w))}</a></td>'
            f'<td>{salary.fmt_krw(rn["monthlyNet"])}원</td></tr>'
        )
    site.link(path, "table/index.html")
    site.link(path, "negotiate/index.html")

    # 가까운 역계산 링크
    rev = min(REVERSE_TARGETS, key=lambda t: abs(t * 10000 - r["monthlyNet"]))
    site.link(path, f"reverse/{rev}/index.html")

    faq = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f"연봉 {label} 실수령액은 얼마인가요?",
             "acceptedAnswer": {"@type": "Answer", "text": f"{YEAR}년 기준 연봉 {label} 원의 월 실수령액은 약 {salary.fmt_krw(r['monthlyNet'])}원입니다 (부양가족 1인, 비과세 미적용). 4대보험 {salary.fmt_krw(r['pension'] + r['health'] + r['care'] + r['employment'])}원과 세금 {salary.fmt_krw(r['incomeTax'] + r['localTax'])}원이 매월 공제됩니다."}},
            {"@type": "Question", "name": "실수령액이 회사마다 다른 이유는?",
             "acceptedAnswer": {"@type": "Answer", "text": "비과세 수당(식대·차량유지비 등) 구성, 부양가족 수, 회사의 공제 항목(노조비·사우회비 등)에 따라 달라집니다. 본 계산은 간이세액표 100% 기준 추정치입니다."}},
        ],
    }

    body = f"""<nav class="crumb"><a href="../../index.html">계산기</a> › <a href="../../table/index.html">실수령액표</a> › 연봉 {label}</nav>
<div class="answer">
  <div class="eq">연봉 {label} 실수령액 <b>월 {salary.fmt_krw(r["monthlyNet"])}원</b></div>
  <div class="sub">{YEAR}년 기준 · 연 실수령 {salary.fmt_krw(r["annualNet"])}원 · 부양가족 1인 기준</div>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">공제 내역 분해</h2>
  <table class="tbl"><tbody>{breakdown_rows(r)}</tbody></table>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">근처 연봉 비교</h2>
  <table class="tbl"><thead><tr><th>연봉</th><th>월 실수령</th></tr></thead><tbody>{''.join(near_rows)}</tbody></table>
</div>
<div class="card">
  <div class="rel-grid">
    <a class="rel-link" href="../../index.html">내 조건으로 다시 계산 (부양가족·식대)</a>
    <a class="rel-link" href="../../reverse/{rev}/index.html">월 {rev}만 받으려면 연봉 얼마?</a>
    <a class="rel-link" href="../../negotiate/index.html">연봉 협상 시뮬레이터</a>
  </div>
</div>"""

    seo = f"""<section class="seo-content">
<h2>연봉 {label}, 왜 월 {salary.fmt_krw(r["monthlyNet"])}원인가요?</h2>
<p>세전 월급 {salary.fmt_krw(r["monthlyGross"])}원에서 국민연금·건강보험(장기요양 포함)·고용보험으로 {salary.fmt_krw(r['pension'] + r['health'] + r['care'] + r['employment'])}원, 소득세와 지방소득세로 {salary.fmt_krw(r['incomeTax'] + r['localTax'])}원이 공제됩니다. 부양가족 수가 늘거나 비과세 식대(월 20만 원)를 적용하면 실수령액이 늘어납니다 — 위 계산기에서 조건을 바꿔 확인하세요.</p>
</section>"""

    site.emit(path, shell(
        title=f"연봉 {label} 실수령액 — 월 {salary.fmt_krw(r['monthlyNet'])}원 ({YEAR}년) | 연봉계산소",
        desc=f"{YEAR}년 연봉 {label} 원의 월 실수령액은 {salary.fmt_krw(r['monthlyNet'])}원입니다. 4대보험·소득세 공제 내역 분해와 근처 연봉 비교표 제공.",
        canonical=canonical, depth=2, body=body, jsonld=faq, seo_html=seo,
    ))


# ── 역계산 페이지 ────────────────────────────────
def solve_annual_for_net(target_monthly):
    lo, hi = 10_000_000, 400_000_000
    while hi - lo > 10_000:
        mid = (lo + hi) // 2
        if salary.compute_net(mid)["monthlyNet"] < target_monthly:
            lo = mid
        else:
            hi = mid
    return hi


def build_reverse_page(site, t):
    target = t * 10000
    annual = solve_annual_for_net(target)
    annual_man = round(annual / 10_000_000) * 1000  # 표시용 반올림(만원, 천만 단위 아님 — 아래서 정밀 표기)
    r = salary.compute_net(annual)
    path = f"reverse/{t}/index.html"
    canonical = f"{SITE_URL}/reverse/{t}/"

    rows = []
    for w in nearby(REVERSE_TARGETS, t, 4):
        a = solve_annual_for_net(w * 10000)
        site.link(path, f"reverse/{w}/index.html")
        rows.append(f'<tr><td><a href="../{w}/index.html">월 {w}만 원</a></td><td>연봉 약 {salary.fmt_manwon(round(a, -5))}</td></tr>')
    # 가까운 연봉 페이지 링크
    near_salary = min(sorted(set(ANNUAL_MANWON)), key=lambda mm: abs(mw(mm) - annual))
    site.link(path, f"salary/{near_salary}/index.html")
    site.link(path, "index.html") if False else None

    body = f"""<nav class="crumb"><a href="../../index.html">계산기</a> › 역계산 › 월 {t}만 원</nav>
<div class="answer">
  <div class="eq">월 실수령 {t}만 원 → 연봉 <b>약 {salary.fmt_manwon(round(annual, -5))}</b></div>
  <div class="sub">{YEAR}년 기준 · 세전 월급 약 {salary.fmt_krw(r["monthlyGross"])}원 (부양가족 1인)</div>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">이 연봉의 공제 내역</h2>
  <table class="tbl"><tbody>{breakdown_rows(r)}</tbody></table>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">다른 목표 실수령액</h2>
  <table class="tbl"><thead><tr><th>목표 월 실수령</th><th>필요 연봉</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</div>
<div class="card">
  <div class="rel-grid">
    <a class="rel-link" href="../../salary/{near_salary}/index.html">연봉 {salary.fmt_manwon(mw(near_salary))} 상세 보기</a>
    <a class="rel-link" href="../../negotiate/index.html">협상 시뮬레이터로 인상률 계산</a>
  </div>
</div>"""

    site.emit(path, shell(
        title=f"월 실수령 {t}만 원 받으려면 연봉 얼마? ({YEAR}년) | 연봉계산소",
        desc=f"월 실수령액 {t}만 원을 받으려면 {YEAR}년 기준 연봉 약 {salary.fmt_manwon(round(annual, -5))} 원이 필요합니다. 공제 내역과 목표별 필요 연봉표 제공.",
        canonical=canonical, depth=2, body=body,
    ))


# ── 총괄표 ──────────────────────────────────────
def build_table_page(site):
    path = "table/index.html"
    rows = []
    for m in range(2000, 12001, 100):
        r = salary.compute_net(mw(m))
        cell = f'<a href="../salary/{m}/index.html">{salary.fmt_manwon(mw(m))}</a>'
        site.link(path, f"salary/{m}/index.html")
        rows.append(f'<tr><td>{cell}</td><td>{salary.fmt_krw(r["monthlyGross"])}원</td><td>{salary.fmt_krw(r["monthlyNet"])}원</td></tr>')
    site.link(path, "index.html") if False else None

    body = f"""<nav class="crumb"><a href="../index.html">계산기</a> › {YEAR} 실수령액표</nav>
<div>
  <h1 class="page-title">{YEAR}년 연봉 실수령액표</h1>
  <p class="page-desc">연봉 2,000만~1억 2,000만 원 · 부양가족 1인 · 비과세 미적용 기준. 연봉을 누르면 공제 분해를 볼 수 있어요.</p>
</div>
<div class="card" style="max-height:70vh;overflow-y:auto">
  <table class="tbl"><thead><tr><th>연봉</th><th>월 세전</th><th>월 실수령</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</div>"""

    site.emit(path, shell(
        title=f"{YEAR}년 연봉 실수령액표 (2,000만~1억 2천만) | 연봉계산소",
        desc=f"{YEAR}년 4대보험·간이세액표 반영 연봉 실수령액표. 연봉 100만 원 단위로 월 세전·실수령액을 한眼에.",
        canonical=f"{SITE_URL}/table/", depth=1, body=body, rails=True,
    ))


# ── 허브(인터랙티브) ────────────────────────────
def build_index(site):
    path = "index.html"
    for target in ["table/index.html", "negotiate/index.html", "guide/index.html",
                   "salary/3000/index.html", "salary/4000/index.html", "salary/5000/index.html",
                   "salary/6000/index.html", "salary/8000/index.html", "salary/10000/index.html",
                   "reverse/300/index.html", "reverse/400/index.html", "reverse/250/index.html"]:
        site.link(path, target)

    popular = "".join(
        f'<a class="rel-link" href="salary/{m}/index.html">연봉 {salary.fmt_manwon(mw(m))}</a>'
        for m in [3000, 4000, 5000, 6000, 8000, 10000]
    ) + "".join(
        f'<a class="rel-link" href="reverse/{t}/index.html">월 {t}만 받으려면?</a>'
        for t in [250, 300, 400]
    )

    body = f"""<div>
  <h1 class="page-title">{YEAR} 연봉 실수령액 계산기</h1>
  <p class="page-desc">4대보험·간이세액표 기준. 부양가족·자녀·비과세 식대까지 반영한 진짜 월급.</p>
</div>
<div class="card">
  <div class="calc-form">
    <label>연봉 (만원)
      <input type="number" id="in-annual" inputmode="numeric" value="4000" min="0" step="100" />
    </label>
    <label>부양가족 수 (본인 포함)
      <select id="in-dep">{''.join(f'<option value="{i}"{" selected" if i == 1 else ""}>{i}명</option>' for i in range(1, 9))}</select>
    </label>
    <label>8~20세 자녀 수
      <select id="in-child">{''.join(f'<option value="{i}">{i}명</option>' for i in range(0, 5))}</select>
    </label>
  </div>
  <label class="check-row"><input type="checkbox" id="in-meal" /> 비과세 식대 월 20만 원 포함</label>
  <div class="net-hero">
    <div class="label">월 실수령액</div>
    <div class="value" id="out-net">-</div>
    <div class="per" id="out-annual"></div>
  </div>
  <div class="deduct-bar" id="bar"></div>
  <div class="bar-legend" id="bar-legend"></div>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">공제 내역</h2>
  <table class="tbl"><tbody id="out-table"></tbody></table>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">바로가기</h2>
  <div class="rel-grid">{popular}</div>
</div>"""

    seo = f"""<section class="seo-content">
<h2>실수령액은 어떻게 계산되나요?</h2>
<p>월 급여에서 국민연금(4.5%), 건강보험과 장기요양보험, 고용보험(0.9%), 그리고 근로소득 간이세액표에 따른 소득세와 지방소득세(소득세의 10%)를 공제한 금액이 실수령액입니다. 부양가족이 많을수록 소득세가 줄고, 식대 등 비과세 수당은 공제 계산에서 제외되어 실수령액이 늘어납니다.</p>
<h2>자주 묻는 질문</h2>
<dl>
<dt>계산 결과가 실제 월급과 왜 다른가요?</dt>
<dd>회사의 비과세 수당 구성, 상여 지급 방식, 노조비 같은 회사별 공제 때문입니다. 본 계산기는 간이세액표 100% 기준 추정치이며, 연말정산에서 최종 정산됩니다.</dd>
<dt>요율은 언제 기준인가요?</dt>
<dd>{YEAR}년 고시 요율 기준이며 출처는 가이드 페이지에 정리되어 있습니다.</dd>
</dl>
</section>"""

    site.emit(path, shell(
        title=f"{YEAR} 연봉 실수령액 계산기 — 부양가족·비과세 반영 | 연봉계산소",
        desc=f"{YEAR}년 연봉 실수령액을 즉시 계산. 4대보험·간이세액표·부양가족·자녀·비과세 식대 반영. 연봉별 실수령액표와 역계산까지 무료.",
        canonical=f"{SITE_URL}/", depth=0, body=body, seo_html=seo, rails=True,
        jsonld={"@context": "https://schema.org", "@type": "WebApplication", "name": "연봉계산소",
                "url": f"{SITE_URL}/", "applicationCategory": "FinanceApplication", "operatingSystem": "Web",
                "inLanguage": "ko", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW"},
                "description": f"{YEAR}년 연봉 실수령액 계산기 — 4대보험·간이세액표 기준, 부양가족·비과세 반영"},
        extra_script="""<script type="module">
import { initCalculator } from './js/app.js';
initCalculator();
</script>""",
    ))


# ── 협상 시뮬레이터 ──────────────────────────────
def build_negotiate(site):
    path = "negotiate/index.html"
    site.link(path, "index.html") if False else None
    for m in [4000, 5000, 6000]:
        site.link(path, f"salary/{m}/index.html")

    body = f"""<nav class="crumb"><a href="../index.html">계산기</a> › 연봉 협상 시뮬레이터</nav>
<div>
  <h1 class="page-title">연봉 협상 시뮬레이터</h1>
  <p class="page-desc">"5% 올리면 통장에 실제로 얼마 더 들어올까?" — 인상률의 세후 가치를 확인하세요.</p>
</div>
<div class="card">
  <div class="calc-form">
    <label>현재 연봉 (만원)
      <input type="number" id="n-current" inputmode="numeric" value="4000" min="0" step="100" />
    </label>
    <label>인상률 (%)
      <input type="number" id="n-rate" inputmode="decimal" value="5" min="0" max="100" step="0.5" />
    </label>
  </div>
  <div class="net-hero">
    <div class="label">월 실수령 증가분</div>
    <div class="value" id="n-delta">-</div>
    <div class="per" id="n-detail"></div>
  </div>
  <table class="tbl"><tbody id="n-table"></tbody></table>
</div>
<div class="card">
  <h2 style="font-size:1rem;margin-bottom:10px">거꾸로: 월 실수령을 늘리려면</h2>
  <div class="calc-form">
    <label>목표 월 증가분 (만원)
      <input type="number" id="n-goal" inputmode="numeric" value="20" min="1" step="5" />
    </label>
  </div>
  <p style="font-size:0.95rem;margin-top:10px" id="n-reverse">-</p>
</div>
<div class="card">
  <div class="rel-grid">
    <a class="rel-link" href="../salary/4000/index.html">연봉 4,000만 상세</a>
    <a class="rel-link" href="../salary/5000/index.html">연봉 5,000만 상세</a>
    <a class="rel-link" href="../salary/6000/index.html">연봉 6,000만 상세</a>
  </div>
</div>"""

    seo = """<section class="seo-content">
<h2>연봉 인상분은 왜 생각보다 적게 들어오나요?</h2>
<p>인상분에는 4대보험과 소득세가 함께 붙습니다. 특히 과세표준 구간이 올라가면 인상분에 적용되는 한계세율이 높아져, 세전 인상률보다 세후 증가율이 낮아지는 것이 정상입니다. 협상 때는 세전 금액이 아니라 "월 실수령 기준으로 얼마가 늘어나는가"를 확인하고 목표를 세우는 것이 유리합니다.</p>
</section>"""

    site.emit(path, shell(
        title="연봉 협상 시뮬레이터 — 인상률의 세후 가치 계산 | 연봉계산소",
        desc="연봉 5% 인상이면 월 실수령이 실제로 얼마나 늘까? 인상률→세후 증가분, 목표 증가분→필요 인상률 역계산까지 무료 시뮬레이터.",
        canonical=f"{SITE_URL}/negotiate/", depth=1, body=body, seo_html=seo, rails=True,
        extra_script="""<script type="module">
import { initNegotiate } from '../js/app.js';
initNegotiate();
</script>""",
    ))


# ── 가이드 ──────────────────────────────────────
def build_guide(site):
    path = "guide/index.html"
    for m in [3000, 5000, 8000]:
        site.link(path, f"salary/{m}/index.html")

    body = f"""<nav class="crumb"><a href="../index.html">계산기</a> › 공제 항목 가이드</nav>
<div>
  <h1 class="page-title">월급에서 빠지는 돈, 전부 해설</h1>
  <p class="page-desc">{YEAR}년 기준 4대보험 요율과 소득세 계산 구조를 한 페이지로.</p>
</div>
<div class="card seo-content" style="border-top:none;padding:20px">
<h2>1. 국민연금 — 월 급여의 4.5%</h2>
<p>회사와 근로자가 절반씩 부담합니다(총 9%). 기준소득월액에 상한과 하한이 있어, 상한을 넘는 고연봉자는 연봉이 올라도 국민연금 공제액이 더 늘지 않습니다.</p>
<h2>2. 건강보험 + 장기요양보험</h2>
<p>건강보험료는 보수월액에 요율을 곱해 산정하고(근로자 절반 부담), 장기요양보험료는 건강보험료에 다시 일정 비율을 곱해 붙습니다. 매년 요율이 고시되며, 이 사이트는 {YEAR}년 고시 요율을 사용합니다.</p>
<h2>3. 고용보험 — 월 급여의 0.9%</h2>
<p>실업급여 재원입니다. 회사는 추가로 고용안정·직업능력개발 부담금을 냅니다(근로자 부담 아님).</p>
<h2>4. 소득세 — 간이세액표 룩업</h2>
<p>매월 원천징수되는 소득세는 국세청 근로소득 간이세액표에 따라 월 급여 구간과 공제대상 가족 수로 결정됩니다. 근로소득공제 → 과세표준 → 기본세율(6~45%) 구조로 산출되며, 부양가족이 많을수록 줄어듭니다. 연말정산에서 실제 세액과의 차이를 정산합니다.</p>
<h2>5. 지방소득세 — 소득세의 10%</h2>
<p>소득세에 비례해 자동으로 붙습니다.</p>
<h2>실수령액을 늘리는 합법적 방법</h2>
<ul>
<li><strong>비과세 식대(월 20만 원)</strong>: 급여 구성에 포함되면 그만큼 공제 계산에서 빠집니다.</li>
<li><strong>부양가족 등록</strong>: 소득 요건을 충족하는 가족을 공제대상으로 올리면 매월 소득세가 줄어듭니다.</li>
<li><strong>연말정산 공제 챙기기</strong>: 월 실수령과 별개로, 연 단위 환급으로 돌아옵니다.</li>
</ul>
<p style="margin-top:14px">직접 확인: <a href="../salary/3000/index.html">연봉 3,000만</a> · <a href="../salary/5000/index.html">5,000만</a> · <a href="../salary/8000/index.html">8,000만</a> 공제 분해</p>
</div>"""

    site.emit(path, shell(
        title=f"{YEAR} 4대보험 요율·소득세 공제 완전 해설 | 연봉계산소",
        desc=f"국민연금 4.5%, 건강보험, 고용보험 0.9%, 간이세액표 — {YEAR}년 월급 공제 항목을 전부 해설하고 실수령액 늘리는 방법까지.",
        canonical=f"{SITE_URL}/guide/", depth=1, body=body, rails=True,
    ))


def build_sitemap(site):
    urls = []
    for path in sorted(site.pages):
        loc = SITE_URL + "/" if path == "index.html" else SITE_URL + "/" + path.replace("index.html", "")
        urls.append(f"<url><loc>{loc}</loc></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return len(urls)


def main():
    for d in ("salary", "reverse", "table", "negotiate", "guide"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)

    site = Site()
    build_index(site)
    for m in sorted(set(ANNUAL_MANWON)):
        build_salary_page(site, m)
    for t in REVERSE_TARGETS:
        build_reverse_page(site, t)
    build_table_page(site)
    build_negotiate(site)
    build_guide(site)

    site.verify()
    site.write()
    n = build_sitemap(site)
    print(f"[generate] 페이지 {len(site.pages)}개, sitemap {n} URL, 고아 0 검증 통과")


if __name__ == "__main__":
    main()
