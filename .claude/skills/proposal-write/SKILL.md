---
name: proposal-write
description: "사업계획서 초안 작성 + 휴먼라이징 + 시각자료 생성. '초안 작성', '초안 보강', '휴먼라이징', '시각자료 생성' 요청 시 사용. 양식 슬롯 수에 정확히 대응하는 sections.json + fill.json 동시 생성."
---

# proposal-write — 초안 작성 + 휴먼라이징 + 시각자료

## 핵심 역할

준비자료와 리서치 결과를 기반으로 사업계획서 초안을 작성하고, 심사위원 검토 후 보강하고, 휴먼라이징과 시각자료 생성까지 수행한다. `draft.md` + `draft_sections.json` + `draft_fill.json`을 동시에 생성하여 HWPX 빌드에 바로 사용 가능.

## 단독 사용

```
초안 작성해줘
초안 보강해줘
휴먼라이징 해줘
시각자료 생성해줘
```

## 파이프라인 사용

`/proposal-research` 다음에 호출. `/proposal-review`에서 미달 시 보강 요청을 받아 재작성.

---

## 작업 원칙

1. **핵심 3문** 논리축: Why Now / Why Us / Why 지원 필요
2. **개조식 명사형** 문체 (~구축, ~확보). 서술형 금지
3. 약어 첫 등장 시 영문 풀네임 + 한국어 설명 병기
4. **광탈 패턴** 사전 배제: "4차 산업혁명", "혁신적인", "세계 최초", "1식" 등
5. 외부 인용 시 출처 URL·**Tier·발행연도** 인라인 명기. **`_workspace/01_researcher/approved_citations.json`에 없는 인용은 본문·테이블·시각자료 어디에도 사용 금지**. 미승인 자리는 `[사용자 미승인 — 인용 보류]` 태그로 명시한다.

## 외부 인용 규칙 (사용자 승인 게이트 통과 인용만 사용)

`/proposal-research`의 Step 4 사용자 승인 게이트를 통과한 인용만 본문에 들어갈 수 있다.

### 입력 파일
- `_workspace/01_researcher/approved_citations.json` — 사용자 승인 인용 (단일 진실 공급원)
- `_workspace/01_researcher/source_verification.md` — Tier·신선도·일치도·원문 스니펫 (출처 라벨 작성 시 참고)

### 인용 인라인 형식
```
"국내 SaaS 시장 5.2조원" (KOSIS, 2024, T1, https://kosis.kr/...)
```
- 출처 기관명 + 발행연도 + Tier + URL을 묶어서 명기
- 수정값(modified_from)이 있는 경우 수정값을 사용 (원본 값 사용 금지)
- 차단 도메인(언론·블로그·보도자료) 인용 금지 — 룰셋 §1 참조

### TAM/SAM/SOM 셀 강제
시장규모 섹션은 `references/research-quality-rules.md` §4 산식 템플릿대로 TAM·SAM·SOM 3셀 모두 산식·출처·가정 보수성 근거를 작성한다. reviewer 양식 게이트가 누락 시 차단한다.

---

## Step 0: 광탈 패턴 사전 배제

초안 작성 전에 절대 사용하지 않을 패턴을 설정:

**언어 광탈 패턴:**
- "세계 최고 수준의 AI 기술" — 근거 없는 최상급
- "국내 유일" / "독보적" — 검증 불가 주장
- "혁신적인" / "차세대" / "게임체인저" — 추상적 수식어
- "본 사업은 ~을 목적으로 하며" — AI 작성 흔적 1순위
- "~할 것으로 기대됩니다" — 막연한 미래 추정
- "4차 산업혁명" / "디지털 전환" — 남발된 유행어

**구조 광탈 패턴:**
- 10페이지 중 7페이지+ 기술 설명 → "사업화 의지 부족"
- 정량적 목표 0개 또는 비현실적 → "성의 없음" / "신뢰 불가"
- 예산 산출근거 "1식" → 감점 확정
- 경쟁사 분석 없음 → 시장 이해도 부족

---

## Step 1: 핵심 3문 답변 정의

**Why Now** — 시장/기술/규제에서 지금 이 시점이 특별한 이유 (데이터 근거)
**Why Us** — 경쟁사 대비 우리 팀이 더 잘 해결할 구체적 근거 (특허, 인력, 고객)
**Why 지원 필요** — 자금 없이 왜 안 되는가 (현금잔고 vs 개발비용, BEP 시뮬레이션, 런웨이)

재무 수치는 AI가 임의로 생성하지 않음. 재무제표에서 직접 계산하고, 없으면 사용자에게 요청.

---

## Step 2: 섹션별 초안 작성

### 템플릿 로딩 규칙

준비자료(`_workspace/00_input/준비자료.md`)의 `template_dir` 값을 읽어 해당 디렉토리의 템플릿을 사용한다:

| 템플릿 | 파일 패턴 |
|--------|---------|
| sections | `{template_dir}/sections_template.json` 또는 `{template_dir}/sections_*.json` |
| fill | `{template_dir}/fill_template.json` 또는 `{template_dir}/fill_*.json` |
| bold_keywords | `{template_dir}/bold_keywords_template.json` 또는 `{template_dir}/bold_keywords_*.json` |
| images | `{template_dir}/images_template.json` 또는 `{template_dir}/images_*.json` |

`template_dir`이 없거나 해당 파일이 없으면 `templates/` 루트의 기본 템플릿을 사용한다.

**양식 구조 기준으로 작성.** 양식의 테이블맵·섹션명·ㅇ/- 단락 수를 그대로 따른다.

### 양식 슬롯 대응 원칙 (필수)

1. **ㅇ 블록 수 = ◦ 슬롯 수**: 양식에 ◦가 3개면 ㅇ도 정확히 3개
2. **- 항목 수 <= - 슬롯 수**: 양식에 -가 2개면 - 항목도 2개 이하
3. **내용 > 슬롯**: 하나의 ㅇ 안에서 개조식으로 병합. 별도 ㅇ 분리 금지
4. **내용 < 슬롯**: 내용을 분할하여 빈 슬롯 없이 채움

### 양식 작성요령(writing_guide_full) 매핑 원칙

`sections_template.json`의 각 섹션에 `writing_guide_full` 필드가 있으면, 해당 양식의 작성요령 테이블에서 자동 추출된 **원문 전문**이다. 반드시 다음 원칙에 따라 초안에 반영한다:

1. **필수 읽기**: `writing_guide_full`이 존재하면 해당 섹션 작성 전에 반드시 읽는다
2. **ㅇ 항목 1:1 대응**: 작성요령의 ㅇ(또는 ◦) 항목 하나가 초안의 ㅇ 블록 하나에 대응되도록 매핑. 작성요령에 4개 항목이면 초안에도 4개 ㅇ 블록
3. **키워드 완전 커버**: 작성요령에 명시된 키워드(시장규모, 성장률, TRL, 경쟁사, 특허 등)는 초안에 반드시 포함. 누락 시 심사위원이 "양식 지시사항 미이행"으로 감점
4. **순서 유지**: 작성요령이 "시장규모 → 성장률 → 문제점" 순이면 초안도 동일 순서
5. **writing_guide(요약) vs writing_guide_full(전문)**: `writing_guide`는 작성 전략 힌트, `writing_guide_full`은 양식이 요구하는 구체적 항목. 둘 다 있으면 `writing_guide_full`을 구조 기준으로, `writing_guide`를 톤/전략 기준으로 사용

> `writing_guide_full`이 없는 섹션은 기존대로 `writing_guide`만 참조한다.

### 작성 순서

1. **요약표 초안** — 양식의 요약표 셀 구조 그대로 한 줄씩 키워드
2. **본문 서술 섹션** — 배점 높은 섹션부터 공을 들임
3. **테이블 데이터** — 인력, 정량목표, 추진일정, 예산 등
4. **요약표 최종 다듬기** — 본문 반영 후 첫인상 최적화

### Why Us 경쟁사 분석 구조

차별점만 나열하지 않고, **우리가 못하는 것을 먼저 인정** + 그럼에도 더 나은 이유 제시:
- 직접 경쟁사 3개 (가격/기능/타겟/약점 표)
- 간접 경쟁사 2개 (해결 방식/한계 표)
- 대체재 (엑셀·수기 → 전환 근거)
- 우리의 한계 인정 + 그럼에도 우위

### 편집 원칙

- 키워드 볼드+밑줄 (핵심 수치, 규제명, 차별점, 정량 목표)
- 표·도표 최대 활용 (경쟁사 비교, 수상이력, 간트차트, 예산, 매출 추이)
- 전문용어 첫 등장 시 괄호 풀이 (SDGs, IRIS+, i18n 등)
- 개조식 명사형 문체 필수

---

## Step 3: sections.json + fill.json 동시 생성

`draft.md` 작성과 동시에 구조화된 출력물을 생성:

- `draft_sections.json`: `{"sections": [{"header_keyword": "...", "pairs": [["ㅇ text", "- text"], ...]}]}`
- `draft_fill.json`: `{"cells": [{"table_index": N, "row": R, "col": C, "text": "...", "preserve_style": true}, ...]}`

앞표지(T0) + 요약문(T2)의 필수 셀을 `draft_fill.json`에 반드시 포함.

---

## Step 4: 필수 기재 체크리스트 (TIPS)

초안 완료 전 전부 확인. 누락 시 `/proposal-review`가 반려:

- [ ] 앞표지 데이터 (과제명, 기관명, 사업자번호, 연구책임자, 연구개발기간, 연구개발비)
- [ ] 요약문 데이터 (사업명, 과제명, 기간, 총비, 최종목표, 전체내용, 기대효과, 핵심어 5개)
- [ ] 커버페이지 (과제명, 운영사명, 창업기업명)
- [ ] KIPRIS 검색 결과 10건 (`/proposal-research`의 kipris_search.md)
- [ ] 위탁기관명 + 역할 분담 근거
- [ ] 기술유출 방지대책 (비밀유지, 접근통제, 데이터 격리)
- [ ] 고용창출 서술 (교육프로그램, 스톡옵션, 내일채움공제, 직무보상발명)
- [ ] 5-1(안전) / 5-2(보안) / 5-3(기타) 각각 별도 기재
- [ ] 단위 정합성 (3-6 사업화 목표: 양식 표기 단위와 값 일치)

---

## Step 5: 휴먼라이징

심사위원 검토 통과 후 수행. AI 패턴 30개 탐지 + 치환:

| AI 표현 | 사람 표현 |
|---------|---------|
| 본 사업은 ~을 목적으로 하며 | [사업명]은 ~ |
| 이를 통해 ~의 효과를 기대할 수 있습니다 | ~으로 이어짐 |
| 혁신적인 | (삭제 또는 수치로 대체) |
| ~함으로써 | ~해서 |
| 기여할 것으로 기대됩니다 | 기여 (근거 수치 병기) |

목표: 전 섹션 AI 점수 30점 이하.

---

## Step 6: 시각자료 생성

초안에서 시각화 대상 추출 → 이미지 생성:

| 대상 | 생성 방법 |
|------|---------|
| TAM/SAM/SOM 차트 | matplotlib bar/line |
| 시스템 아키텍처 | OpenAI gpt-image-2(영문) 또는 mermaid |
| 핵심 알고리즘 플로우 | mermaid 또는 OpenAI gpt-image-2 |
| 경쟁사 비교 레이더 | matplotlib radar |
| 투자 로드맵 타임라인 | matplotlib timeline |
| TRL 진행도 | matplotlib horizontal bar |

브랜드 색상 자동 추출 (로고/소개서 이미지가 있을 때).

---

## 분량 비율 (TIPS 8억 기준)

- 기술 40% / 사업화 30% / 팀+실적 30%
- 기술 50% 초과 시 경고, 사업화 15% 미만 시 경고

---

## 에이전트 호출

Agent Teams 모드: `writer.md` + `visualizer.md` 에이전트 호출.

---

## 입력/출력

- **입력**: `_workspace/00_input/준비자료.md` + `_workspace/01_researcher/`
- **출력**:
  - `_workspace/02_writer/draft.md`
  - `_workspace/02_writer/draft_sections.json`
  - `_workspace/02_writer/draft_fill.json`
  - `_workspace/02_writer/draft_humanized.md`
  - `_workspace/04_visualizer/` (이미지 + image_manifest.json)
- **이전 단계**: `/proposal-research`
- **다음 단계**: `/proposal-review`
