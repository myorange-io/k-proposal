#!/usr/bin/env python3
"""
양식 자동 인식 → template_map.json 초안 자동 생성

kordoc MCP의 parse_form 결과 또는 hwpx_handler의 analyze 결과를 조합하여
새 공고 양식에 대한 template_map.json 초안을 자동으로 생성한다.

사용법:
    python auto_template_map.py "양식.hwpx" -o template_map_draft.json
    python auto_template_map.py "양식.hwpx" -o template_map_draft.json --kordoc-json form_fields.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LABEL_KEYWORDS = {
    "성명", "이름", "주소", "전화", "전화번호", "휴대폰", "연락처",
    "생년월일", "주민등록번호", "소속", "직위", "직급", "부서",
    "이메일", "팩스", "학교", "사업자등록번호", "법인등록번호",
    "신청인", "대표자", "담당자", "작성자", "확인자", "승인자",
    "일시", "날짜", "기간", "장소", "목적", "사유", "비고",
    "금액", "수량", "단가", "합계", "계", "소계",
    "사업명", "과제명", "기업명", "회사명", "상호",
}

PURPOSE_PATTERNS = {
    "신청서": [r"신청서", r"접수", r"신청인"],
    "요약": [r"요약", r"개요", r"총괄"],
    "인력": [r"인력", r"참여.*인력", r"핵심.*인력", r"수행.*조직"],
    "파트너": [r"협력", r"파트너", r"외부.*전문"],
    "보유기술": [r"보유.*기술", r"지식재산", r"특허", r"인프라"],
    "정량목표": [r"정량", r"성과.*지표", r"목표", r"KPI"],
    "추진일정": [r"추진.*일정", r"일정", r"마일스톤"],
    "예산": [r"예산", r"소요.*자금", r"사업비", r"비목"],
    "서명": [r"서명", r"날인", r"대표.*인"],
    "작성요령": [r"작성.*요령", r"유의.*사항", r"참고", r"안내"],
}


def classify_table_purpose(cells_text: str) -> str:
    """테이블의 전체 텍스트를 분석하여 용도를 추론"""
    for purpose, patterns in PURPOSE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, cells_text, re.IGNORECASE):
                return purpose
    return "unknown"


def is_label_cell(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > 30:
        return False
    for kw in LABEL_KEYWORDS:
        if kw in text:
            return True
    if re.match(r'^[가-힣\s()·:]{2,8}$', text) and not re.search(r'\d', text):
        return True
    return False


def detect_editable_cells(rows: list) -> list:
    """빈 셀(편집 가능)을 감지하여 필드 매핑 생성"""
    fields = []
    for r_idx, row in enumerate(rows):
        for c_idx in range(len(row) - 1):
            label_text = row[c_idx].strip()
            value_text = row[c_idx + 1].strip()
            if is_label_cell(label_text) and not value_text:
                fields.append({
                    "row": r_idx,
                    "col": c_idx + 1,
                    "label": label_text.rstrip(":："),
                    "editable": True,
                })
    return fields


def run_hwpx_handler(hwpx_path: str, handler_path: str = None):
    """hwpx_handler.py analyze를 실행하여 테이블 구조 추출"""
    if handler_path is None:
        script_dir = Path(__file__).parent.parent / "skill"
        handler_path = str(script_dir / "hwpx_handler.py")

    tables = []
    try:
        result = subprocess.run(
            [sys.executable, handler_path, "analyze", hwpx_path, "-a"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            current_table = None
            for line in result.stdout.splitlines():
                table_match = re.match(r'=+ Table (\d+)', line)
                if table_match:
                    if current_table is not None:
                        tables.append(current_table)
                    current_table = {
                        "index": int(table_match.group(1)),
                        "rows": [],
                        "raw_text": "",
                    }
                elif current_table is not None:
                    current_table["raw_text"] += line + "\n"
                    row_match = re.match(r'\s*R(\d+)', line)
                    if row_match:
                        cells = re.findall(r'\[([^\]]*)\]', line)
                        current_table["rows"].append(cells)
            if current_table is not None:
                tables.append(current_table)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return tables


def merge_kordoc_fields(template_map: dict, kordoc_json_path: str):
    """kordoc parse_form 결과를 template_map에 병합"""
    with open(kordoc_json_path, 'r', encoding='utf-8') as f:
        form_result = json.load(f)

    fields = form_result.get("fields", [])
    for field in fields:
        label = field.get("label", "")
        value = field.get("value", "")
        row = field.get("row", -1)
        col = field.get("col", -1)
        if label and row >= 0:
            for t_key, t_data in template_map.get("tables", {}).items():
                for f_entry in t_data.get("fields", []):
                    if f_entry.get("label") == label:
                        f_entry["kordoc_detected"] = True
                        if value:
                            f_entry["sample_value"] = value
                        break


def generate_template_map(hwpx_path: str, kordoc_json_path: str = None) -> dict:
    """양식 HWPX를 분석하여 template_map 초안 생성"""
    tables = run_hwpx_handler(hwpx_path)

    template_map = {
        "_comment": "auto-generated draft — review and adjust before use",
        "source_file": Path(hwpx_path).name,
        "tables": {},
        "guide_tables": [],
        "writing_order": [],
    }

    for table in tables:
        t_idx = table["index"]
        purpose = classify_table_purpose(table["raw_text"])
        fields = detect_editable_cells(table["rows"])

        t_key = f"T{t_idx}"
        t_entry = {
            "index": t_idx,
            "purpose": purpose,
            "row_count": len(table["rows"]),
            "fields": fields,
            "expandable": purpose in ("인력", "파트너", "보유기술", "예산"),
            "editable": purpose != "작성요령",
        }

        if purpose == "작성요령":
            template_map["guide_tables"].append(t_idx)
        else:
            template_map["writing_order"].append(t_key)

        template_map["tables"][t_key] = t_entry

    if kordoc_json_path:
        merge_kordoc_fields(template_map, kordoc_json_path)

    return template_map


def main():
    parser = argparse.ArgumentParser(
        description="양식 HWPX → template_map.json 초안 자동 생성"
    )
    parser.add_argument("hwpx", help="양식 HWPX 파일 경로")
    parser.add_argument("-o", "--output", default="template_map_draft.json",
                        help="출력 JSON 파일 경로")
    parser.add_argument("--kordoc-json", help="kordoc parse_form 결과 JSON 파일 (선택)")
    parser.add_argument("--handler", help="hwpx_handler.py 경로 (기본: skill/hwpx_handler.py)")
    args = parser.parse_args()

    template_map = generate_template_map(args.hwpx, args.kordoc_json)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(template_map, f, ensure_ascii=False, indent=2)

    print(f"template_map 초안 생성 완료: {args.output}")
    print(f"  테이블: {len(template_map['tables'])}개")
    print(f"  작성요령 테이블: {template_map['guide_tables']}")
    print(f"  작성 순서: {template_map['writing_order']}")
    total_fields = sum(
        len(t.get("fields", []))
        for t in template_map["tables"].values()
    )
    print(f"  감지된 편집 가능 필드: {total_fields}개")


if __name__ == "__main__":
    main()
