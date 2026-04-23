#!/usr/bin/env python3
"""HWPX 전체 생성 스크립트: 테이블 셀 채우기 + 개조식 본문 채우기

사용법:
  python build_hwpx.py --base /path/to/project --orig 원본.hwpx --out 출력.hwpx

또는 스크립트 상단의 경로를 직접 수정하여 사용.
"""
import zipfile, shutil, os, re, copy, json, subprocess, sys, argparse
from lxml import etree

# ── 경로 설정 (프로젝트에 맞게 수정) ──
BASE = os.environ.get("HWPX_BASE", os.getcwd())
ORIG = os.environ.get("HWPX_ORIG", os.path.join(BASE, "원본양식.hwpx"))
OUT = os.environ.get("HWPX_OUT", os.path.join(BASE, "제출용.hwpx"))
HANDLER = os.path.expanduser("~/.claude/skills/k-proposal/.venv/bin/python3")
HANDLER_PY = os.path.expanduser("~/.claude/skills/k-proposal/hwpx_handler.py")

# CLI 인자 지원
parser = argparse.ArgumentParser(description='HWPX 빌드')
parser.add_argument('--base', default=BASE, help='프로젝트 디렉토리')
parser.add_argument('--orig', default=ORIG, help='원본 양식 HWPX')
parser.add_argument('--out', default=OUT, help='출력 HWPX')
parser.add_argument('--audit-draft', metavar='PATH',
                    help='빌드 후 완전성 감사를 수행할 초안 마크다운 경로')
parser.add_argument('--audit-threshold', type=float, default=20.0,
                    help='감사 통과 임계치 %% (기본 20.0)')
parser.add_argument('--audit-strict', action='store_true',
                    help='크리티컬 섹션이 하나라도 있으면 빌드 실패 처리')
args, _ = parser.parse_known_args()
BASE, ORIG, OUT = args.base, args.orig, args.out

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
HC = '{http://www.hancom.co.kr/hwpml/2011/core}'

# ============================================================
# 0. 원본 복사
# ============================================================
shutil.copy(ORIG, OUT)
print(f"원본 복사: {OUT}")

# ============================================================
# 1단계: 테이블 셀 채우기 (hwpx_handler fill)
# ============================================================
# data/ 폴더 내 fill_*.json 파일을 순서대로 실행
data_dir = os.path.join(BASE, "data")
if os.path.isdir(data_dir):
    for json_file in sorted(os.listdir(data_dir)):
        if json_file.startswith('fill_') and json_file.endswith('.json'):
            path = os.path.join(data_dir, json_file)
            result = subprocess.run(
                [HANDLER, HANDLER_PY, "fill", OUT, OUT, "--data", path],
                capture_output=True, text=True
            )
            print(f"[{json_file}] {result.stdout.strip().split(chr(10))[-1]}")
else:
    print(f"WARN: data 디렉토리 없음: {data_dir}. fill_*.json 파일을 data/ 폴더에 넣어주세요.")

# (하드코딩 예시 데이터 삭제됨)
# 실제 사용 시 data/fill_사업계획서.json을 준비하면 위 1단계에서 자동 처리됩니다.
# templates/ 폴더의 *_template.json을 data/로 복사 후 내용을 채워 사용하세요.

# ============================================================
# 2단계: 개조식 단락 채우기 (텍스트 패턴 매칭) — fill_all.py 방식
# ============================================================
with zipfile.ZipFile(OUT, 'r') as zf:
    orig_infos = {info.filename: info for info in zf.infolist()}
    all_files = {name: zf.read(name) for name in zf.namelist()}
    namelist = zf.namelist()

root = etree.fromstring(all_files['Contents/section0.xml'])
children = list(root)

BLACK_STYLE = "79"

def get_text(elem):
    return ''.join(t.text or '' for t in elem.iter(f'{HP}t')).strip()

def set_text(elem, new_text):
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
    for run in elem.iter(f'{HP}run'):
        run.set('charPrIDRef', BLACK_STYLE)
    for lsa in elem.findall(f'{HP}linesegarray'):
        elem.remove(lsa)
    etree.SubElement(elem, f'{HP}linesegarray')
    return True

# 개조식 본문: data/sections.json이 있으면 로딩, 없으면 아래 하드코딩 사용
sections_json = os.path.join(BASE, "data", "sections.json")
if os.path.exists(sections_json):
    with open(sections_json, 'r', encoding='utf-8') as f:
        _sec_data = json.load(f)
    SECTIONS = [(s['header_keyword'], s['pairs']) for s in _sec_data.get('sections', [])]
    print(f"[sections.json] {len(SECTIONS)}개 섹션 로딩")
else:
    # (하드코딩 예시 데이터 삭제됨)
    # 실제 사용 시 data/sections.json을 준비하세요.
    # templates/sections_template.json을 data/sections.json으로 복사 후 내용을 채워 사용하세요.
    SECTIONS = []
    print("WARN: data/sections.json 없음. 개조식 단락 채우기를 건너뜁니다.")

count = 0
for header_keyword, pairs in SECTIONS:
    header_idx = None
    for i, child in enumerate(children):
        if child.tag.split('}')[-1] == 'p' and header_keyword in get_text(child):
            header_idx = i
            break
    if header_idx is None:
        print(f"  WARN: header '{header_keyword}' not found")
        continue

    search_start = header_idx + 1
    for pair in pairs:
        o_text, dash_text = pair

        if o_text is not None and dash_text is None:
            for j in range(search_start, min(search_start + 5, len(children))):
                child = children[j]
                if child.tag.split('}')[-1] != 'p':
                    continue
                txt = get_text(child)
                if txt in ['1.', '1', '']:
                    if set_text(child, o_text):
                        count += 1
                    search_start = j + 1
                    break
            continue

        if o_text is None:
            for j in range(search_start, min(search_start + 5, len(children))):
                child = children[j]
                if child.tag.split('}')[-1] != 'p':
                    continue
                txt = get_text(child)
                if txt == '-':
                    if set_text(child, dash_text):
                        count += 1
                    search_start = j + 1
                    break
            continue

        for j in range(search_start, min(search_start + 8, len(children))):
            child = children[j]
            if child.tag.split('}')[-1] != 'p':
                continue
            txt = get_text(child)
            if txt in ['ㅇ', '◦', '']:
                if set_text(child, o_text):
                    count += 1
                for k in range(j + 1, min(j + 3, len(children))):
                    child2 = children[k]
                    if child2.tag.split('}')[-1] != 'p':
                        continue
                    txt2 = get_text(child2)
                    if txt2 in ['-', '']:
                        if dash_text and set_text(child2, dash_text):
                            count += 1
                        search_start = k + 1
                        break
                else:
                    search_start = j + 1
                break

print(f"\n개조식 단락 채움: {count}개")

# ============================================================
# 2.5단계: 작성요령 테이블 셀 → 본문 ◦/- 단락 이동 (안전망)
# ============================================================
fix_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fix_body_paragraphs.py')
if os.path.exists(fix_script):
    import importlib.util
    spec = importlib.util.spec_from_file_location("fix_body_paragraphs", fix_script)
    fix_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fix_mod)

# ============================================================
# 2.7단계: 미사용 불릿 마커(◦/-) 단락 삭제
# ============================================================
root = etree.fromstring(all_files['Contents/section0.xml'])
children = list(root)
removed_empty = 0
for child in reversed(children):
    if child.tag.split('}')[-1] != 'p':
        continue
    if child.find(f'.//{HP}tbl') is not None:
        continue
    txt = get_text(child)
    if txt in ('◦', 'ㅇ', '○', '-'):
        root.remove(child)
        removed_empty += 1
print(f"빈 불릿 마커 삭제: {removed_empty}개")

# ============================================================
# 2.9단계: 작성요령 테이블 삭제
# ============================================================
children = list(root)
removed_guides = 0
for child in reversed(children):
    if child.tag.split('}')[-1] != 'p':
        continue
    tbl = child.find(f'.//{HP}tbl')
    if tbl is None:
        continue
    rows = tbl.findall(f'{HP}tr')
    if not rows:
        continue
    cells = rows[0].findall(f'{HP}tc')
    if not cells:
        continue
    first_cell_text = get_text(cells[0])
    if '작성요령' in first_cell_text:
        root.remove(child)
        removed_guides += 1
print(f"작성요령 테이블 삭제: {removed_guides}개")

# ============================================================
# 3-0단계: 커버페이지 플레이스홀더 교체
# ============================================================
cover_json = os.path.join(BASE, "data", "cover.json")
if os.path.exists(cover_json):
    with open(cover_json, 'r', encoding='utf-8') as f:
        cover_data = json.load(f)
    cover_replacements = {
        "(과제명) 창업기업의 사업에 대한 소개글": cover_data.get("title", ""),
        "운영사명": cover_data.get("operator", ""),
        "창업기업명": cover_data.get("company", ""),
    }
    cover_count = 0
    for child in root.iter(f'{HP}t'):
        if child.text and child.text.strip() in cover_replacements:
            replacement = cover_replacements[child.text.strip()]
            if replacement:
                child.text = replacement
                cover_count += 1
    print(f"커버페이지 교체: {cover_count}개")
else:
    print("WARN: data/cover.json 없음. 커버페이지 교체를 건너뜁니다.")

all_files['Contents/section0.xml'] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

# ============================================================
# 3단계: 저장 (XML 선언 큰따옴표 + 원본 ZIP 메타데이터 보존)
# ============================================================
xml_str = all_files['Contents/section0.xml'].decode('utf-8')
xml_str = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', xml_str, count=1)
all_files['Contents/section0.xml'] = xml_str.encode('utf-8')

# header.xml, content.hpf도 따옴표 수정
for key in ['Contents/header.xml', 'Contents/content.hpf']:
    if key in all_files:
        txt = all_files[key].decode('utf-8')
        txt = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>', txt, count=1)
        all_files[key] = txt.encode('utf-8')

tmp = OUT + '.tmp'
with zipfile.ZipFile(tmp, 'w') as zfout:
    for name in namelist:
        info = orig_infos.get(name)
        if info:
            zfout.writestr(info, all_files[name])
        else:
            zfout.writestr(name, all_files[name])
os.replace(tmp, OUT)
print(f"\nHWPX 저장 완료: {OUT}")

# ============================================================
# 4단계: 초안↔HWPX 완전성 감사 (옵션)
# ============================================================
# 초안 경로가 주어진 경우에만 실행. sections.json/fill.json을 아무리 잘 채워도
# 초안에 있던 내용이 중간에 누락될 수 있으므로, 최종 HWPX가 초안을 얼마나
# 담고 있는지를 앵커 토큰 기반으로 감사한다.
if args.audit_draft:
    audit_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'audit_completeness.py')
    if not os.path.exists(audit_script):
        print(f"\nWARN: audit_completeness.py 없음: {audit_script} — 감사 생략")
    elif not os.path.exists(args.audit_draft):
        print(f"\nWARN: 초안 파일 없음: {args.audit_draft} — 감사 생략")
    else:
        print("\n" + "=" * 60)
        print("완전성 감사 실행")
        print("=" * 60)
        audit_cmd = [
            sys.executable, audit_script,
            '--draft', args.audit_draft,
            '--hwpx', OUT,
            '--threshold', str(args.audit_threshold),
        ]
        if args.audit_strict:
            audit_cmd.append('--strict')
        result = subprocess.run(audit_cmd)
        if result.returncode == 1:
            print("\n⚠️  감사 실패: 누락된 내용이 임계치를 초과합니다.")
            print("   → writer가 fill JSON 또는 _fill_body 스크립트에 해당 섹션을 추가해야 합니다.")
            sys.exit(1)
        elif result.returncode != 0:
            print(f"\n감사 스크립트 오류 (exit={result.returncode})")
            sys.exit(result.returncode)
