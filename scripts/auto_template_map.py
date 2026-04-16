#!/usr/bin/env python3
"""
양식 자동 인식 → template_map.json 초안 자동 생성

hwpx_handler의 analyze 결과와 kordoc(설치 시 자동 사용)를 조합하여
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
import tempfile
from pathlib import Path

LABEL_KEYWORDS = {
    "성명", "이름", "주소", "전화", "전화번호", "휴대폰", "연락처",
    "생년월일", "주민등록번호", "소속", "직위", "직급", "부서",
    "이메일", "팩스", "학교", "사업자등록번호", "법인등록번호",
    "신청인", "대표자", "담당자", "작성자", "확인자", "승인자",
    "일시", "날짜", "기간", "장소", "목적", "사유", "비고",
    "금액", "수량", "단가", "합계", "계", "소계",
    "사업명", "과제명", "기업명", "회사명", "상호",
    # TIPS R&D 특화 키워드
    "TRL", "기술성숙도", "출연금", "정부지원연구개발비", "민간부담금",
    "현금", "현물", "투자금", "운영사", "선투자", "세계최고수준",
    "성능지표", "평가항목", "평가방법", "평가환경", "비중",
    "보안등급", "연구책임자", "인건비계상률", "경쟁사명", "판매가격",
    "연구개발비", "연구시설", "장비명", "구축비용", "연구실운영비",
    "매출액", "수출액", "자본금", "연구개발기간", "설립년월일",
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
    # TIPS R&D 특화 패턴
    "성능지표": [r"성능.*지표", r"평가항목.*주요.*성능", r"세계최고수준", r"목표.*설정.*근거"],
    "평가방법": [r"평가방법", r"평가환경", r"공인.*시험"],
    "경쟁사": [r"경쟁사", r"판매가격", r"연.*판매액"],
    "시장현황": [r"시장.*규모", r"시장.*점유율", r"목표.*시장"],
    "사업화성과": [r"사업화.*성과", r"예상.*매출", r"매출.*산정"],
    "연구개발비": [r"연구개발비", r"정부.*지원", r"기관.*부담", r"출연금", r"민간.*부담"],
    "시설장비": [r"시설.*장비", r"구축.*비용", r"설치.*장소"],
    "보안등급": [r"보안.*등급", r"보안.*과제", r"자체.*점검"],
    "고용": [r"고용.*현황", r"신규.*고용", r"상시.*고용"],
    "글로벌": [r"글로벌.*진출", r"해외.*투자", r"현지.*창업", r"수출"],
    "운영사보육": [r"운영사.*지원", r"보육.*전략", r"전담.*멘토"],
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


def _try_kordoc_form(hwpx_path: str) -> dict | None:
    """kordoc bridge를 통해 양식 필드 자동 추출 시도"""
    try:
        skill_dir = Path(__file__).parent.parent / "skill"
        sys.path.insert(0, str(skill_dir))
        from kordoc_bridge import get_bridge
        bridge = get_bridge()
        if bridge.available:
            return bridge.parse_form(hwpx_path)
    except ImportError:
        pass
    return None


def extract_guide_table_text(hwpx_path: str, table_index: int) -> dict:
    """hwpx_handler의 read-table을 호출하여 작성요령 테이블의 전체 텍스트를 추출"""
    handler_path = str(Path(__file__).parent.parent / "skill" / "hwpx_handler.py")
    try:
        result = subprocess.run(
            [sys.executable, handler_path, "read-table", hwpx_path,
             "--table", str(table_index), "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        data = json.loads(result.stdout)
        cells = data.get("cells", [])
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return {}

    all_texts = []
    bullet_items = []
    for cell in cells:
        text = cell.get("text", "").strip()
        if not text:
            continue
        all_texts.append(text)
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # ㅇ, -, *, · 등 bullet으로 시작하는 항목을 개별 추출
            if re.match(r'^[ㅇ○◦\-\*·•▶►☞]', line):
                clean = re.sub(r'^[ㅇ○◦\-\*·•▶►☞]\s*', '', line).strip()
                if clean and len(clean) > 5:
                    bullet_items.append(clean)

    full_text = "\n".join(all_texts)
    return {
        "full_text": full_text,
        "bullet_items": bullet_items,
    }


def detect_clickhere_fields(hwpx_path: str) -> list:
    """hwpx_handler의 detect_fields를 호출하여 누름틀 필드 목록 추출"""
    handler_path = str(Path(__file__).parent.parent / "skill" / "hwpx_handler.py")
    try:
        result = subprocess.run(
            [sys.executable, handler_path, "detect-fields", hwpx_path, "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def generate_template_map(hwpx_path: str, kordoc_json_path: str = None) -> dict:
    """양식 HWPX를 분석하여 template_map 초안 생성"""
    tables = run_hwpx_handler(hwpx_path)

    template_map = {
        "_comment": "auto-generated draft — review and adjust before use",
        "source_file": Path(hwpx_path).name,
        "tables": {},
        "guide_tables": [],
        "guide_table_contents": {},
        "clickhere_fields": [],
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

    # 작성요령 테이블에서 전체 텍스트 추출
    for guide_idx in template_map["guide_tables"]:
        guide_content = extract_guide_table_text(hwpx_path, guide_idx)
        if guide_content.get("full_text"):
            # narrative_sections에서 연결된 섹션 이름 찾기
            linked_section = ""
            t_key = f"T{guide_idx}"
            t_data = template_map["tables"].get(t_key, {})
            purpose = t_data.get("purpose", "")

            template_map["guide_table_contents"][str(guide_idx)] = {
                "linked_section": linked_section,
                "full_text": guide_content["full_text"],
                "bullet_items": guide_content["bullet_items"],
            }

    if kordoc_json_path:
        merge_kordoc_fields(template_map, kordoc_json_path)
    else:
        form_result = _try_kordoc_form(hwpx_path)
        if form_result:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, encoding='utf-8'
            ) as f:
                json.dump(form_result, f, ensure_ascii=False)
                tmp_path = f.name
            try:
                merge_kordoc_fields(template_map, tmp_path)
                template_map["_kordoc_auto"] = True
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    # 누름틀(ClickHere) 필드 감지
    clickhere = detect_clickhere_fields(hwpx_path)
    if clickhere:
        template_map["clickhere_fields"] = [
            {"name": f["name"], "guide": f["guide"], "field_type": f["field_type"]}
            for f in clickhere
        ]

    return template_map


def enrich_sections_template(sections_template_path: str, template_map_path: str):
    """기존 sections_template.json에 template_map의 guide_table_contents를 매칭하여
    writing_guide_full 필드를 자동 추가한다.

    Args:
        sections_template_path: sections_*.json 파일 경로
        template_map_path: template_map_*.json 파일 경로 (guide_table_contents 포함)
    """
    with open(sections_template_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)
    with open(template_map_path, 'r', encoding='utf-8') as f:
        tmap = json.load(f)

    guide_contents = tmap.get("guide_table_contents", {})
    narrative_sections = tmap.get("narrative_sections", [])

    # header_keyword → guide_table index 매핑
    keyword_to_guide = {}
    for ns in narrative_sections:
        kw = ns.get("header_keyword", "")
        gt = ns.get("guide_table")
        if kw and gt is not None:
            keyword_to_guide[kw] = str(gt)

    enriched = 0
    for section in sections.get("sections", []):
        header_kw = section.get("header_keyword", "")
        guide_idx = keyword_to_guide.get(header_kw)
        if guide_idx and guide_idx in guide_contents:
            gc = guide_contents[guide_idx]
            section["writing_guide_full"] = gc.get("full_text", "")
            enriched += 1

    with open(sections_template_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    return enriched


def main():
    parser = argparse.ArgumentParser(
        description="양식 HWPX → template_map.json 초안 자동 생성"
    )
    parser.add_argument("hwpx", help="양식 HWPX 파일 경로")
    parser.add_argument("-o", "--output", default="template_map_draft.json",
                        help="출력 JSON 파일 경로")
    parser.add_argument("--kordoc-json", help="kordoc parse_form 결과 JSON 파일 (선택)")
    parser.add_argument("--handler", help="hwpx_handler.py 경로 (기본: skill/hwpx_handler.py)")
    parser.add_argument("--enrich-sections", metavar="SECTIONS_JSON",
                        help="기존 sections_template.json에 writing_guide_full 추가")
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
    gc_count = len(template_map.get("guide_table_contents", {}))
    if gc_count:
        print(f"  작성요령 텍스트 추출: {gc_count}개 테이블")
    ch_count = len(template_map.get("clickhere_fields", []))
    if ch_count:
        print(f"  누름틀(ClickHere) 필드: {ch_count}개")

    # sections_template.json에 writing_guide_full 자동 추가
    if args.enrich_sections:
        enriched = enrich_sections_template(args.enrich_sections, args.output)
        print(f"  sections_template 보강: {enriched}개 섹션에 writing_guide_full 추가")


if __name__ == "__main__":
    main()
