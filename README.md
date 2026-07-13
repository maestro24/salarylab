# 연봉계산소 (SalaryLab) — 실수령액 pSEO

2026년 연봉 실수령액 계산기 + 연봉별/역계산 정적 페이지. 순수 정적, 프레임워크 0.

**운영 URL**: https://maestro24.github.io/salarylab/

## 아키텍처

```
data/rates.json          2026 요율·상하한 (소스 오브 트루스, 출처: data/SOURCES.md)
scripts/salary.py        Python 엔진 ─┐ 같은 JSON,
js/salary.js             JS 엔진     ─┘ 교차 검증 + 외부 실수령액표 대조
scripts/generate.py      엔진 × 템플릿 → salary/·reverse/·table/·negotiate/·guide/
                         (고아 0 검증, 상한 300 강제)
js/app.js                허브 계산기·협상 시뮬레이터 (클라이언트 실시간)
```

## 명령

```bash
python scripts/generate.py            # 사이트 재생성 (rates.json 수정 후)
python -m unittest discover tests     # 엔진 테스트 + 외부 교차 fixture
node tests/salary.test.mjs            # JS 엔진 + Python 교차 검증
python -m http.server 8000            # 로컬 확인
```

## 정확도 게이트 (중요)

- 소득세는 간이세액표 산식 원본 구현 — 근사식 금지
- Python↔JS 전 구간 완전 일치 (tests/fixtures/cross_check.json)
- 외부 공개 실수령액표 20지점 대조 (tests/fixtures/external_check.json, ±3,000원)
- 게이트 실패 시 배포 금지

## 연간 유지 (매년 1월)

1. 4대보험 요율·상하한, 간이세액표 파라미터 조사 → data/rates.json 갱신 (+SOURCES.md)
2. scripts/generate.py 의 YEAR 상수 변경
3. 테스트 fixture 갱신 → 재생성 → 커밋
