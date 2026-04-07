# k-proposal

> 정부지원사업 사업계획서, AI가 처음부터 끝까지 만들어 줍니다.

## 이게 뭔가요?

정부지원사업에 지원할 때 가장 힘든 건 **사업계획서 작성**입니다. 이 스킬을 사용하면 Claude Code가 공고문을 분석하고, 회사 자료를 읽고, 사업계획서 초안을 작성하고, HWPX/DOCX 파일까지 자동으로 만들어 줍니다.

### 할 수 있는 것

- 공고문(HWPX/HWP/PDF)을 읽고 평가기준, 예산규칙, 제출서류를 자동 정리
- 회사 자료(재무제표, 서비스 소개서 등)를 분석해서 사업계획서에 반영
- 새 양식의 테이블 구조를 자동 인식하여 template_map 초안 생성
- 심사위원이 싫어하는 표현(광탈 패턴)을 자동으로 걸러냄
- AI가 쓴 티가 나는 문장을 사람이 쓴 것처럼 바꿔줌 (휴먼라이징)
- 시장규모 차트, 서비스 아키텍처, KPI 인포그래픽 등 시각 자료 자동 생성 (브랜드 색상 자동 추출)
- 두 문서를 비교하여 변경 내역을 신구대조표로 확인
- 최종 제출용 HWPX 파일 자동 생성 (DOCX는 요청 시 추가 생성)
- **TIPS(팁스) 일반트랙 연구개발계획서** 전용 워크플로우 지원 (2026년 대개편 반영)

---

## 빠른 시작 (5분)

### Step 1. 사전 준비자료 모으기

스킬이 좋은 사업계획서를 쓰려면 **회사 자료가 필수**입니다. 아래 자료를 하나의 폴더에 모아두세요.

> **`.hwp` (구버전 한글) 파일**: kordoc MCP 서버가 설치되어 있으면 `.hwp` 파일을 직접 읽을 수 있습니다. 설치되어 있지 않으면 한글에서 **다른 이름으로 저장 → 파일 형식: HWPX**로 변환 후 사용하세요.

#### 필수 자료

| 자료 | 형식 | 왜 필요한가 |
|------|------|-------------|
| **모집공고문** | HWPX, HWP, PDF | 평가기준, 예산규칙, 지원자격 파악 |
| **작성서식** (사업계획서 양식) | **HWPX** (`.hwp`는 kordoc MCP로 읽기만 가능) | 테이블 구조 분석 + 데이터 채우기 |
| **사업자등록증** | PDF | 기업명, 대표자, 설립일, 주소, 업종 |
| **최근 재무제표** (최소 1년) | PDF 또는 XLSX | 매출액, 자산, 부채 → 재무건전성 근거 |

#### 있으면 좋은 자료 (많을수록 계획서 품질 향상)

| 자료 | 형식 | 활용처 |
|------|------|--------|
| 서비스/제품 소개서 | PDF 또는 DOCX | 기술스택, 아키텍처, 차별점 |
| 이전에 쓴 사업계획서 | HWPX 또는 DOCX | 기존 서술 재활용, 문체 참고 |
| 투자 IR 자료 | PDF | 비전, 시장분석, 비즈니스 모델 |
| 수상/선정 이력 증빙 | PDF | 공신력 있는 수상실적 근거 |
| 고객사 계약서/세금계산서 | PDF | 매출 증빙, 사업화 실적 |
| 특허/저작권 등록증 | PDF | 기술 경쟁력 근거 |
| 팀원 이력서 (핵심인력) | PDF 또는 DOCX | 수행역량 섹션 근거 |

> **팁**: 자료가 부족해도 진행은 가능합니다. 하지만 재무제표 없이 매출 데이터를 쓰면 팩트체크에서 걸리고, 서비스 소개서 없이 기술 설명을 쓰면 내용이 얕아집니다. 가능한 한 많이 모아주세요.

### Step 2. 설치 (원스텝)

```bash
git clone https://github.com/myorange-io/k-proposal.git
cd k-proposal
./setup.sh
```

`setup.sh`가 아래를 한 번에 처리합니다:
- Python 의존성 설치 (`lxml`, `python-docx`, `matplotlib`, `Pillow`)
- kordoc 설치 확인 및 MCP 서버 자동 설정 (Node.js 있을 때)
- Claude Code 스킬 등록 (`~/.claude/skills/k-proposal/`)

> **Node.js가 없어도 기본 기능은 동작합니다.** kordoc은 HWP/PDF 고급 파싱을 위한 선택적 의존성으로, Node.js가 설치되어 있으면 자동으로 활성화됩니다.

### Step 3. 실행

```
사업계획서 작성해줘 /k-proposal
```

스킬이 실행되면 먼저 **모드를 물어봅니다**:

```
어떤 모드로 진행할까요?
A) 협업 모드 — 중요한 결정은 함께 (추천)
B) 자동 모드 — 전부 맡기고 결과만 확인
```

- **협업 모드** (추천): 사업명, 예산, 목표 등 중요한 결정 5곳에서 선택지를 보여줍니다
- **자동 모드**: AI가 다 결정하고 결과물만 보여줍니다. 급할 때 사용

### Step 4. 자료 탐색 → 진행

모드를 선택하면 AI가 **현재 폴더를 자동으로 탐색**합니다. 별도로 파일 경로를 알려줄 필요 없습니다.

```
AI: 현재 폴더에서 아래 파일을 찾았습니다.
    📄 공고문: 모집공고.pdf
    📋 작성서식: 사업계획서_양식.hwpx
    🏢 회사자료: 서비스소개서.pdf, 재무제표_2024.xlsx
    용도가 맞나요? 추가로 전달할 파일이 있으면 알려주세요.
```

파일이 다른 폴더에 있으면 그 경로를 알려주세요. 이후 Phase 1~5까지 자동 진행됩니다.

### Step 5. 결과물 확인

완성되면 아래 파일이 생성됩니다:

```
프로젝트폴더/
├── 제출용_사업계획서.hwpx     ← 메인 산출물 (원본 양식 기반)
├── _시각자료/                 ← 차트, 아키텍처 이미지 (HWPX에 삽입됨)
├── _사업계획서_준비자료.md    ← 공고 분석 + 회사 자료 정리
├── _초안.md                  ← 마크다운 초안
└── _발표평가_Q&A.md          ← 모의 질문 50개+ 답변
```

> **HWPX가 메인 산출물**입니다. DOCX가 필요하면 "DOCX도 만들어줘"라고 요청하면 추가 생성합니다.

---

## 작동 원리 (전체 워크플로우)

```
Phase 0         Phase 1         Phase 2          Phase 3       Phase 3.5      Phase 3.7       Phase 4        (Phase 4-opt)  Phase 5
파일 탐색   → 공고/양식 분석 → 회사자료 분석 → 초안 작성 → 휴먼라이징 → 시각자료 생성 → HWPX 채우기 → DOCX(요청시) → 검토/제출
HWP자동파싱    kordoc활용       자동         협업 or 자동    자동(필수)     자동(필수)        자동(메인)                     AI 리뷰
```

| Phase | 뭘 하나요? | 왜 필요한가요? |
|-------|-----------|---------------|
| 0. 파일 탐색 | 현재 폴더에서 공고문·양식·회사자료 자동 탐색. `.hwp`는 kordoc MCP로 자동 파싱 | 파일 경로 묻지 않고 바로 시작 |
| 1. 공고/양식 분석 | 공고문에서 평가기준, 예산규칙, 일정 추출. 양식 테이블 구조 파악 | 평가기준에 맞춰 써야 점수가 높음 |
| 2. 회사자료 분석 | 재무제표, 서비스소개서, 기존 계획서에서 정보 추출 | 실제 데이터로 써야 신뢰도가 높음 |
| 3. 초안 작성 | 양식 구조에 맞게 핵심 3문(Why Now / Why Us / Why 지원) 포함 섹션별 작성 | 논리 구조가 합격의 핵심 |
| 3.5. 휴먼라이징 | AI 작성 흔적 제거, 개조식 명사형 문체 변환 | 심사역이 AI 문체를 3초 만에 알아봄 |
| 3.7. 시각자료 생성 | 시장규모 차트, 서비스 아키텍처 등 이미지 파일 생성 | HWPX에 바로 삽입하기 위해 먼저 준비 |
| 4. HWPX 채우기 | 원본 양식에 초안 내용 + 시각자료 삽입 | 제출 형식 그대로 완성 |
| (4-opt) DOCX 생성 | 요청 시에만 DOCX 추가 생성 | DOCX가 필요한 경우에만 |
| 5. 검토/제출 | 광탈 패턴 점검, 팩트체크, 발표평가 Q&A 생성 | 제출 전 마지막 안전망 |

---

## TIPS(팁스) 일반트랙 연구개발계획서

### TIPS란?

민관공동창업자발굴육성(TIPS)은 민간 운영사(VC)가 선투자한 뒤 정부가 R&D 자금을 매칭 지원하는 프로그램입니다. 2026년 대개편으로 R&D 지원금이 최대 **8억원**으로 증액되었습니다.

### TIPS 사용법

```
TIPS 연구개발계획서 작성해줘 /k-proposal
```

tips/ 폴더에 아래 파일을 넣으면 자동으로 TIPS 일반트랙 워크플로우가 활성화됩니다:

```
tips/
├── 2026년+팁스+창업기업+지원계획+수정+공고.hwpx   ← 공고문
├── 붙임1.+...+운영지침+...+본문.pdf               ← 운영지침 (208p)
├── 붙임2.+...+운영지침+...+별지서식.hwpx           ← 양식 서식
└── [붙임3] 팁스 신청방법...유의사항.pdf            ← 유의사항
```

### TIPS 전용 기능

| 기능 | 설명 |
|------|------|
| 서류평가 4대항목 매칭 | 문제인식/실현가능성/성장전략/팀구성에 1:1 대응하는 섹션 자동 구성 |
| 광탈 패턴 30개 | TIPS 특화 탈락 사유 자동 감지 ("4차 산업혁명", TRL 미기재, 팀 미분리 등) |
| 분량 비율 가이드 | 기술 40% / 사업화 30% / 팀 30% 밸런스 자동 검증 |
| 성능지표 역설계 | 선정 + 2년 후 최종평가 동시 달성을 위한 목표 수준 자동 판정 |
| 후속 투자 시나리오 | TIPS R&D → Post-TIPS → 시리즈A 성장 사다리 자동 생성 |
| 예산 자동 검증 | 2026년 인건비 단가, 비목별 한도, "1식" 금지 규칙 적용 |
| 가점 자동 스캔 | 비수도권(3점), ESG(2점), 벤처인증(1점) 등 활용 가능한 가점 안내 |
| 핵심 3문 | Why Now(기술 타이밍) / Why Us(팀+IP) / Why 정부 R&D(자력 불가 증명) |

### TIPS 관련 파일

| 파일 | 설명 |
|------|------|
| `tips/template_map_tips_일반트랙.json` | 별지 제3호(3-1) 본문1 테이블 T25~T79 매핑 + 예산 규칙 |
| `tips/TIPS_리서치_2024_2026.md` | 최근 3년 통계, 합격/탈락 패턴, 최종평가 기준 등 리서치 레퍼런스 |
| `templates/tips/fill_연구개발계획서_template.json` | 성능지표, 경쟁사, 고용, 사업화성과 테이블 셀 데이터 |
| `templates/tips/sections_연구개발계획서_template.json` | 12개 서술형 본문 섹션 (4대 평가항목 매칭) |
| `templates/tips/bold_keywords_tips_template.json` | 심사위원용 강조 키워드 6개 카테고리 |
| `templates/tips/images_tips_template.json` | 아키텍처, 플로우차트, 시장규모 등 6종 이미지 설정 |

### 2026년 TIPS 주요 변경사항

- R&D 지원금: 5억 → **최대 8억원** (60% 증액)
- 선정 규모: **800개사**
- 접수 방식: 수시 → **분기별** (1, 2, 3분기 각 1회)
- 선투자: 수도권 **2억+**, 비수도권 **1억+**
- 가점: 최대 **5점** (비수도권 3점, ESG 2점, 벤처인증 1점, 퇴직연금 1점)
- 비수도권 선정 **50% 우선 할당**

---

## 상세 문서 (개발자/고급 사용자용)

아래부터는 내부 구조, 빌드 파이프라인, 코드 수준의 상세 설명입니다.
처음 사용하시는 분은 위의 "빠른 시작"만 따라하면 됩니다.

---

정부지원사업 사업계획서를 **파일 탐색 → 공고/양식 분석 → 초안 작성 → 휴먼라이징 → 시각자료 생성 → HWPX 채우기 → 검토 → 제출**까지 end-to-end로 처리하는 Claude Code / Cursor 스킬 + 작업 스크립트.

## 구조

```
k-proposal/
├── setup.sh                  # 원스텝 설치 (pip + kordoc + MCP 설정)
├── skill/                    # Claude Code 스킬 (SKILL.md + 핸들러)
│   ├── SKILL.md              # 스킬 정의 (전체 워크플로우 + TIPS 전용 워크플로우)
│   ├── hwpx_handler.py       # HWPX 파일 분석/채우기/행추가 핸들러 (손상 ZIP 자동 복구 포함)
│   ├── visual_gen.py         # 시각 자료 생성 (Gemini + matplotlib + mermaid)
│   ├── text_sanitizer.py     # 한국어 텍스트 정제 (균등배분 공백, HWP 대체텍스트 제거)
│   ├── kordoc_bridge.py      # kordoc CLI 브릿지 (MCP 없이 Python에서 직접 호출)
│   └── template_map.json     # 템플릿 매핑 정보 (일반 사업화 자금)
├── scripts/                  # HWPX 빌드 파이프라인 스크립트
│   ├── build_hwpx.py         # Step 1+2: 테이블 셀 채우기 + 개조식 본문 채우기
│   ├── postprocess_hwpx.py   # Step 3: diff 기반 후처리 (lineseg + 볼드밑줄 + 이미지 + 네임스페이스)
│   ├── fix_namespaces.py     # 네임스페이스 정규화 (ns0:/ns1: → hh/hc/hp/hs)
│   ├── insert_image.py       # HWPX 이미지 삽입 (merryAI 3단계 방식)
│   ├── auto_template_map.py  # 양식 자동 인식 → template_map 초안 생성 (TIPS 키워드 포함)
│   ├── compare_docs.py       # 문서 비교 (신구대조표) — HWPX 블록 단위 diff
│   └── fill_all_reference.py # 참고용: 테이블+개조식 통합 스크립트
├── templates/                # JSON 데이터 템플릿 (프로젝트별 data/ 폴더에 복사하여 사용)
│   ├── fill_신청서_template.json       # 신청서(T1) 기업정보
│   ├── fill_사업계획서_template.json   # 사업계획서 테이블 (T3, T5~T8, T10, T13~T15, T22)
│   ├── sections_template.json         # 개조식 본문 서술 (header_keyword + pairs)
│   ├── bold_keywords_template.json    # 볼드+밑줄 강조 키워드
│   ├── images_template.json           # 이미지 삽입 설정 (파일명, 위치, 너비)
│   └── tips/                          # TIPS 일반트랙 전용 템플릿
│       ├── fill_연구개발계획서_template.json     # 성능지표, 경쟁사, 사업화성과 셀 데이터
│       ├── sections_연구개발계획서_template.json  # 12개 서술형 본문 (4대 평가항목 매칭)
│       ├── bold_keywords_tips_template.json     # TIPS 심사 강조 키워드 6개 카테고리
│       └── images_tips_template.json            # 아키텍처, 플로우차트 등 6종 이미지
├── tips/                     # TIPS 일반트랙 관련 자료 + 매핑
│   ├── template_map_tips_일반트랙.json           # 별지 제3호(3-1) T25~T79 테이블 매핑 + 예산 규칙
│   ├── TIPS_리서치_2024_2026.md                  # 최근 3년 리서치 레퍼런스
│   ├── 2026년+팁스+...+수정+공고.hwpx            # 공고문
│   ├── 붙임1.+...+운영지침+...+본문.pdf          # 운영지침 (208p)
│   ├── 붙임2.+...+운영지침+...+별지서식.hwpx     # 양식 서식
│   └── [붙임3] 팁스 신청방법...유의사항.pdf      # 유의사항
├── references/               # 참조 문서
│   └── xml-internals.md      # HWPX ZIP 구조, 네임스페이스, 단위 변환, XML 요소 상세
├── evals/                    # 품질 검증 테스트
│   └── evals.json            # 12개 자동 검증 케이스 (광탈 패턴, 문체, 예산, HWPX 등)
└── examples/                 # 예시 (선택적)
```

## HWPX 빌드 파이프라인

```
원본 HWPX 양식
    │
    ▼
[build_hwpx.py]  ─── Step 1: hwpx_handler fill (테이블 셀 채우기)
    │                 Step 2: lxml 직접 조작 (개조식 본문 텍스트 패턴 매칭)
    │                 Step 3: XML 선언 큰따옴표 + ZIP 메타데이터 보존
    ▼
[postprocess_hwpx.py] ─── Step 4: 원본 대비 diff → linesegarray 빈 태그 교체 (글자 겹침 해결)
    │                      Step 5: charPrIDRef → 검정(79) 변경 (파란색 가이드 제거)
    │                      Step 6: 볼드+밑줄 charPr 등록 + 키워드 강조 (run 분할)
    │                      Step 7: 이미지 삽입 (merryAI 3단계: BinData + manifest + hp:pic)
    │                      Step 8: 최종 ZIP 메타데이터 복원
    │                      Step 9: 네임스페이스 정규화 (ns0:/ns1: → hh/hc/hp/hs)
    ▼
제출용 HWPX
```

## HWPX 편집 시 핵심 원칙

### 글자 겹침 해결
```python
# 원본과 수정본의 모든 <hp:p> 텍스트를 비교
# 텍스트가 변경된 단락의 linesegarray를 빈 태그로 교체
# → 한글이 파일을 열 때 줄 레이아웃을 재계산함
for lsa in mod_p.findall(f'{HP}linesegarray'):
    mod_p.remove(lsa)
etree.SubElement(mod_p, f'{HP}linesegarray')
```

**핵심**: 특정 charPrIDRef만 필터링하면 안 됨. **원본 대비 diff 기반으로 변경된 모든 단락**을 찾아야 함.

### XML 선언 따옴표
```python
# lxml은 작은따옴표 사용 → 한글은 큰따옴표만 인식
xml_str = re.sub(r'<\?xml[^?]*\?>', 
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', 
    xml_str, count=1)
```

### 이미지 삽입 (merryAI 방식)
3단계 프로세스:
1. `BinData/`에 이미지 파일 복사 + 고유 ID 생성
2. `Contents/content.hpf` manifest에 `opf:item` 등록
3. `Contents/section0.xml`에 `hp:p > hp:run > hp:pic > hc:img` XML 생성

참고: [merryAI/hwpx-report-automation](https://github.com/merryAI-dev/hwpx-report-automation)

### ZIP 메타데이터 보존
- `mimetype`은 반드시 첫 엔트리, `ZIP_STORED` 압축
- 원본 `ZipInfo`를 그대로 `writestr(info, data)`로 전달
- 새로 추가된 파일(이미지 등)은 `ZIP_DEFLATED`

## 산출물 형식

**HWPX가 메인 산출물**, **DOCX는 요청 시 추가 생성**.

- HWPX: 원본 양식의 테이블 셀에 데이터를 채우고, 개조식 본문을 lxml로 직접 조작 + 시각 자료 삽입
- DOCX: 사용자가 "DOCX도 만들어줘"라고 요청할 때만 python-docx로 생성

## 사용법

### 1. 설치

```bash
git clone https://github.com/myorange-io/k-proposal.git
cd k-proposal && ./setup.sh

# 업데이트 시
cd k-proposal && git pull && ./setup.sh
```

### 2. 사업계획서 작성 요청

Claude Code에서 아래와 같이 요청하면 스킬이 자동으로 실행된다.

```
사업계획서 작성해줘 /k-proposal
```

### 3. 실행 모드 선택

스킬이 실행되면 먼저 모드를 물어본다.

#### 모드 A: 협업 모드 (기본, 추천)

AI가 초안을 작성하되, **핵심 의사결정 포인트에서 사용자에게 질문**한다.

```
질문 순서:
1. 사업명 확정 — 후보 3개 제시 → 택1 또는 수정
2. 핵심 수행 내용 — 옵션 제시 → 선택
3. 예산 배분 — 초안 제시 → 항목별 조정
4. 정량적 목표 — 초안 제시 → 목표치 조정
5. 최종 확인 — HWPX 저장 전 내용 확인
```

예시 대화:
```
사용자: 우리 서비스 고도화로 지원할게
AI: 어떤 모드로 진행할까요?
    A) 협업 모드 — 중요한 결정은 함께 (추천)
    B) 자동 모드 — 전부 맡기고 결과만 확인
사용자: A
AI: [사업명 후보 3개 제시]
    A) (서비스명) 고도화 및 시장 확대 기반 구축
    B) ...
    C) ...
사용자: A
AI: [핵심 수행 내용 옵션 제시]
    ...
```

#### 모드 B: 자동 모드

AI가 모든 결정을 내려 **한 번에 완성본을 생성**한다.
사업명, 예산, 목표 등을 AI가 최적으로 결정하고, 완성 후 "수정할 부분 있으세요?" 한 번만 질문한다.

### 4. 전체 워크플로우

```
Phase 0         Phase 1         Phase 2          Phase 3           Phase 3.5        Phase 3.7       Phase 4          Phase 5
파일 탐색   → 공고/양식 분석 → 회사자료 분석 → 초안 작성 ────→ 즉시 휴먼라이징 → 시각자료 생성 → HWPX 채우기 → 검토/제출
HWP자동파싱    kordoc활용       자동         협업 or 자동        자동(필수)        자동(필수)        자동(메인)     AI 리뷰
```

| Phase | 내용 | 산출물 |
|-------|------|--------|
| 0 | 현재 폴더 자동 탐색, 파일 용도 분류, `.hwp` 자동 파싱 | — |
| 1 | 공고문 분석 (평가기준, 예산규칙, 일정), 양식 분석 (테이블 구조, 빈셀 매핑) | `_준비자료.md` |
| 2 | 참고자료 분석 (서비스소개서, 재무제표, 기존 신청서 등) | `_준비자료.md` 추가 |
| 3 | 핵심 3문(Why Now / Why Us / Why 지원 필요) 정의, 섹션별 초안 작성 (마크다운) | `_초안.md` |
| 3.5 | AI 작성 흔적 제거, 개조식 명사형 문체 전환, 약어 설명 추가 | `_초안.md` 업데이트 |
| 3.7 | 시장규모 차트, 서비스 아키텍처 등 시각자료 이미지 생성 | `_시각자료/` |
| 4 | HWPX 양식 채우기 (빌드 파이프라인) + 시각자료 삽입. DOCX는 요청 시 추가 | `.hwpx` (+ `.docx`) |
| 5 | 광탈 패턴 점검, 팩트체크, 시장 데이터 검증, 발표평가 Q&A 생성 | `_Q&A.md` |

### 5. 시각 자료 생성

| 유형 | 도구 | 이유 |
|------|------|------|
| 데이터 차트 / 인포그래픽 (시장규모, 매출, KPI 카드) | matplotlib | 한국어 폰트 정확, 수치 정밀 |
| 개념도/아키텍처/로드맵 | 나노 바나나 프로 (Gemini, 영문) | 시각적 완성도 높음. 한국어는 깨짐 |

지원 차트 타입: `bar`, `horizontal_bar`, `line`, `area`, `pie`, `donut`, `stacked_bar`, `grouped_bar`, `infographic`

```bash
PYTHON=~/.claude/skills/k-proposal/.venv/bin/python3
VGEN="$PYTHON ~/.claude/skills/k-proposal/visual_gen.py"

# 단일 차트 생성
$VGEN chart config.json -o _시각자료/chart.png

# 변형 3개 생성 (브랜드 색상 자동 탐색 + 기본 팔레트 2종)
$VGEN chart config.json -o _시각자료/chart.png --count 3 --auto-brand

# 로고 이미지 지정해서 브랜드 색상 추출
$VGEN chart config.json -o _시각자료/chart.png --count 3 --brand-image 로고.png

# Gemini 이미지 (영문 프롬프트, 변형 3개)
$VGEN gemini "Service architecture: mobile app → API → AI engine → DB" \
  -o _시각자료/arch.png --style diagram --count 3
```

### 6. HWPX 양식 분석 명령어

```bash
PYTHON=~/.claude/skills/k-proposal/.venv/bin/python3
HANDLER="$PYTHON ~/.claude/skills/k-proposal/hwpx_handler.py"

# 전체 테이블 구조 (처음 3행)
$HANDLER analyze "양식.hwpx"

# 특정 테이블 전체 행 (✎=빈셀)
$HANDLER analyze "양식.hwpx" -t 1 -a

# 테이블 일괄 읽기 (JSON)
$HANDLER read-table "양식.hwpx" -t 3 --json

# 채우기 전 검증
$HANDLER fill "양식.hwpx" "출력.hwpx" --data data.json --validate

# 채우기 실행
$HANDLER fill "양식.hwpx" "출력.hwpx" --data data.json

# 행 추가
$HANDLER add-rows "양식.hwpx" "출력.hwpx" -t 7 -n 5 --template-row 1
```

### 7. 양식 자동 인식 + 문서 비교

```bash
# 새 양식에 대한 template_map 초안 자동 생성
python scripts/auto_template_map.py "양식.hwpx" -o template_map_draft.json

# kordoc parse_form 결과를 병합하여 정확도 향상
python scripts/auto_template_map.py "양식.hwpx" -o template_map_draft.json \
  --kordoc-json form_fields.json

# 두 HWPX 문서 비교 (신구대조표)
python scripts/compare_docs.py "원본.hwpx" "수정본.hwpx"
python scripts/compare_docs.py "원본.hwpx" "수정본.hwpx" -o _비교결과.md
python scripts/compare_docs.py "원본.hwpx" "수정본.hwpx" --tables-only  # 테이블만 비교
```

## 작성 규칙 요약

| 규칙 | 내용 |
|------|------|
| 문체 | 개조식 명사형 (~구축, ~확보, ~확장). 서술형 금지 |
| 약어 | 첫 등장 시 영문 풀네임 + 한국어 설명 병기 |
| 예산 | "1식" 금지. 공수 기반 산출. 전산개발비는 외주 용역 표현 |
| 시장 데이터 | 제품 직접 타겟 시장 데이터 사용. 연결 논리 필수 |
| 시각 자료 | 차트/인포그래픽: matplotlib (브랜드 색상 자동 추출, `--count 3`으로 변형 생성). 개념도: Gemini(영문) |
| 광탈 패턴 | "세계 최고 수준", "혁신적인", "본 사업은~" 등 금지 |

## 의존성

`./setup.sh`를 실행하면 아래 의존성이 자동으로 설치/설정됩니다.

| 구분 | 패키지 | 필수 여부 |
|------|--------|-----------|
| Python (필수) | `lxml`, `python-docx`, `matplotlib`, `Pillow` | 필수 |
| Python (선택) | `google-genai` | Gemini 이미지 생성 시 |
| Node.js (선택) | `kordoc` (via npx) | HWP/PDF 고급 파싱, 문서 비교, 양식 인식 |

```bash
# 수동 설치 시
pip install lxml python-docx matplotlib Pillow
pip install google-genai              # Gemini 이미지 생성
npm install -g kordoc                 # HWP/PDF 고급 파싱 (Node.js 필요)
```

## 새 프로젝트에서 사용하기

### 일반 사업화 자금

```bash
# 1. 프로젝트 폴더 생성
mkdir my-project && cd my-project

# 2. 원본 양식 HWPX 복사
cp /path/to/작성서식.hwpx ./원본양식.hwpx

# 3. data/ 폴더에 JSON 데이터 준비
mkdir data
# templates/ 폴더의 *_template.json을 data/로 복사 후 내용 수정
cp templates/fill_신청서_template.json data/fill_01_신청서.json
cp templates/fill_사업계획서_template.json data/fill_02_사업계획서.json
cp templates/sections_template.json data/sections.json
cp templates/bold_keywords_template.json data/bold_keywords.json
cp templates/images_template.json data/images.json

# 4. 시각 자료 생성
mkdir _시각자료
# matplotlib 또는 Gemini로 이미지 생성

# 5. 빌드 실행
python scripts/build_hwpx.py --base . --orig 원본양식.hwpx --out 제출용.hwpx
python scripts/postprocess_hwpx.py --base . --hwpx 제출용.hwpx --orig 원본양식.hwpx

# 6. 한글에서 열어 확인
```

### TIPS 일반트랙 연구개발계획서

```bash
# 1. 프로젝트 폴더에 TIPS 공고 자료 넣기
mkdir my-tips-project && cd my-tips-project
# tips/ 폴더에 공고문, 운영지침, 별지서식, 유의사항 복사

# 2. 회사 자료 준비 (재무제표, 서비스소개서, 특허 등)
# 폴더에 함께 넣기

# 3. 스킬 실행 — TIPS 키워드가 감지되면 자동으로 전용 워크플로우 활성화
# Claude Code / Cursor에서:
TIPS 연구개발계획서 작성해줘

# 4. data/ 폴더에 TIPS 전용 JSON 데이터 준비 (수동 빌드 시)
mkdir data
cp templates/tips/fill_연구개발계획서_template.json data/fill_tips.json
cp templates/tips/sections_연구개발계획서_template.json data/sections_tips.json
cp templates/tips/bold_keywords_tips_template.json data/bold_keywords.json
cp templates/tips/images_tips_template.json data/images.json
```

## 참고한 저장소

이 스킬을 만들 때 아래 저장소들을 참고했습니다.

| 저장소 | 참고 내용 |
|--------|----------|
| [chrisryugj/kordoc](https://github.com/chrisryugj/kordoc) | 한국어 문서(HWP/HWPX/PDF/XLSX/DOCX) 통합 파싱·마크다운 변환 라이브러리. 양식 필드 자동 인식(`parse_form`), 크로스 포맷 문서 비교(`diffBlocks`), 손상 ZIP 복구, 한국어 텍스트 정제(균등배분 공백·도형 대체텍스트 제거), MCP 서버 통합을 참고 |
| [merryAI/hwpx-report-automation](https://github.com/merryAI-dev/hwpx-report-automation) | HWPX 이미지 삽입 3단계 방식 (BinData + manifest + hp:pic XML). `insert_image.py`의 핵심 로직을 TypeScript → Python으로 포팅 |
| [203050company/kstartup-business-plan-reviewer](https://github.com/203050company/kstartup-business-plan-reviewer) | 예비창업패키지 사업계획서 검토 스킬. 광탈 패턴 감지, AI 작성 흔적 탐지, 휴먼라이징 치환 패턴, 발표평가 Q&A 생성 로직을 참고 |
| [Canine89/gonggong_hwpxskills](https://github.com/Canine89/gonggong_hwpxskills) | python-hwpx 기반 범용 HWPX 스킬. 네임스페이스 정규화(`fix_namespaces.py`), evals 자동 검증, XML 레퍼런스 분리 구조를 벤치마킹 |
| [merryAI-dev/hwpx-filler](https://github.com/merryAI-dev/hwpx-filler) | Rust+WASM 기반 HWPX 셀 채우기 엔진. 2-pass 바이트 레벨 패치(lxml 재직렬화 없음), self-closing `<hp:run/>` 케이스 분리, 행 클론 기능을 참고 |

## 라이선스

[MIT License](LICENSE) © 2026 MyOrange
