---
name: proposal-analyze
description: "정부지원사업 공고문과 양식을 분석하여 평가기준, 예산규칙, 양식 테이블맵, 지원유형, 심사역 프로파일을 추출하는 스킬. '공고문 분석', '양식 분석', '양식 구조 파악', '평가기준 추출' 요청 시 사용."
---

# proposal-analyze — 공고문/양식 분석

## 핵심 역할

프로젝트 폴더의 공고문(HWPX/HWP/PDF)과 작성서식(HWPX)을 자동 탐색·분석하여, 이후 모든 단계에서 사용할 `준비자료.md`를 생성한다.

## 단독 사용

```
이 공고문 분석해줘
양식 구조 파악해줘
평가기준 추출해줘
```

## 파이프라인 사용

`/proposal` 전체 파이프라인의 첫 단계로 자동 호출된다.

---

## Step 0: 파일 자동 탐색

현재 작업 디렉토리를 먼저 탐색한다 (경로를 묻기 전에).

```bash
find . -maxdepth 3 \( \
  -name "*.hwpx" -o -name "*.hwp" \
  -o -name "*.pdf" \
  -o -name "*.docx" -o -name "*.doc" \
  -o -name "*.pptx" -o -name "*.ppt" \
  -o -name "*.xlsx" -o -name "*.xls" \
  -o -name "*.txt" -o -name "*.md" \
  -o -name "*.key" -o -name "*.pages" -o -name "*.numbers" \
\) 2>/dev/null | sort
```

탐색 결과를 용도별로 분류:

| 용도 | 파일 패턴 |
|------|----------|
| 모집공고문 | `*공고*`, `*모집*`, `*지원사업*` |
| 작성서식(양식) | `*서식*`, `*양식*`, `*template*`, `*신청서*`, `*계획서 양식*` |
| 회사 참고자료 | `*소개서*`, `*재무*`, `*IR*`, `*사업자*`, `*계획서*` |

분류가 불명확한 파일만 사용자에게 확인. 파일이 없으면 "공고문과 작성서식 파일을 이 폴더에 넣어주세요" 안내 후 대기.

> `.hwp` 파일: kordoc MCP 설치 시 `parse_document`로 직접 파싱 가능. 없으면 한글에서 HWPX 변환 요청.

---

## Step 1: 공고문 분석

### 1-1. 텍스트 추출

**kordoc MCP 활용:**
- PDF: `parse_document`로 마크다운 변환, 테이블 자동 추출, 머리글/바닥글 필터링
- HWP: `parse_document`로 레거시 HWP5 바이너리 직접 파싱
- `parse_form`으로 양식 필드 label-value 자동 인식
- `parse_table`로 특정 테이블만 정밀 추출 (예산표, 평가기준표)

**텍스트 정제** (`text_sanitizer.py`):
- HWP 도형/OLE 대체텍스트 제거 ("사각형입니다" 등 26종)
- 균등배분 공백 복원 ("현 장 대 응" → "현장대응")
- 연속 공백/탭 정리

### 1-2. 추출 항목

- 사업 개요 (사업명, 목적, 기간, 지원금액, 모집규모)
- 지원 자격 요건 (기본요건, 우대요건, 결격사유)
- **평가 기준** (항목별 배점, 세부 평가내용) -- 가장 중요
- 제출 서류 목록 + 형식
- 주요 일정 (마감일, 중간평가일, 최종평가일, 협약일)
- 예산 편성 규칙 (비목, 세목, 사용가능 범위, 비목별 지출 한도 비율)
- 주관기관 지역 (지역성 강조 포인트)
- 주관기관 유형 (심사역 프로파일 추론용)

### 1-3. 지원 유형 분류

공고문 분석 직후, 아래 유형 중 하나로 분류. **유형에 따라 전체 전략이 달라진다.**

| 유형 | 핵심 판단 신호 | 전략 가중치 |
|------|-------------|-----------|
| **예비창업패키지/초기창업패키지** | "예비창업자", "초기창업", 매출 0 허용 | 아이디어 신선도·창업 의지 최대화 |
| **창업도약패키지** | "3년 이내", 스케일업 강조 | 시장 검증 증거·스케일업 시나리오 |
| **TIPS/딥테크** | "기술성", 투자사 연계 | 기술 차별성·논문·특허·투자확약서 |
| **지역 R&D/사업화** | 지자체 주관, 지역 명시 | 지역 기여·지역 파트너·지역 고용 극대화 |
| **수출바우처/글로벌** | "수출", "해외진출" | 수출 실적·해외 파이프라인 구체성 |
| **일반 사업화** | 위에 해당 없음 | 사업성·실행가능성·팀 역량 균형 |

### 1-4. 주관기관 프로파일 → 심사역 성향 추론

| 주관기관 유형 | 심사역 성향 | 작성 톤 |
|------------|-----------|--------|
| 창진원·중기부 | 전문 심사역 | 숫자·스케일업 논리, 전문용어 허용 |
| 테크노파크·진흥원 | 현장 + 교수 혼합 | 기술 실현 가능성 + 사업성 균형 |
| 지자체 직접 | 지역 공무원 | 전문용어 최소화, 지역 기여 극대화 |
| TIPS 운용사(VC) | 투자자 관점 | Unit Economics·Exit 시나리오 |
| 대기업·공기업 | 업종 전문가 | 해당 산업 용어·레퍼런스 활용 |

---

## Step 2: 양식 분석

작성서식 HWPX의 테이블 구조를 파악한다.

```bash
HANDLER="python skill/hwpx_handler.py"

$HANDLER analyze "양식.hwpx"                    # 전체 구조
$HANDLER analyze "양식.hwpx" -t 1 -a            # 특정 테이블 전체 행
$HANDLER read-table "양식.hwpx" -t 3 --json     # JSON 형식
```

**template_map 자동 생성 (새 양식):**
```bash
python scripts/auto_template_map.py "양식.hwpx" -o template_map_draft.json
```

산출물: 테이블 인덱스, 행/열, 셀 매핑(빈셀 ✎), 병합 정보, 작성요령 테이블 위치

### 작성요령 텍스트 자동 추출

`auto_template_map.py`는 작성요령(guide) 테이블의 **전체 텍스트**를 자동 추출하여 `guide_table_contents` 키에 저장한다:

```bash
python scripts/auto_template_map.py "양식.hwpx" -o template_map_draft.json
```

결과물의 `guide_table_contents`에 각 작성요령 테이블의 원문이 포함된다:

```json
{
  "guide_table_contents": {
    "5": {
      "full_text": "ㅇ 시장현황 및 문제점을 시장 및 기술트렌드 측면에서 기술...",
      "bullet_items": ["시장현황 및 문제점을 시장 및 기술트렌드 측면에서 기술", ...]
    }
  }
}
```

이 데이터는 `sections_template.json`의 `writing_guide_full` 필드로 전달되어, `/proposal-write`가 양식이 요구하는 구체적 항목을 빠짐없이 커버하도록 한다.

**sections_template 보강 (선택):**
```bash
python scripts/auto_template_map.py "양식.hwpx" -o template_map.json \
  --enrich-sections templates/tips/sections_연구개발계획서_template.json
```

---

## Step 3: 준비자료 생성

분석 결과를 `_workspace/00_input/준비자료.md`로 저장:
- 공고 요약, 평가기준표
- **지원 유형** + **주관기관 프로파일**
- 예산규칙(비목별 한도 포함)
- 양식 테이블맵
- **작성요령 요약** (각 서술형 섹션에 대한 양식의 구체적 요구사항)
- 광탈 패턴 목록, 지역성 포인트

### 유형 → 템플릿 경로 매핑

준비자료에 아래 두 필드를 반드시 기록한다. 이후 `/proposal-write`와 `/proposal-build`가 이 값으로 해당 유형의 템플릿을 자동 로드한다.

```
proposal_type: tips | startup | scaleup | regional | general
template_dir: templates/tips/ | templates/startup/ | templates/scaleup/ | templates/regional/ | templates/
```

| 유형 | proposal_type | template_dir |
|------|--------------|-------------|
| TIPS/딥테크 | tips | templates/tips/ |
| 예비창업/초기창업패키지 | startup | templates/startup/ |
| 창업도약패키지 | scaleup | templates/scaleup/ |
| 지역 R&D/사업화 | regional | templates/regional/ |
| 일반 사업화 / 기타 | general | templates/ |

---

## 입력/출력

- **입력**: 프로젝트 폴더의 HWPX/HWP/PDF 파일
- **출력**: `_workspace/00_input/준비자료.md`
- **참조 스크립트**: `scripts/auto_template_map.py`, `skill/text_sanitizer.py`
- **다음 단계**: `/proposal-research`
