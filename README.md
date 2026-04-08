# k-proposal

> 정부지원사업 사업계획서, AI가 처음부터 끝까지 만들어 줍니다.

공고문 분석부터 HWPX 제출 파일 생성까지 end-to-end. 심사위원 관점 모의 채점으로 약점을 잡고, 광탈 패턴을 자동으로 걸러내고, AI가 쓴 티를 지워줍니다.

**TIPS(팁스) 일반트랙** 전용 워크플로우 내장 -- 2026년 대개편(R&D 8억, 800개사) 완벽 반영.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| 공고문 자동 분석 | HWPX/HWP/PDF 공고문에서 평가기준, 예산규칙, 일정, 제출서류 자동 추출 |
| 양식 자동 인식 | 새 양식의 테이블 구조를 자동 파악하여 template_map 초안 생성 |
| 회사 자료 분석 | 재무제표, 서비스소개서, IR 자료에서 핵심 데이터 자동 추출 |
| 초안 작성 | Why Now / Why Us / Why 지원 필요 -- 합격하는 논리 구조로 섹션별 작성 |
| 휴먼라이징 | AI 작성 흔적 30개 패턴 자동 탐지 + 치환. 심사역은 AI 문체를 3초 만에 안다 |
| **심사위원 관점 검토** | 평가기준별 모의 채점 + 킬러 질문 생성 + 약점 자동 개선. 60점 미만 시 진행 차단 |
| 광탈 패턴 감지 | "세계 최고 수준", "혁신적인", "1식" 산출근거 등 감점 표현 자동 차단 |
| 시각 자료 생성 | 시장규모 차트, 서비스 아키텍처, KPI 인포그래픽 (브랜드 색상 자동 추출) |
| HWPX 자동 생성 | 원본 양식 그대로 유지하며 테이블 + 본문 + 이미지 채우기 |
| 발표평가 Q&A | 모의 질문 50개+ 답변 자동 생성 (서류 페이지 번호 병기) |
| TIPS 전용 워크플로우 | 서류평가 4대항목 매칭, 성능지표 역설계, 후속 투자 시나리오, 예산 자동 검증 |
| **Agent Teams 병렬 실행** | researcher + writer + reviewer + visualizer 4명이 동시 작업 (실험적) |

---

## 빠른 시작

### 1. 설치

```bash
git clone https://github.com/myorange-io/k-proposal.git
cd k-proposal && ./setup.sh

# Agent Teams 활성화 (선택, Claude Code v2.1.32+)
# settings.json에 추가하거나:
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### 2. 자료 준비

프로젝트 폴더에 아래 파일을 넣어두세요.

**필수**: 모집공고문(HWPX/HWP/PDF) + 작성서식(HWPX) + 사업자등록증 + 재무제표

**있으면 좋은 것**: 서비스소개서, 이전 사업계획서, IR 자료, 수상이력, 고객사 계약서, 특허등록증/출원서(청구항·명세서 포함), 팀원 이력서

> `.hwp` 파일은 kordoc MCP 서버가 설치되어 있으면 자동으로 읽습니다. 없으면 한글에서 HWPX로 변환하세요.

### 3. 실행

```
사업계획서 작성해줘
```

AI가 폴더를 자동 탐색하고, 모드를 물어봅니다:
- **협업 모드** (추천): 사업명, 예산, 목표 등 5개 결정 포인트에서 선택지 제시
- **자동 모드**: AI가 다 결정하고 결과만 보여줌

### 4. 결과물

```
프로젝트폴더/
├── 제출용_사업계획서.hwpx       ← 메인 산출물
├── _시각자료/                   ← 차트, 아키텍처 이미지
├── _사업계획서_준비자료.md      ← 공고 분석 + 회사 자료 정리
├── _초안.md                    ← 마크다운 초안
├── _심사위원_검토결과.md        ← 모의 채점 결과 + 개선 내역
└── _발표평가_Q&A.md            ← 모의 질문 50개+ 답변
```

---

## 작동 원리

```
Phase 0    Phase 1       Phase 2        Phase 3      Phase 3.5          Phase 3.6     Phase 3.7     Phase 4       Phase 5
파일탐색 → 공고/양식분석 → 회사자료분석 → 초안작성 → 심사위원 관점 검토 → 휴먼라이징 → 시각자료생성 → HWPX채우기 → 검토/제출
```

| Phase | 뭘 하나요? | 왜 필요한가요? |
|-------|-----------|---------------|
| 0 | 폴더 자동 탐색, 파일 분류 | 경로 묻지 않고 바로 시작 |
| 1 | 공고문에서 평가기준, 예산, 일정 추출. 양식 테이블 분석 | 평가기준에 맞춰 써야 점수가 높음 |
| 2 | 재무제표, 소개서에서 팀/기술/실적 추출 | 실제 데이터로 써야 신뢰도가 높음 |
| 3 | Why Now / Why Us / Why 지원 필요 논리축으로 초안 작성 | 논리 구조가 합격의 핵심 |
| **3.5** | **심사위원 관점 모의 채점 + 킬러 질문 + 약점 개선** | **60점 미만 항목을 내용 확정 전에 잡아냄** |
| 3.6 | AI 흔적 제거, 개조식 명사형 문체 전환 | 내용 확정 후 휴먼라이징해야 AI 흔적이 안 남음 |
| 3.7 | 시장규모 차트, 아키텍처 등 이미지 생성 | HWPX에 삽입할 시각자료 선준비 |
| 4 | 원본 양식에 초안 + 시각자료 삽입, HWPX 생성 | 제출 형식 그대로 완성 |
| 5 | 광탈 패턴 최종 점검, 팩트체크, Q&A 생성 | 제출 전 마지막 안전망 |

### Phase 3.6: 심사위원 관점 검토 (상세)

초안 완성 후 HWPX 채우기 전에 **반드시** 수행하는 품질 관문.

```
초안 완료 → [1] 평가기준 채점 → [2] 킬러 질문 → [3] 약점 개선 → [4] 재채점 → 통과 시 Phase 3.7
             60점 미만 차단      답변 불가 식별     보강 실행       전항목 60+ 확인
```

**1단계 -- 모의 채점**: 공고문의 평가기준에 맞춰 심사위원 2인(현장 전문가 + 심사 경력 심사역)을 시뮬레이션. 항목당 100점. 60점 미만이 하나라도 있으면 다음 단계로 진행하지 않습니다.

**2단계 -- 킬러 질문**: "사업비 규모가 적정한 근거?", "경쟁사 대비 차별점 한 문장으로?", "6개월 뒤 중간평가 산출물?" 등 실제 평가에서 나올 질문을 생성하고 초안만으로 답변 가능한지 판정합니다.

**3단계 -- 약점 개선**: 답변 불가 항목은 내용 추가, 60점 미만 항목은 전면 보강. 회사 자료에 없는 데이터는 지어내지 않고 사용자에게 요청합니다.

**4단계 -- 재채점**: 최대 2회 반복. 3회 시도 후에도 미달이면 부족한 자료 목록을 안내합니다.

> 심사위원 검토에서 내용을 보강하면 새로운 AI 표현이 추가될 수 있으므로, **내용 확정(Phase 3.5) 후에 휴먼라이징(Phase 3.6)**을 수행합니다.

---

## TIPS 일반트랙 연구개발계획서

### TIPS란?

민관공동창업자발굴육성(TIPS) -- 운영사(VC)가 선투자하고 정부가 R&D 자금을 매칭하는 프로그램. 2026년 대개편으로 **R&D 최대 8억원**, 선정 **800개사**.

### 사용법

```
TIPS 연구개발계획서 작성해줘
```

tips/ 폴더에 공고 자료를 넣으면 자동으로 TIPS 전용 워크플로우가 활성화됩니다.

### TIPS 전용 기능

| 기능 | 설명 |
|------|------|
| 서류평가 4대항목 매칭 | 문제인식 / 실현가능성 / 성장전략 / 팀구성에 1:1 대응하는 섹션 자동 구성 |
| TIPS 심사위원 검토 | 기술전문가 + 사업화전문가 + 투자자 3인 시뮬레이션 채점 + 킬러 질문 10개 |
| 광탈 패턴 30개 | "4차 산업혁명", TRL 미기재, 팀 미분리, "1식" 산출근거 등 자동 감지 |
| 분량 비율 가이드 | 기술 40% / 사업화 30% / 팀 30% 밸런스 자동 검증 |
| 성능지표 역설계 | 선정 + 2년 후 최종평가 동시 달성을 위한 목표 수준 자동 판정 (세계최고 대비 60-80% 권장) |
| 후속 투자 시나리오 | TIPS R&D -> Post-TIPS -> 시리즈A 성장 사다리 자동 생성 |
| 예산 자동 검증 | 2026년 인건비 단가(책임연구원 378만/월), 비목별 한도, "1식" 금지 |
| 가점 자동 스캔 | 비수도권(3점), ESG(2점), 벤처인증(1점), 퇴직연금(1점) |
| 핵심 3문 | Why Now(기술 타이밍) / Why Us(팀+IP) / Why 정부 R&D(자력 불가 증명) |

### 2026년 TIPS 주요 변경사항

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| R&D 지원금 | 5억원 | **최대 8억원** |
| 선정 규모 | 700개사 | **800개사** |
| 접수 방식 | 수시 | **분기별** (1, 2, 3분기) |
| 선투자(수도권) | 1-2억 | **2억 이상** |
| 가점 최대 | 3점 | **5점** |
| 비수도권 | - | **선정 50% 우선 할당** |

---

## 프로젝트 구조

```
k-proposal/
├── setup.sh                     # 원스텝 설치
├── .claude/agents/              # Agent Teams 에이전트 정의
│   ├── researcher.md            # 시장 리서치 + 출처 검증
│   ├── writer.md                # 초안 작성 + 휴먼라이징
│   ├── reviewer.md              # 심사위원 관점 검토
│   └── visualizer.md            # 시각 자료 생성
├── skill/                       # AI 스킬 정의
│   ├── SKILL.md                 # 전체 워크플로우 + TIPS 전용 워크플로우
│   ├── hwpx_handler.py          # HWPX 분석/채우기/행추가 (손상 ZIP 자동 복구)
│   ├── visual_gen.py            # 시각 자료 생성 (matplotlib + Gemini + mermaid)
│   ├── text_sanitizer.py        # 한국어 텍스트 정제
│   ├── kordoc_bridge.py         # kordoc CLI 브릿지
│   └── template_map.json        # 일반 사업화 자금 양식 매핑
├── scripts/                     # HWPX 빌드 파이프라인
│   ├── build_hwpx.py            # 테이블 셀 + 개조식 본문 채우기
│   ├── postprocess_hwpx.py      # diff 후처리 (겹침해결 + 볼드 + 이미지 + 네임스페이스)
│   ├── fix_namespaces.py        # ns0:/ns1: -> hh/hc/hp/hs 정규화
│   ├── insert_image.py          # HWPX 이미지 삽입 (3단계)
│   ├── auto_template_map.py     # 양식 자동 인식 -> template_map 생성
│   ├── compare_docs.py          # 문서 비교 (신구대조표)
│   └── test_hwpx.py             # HWPX 파일 자동 검증
├── templates/                   # JSON 데이터 템플릿
│   ├── fill_신청서_template.json
│   ├── fill_사업계획서_template.json
│   ├── sections_template.json
│   ├── bold_keywords_template.json
│   ├── images_template.json
│   └── tips/                    # TIPS 전용 템플릿
│       ├── fill_연구개발계획서_template.json
│       ├── sections_연구개발계획서_template.json
│       ├── bold_keywords_tips_template.json
│       └── images_tips_template.json
├── tips/                        # TIPS 관련 자료 + 매핑
│   ├── template_map_tips_일반트랙.json
│   ├── TIPS_리서치_2024_2026.md
│   └── (공고문, 운영지침, 별지서식, 유의사항)
├── references/                  # HWPX 내부 구조 레퍼런스
├── evals/                       # 품질 검증 12개 테스트 케이스
└── examples/
```

---

## HWPX 빌드 파이프라인

```
원본 양식 HWPX
    |
    v
[build_hwpx.py]
    Step 1: 테이블 셀 채우기 (hwpx_handler fill)
    Step 2: 개조식 본문 채우기 (lxml 텍스트 패턴 매칭)
    |
    v
[postprocess_hwpx.py]
    Step 3: linesegarray 교체 (글자 겹침 해결)
    Step 4: charPr 색상 변경 (파란 가이드 -> 검정)
    Step 5: 볼드+밑줄 키워드 강조
    Step 6: 이미지 삽입 (BinData + manifest + hp:pic)
    Step 7: ZIP 메타데이터 복원
    Step 8: 네임스페이스 정규화
    |
    v
제출용 HWPX
```

---

## 명령어 참고

### HWPX 양식 분석

```bash
HANDLER="python ~/.claude/skills/k-proposal/hwpx_handler.py"

$HANDLER analyze "양식.hwpx"                    # 전체 테이블 구조
$HANDLER analyze "양식.hwpx" -t 1 -a            # 특정 테이블 전체 행
$HANDLER read-table "양식.hwpx" -t 3 --json     # JSON 형식 읽기
$HANDLER fill "양식.hwpx" "출력.hwpx" --data data.json  # 채우기
```

### 시각 자료 생성

```bash
VGEN="python ~/.claude/skills/k-proposal/visual_gen.py"

$VGEN chart config.json -o chart.png                          # 단일 차트
$VGEN chart config.json -o chart.png --count 3 --auto-brand   # 브랜드 색상 3종
$VGEN gemini "System architecture diagram" -o arch.png        # Gemini 개념도
```

지원 차트: `bar`, `horizontal_bar`, `line`, `area`, `pie`, `donut`, `stacked_bar`, `grouped_bar`, `infographic`

### 양식 자동 인식 + 문서 비교

```bash
python scripts/auto_template_map.py "양식.hwpx" -o template_map.json
python scripts/compare_docs.py "원본.hwpx" "수정본.hwpx" -o _비교결과.md
```

---

## 작성 규칙

| 규칙 | 내용 |
|------|------|
| 문체 | 개조식 명사형 (~구축, ~확보). 서술형 금지 |
| 약어 | 첫 등장 시 영문 풀네임 + 한국어 설명 병기 |
| 예산 | "1식" 금지. 공수(인원 x 기간 x 단가) 기반 산출 |
| 시장 데이터 | 직접 타겟 시장 데이터 + 연결 논리 필수 |
| 시각 자료 | 데이터 차트: matplotlib. 개념도: Gemini(영문) |
| 광탈 패턴 | "세계 최고 수준", "혁신적인", "본 사업은~" 등 금지 |
| 성능지표 | 정량 수치만. 세계최고 대비 60-80% 권장. "1식" 평가 금지 |

---

## 의존성

```bash
./setup.sh  # 아래를 한 번에 처리
```

| 구분 | 패키지 | 필수 여부 |
|------|--------|-----------|
| Python | `lxml`, `python-docx`, `matplotlib`, `Pillow` | 필수 |
| Python | `google-genai` | Gemini 이미지 생성 시 |
| Node.js | `kordoc` (via npx) | HWP/PDF 고급 파싱 (선택) |

---

## 참고한 저장소

| 저장소 | 참고 내용 |
|--------|----------|
| [chrisryugj/kordoc](https://github.com/chrisryugj/kordoc) | HWP/HWPX/PDF 통합 파싱, 양식 필드 인식, 문서 비교, 한국어 텍스트 정제, MCP 서버 |
| [merryAI/hwpx-report-automation](https://github.com/merryAI-dev/hwpx-report-automation) | HWPX 이미지 삽입 3단계 방식 (BinData + manifest + hp:pic) |
| [203050company/kstartup-business-plan-reviewer](https://github.com/203050company/kstartup-business-plan-reviewer) | 광탈 패턴 감지, AI 흔적 탐지, 휴먼라이징, 발표평가 Q&A |
| [Canine89/gonggong_hwpxskills](https://github.com/Canine89/gonggong_hwpxskills) | 네임스페이스 정규화, evals 자동 검증, XML 레퍼런스 |
| [merryAI-dev/hwpx-filler](https://github.com/merryAI-dev/hwpx-filler) | Rust+WASM HWPX 셀 채우기, self-closing `<hp:run/>` 처리 |

## 라이선스

[MIT License](LICENSE) &copy; 2026 MyOrange
