
## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

## 하네스: k-proposal

**목표:** 정부지원사업 사업계획서(TIPS 포함)를 6개 전문 스킬 파이프라인으로 자동 작성

**트리거 → 스킬 라우팅:**
- 사업계획서 작성, TIPS 연구개발계획서, 계획서 전체 → `proposal-orchestrator` (전체 파이프라인)
- 공고문 분석, 양식 분석 → `proposal-analyze`
- 시장 리서치, 경쟁사 분석, KIPRIS → `proposal-research`
- 초안 작성, 초안 보강, 휴먼라이징, 시각자료 → `proposal-write`
- 계획서 검토, 심사위원 채점, 양식 충족 → `proposal-review`
- HWPX 채우기, HWPX 빌드 → `proposal-build`
- 발표평가 준비, Q&A 생성, 최종 점검 → `proposal-qa`
- 단순 질문은 직접 응답 가능

**에이전트 팀:** researcher(리서치+KIPRIS) + writer(초안+sections.json) + reviewer(양식게이트+채점) + visualizer(시각자료)

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-04-23 | 스타일 충실도 향상: 양식 charShape 카탈로그 자동 추출 + fill rich content(charShapeId·runs·줄바꿈·다중 단락) 지원 + test_hwpx 마크업 잔존 검사 | extract_style_catalog, hwpx_handler.set_cell_rich, proposal-analyze, proposal-write, writer 에이전트, test_hwpx | 양식의 폰트/크기/강조/줄바꿈을 정확히 반영 (실제 사례 분석 기반 휴리스틱) |
| 2026-04-16 | rhwp 참고 반영: @rhwp/core WASM 검증, 누름틀 필드 API, LINE_SEG 모니터링, xml-internals 크로스레퍼런스 보강 | hwpx_handler, auto_template_map, xml-internals, test_hwpx | rhwp 프로젝트 분석 결과 반영 |
| 2026-04-16 | 작성요령 자동 추출: guide_table_contents 추출 + writing_guide_full 연동 | auto_template_map, proposal-write, proposal-analyze | 양식 작성요령을 writer에 자동 전달 |
| 2026-04-10 | gstack 패턴 스킬 분리: 6개 독립 스킬 + 오케스트레이터 | 전체 | 모놀리식 1,768줄 → 스킬별 분리 |
| 2026-04-10 | 스킬 근본 수정: 양식게이트, KIPRIS, sections.json 출력 등 | 에이전트+템플릿 | 재발 방지 |
| 2026-04-09 | 하네스 초기 구성 | 전체 | 에이전트 4종 + 오케스트레이터 생성 |

## MCP Servers

kordoc MCP 서버로 문서 파싱을 수행한다.
HWP, HWPX, PDF, XLSX, DOCX 파일을 마크다운으로 변환하고,
양식 필드를 자동 인식하고, 두 문서를 비교할 수 있다.

`.cursor/mcp.json` 설정:
```json
{
  "mcpServers": {
    "kordoc": {
      "command": "kordoc-mcp",
      "args": []
    }
  }
}
```

CLI 직접 사용: `kordoc <파일경로>` (글로벌 설치 완료)

사용 가능한 MCP 도구:
- `parse_document` — HWP/HWPX/PDF/XLSX/DOCX → 마크다운 변환
- `detect_format` — 매직 바이트로 파일 포맷 감지
- `parse_metadata` — 메타데이터만 빠르게 추출
- `parse_pages` — 특정 페이지/섹션 범위만 파싱
- `parse_table` — N번째 테이블만 추출
- `compare_documents` — 두 문서 비교 (크로스 포맷 HWP↔HWPX 가능)
- `parse_form` — 양식 필드를 label-value JSON으로 추출
