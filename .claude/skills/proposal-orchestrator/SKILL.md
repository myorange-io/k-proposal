---
name: proposal-orchestrator
description: "정부지원사업 사업계획서 작성 파이프라인 오케스트레이터. '사업계획서 작성', 'TIPS 연구개발계획서', '계획서 작성' 요청 시 전체 파이프라인 실행. 개별 단계 요청 시 해당 스킬로 라우팅. 후속 작업(수정, 보완, 재실행) 시에도 이 스킬 사용."
---

# proposal-orchestrator — 사업계획서 파이프라인

정부지원사업 사업계획서(TIPS 포함)를 6개 전문 스킬의 파이프라인으로 작성한다.

## 스킬 라우팅

| 트리거 | 실행 스킬 |
|--------|----------|
| "사업계획서 작성", "TIPS 연구개발계획서" | **전체 파이프라인** (아래 참조) |
| "공고문 분석", "양식 분석", "양식 구조 파악" | `/proposal-analyze` |
| "시장 리서치", "경쟁사 분석", "KIPRIS 검색" | `/proposal-research` |
| "초안 작성", "초안 보강", "휴먼라이징", "시각자료 생성" | `/proposal-write` |
| "계획서 검토", "심사위원 채점", "양식 충족 확인" | `/proposal-review` |
| "HWPX 채워줘", "HWPX 빌드", "양식에 내용 넣어줘" | `/proposal-build` |
| "발표평가 준비", "Q&A 생성", "최종 점검" | `/proposal-qa` |

---

## 전체 파이프라인

```
/proposal-analyze → /proposal-research → /proposal-write → /proposal-review
    → (통과 시) /proposal-write --humanize → /proposal-build → /proposal-qa
    → (미달 시) /proposal-write 보강 → /proposal-review 재채점 (최대 2회)
```

### 데이터 흐름

```
_workspace/
├── 00_input/준비자료.md          ← /proposal-analyze 산출
├── 01_researcher/                ← /proposal-research 산출
│   ├── market_research.md
│   ├── competitor_analysis.md
│   ├── source_verification.md
│   └── kipris_search.md
├── 02_writer/                    ← /proposal-write 산출
│   ├── draft.md
│   ├── draft_sections.json
│   ├── draft_fill.json
│   └── draft_humanized.md
├── 03_reviewer/                  ← /proposal-review 산출
│   ├── gate_check.md
│   ├── review_result.md
│   └── final_review.md
└── 04_visualizer/                ← /proposal-write 산출
    ├── *.png
    └── image_manifest.json
```

산출물: `제출용_사업계획서.hwpx` + `_발표평가_Q&A.md`

---

## 실행 모드

사용자에게 모드를 먼저 확인:

> **어떤 모드로 진행할까요?**
> - **A) 협업 모드** (추천) — 사업명, 예산, 목표 등 5개 결정 포인트에서 함께 결정
> - **B) 자동 모드** — AI가 전부 결정, 결과만 확인

---

## Agent Teams 병렬 실행

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 환경변수 설정 시 병렬 실행:

| 에이전트 | 역할 | 정의 파일 |
|---------|------|---------|
| researcher | 시장 리서치 + 출처 검증 + KIPRIS | `.claude/agents/researcher.md` |
| writer | 초안 + sections.json + fill.json + 휴먼라이징 | `.claude/agents/writer.md` |
| reviewer | 양식 게이트(10항목) + 채점 + 킬러 질문 | `.claude/agents/reviewer.md` |
| visualizer | 시각자료 생성 (차트, 아키텍처, 인포그래픽) | `.claude/agents/visualizer.md` |

```
/proposal-analyze (리드)
    ├─→ [researcher] 리서치 + KIPRIS
    ├─→ [writer] 초안 (researcher 결과 수신 후 반영)
    │       ├─→ [reviewer] 채점 + 킬러 질문
    │       │       └─→ (미달 시 writer 보강 → 재채점)
    │       └─→ [visualizer] 시각자료 (writer 초안 기반, 병렬)
    └─→ /proposal-build (리드, 전원 완료 후)
         └─→ /proposal-qa (리드)
```

Agent Teams를 쓰지 않을 때: 단일 세션에서 순차적으로 각 스킬 실행.

---

## 컨텍스트 확인 (Phase 0)

1. `_workspace/` 존재 여부 확인
2. 실행 모드 결정:
   - **미존재** → 초기 실행. `/proposal-analyze`부터 시작
   - **존재 + 부분 수정 요청** → 해당 스킬만 재호출
   - **존재 + 새 입력** → `_workspace_{timestamp}/`로 이동 후 처음부터

---

## 에러 핸들링

- researcher 리서치 실패 → writer에게 "[리서치 미확보]" 태그, 회사 자료만으로 작성
- reviewer 3회 반복 미통과 → 리드에게 보고, 부족 자료 목록 사용자 안내
- visualizer 이미지 생성 실패 → 이미지 없이 HWPX 진행 (리드가 보고)
- build HWPX 손상 → hwpx_handler 자동 복구 시도. 실패 시 사용자에게 알림

---

## TIPS 전용

TIPS 공고 감지 시 자동 활성화:
- 서류평가 4대항목 매칭 (문제인식/실현가능성/성장전략/팀구성)
- 킬러 질문 10개 (TIPS 특화)
- 성능지표 목표 수준 검증 (세계최고 대비 60-80%)
- 예산 자동 검증 (2026년 인건비 단가, 비목별 한도)
- 가점 자동 스캔 (비수도권 3점, ESG 2점, 벤처인증 1점)
