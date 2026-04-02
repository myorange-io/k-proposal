#!/usr/bin/env python3
"""HWPX 후처리: diff 기반 lineseg/charPr 수정 + 볼드+밑줄 강조 + 이미지 삽입 + 네임스페이스 정규화

사용법:
  python postprocess_hwpx.py --base /path/to/project --hwpx 제출용.hwpx --orig 원본.hwpx
"""
import zipfile, os, re, copy, sys, argparse, json
from lxml import etree

# ── 경로 설정 (프로젝트에 맞게 수정) ──
BASE = os.environ.get("HWPX_BASE", os.getcwd())
_parser = argparse.ArgumentParser(description='HWPX 후처리')
_parser.add_argument('--base', default=BASE)
_parser.add_argument('--hwpx', default=os.path.join(BASE, "제출용.hwpx"))
_parser.add_argument('--orig', default=os.path.join(BASE, "원본양식.hwpx"))
_args, _ = _parser.parse_known_args()
BASE = _args.base
V10 = _args.hwpx
ORIG = _args.orig

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
HC = '{http://www.hancom.co.kr/hwpml/2011/core}'

# ============================================================
# 1. ZIP 데이터 로드
# ============================================================
with zipfile.ZipFile(ORIG) as zf:
    orig_section = zf.read('Contents/section0.xml')

with zipfile.ZipFile(V10, 'r') as zf:
    mod_infos = {info.filename: info for info in zf.infolist()}
    all_files = {name: zf.read(name) for name in zf.namelist()}
    namelist = zf.namelist()

orig_root = etree.fromstring(orig_section)
mod_root = etree.fromstring(all_files['Contents/section0.xml'])
header_root = etree.fromstring(all_files['Contents/header.xml'])

# ============================================================
# 2. 볼드+밑줄 charPr 스타일 등록 (header.xml)
# ============================================================
max_charpr_id = 0
for cp in header_root.iter(f'{HH}charPr'):
    cid = int(cp.get('id', '0'))
    if cid > max_charpr_id:
        max_charpr_id = cid

BOLD_UL_ID = str(max_charpr_id + 1)

charpr_79 = None
for cp in header_root.iter(f'{HH}charPr'):
    if cp.get('id') == '79':
        charpr_79 = cp
        break

if charpr_79 is not None:
    new_charpr = copy.deepcopy(charpr_79)
    new_charpr.set('id', BOLD_UL_ID)
    bold_el = new_charpr.find(f'{HH}bold')
    if bold_el is None:
        bold_el = etree.SubElement(new_charpr, f'{HH}bold')
    ul_el = new_charpr.find(f'{HH}underline')
    if ul_el is None:
        ul_el = etree.SubElement(new_charpr, f'{HH}underline')
    ul_el.set('type', 'BOTTOM')
    ul_el.set('shape', 'SOLID')
    ul_el.set('color', '#000000')

    charpr_list = None
    for el in header_root.iter(f'{HH}charProperties'):
        charpr_list = el
        break
    if charpr_list is None:
        for el in header_root.iter():
            if el.tag.endswith('}charProperties'):
                charpr_list = el
                break

    if charpr_list is not None:
        charpr_list.append(new_charpr)
        old_cnt = int(charpr_list.get('itemCnt', '0'))
        charpr_list.set('itemCnt', str(old_cnt + 1))
        print(f'볼드+밑줄 charPr ID={BOLD_UL_ID} 등록 완료')
else:
    BOLD_UL_ID = '79'
    print('WARN: charPr 79 없음, 볼드+밑줄 미적용')

all_files['Contents/header.xml'] = etree.tostring(
    header_root, xml_declaration=True, encoding='UTF-8', standalone=True
)

# ============================================================
# 3. 강조할 키워드 목록 (DOCX 내용 기준)
# ============================================================
# 강조 키워드: data/bold_keywords.json이 있으면 로딩, 없으면 아래 기본값 사용
keywords_json = os.path.join(BASE, "data", "bold_keywords.json")
if os.path.exists(keywords_json):
    with open(keywords_json, 'r', encoding='utf-8') as f:
        BOLD_KEYWORDS = json.load(f).get('keywords', [])
    print(f'[bold_keywords.json] {len(BOLD_KEYWORDS)}개 키워드 로딩')
else:
    # (아래는 예시 — 프로젝트에 맞게 수정)
    BOLD_KEYWORDS = [
        # 핵심 수치 (예시)
        '00억 달러', '00% 성장', '00만원',
        # 정책 근거 (예시)
        'EU CSRD', 'SDGs 2030',
        # 제품명 (예시)
        '(제품명)',
    ]

# ============================================================
# 4. diff 기반 후처리
# ============================================================
orig_texts = [(p, ''.join(t.text or '' for t in p.iter(f'{HP}t'))) for p in orig_root.iter(f'{HP}p')]
mod_texts = [(p, ''.join(t.text or '' for t in p.iter(f'{HP}t'))) for p in mod_root.iter(f'{HP}p')]

count_fix = 0
count_bold = 0

for i, (mod_p, mod_text) in enumerate(mod_texts):
    if i >= len(orig_texts):
        orig_text = ''
    else:
        _, orig_text = orig_texts[i]

    if mod_text != orig_text and mod_text.strip():
        # linesegarray → 빈 태그
        for lsa in mod_p.findall(f'{HP}linesegarray'):
            mod_p.remove(lsa)
        etree.SubElement(mod_p, f'{HP}linesegarray')

        # charPrIDRef → 79 (기본 검정)
        for run in mod_p.iter(f'{HP}run'):
            run.set('charPrIDRef', '79')
        count_fix += 1

        # 키워드 볼드+밑줄
        for run in list(mod_p.iter(f'{HP}run')):
            t_elem = run.find(f'{HP}t')
            if t_elem is None or not t_elem.text:
                continue

            text = t_elem.text
            found_keywords = [kw for kw in BOLD_KEYWORDS if kw in text]
            if not found_keywords:
                continue

            found_keywords.sort(key=len, reverse=True)

            segments = []
            remaining = text
            while remaining:
                earliest_pos = len(remaining)
                earliest_kw = None
                for kw in found_keywords:
                    pos = remaining.find(kw)
                    if pos != -1 and pos < earliest_pos:
                        earliest_pos = pos
                        earliest_kw = kw
                if earliest_kw is None:
                    segments.append((remaining, False))
                    break
                if earliest_pos > 0:
                    segments.append((remaining[:earliest_pos], False))
                segments.append((earliest_kw, True))
                remaining = remaining[earliest_pos + len(earliest_kw):]

            if len(segments) <= 1:
                continue

            parent = run.getparent()
            if parent is None:
                continue

            run_idx = list(parent).index(run)
            parent.remove(run)

            for si, (seg_text, is_bold) in enumerate(segments):
                if not seg_text:
                    continue
                new_run = etree.Element(f'{HP}run')
                new_run.set('charPrIDRef', BOLD_UL_ID if is_bold else '79')
                new_t = etree.SubElement(new_run, f'{HP}t')
                new_t.text = seg_text
                parent.insert(run_idx + si, new_run)
                if is_bold:
                    count_bold += 1

print(f'후처리: {count_fix}개 단락 lineseg 수정, {count_bold}개 키워드 볼드+밑줄')

# ============================================================
# 5. 저장 (XML 선언 + ZIP 메타데이터 보존)
# ============================================================
xml_bytes = etree.tostring(mod_root, xml_declaration=True, encoding='UTF-8', standalone=True)
xml_str = xml_bytes.decode('utf-8')
xml_str = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', xml_str, count=1)
all_files['Contents/section0.xml'] = xml_str.encode('utf-8')

hdr_str = all_files['Contents/header.xml'].decode('utf-8')
hdr_str = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', hdr_str, count=1)
all_files['Contents/header.xml'] = hdr_str.encode('utf-8')

# content.hpf도
if 'Contents/content.hpf' in all_files:
    hpf_str = all_files['Contents/content.hpf'].decode('utf-8')
    hpf_str = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', hpf_str, count=1)
    all_files['Contents/content.hpf'] = hpf_str.encode('utf-8')

with zipfile.ZipFile(V10, 'w') as zfout:
    for name in namelist:
        info = mod_infos.get(name)
        if info:
            zfout.writestr(info, all_files[name])
        else:
            zfout.writestr(name, all_files[name])

print(f'후처리 저장: {V10}')

# ============================================================
# 6. 이미지 삽입
# ============================================================
sys.path.insert(0, os.path.join(BASE, '_작업파일'))
from insert_image import insert_image_to_hwpx

# 이미지 삽입: data/images.json이 있으면 로딩, 없으면 _시각자료/ 폴더 자동 탐색
IMG_DIR = os.path.join(BASE, '_시각자료')
images_json = os.path.join(BASE, 'data', 'images.json')

if os.path.exists(images_json):
    with open(images_json, 'r', encoding='utf-8') as f:
        images = [(img['file'], img['after_table'], img.get('width_cm', 15)) for img in json.load(f).get('images', [])]
    print(f'[images.json] {len(images)}개 이미지 설정 로딩')
else:
    # 기본값: _시각자료/ 폴더의 PNG 파일을 순서대로 (after_table은 수동 지정 필요)
    images = []
    if os.path.isdir(IMG_DIR):
        print(f'WARN: data/images.json 없음. _시각자료/ 폴더의 이미지를 수동으로 지정하세요.')
        print(f'  예시: {{"images": [{{"file": "chart.png", "after_table": 4, "width_cm": 15}}]}}')

for img_name, after_t, width in images:
    img_path = os.path.join(IMG_DIR, img_name)
    if os.path.exists(img_path):
        r = insert_image_to_hwpx(V10, V10, img_path, after_table_index=after_t, width_cm=width)
        print(f'이미지: {img_name} → after T{after_t} ({r["image_id"]})')
    else:
        print(f'SKIP: {img_name} 파일 없음')

# ============================================================
# 7. 최종 ZIP 메타데이터 복원
# ============================================================
entries = {}
with zipfile.ZipFile(V10, 'r') as zf:
    for name in zf.namelist():
        entries[name] = zf.read(name)

# XML 선언 최종 수정 (이미지 삽입이 lxml tostring을 다시 씀)
for key in list(entries.keys()):
    if key.endswith('.xml') or key.endswith('.hpf'):
        txt = entries[key].decode('utf-8')
        txt = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', txt, count=1)
        entries[key] = txt.encode('utf-8')

orig_infos = {}
with zipfile.ZipFile(ORIG, 'r') as zf:
    for info in zf.infolist():
        orig_infos[info.filename] = info

tmp = V10 + '.tmp'
with zipfile.ZipFile(tmp, 'w') as zfout:
    for name, data in entries.items():
        if name == 'mimetype':
            zfout.writestr(name, data, compress_type=zipfile.ZIP_STORED)
        elif name in orig_infos:
            zfout.writestr(orig_infos[name], data)
        else:
            zfout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

os.replace(tmp, V10)

# ============================================================
# 8. 네임스페이스 정규화 (ns0:/ns1: → hh/hc/hp/hs 표준 프리픽스)
# ============================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_namespaces import fix_hwpx_namespaces

ns_fixes = fix_hwpx_namespaces(V10)
if ns_fixes > 0:
    print(f'네임스페이스 정규화: {ns_fixes}개 프리픽스 교체')
else:
    print('네임스페이스 정규화: 교체 대상 없음 (정상)')

print(f'\nv10 최종: {os.path.getsize(V10):,} bytes')
