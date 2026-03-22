# ADR-002: 프론트엔드 Vanilla JS 채택 (프레임워크 미사용)

- **날짜:** 2026-03-20
- **상태:** 승인됨

## 결정

프론트엔드를 React, Vue, Angular 없이 Vanilla HTML/CSS/JavaScript로 구현한다.

## 배경

- 금융 대시보드는 데이터 시각화가 핵심 — 렌더링 프레임워크보다 Plotly.js 연동이 중요
- 빌드 파이프라인(webpack, vite 등) 없이 정적 파일로 직접 서빙 가능해야 함
- GitHub Actions으로 배포하는 경량 운영 환경에서 Node.js 빌드 단계 추가 부담

## 선택된 방안

**Vanilla JS + Plotly.js CDN:**
- HTML 파일을 FastAPI `static` 마운트 또는 직접 브라우저 열기로 서빙
- Plotly.js CDN 로드 — 번들러 불필요
- `Promise.all()` + `fetch()` 로 병렬 API 호출

## 대안과 기각 이유

| 대안 | 기각 이유 |
|------|----------|
| React | 빌드 파이프라인 필요, 이 규모에서 과도 |
| Vue.js CDN | CDN Vue는 프로덕션 권장 아님, 추가 학습 비용 |
| Streamlit | Python 전용 차트, Plotly 커스터마이징 제한 (requirements.txt에 있으나 미채택) |

## 결과

- `script.js` 단일 파일에 모든 프론트엔드 로직 집중 → 파일 분리 없이 추적 용이
- 컬럼 다형성 방어, 타임아웃 처리 등 순수 JS로 직접 구현
- 프레임워크 업데이트에 따른 breaking change 위험 없음
