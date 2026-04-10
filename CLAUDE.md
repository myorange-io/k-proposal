
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

**목표:** 정부지원사업 사업계획서(TIPS 포함)를 에이전트 팀으로 자동 작성

**트리거:** 사업계획서, TIPS 연구개발계획서, 계획서 작성 요청 시 `proposal-orchestrator` 스킬을 사용하라. 단순 질문은 직접 응답 가능.

**에이전트 팀:** researcher(리서치) + writer(초안) + reviewer(심사위원 검토) + visualizer(시각자료)

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
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
