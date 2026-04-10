#!/usr/bin/env python3
"""작성요령 테이블 셀에 잘못 채워진 내용을 본문 ◦/- 단락으로 이동하는 스크립트.

문제: hwpx_handler fill이 테이블 셀에만 쓸 수 있어서 본문 서술 영역(◦/- 단락)이 비어 있고,
      내용이 작성요령 테이블의 R0 c1 셀에 들어가 있음.

해법: 작성요령 테이블 앞의 빈 ◦/- 단락을 찾아 내용을 이동시킴.

사용법:
  python fix_body_paragraphs.py <input.hwpx> [output.hwpx]
  python fix_body_paragraphs.py <input.hwpx>  # in-place 수정
"""
import re
import sys
import os
import zipfile
from lxml import etree

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
BLACK_STYLE = "79"


def get_text(elem):
    return ''.join(t.text or '' for t in elem.iter(f'{HP}t')).strip()


def set_text_on_paragraph(p, new_text):
    """단락의 텍스트를 교체. 기존 스타일 보존, linesegarray 리셋."""
    for t in p.iter(f'{HP}t'):
        t.text = new_text
        break
    else:
        for run in p.iter(f'{HP}run'):
            t = etree.SubElement(run, f'{HP}t')
            t.text = new_text
            break
        else:
            return False
    for run in p.iter(f'{HP}run'):
        run.set('charPrIDRef', BLACK_STYLE)
    for lsa in p.findall(f'{HP}linesegarray'):
        p.remove(lsa)
    etree.SubElement(p, f'{HP}linesegarray')
    return True


def is_guide_table_with_content(p_elem):
    """작성요령 테이블이면서 실제 콘텐츠(ㅇ 블록)를 포함하는 단락인지 확인."""
    tbl = p_elem.find(f'.//{HP}tbl')
    if tbl is None:
        return False, None

    rows = tbl.findall(f'{HP}tr')
    if len(rows) < 1:
        return False, None

    first_row_cells = rows[0].findall(f'{HP}tc')
    if len(first_row_cells) < 1:
        return False, None

    first_cell_text = get_text(first_row_cells[0])
    if '작성요령' not in first_cell_text:
        return False, None

    if len(first_row_cells) < 2:
        return False, None

    content_text = get_text(first_row_cells[1])
    if not content_text or 'ㅇ' not in content_text:
        return False, None

    return True, content_text


def parse_content_blocks(text):
    """작성요령 셀의 텍스트를 ㅇ/- 블록으로 파싱.

    Returns: [(circle_text, [dash_texts]), ...]
    """
    lines = text.split('\n')
    blocks = []
    current_circle = None
    current_circle_body = []
    current_dashes = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith('ㅇ ') or stripped.startswith('ㅇ\u3000'):
            if current_circle is not None:
                full_circle = current_circle
                if current_circle_body:
                    full_circle += '\n' + '\n'.join(current_circle_body)
                blocks.append((full_circle, current_dashes))
            current_circle = stripped
            current_circle_body = []
            current_dashes = []
        elif stripped.startswith('- ') or stripped.startswith('- \u3000'):
            current_dashes.append(stripped)
        else:
            if current_circle is not None:
                current_circle_body.append(stripped)

    if current_circle is not None:
        full_circle = current_circle
        if current_circle_body:
            full_circle += '\n' + '\n'.join(current_circle_body)
        blocks.append((full_circle, current_dashes))

    return blocks


def find_empty_bullet_paragraphs_before(children, table_idx):
    """작성요령 테이블 앞의 빈 ◦/- 단락들을 찾아서 반환.

    중간에 다른 테이블(경쟁사, 지식재산권 등)이나 소제목("< ... >")이 있어도
    그 너머까지 스캔하여 ◦/- 단락을 찾는다.

    Returns: [(idx, type), ...] where type is 'circle' or 'dash'
    """
    bullets = []
    i = table_idx - 1

    MAJOR_HEADERS = re.compile(
        r'^(Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|Ⅵ)\.'
    )

    while i >= 0:
        tag = children[i].tag.split('}')[-1]
        if tag != 'p':
            break

        has_tbl = children[i].find(f'.//{HP}tbl') is not None
        txt = get_text(children[i])

        if has_tbl:
            is_guide, _ = is_guide_table_with_content(children[i])
            if is_guide:
                break
            i -= 1
            continue

        if txt in ('◦', 'ㅇ', '○'):
            bullets.append((i, 'circle'))
        elif txt == '-':
            bullets.append((i, 'dash'))
        elif txt == '':
            pass
        elif txt.startswith('<') and txt.endswith('>'):
            pass
        elif MAJOR_HEADERS.match(txt):
            break
        elif len(txt) > 2 and not txt.startswith('◦') and not txt.startswith('-'):
            pass

        i -= 1

    bullets.reverse()
    return bullets


def assign_content_to_bullets(blocks, bullet_slots):
    """콘텐츠 블록을 ◦/- 슬롯에 할당.

    Returns: [(idx, text), ...]
    """
    assignments = []

    circle_slots = [(idx, t) for idx, t in bullet_slots if t == 'circle']
    circle_to_dash_slots = {}

    current_circle_idx = -1
    for idx, t in bullet_slots:
        if t == 'circle':
            current_circle_idx = idx
            circle_to_dash_slots[current_circle_idx] = []
        elif t == 'dash' and current_circle_idx >= 0:
            circle_to_dash_slots[current_circle_idx].append(idx)

    for ci, (c_idx, _) in enumerate(circle_slots):
        if ci >= len(blocks):
            break

        circle_text, dash_texts = blocks[ci]

        if ci == len(circle_slots) - 1 and ci < len(blocks) - 1:
            extra_blocks = blocks[ci + 1:]
            for eb_circle, eb_dashes in extra_blocks:
                circle_text += '\n' + eb_circle
                dash_texts = dash_texts + eb_dashes

        dash_slots = circle_to_dash_slots.get(c_idx, [])

        # ◦를 "  ◦ " 접두사로 유지 (원본 양식의 들여쓰기 관례)
        # 원본이 "◦" 하나였으므로, ㅇ → ◦로 변환
        final_circle = circle_text.replace('ㅇ ', '◦ ', 1) if circle_text.startswith('ㅇ') else circle_text
        assignments.append((c_idx, final_circle))

        if dash_slots and dash_texts:
            if len(dash_texts) <= len(dash_slots):
                for di, d_idx in enumerate(dash_slots):
                    if di < len(dash_texts):
                        assignments.append((d_idx, dash_texts[di]))
            else:
                for di, d_idx in enumerate(dash_slots):
                    if di < len(dash_slots) - 1:
                        if di < len(dash_texts):
                            assignments.append((d_idx, dash_texts[di]))
                    else:
                        remaining = dash_texts[di:]
                        combined = '\n'.join(remaining)
                        assignments.append((d_idx, combined))

    return assignments


def fix_hwpx(input_path, output_path=None):
    if output_path is None:
        output_path = input_path

    with zipfile.ZipFile(input_path, 'r') as zf:
        orig_infos = {info.filename: info for info in zf.infolist()}
        all_files = {name: zf.read(name) for name in zf.namelist()}
        namelist = zf.namelist()

    root = etree.fromstring(all_files['Contents/section0.xml'])
    children = list(root)

    total_filled = 0
    tables_processed = 0

    for i, child in enumerate(children):
        is_guide, content = is_guide_table_with_content(child)
        if not is_guide:
            continue

        blocks = parse_content_blocks(content)
        if not blocks:
            continue

        bullet_slots = find_empty_bullet_paragraphs_before(children, i)
        if not bullet_slots:
            print(f"  [idx {i}] 작성요령 발견, 앞에 빈 ◦/- 없음 — 건너뜀")
            continue

        assignments = assign_content_to_bullets(blocks, bullet_slots)

        for idx, text in assignments:
            if set_text_on_paragraph(children[idx], text):
                total_filled += 1
                preview = text[:60].replace('\n', '↵')
                print(f"  [{idx}] ← {preview}...")

        tables_processed += 1
        print(f"  작성요령 T@{i}: {len(blocks)}블록 → {len(assignments)}개 단락 채움")

    print(f"\n총 {tables_processed}개 작성요령 테이블 처리, {total_filled}개 단락 채움")

    xml_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    xml_str = xml_bytes.decode('utf-8')
    xml_str = re.sub(
        r'<\?xml[^?]*\?>',
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
        xml_str, count=1
    )
    all_files['Contents/section0.xml'] = xml_str.encode('utf-8')

    for key in ['Contents/header.xml', 'Contents/content.hpf']:
        if key in all_files:
            txt = all_files[key].decode('utf-8')
            txt = re.sub(
                r'<\?xml[^?]*\?>',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
                txt, count=1
            )
            all_files[key] = txt.encode('utf-8')

    tmp = output_path + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as zfout:
        for name in namelist:
            if name == 'mimetype':
                zfout.writestr(name, all_files[name], compress_type=zipfile.ZIP_STORED)
            elif name in orig_infos:
                zfout.writestr(orig_infos[name], all_files[name])
            else:
                zfout.writestr(name, all_files[name], compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, output_path)
    print(f"\n저장 완료: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python fix_body_paragraphs.py <input.hwpx> [output.hwpx]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file
    fix_hwpx(input_file, output_file)
