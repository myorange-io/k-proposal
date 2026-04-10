---
name: proposal-orchestrator
description: "정부지원사업 사업계획서 작성 에이전트 팀을 조율하는 오케스트레이터. '사업계획서 작성', 'TIPS 연구개발계획서', '계획서 팀으로 작성', '에이전트 팀으로 사업계획서' 요청 시 사용. 후속 작업: 결과 수정, 부분 재실행, 보완, 다시 실행, 이전 결과 개선 요청 시에도 반드시 이 스킬을 사용."
---

# Proposal Orchestrator

정부지원사업 사업계획서(TIPS 포함)를 에이전트 팀으로 작성하는 오케스트레이터.

## 실행 모드: 에이전트 팀

## 에이전트 구성

| 팀원 | 역할 | 정의 파일 | 출력 |
|------|------|---------|------|
| researcher | 시장 리서치 + 출처 URL 검증 | `.claude/agents/researcher.md` | `_workspace/01_researcher/` |
| writer | 초안 작성 + 휴먼라이징 | `.claude/agents/writer.md` | `_workspace/02_writer/` |
| reviewer | 심사위원 관점 채점 + 약점 보강 지시 | `.claude/agents/reviewer.md` | `_workspace/03_reviewer/` |
| visualizer | 시각 자료 생성 | `.claude/agents/visualizer.md` | `_workspace/04_visualizer/` |

## 워크플로우

### Phase 0: 컨텍스트 확인

1. `_workspace/` 존재 여부 확인
2. 실행 모드 결정:
   - **미존재** → 초기 실행. Phase 1로
   - **존재 + 부분 수정 요청** → 해당 에이전트만 재호출
   - **존재 + 새 입력** → `_workspace_{timestamp}/`로 이동 후 Phase 1

### Phase 1: 준비 (리드 수행)

1. 현재 폴더 자동 탐색 — 공고문, 양식, 회사 자료 분류
2. `_workspace/00_input/` 생성
3. 공고문 분석 → 평가기준, 예산규칙, 일정 추출
4. 양식 분석 → 테이블 구조, template_map 확인
5. 회사 자료 분석 → 기업정보, 기술, 재무, 실적, 특허/IP 추출
6. 지원 유형 분류 (TIPS/예비창업/창업도약/지역R&D 등)
7. 분석 결과를 `_workspace/00_input/준비자료.md`에 저장

### Phase 2: 팀 구성

팀 생성 (4명):
```
TeamCreate(
  team_name: "proposal-team",
  members: [
    { name: "researcher", agent_type: "researcher", model: "opus",
      prompt: "시장 리서치를 수행하라. _workspace/00_input/준비자료.md를 읽고, 시장 규모, 경쟁사, 정책 동향을 검색하라. 모든 인용에 출처 URL을 확보하고 WebFetch로 검증하라. 결과를 _workspace/01_researcher/에 저장하라." },
    { name: "writer", agent_type: "writer", model: "opus",
      prompt: "사업계획서 초안을 작성하라. researcher의 리서치 결과가 오면 반영하라. _workspace/00_input/준비자료.md + _workspace/01_researcher/를 기반으로 작성하라. 결과를 _workspace/02_writer/draft.md에 저장하라." },
    { name: "reviewer", agent_type: "reviewer", model: "opus",
      prompt: "writer의 초안을 심사위원 관점에서 검토하라. 평가기준별 채점 + 킬러 질문 생성. 60점 미만 항목 발견 시 writer에게 구체적 보강 지시를 보내라. 결과를 _workspace/03_reviewer/에 저장하라." },
    { name: "visualizer", agent_type: "visualizer", model: "opus",
      prompt: "writer의 초안에서 시각 자료 목록을 추출하고 이미지를 생성하라. 결과를 _workspace/04_visualizer/에 저장하라." }
  ]
)
```

작업 등록:
```
TaskCreate(tasks: [
  { title: "시장 리서치", description: "시장 규모, 경쟁사, 정책 데이터 검색 + 출처 URL 검증", assignee: "researcher" },
  { title: "초안 작성", description: "준비자료 + 리서치 결과 기반 섹션별 초안", assignee: "writer", depends_on: ["시장 리서치"] },
  { title: "심사위원 채점", description: "초안 평가기준별 채점 + 킬러 질문 + 보강 지시", assignee: "reviewer", depends_on: ["초안 작성"] },
  { title: "시각 자료 생성", description: "초안 기반 차트, 아키텍처, 인포그래픽 생성", assignee: "visualizer", depends_on: ["초안 작성"] },
  { title: "초안 보강", description: "reviewer 피드백 반영하여 약점 보강", assignee: "writer", depends_on: ["심사위원 채점"] },
  { title: "휴먼라이징", description: "AI 흔적 제거, 개조식 명사형 문체 전환", assignee: "writer", depends_on: ["초안 보강"] }
])
```

### Phase 3: 팀 실행 + 모니터링

1. researcher → 리서치 완료 → writer에게 결과 전달
2. writer → 초안 작성 → reviewer + visualizer 동시 시작
3. reviewer → 채점 → 60점 미만 시 writer에게 보강 지시 → writer 보강 → 재채점 (최대 2회)
4. reviewer 통과 → writer 휴먼라이징
5. visualizer → 이미지 생성 완료

리드는 진행 상황을 모니터링하고, 전원 완료 대기.

### Phase 4: HWPX 채우기 (리드 수행)

모든 팀원 완료 후 리드가 직접 수행:

**입력 파일:**
1. `_workspace/02_writer/draft_humanized.md` — 최종 초안
2. `_workspace/02_writer/draft_sections.json` — 개조식 단락용 구조화 데이터
3. `_workspace/02_writer/draft_fill.json` — 테이블 셀 데이터 (앞표지+요약문 포함)
4. `_workspace/04_visualizer/` — 시각 자료 이미지
5. `data/cover.json` — 커버페이지 데이터 (과제명, 운영사명, 기업명)

**빌드 파이프라인 (8단계):**
1. **fill**: 앞표지(T0) + 요약문(T2) + 데이터 테이블 셀 채우기
2. **sections**: 본문 ◦/- 단락 채우기 (sections.json 패턴 매칭)
3. **fix_body_paragraphs**: 작성요령 잔류 내용 → 본문 이동 (안전망)
4. **remove_empty_bullets**: 빈 ◦/- 단락 자동 삭제
5. **remove_guide_tables**: 작성요령 테이블 전체 삭제
6. **replace_cover**: 커버페이지 플레이스홀더 교체
7. **postprocess**: 후처리 (lineseg + charPr + 볼드 + 이미지 삽입)
8. **test_hwpx**: 검증

**Phase 4 완료 조건 (전부 ✅이어야 Phase 5 진행):**
- [ ] 앞표지 필수 셀 기입 완료
- [ ] 요약문 필수 셀 기입 완료
- [ ] 본문 빈 ◦/- 단락 0개
- [ ] 작성요령 테이블 0개
- [ ] 커버페이지 플레이스홀더 0개
- [ ] test_hwpx.py 전 항목 PASS

**산출물:** `제출용_사업계획서.hwpx`

### Phase 5: 최종 검토 + 정리 (리드 수행)

1. 광탈 패턴 최종 스캔
2. 발표평가 Q&A 생성 (`_발표평가_Q&A.md`)
3. 팀 정리
4. 사용자에게 결과 보고

## 데이터 전달 프로토콜

- **태스크 기반**: 작업 의존성으로 순서 보장
- **파일 기반**: `_workspace/` 하위 폴더에 산출물 저장
- **메시지 기반**: reviewer ↔ writer 간 보강 지시/완료 알림

## 에러 핸들링

- researcher 리서치 실패 → writer에게 "[리서치 미확보]" 태그 전달, writer는 회사 자료만으로 작성
- reviewer 3회 반복 미통과 → 리드에게 보고, 부족 자료 목록 사용자에게 안내
- visualizer 이미지 생성 실패 → 해당 이미지 없이 HWPX 진행 (리드가 보고)

## 테스트 시나리오

**정상 흐름**: TIPS 연구개발계획서 작성 → researcher 리서치 → writer 초안 → reviewer 75점 통과 → visualizer 이미지 6종 → 리드 HWPX → 완성
**에러 흐름**: reviewer 1차 55점(사업화 부족) → writer 보강 → 2차 68점 통과 → 휴먼라이징 → 완성
