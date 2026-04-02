#!/usr/bin/env python3
"""
원본 HWPX에서 시작하여 한 번에 모든 내용을 채우는 스크립트.
1단계: 테이블 셀 채우기 (hwpx_handler fill)
2단계: 개조식 단락 채우기 (텍스트 패턴 매칭)
"""
import subprocess, sys, os

BASE = os.environ.get("HWPX_BASE", os.getcwd())
HWPX = os.environ.get("HWPX_FILE", os.path.join(BASE, "제출용.hwpx"))
HANDLER = os.path.expanduser("~/.claude/skills/k-proposal/.venv/bin/python3")
HANDLER_PY = os.path.expanduser("~/.claude/skills/k-proposal/hwpx_handler.py")

# ============================================================
# 1단계: 테이블 셀 채우기
# ============================================================
for json_file in ['fill_step1.json', 'fill_step2.json', 'fill_step4.json']:
    path = os.path.join(BASE, "_작업파일", json_file)
    if os.path.exists(path):
        result = subprocess.run(
            [HANDLER, HANDLER_PY, "fill", HWPX, HWPX, "--data", path],
            capture_output=True, text=True
        )
        print(f"[{json_file}] {result.stdout.strip().split(chr(10))[-1]}")

# ============================================================
# 2단계: 개조식 단락 채우기 (텍스트 패턴 매칭)
# ============================================================
import zipfile, re
from lxml import etree

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'

with zipfile.ZipFile(HWPX, 'r') as zf:
    orig_infos = {info.filename: info for info in zf.infolist()}
    all_files = {name: zf.read(name) for name in zf.namelist()}
    namelist = zf.namelist()

root = etree.fromstring(all_files['Contents/section0.xml'])
children = list(root)

def get_text(elem):
    return ''.join(t.text or '' for t in elem.iter(f'{HP}t')).strip()

BLACK_STYLE = "79"  # charPrIDRef: 맑은고딕 10pt 검정(#000000)

def set_text(elem, new_text):
    """기존 <hp:t> 텍스트만 교체, 없으면 run에 <hp:t> 생성.
    linesegarray를 빈 태그로 교체 (한글이 열 때 줄 레이아웃 재계산 유도).
    charPrIDRef를 검정색 맑은고딕으로 변경."""
    for t in elem.iter(f'{HP}t'):
        t.text = new_text
        break
    else:
        for run in elem.iter(f'{HP}run'):
            t = etree.SubElement(run, f'{HP}t')
            t.text = new_text
            break
        else:
            return False
    # 모든 run의 charPrIDRef를 검정색 맑은고딕으로 변경
    for run in elem.iter(f'{HP}run'):
        run.set('charPrIDRef', BLACK_STYLE)
    # linesegarray를 빈 태그로 교체 (삭제가 아닌 빈 태그 — merryAI 방식)
    # 한글이 빈 linesegarray를 만나면 텍스트에 맞게 줄 레이아웃을 재계산함
    for lsa in elem.findall(f'{HP}linesegarray'):
        elem.remove(lsa)
    empty_lsa = etree.SubElement(elem, f'{HP}linesegarray')
    return True

# 전략: 앞 단락의 고유 텍스트를 키로, 그 뒤의 ㅇ/◦와 - 단락에 내용을 채움
# (하드코딩 예시 데이터 삭제됨)
# 실제 사용 시 아래 SECTIONS를 프로젝트에 맞게 채우세요.
# 형식: (header_keyword, [(ㅇ텍스트, -텍스트), ...])
SECTIONS = [
    # 예시:
    # ('주력 사업 현황 및 개요', [
    #     ("   ㅇ (주력 사업 설명)", "     - (세부 내용)"),
    # ]),
]

if not SECTIONS:
    print("WARN: SECTIONS가 비어있습니다. 스크립트 내 SECTIONS를 채워주세요.")
    sys.exit(0)

count = 0
for header_keyword, pairs in SECTIONS:
    # Find header
    header_idx = None
    for i, child in enumerate(children):
        if child.tag.split('}')[-1] == 'p' and header_keyword in get_text(child):
            header_idx = i
            break
    if header_idx is None:
        print(f"  WARN: header '{header_keyword}' not found")
        continue

    # Process pairs
    search_start = header_idx + 1
    for pair in pairs:
        o_text, dash_text = pair

        if o_text is not None and dash_text is None:
            # Special case: replace the "1." paragraph itself
            for j in range(search_start, min(search_start + 5, len(children))):
                child = children[j]
                if child.tag.split('}')[-1] != 'p':
                    continue
                txt = get_text(child)
                if txt in ['1.', '1', '']:
                    if set_text(child, o_text):
                        count += 1
                        print(f"  [{j}] '1.' → {o_text[:50]}...")
                    search_start = j + 1
                    break
            continue

        if o_text is None:
            # Special case: skip ㅇ, only fill -
            for j in range(search_start, min(search_start + 5, len(children))):
                child = children[j]
                if child.tag.split('}')[-1] != 'p':
                    continue
                txt = get_text(child)
                if txt == '-':
                    if set_text(child, dash_text):
                        count += 1
                        print(f"  [{j}] '-' → {dash_text[:50]}...")
                    search_start = j + 1
                    break
            continue

        # Normal case: find ㅇ/◦ then -
        for j in range(search_start, min(search_start + 8, len(children))):
            child = children[j]
            if child.tag.split('}')[-1] != 'p':
                continue
            txt = get_text(child)
            if txt in ['ㅇ', '◦', '']:
                if set_text(child, o_text):
                    count += 1
                    print(f"  [{j}] ㅇ → {o_text[:50]}...")
                # Find next -
                for k in range(j + 1, min(j + 3, len(children))):
                    child2 = children[k]
                    if child2.tag.split('}')[-1] != 'p':
                        continue
                    txt2 = get_text(child2)
                    if txt2 in ['-', '']:
                        if dash_text and set_text(child2, dash_text):
                            count += 1
                            print(f"  [{k}] '-' → {dash_text[:50]}...")
                        search_start = k + 1
                        break
                else:
                    search_start = j + 1
                break

print(f"\nTotal paragraphs filled: {count}")

# ============================================================
# 3단계: 저장 (원본 ZIP 메타데이터 보존)
# ============================================================
xml_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
xml_str = xml_bytes.decode('utf-8')
xml_str = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', xml_str, count=1)
all_files['Contents/section0.xml'] = xml_str.encode('utf-8')

tmp = HWPX + '.tmp'
with zipfile.ZipFile(tmp, 'w') as zfout:
    for name in namelist:
        info = orig_infos.get(name)
        if info:
            zfout.writestr(info, all_files[name])
        else:
            zfout.writestr(name, all_files[name])
os.replace(tmp, HWPX)
print(f"HWPX saved: {HWPX}")
