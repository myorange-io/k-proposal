#!/usr/bin/env python3
"""
문서 비교 (신구대조표) 유틸리티

두 문서의 텍스트를 블록 단위로 비교하여 변경 사항을 출력한다.
HWPX는 직접 파싱하고, HWP/PDF 등은 kordoc(설치 시 자동 사용)를 통해 변환 후 비교한다.

사용법:
    python compare_docs.py "원본.hwpx" "수정본.hwpx"
    python compare_docs.py "원본.hwp"  "수정본.hwpx"          # 크로스 포맷
    python compare_docs.py "원본.hwpx" "수정본.hwpx" -o diff_report.md
    python compare_docs.py "원본.hwpx" "수정본.hwpx" --tables-only
"""

import argparse
import difflib
import json
import re
import sys
import zipfile
from pathlib import Path

try:
    from lxml import etree
    USING_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree
    USING_LXML = False

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def extract_blocks(hwpx_path: str) -> list:
    """HWPX에서 블록 단위 텍스트 추출 (paragraph, table)"""
    blocks = []
    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        section_files = sorted(
            [n for n in zf.namelist() if re.match(r'Contents/section\d+\.xml', n)]
        )
        for sf in section_files:
            xml_data = zf.read(sf)
            root = etree.fromstring(xml_data)

            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in str(elem.tag) else str(elem.tag)

                if tag == 'tbl':
                    table_text = extract_table_text(elem)
                    if table_text.strip():
                        blocks.append({
                            "type": "table",
                            "text": table_text.strip(),
                        })

                elif tag == 'p':
                    if not is_inside_table(elem, root):
                        para_text = extract_paragraph_text(elem)
                        if para_text.strip():
                            blocks.append({
                                "type": "paragraph",
                                "text": para_text.strip(),
                            })

    return blocks


def is_inside_table(elem, root):
    """요소가 테이블 내부에 있는지 확인 (간이 방식)"""
    parent_map = {c: p for p in root.iter() for c in p}
    current = elem
    while current in parent_map:
        current = parent_map[current]
        tag = current.tag.split('}')[-1] if '}' in str(current.tag) else str(current.tag)
        if tag in ('tc', 'tbl'):
            return True
    return False


def extract_paragraph_text(p_elem) -> str:
    texts = []
    for t_elem in p_elem.iter():
        tag = t_elem.tag.split('}')[-1] if '}' in str(t_elem.tag) else str(t_elem.tag)
        if tag == 't' and t_elem.text:
            texts.append(t_elem.text)
    return ' '.join(texts)


def extract_table_text(tbl_elem) -> str:
    rows_text = []
    for tr in tbl_elem.iter():
        tag = tr.tag.split('}')[-1] if '}' in str(tr.tag) else str(tr.tag)
        if tag == 'tr':
            cells = []
            for tc in tr:
                tc_tag = tc.tag.split('}')[-1] if '}' in str(tc.tag) else str(tc.tag)
                if tc_tag == 'tc':
                    cell_text = []
                    for t in tc.iter():
                        t_tag = t.tag.split('}')[-1] if '}' in str(t.tag) else str(t.tag)
                        if t_tag == 't' and t.text:
                            cell_text.append(t.text)
                    cells.append(' '.join(cell_text))
            if cells:
                rows_text.append(' | '.join(cells))
    return '\n'.join(rows_text)


def compute_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def compare_blocks(blocks_a: list, blocks_b: list, threshold: float = 0.4) -> dict:
    """LCS 기반 블록 비교 — kordoc의 IR-level diff 알고리즘 참고"""
    m, n = len(blocks_a), len(blocks_b)

    if m * n > 5_000_000:
        return _fallback_compare(blocks_a, blocks_b)

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    sim_cache = {}

    def get_sim(i, j):
        key = (i, j)
        if key not in sim_cache:
            a, b = blocks_a[i], blocks_b[j]
            if a["type"] != b["type"]:
                sim_cache[key] = 0.0
            else:
                sim_cache[key] = compute_similarity(a["text"], b["text"])
        return sim_cache[key]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if get_sim(i - 1, j - 1) >= threshold:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    pairs = []
    i, j = m, n
    while i > 0 and j > 0:
        if get_sim(i - 1, j - 1) >= threshold and dp[i][j] == dp[i - 1][j - 1] + 1:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()

    diffs = []
    stats = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}

    ai, bi = 0, 0
    for pi, pj in pairs:
        while ai < pi:
            diffs.append({"type": "removed", "before": blocks_a[ai]})
            stats["removed"] += 1
            ai += 1
        while bi < pj:
            diffs.append({"type": "added", "after": blocks_b[bi]})
            stats["added"] += 1
            bi += 1
        sim = get_sim(ai, bi)
        if sim >= 0.99:
            diffs.append({"type": "unchanged", "before": blocks_a[ai], "after": blocks_b[bi], "similarity": 1.0})
            stats["unchanged"] += 1
        else:
            diffs.append({"type": "modified", "before": blocks_a[ai], "after": blocks_b[bi], "similarity": round(sim, 3)})
            stats["modified"] += 1
        ai += 1
        bi += 1

    while ai < m:
        diffs.append({"type": "removed", "before": blocks_a[ai]})
        stats["removed"] += 1
        ai += 1
    while bi < n:
        diffs.append({"type": "added", "after": blocks_b[bi]})
        stats["added"] += 1
        bi += 1

    return {"stats": stats, "diffs": diffs}


def _fallback_compare(blocks_a, blocks_b):
    diffs = []
    stats = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    for i in range(max(len(blocks_a), len(blocks_b))):
        a = blocks_a[i] if i < len(blocks_a) else None
        b = blocks_b[i] if i < len(blocks_b) else None
        if a and b:
            sim = compute_similarity(a["text"], b["text"]) if a["type"] == b["type"] else 0.0
            if sim >= 0.99:
                diffs.append({"type": "unchanged", "before": a, "after": b, "similarity": 1.0})
                stats["unchanged"] += 1
            elif sim >= 0.4:
                diffs.append({"type": "modified", "before": a, "after": b, "similarity": round(sim, 3)})
                stats["modified"] += 1
            else:
                diffs.append({"type": "removed", "before": a})
                diffs.append({"type": "added", "after": b})
                stats["removed"] += 1
                stats["added"] += 1
        elif a:
            diffs.append({"type": "removed", "before": a})
            stats["removed"] += 1
        elif b:
            diffs.append({"type": "added", "after": b})
            stats["added"] += 1

    return {"stats": stats, "diffs": diffs}


def format_report(result: dict, file_a: str, file_b: str) -> str:
    stats = result["stats"]
    lines = [
        f"# 문서 비교 결과",
        f"",
        f"- 원본: `{file_a}`",
        f"- 수정본: `{file_b}`",
        f"",
        f"## 요약",
        f"",
        f"| 구분 | 건수 |",
        f"|------|------|",
        f"| 추가 | {stats['added']} |",
        f"| 삭제 | {stats['removed']} |",
        f"| 변경 | {stats['modified']} |",
        f"| 동일 | {stats['unchanged']} |",
        f"",
        f"## 상세 변경 내역",
        f"",
    ]

    for d in result["diffs"]:
        dtype = d["type"]
        if dtype == "unchanged":
            continue

        text_preview = ""
        sim_str = ""
        if dtype == "added":
            text_preview = d["after"]["text"][:150]
            lines.append(f"**[추가]** `{d['after']['type']}`")
            lines.append(f"> {text_preview}")
        elif dtype == "removed":
            text_preview = d["before"]["text"][:150]
            lines.append(f"**[삭제]** `{d['before']['type']}`")
            lines.append(f"> ~~{text_preview}~~")
        elif dtype == "modified":
            sim = d.get("similarity", 0)
            lines.append(f"**[변경]** `{d['before']['type']}` (유사도: {sim:.0%})")
            lines.append(f"> 원본: {d['before']['text'][:100]}")
            lines.append(f"> 수정: {d['after']['text'][:100]}")

        lines.append("")

    return "\n".join(lines)


def _extract_blocks_via_kordoc(file_path: str) -> list | None:
    """kordoc bridge로 비-HWPX 파일에서 블록 추출"""
    try:
        skill_dir = Path(__file__).parent.parent / "skill"
        sys.path.insert(0, str(skill_dir))
        from kordoc_bridge import get_bridge
        bridge = get_bridge()
        if not bridge.available:
            return None
        md = bridge.parse(file_path)
        if not md:
            return None
        blocks = []
        for line in md.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("|") and "|" in line[1:]:
                blocks.append({"type": "table", "text": line})
            else:
                blocks.append({"type": "paragraph", "text": line})
        return blocks
    except ImportError:
        return None


def smart_extract_blocks(file_path: str) -> list:
    """파일 확장자에 따라 적절한 추출 방법 선택"""
    ext = Path(file_path).suffix.lower()
    if ext == ".hwpx":
        return extract_blocks(file_path)
    blocks = _extract_blocks_via_kordoc(file_path)
    if blocks is not None:
        return blocks
    if ext == ".hwpx":
        return extract_blocks(file_path)
    print(f"[warn] {ext} 파일은 kordoc가 필요합니다. setup.sh를 실행하세요.", file=sys.stderr)
    return []


def main():
    parser = argparse.ArgumentParser(description="문서 비교 (신구대조표)")
    parser.add_argument("file_a", help="원본 파일 (HWPX/HWP/PDF)")
    parser.add_argument("file_b", help="수정본 파일 (HWPX/HWP/PDF)")
    parser.add_argument("-o", "--output", help="비교 결과 마크다운 파일 출력 경로")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    parser.add_argument("--tables-only", action="store_true", help="테이블 블록만 비교")
    args = parser.parse_args()

    blocks_a = smart_extract_blocks(args.file_a)
    blocks_b = smart_extract_blocks(args.file_b)

    if args.tables_only:
        blocks_a = [b for b in blocks_a if b["type"] == "table"]
        blocks_b = [b for b in blocks_b if b["type"] == "table"]

    result = compare_blocks(blocks_a, blocks_b)

    if args.json:
        output_text = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output_text = format_report(result, args.file_a, args.file_b)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"비교 결과 저장: {args.output}")
    else:
        print(output_text)

    stats = result["stats"]
    print(f"\n추가: {stats['added']} | 삭제: {stats['removed']} | 변경: {stats['modified']} | 동일: {stats['unchanged']}", file=sys.stderr)


if __name__ == "__main__":
    main()
