---
name: proposal-build
description: "HWPX 양식에 초안+시각자료를 채워 제출 파일을 생성하는 8단계 빌드 파이프라인. 'HWPX 채워줘', 'HWPX 빌드', '양식에 내용 넣어줘' 요청 시 사용."
---

# proposal-build — HWPX 8단계 빌드 파이프라인

## 핵심 역할

휴먼라이징 완료된 초안 + 구조화 데이터(sections.json, fill.json) + 시각자료를 원본 HWPX 양식에 채워 제출 파일을 생성한다.

## 단독 사용

```
HWPX 채워줘
HWPX 빌드해줘
양식에 내용 넣어줘
```

## 파이프라인 사용

`/proposal-write --humanize` + `/proposal-review` 통과 후 자동 호출.

---

## 8단계 파이프라인

```
원본 양식 HWPX
    |
    v
Step 1:   fill — 앞표지(T0) + 요약문(T2) + 데이터 테이블 셀 (hwpx_handler fill)
Step 2:   sections — 본문 ◦/- 단락 채우기 (sections.json 패턴 매칭, lxml)
Step 2.5: fix_body_paragraphs — 작성요령 잔류 내용 → 본문 이동 (안전망)
Step 2.7: remove_empty_bullets — 미사용 빈 불릿 마커(◦/-) 삭제
Step 2.9: remove_guide_tables — 작성요령 테이블 전체 삭제
Step 3-0: replace_cover — 커버페이지 플레이스홀더 교체
    |
    v
Step 3:   postprocess — linesegarray 교체 (글자 겹침 해결)
Step 4:   charPr 색상 변경 (파란 가이드 → 검정)
Step 5:   볼드+밑줄 키워드 강조
Step 6:   이미지 삽입 (BinData + manifest + hp:pic)
Step 7:   ZIP 메타데이터 복원
Step 8:   네임스페이스 정규화
    |
    v
test_hwpx — 자동 검증
    |
    v
제출용.hwpx (작성요령 0개, 빈슬롯 0개, 커버 교체 완료)
```

---

## 입력 파일

| 파일 | 용도 |
|------|------|
| `_workspace/02_writer/draft_humanized.md` | 최종 초안 (참조용) |
| `_workspace/02_writer/draft_sections.json` | 개조식 단락 → `data/sections.json`으로 복사 |
| `_workspace/02_writer/draft_fill.json` | 테이블 셀 → `data/fill_*.json`으로 복사 |
| `_workspace/04_visualizer/` | 시각 자료 이미지 |
| `data/cover.json` | 커버페이지 (과제명, 운영사명, 기업명) |
| `data/bold_keywords.json` | 볼드+밑줄 강조 키워드 목록 |

writer가 `준비자료.md`의 `template_dir`에 따라 유형별 템플릿으로 sections.json/fill.json을 생성하므로, build는 유형을 직접 판단하지 않고 writer 산출물을 그대로 사용한다.

---

## 주요 명령어

```bash
HANDLER="python skill/hwpx_handler.py"

# 분석
$HANDLER analyze "양식.hwpx"
$HANDLER analyze "양식.hwpx" -t 1 -a
$HANDLER read-table "양식.hwpx" -t 3 --json

# 채우기 (사전 검증 → 실행)
$HANDLER fill "양식.hwpx" "출력.hwpx" --data data.json --validate
$HANDLER fill "양식.hwpx" "출력.hwpx" --data data.json

# 행 추가 (합계행 복제 방지: --template-row 지정)
$HANDLER add-rows "양식.hwpx" "출력.hwpx" -t 15 -n 3 --template-row 2

# 이미지 삽입
$HANDLER insert-image "양식.hwpx" "출력.hwpx" --image chart.png --after-table 9 --width 14

# 텍스트 단락 삽입
$HANDLER insert-text "양식.hwpx" "출력.hwpx" --after-table 4 --text "본문 추가"
```

---

## 빌드 스크립트

```bash
python scripts/build_hwpx.py --base /path/to/project --orig 원본양식.hwpx --out 제출용.hwpx
python scripts/postprocess_hwpx.py --base /path/to/project --hwpx 제출용.hwpx --orig 원본양식.hwpx
python scripts/test_hwpx.py 제출용.hwpx --orig 원본양식.hwpx
```

---

## 완료 조건 (전부 충족해야 Phase 5 진행)

| 조건 | 검증 방법 |
|------|----------|
| 앞표지 필수 셀 기입 | test_hwpx.py + 수동 확인 |
| 요약문 필수 셀 기입 | test_hwpx.py + 수동 확인 |
| 본문 빈 ◦/- 단락 0개 | build_hwpx.py Step 2.7 자동 삭제 |
| 작성요령 테이블 0개 | build_hwpx.py Step 2.9 자동 삭제 |
| 커버 플레이스홀더 0개 | build_hwpx.py Step 3-0 자동 교체 |
| test_hwpx.py 전 항목 PASS | 자동 실행 |

---

## 알려진 문제 + 해결법

| 문제 | 원인 | 해결 |
|------|------|------|
| 한글에서 글자 겹침 | linesegarray 캐시가 텍스트 길이와 불일치 | postprocess에서 빈 태그로 교체 |
| 파란색 텍스트 | 원본 가이드 스타일(charPr) 잔존 | charPrIDRef를 79(검정)로 변경 |
| 이미지 안 보임 | content.hpf manifest 미등록 | insert_image.py가 자동 등록 |
| ns0:/ns1: 태그 | stdlib ET의 네임스페이스 재작성 | fix_namespaces.py로 정규화 |
| 손상된 ZIP | 비정상 종료 후 재작업 | hwpx_handler 자동 복구 (Local File Header 스캔) |
| 작성요령 잔존 | remove-guides 미수행 | build_hwpx.py Step 2.9 자동 삭제 |
| 빈 ◦/- 잔존 | 슬롯 > 내용 | build_hwpx.py Step 2.7 자동 삭제 |

---

## fill_data.json 형식

```json
{
  "cells": [
    {"table_index": 0, "row": 12, "col": 2, "text": "과제명 국문", "preserve_style": true},
    {"table_index": 2, "row": 0, "col": 1, "text": "사업명", "preserve_style": true}
  ]
}
```

`table_index`: -1은 섹션 마커(무시). `preserve_style`: true면 기존 스타일 유지.

---

## 입력/출력

- **입력**: 원본 양식 HWPX + writer 산출물 + 시각자료
- **출력**: `제출용_사업계획서.hwpx`
- **참조 스크립트**: `build_hwpx.py`, `postprocess_hwpx.py`, `fix_body_paragraphs.py`, `test_hwpx.py`, `fix_namespaces.py`, `insert_image.py`
- **이전 단계**: `/proposal-write --humanize`
- **다음 단계**: `/proposal-qa`
