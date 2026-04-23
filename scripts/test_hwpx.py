#!/usr/bin/env python3
"""
HWPX 파일 검증 스크립트
생성된 HWPX 파일의 알려진 문제들을 사전에 검출한다.

사용법:
  python scripts/test_hwpx.py <파일.hwpx>
  python scripts/test_hwpx.py <파일.hwpx> --orig <원본.hwpx>  # diff 기반 검사 포함

검사 항목:
  [ZIP]       mimetype 첫 엔트리 여부, ZIP_STORED 압축
  [ZIP]       필수 파일 존재 여부
  [XML]       XML 선언 큰따옴표 (한글 파서 요구사항)
  [XML]       ns0:/ns1: 비표준 네임스페이스 프리픽스 없음
  [XML]       hs:sec의 필수 네임스페이스 선언 완전성
  [STYLE]     header.xml에 charPr ID=79 존재
  [STYLE]     section0.xml의 charPrIDRef가 유효한 ID 참조
  [IMAGE]     BinData/ 이미지 파일과 content.hpf manifest 일치
  [IMAGE]     section0.xml의 binaryItemIDRef가 manifest에 등록된 ID 참조
  [MARKUP]    <hp:t> 텍스트 노드에 마크다운 마크업(**·__) 또는 \n 잔존 없음
  [DIFF]      변경된 단락의 linesegarray가 빈 태그로 교체됨 (--orig 필요)
  [DIFF]      원본 대비 텍스트 변경 비율 (0%이면 채우기 실패 의심)
"""

import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
HC = '{http://www.hancom.co.kr/hwpml/2011/core}'
HS = '{http://www.hancom.co.kr/hwpml/2011/section}'

REQUIRED_FILES = [
    'mimetype',
    'Contents/content.hpf',
    'Contents/section0.xml',
    'Contents/header.xml',
    'META-INF/manifest.xml',
]

# hs:sec에 반드시 있어야 하는 네임스페이스 URI 목록
REQUIRED_NS_URIS = {
    'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'http://www.hancom.co.kr/hwpml/2011/head',
    'http://www.hancom.co.kr/hwpml/2011/core',
    'http://www.hancom.co.kr/hwpml/2011/section',
}

PASS = '✅'
FAIL = '❌'
WARN = '⚠️ '


class Result:
    def __init__(self):
        self.items = []

    def ok(self, label, detail=''):
        self.items.append((PASS, label, detail))

    def fail(self, label, detail=''):
        self.items.append((FAIL, label, detail))

    def warn(self, label, detail=''):
        self.items.append((WARN, label, detail))

    def print_all(self):
        fails = [x for x in self.items if x[0] == FAIL]
        warns = [x for x in self.items if x[0] == WARN]
        passes = [x for x in self.items if x[0] == PASS]

        for icon, label, detail in self.items:
            suffix = f'  ({detail})' if detail else ''
            print(f'  {icon} {label}{suffix}')

        print()
        print(f'  결과: {len(passes)}개 통과 / {len(warns)}개 경고 / {len(fails)}개 실패')
        return len(fails)


# ─────────────────────────────────────────────────────────────
# 검사 함수들
# ─────────────────────────────────────────────────────────────

def check_zip_structure(hwpx_path, r):
    """ZIP 구조 검사"""
    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        namelist = zf.namelist()
        infolist = zf.infolist()

        # mimetype 첫 엔트리
        if namelist and namelist[0] == 'mimetype':
            r.ok('[ZIP] mimetype 첫 번째 엔트리')
        else:
            first = namelist[0] if namelist else '(없음)'
            r.fail('[ZIP] mimetype 첫 번째 엔트리', f'실제 첫 엔트리: {first}')

        # mimetype ZIP_STORED
        mime_info = next((i for i in infolist if i.filename == 'mimetype'), None)
        if mime_info is None:
            r.fail('[ZIP] mimetype 파일 존재')
        elif mime_info.compress_type == zipfile.ZIP_STORED:
            r.ok('[ZIP] mimetype ZIP_STORED 압축')
        else:
            r.fail('[ZIP] mimetype ZIP_STORED 압축',
                   f'실제 compress_type={mime_info.compress_type}')

        # 필수 파일 존재
        name_set = set(namelist)
        missing = [f for f in REQUIRED_FILES if f not in name_set]
        if missing:
            r.fail('[ZIP] 필수 파일 존재', f'누락: {", ".join(missing)}')
        else:
            r.ok('[ZIP] 필수 파일 존재')


def check_xml_declarations(hwpx_path, r):
    """XML 선언 큰따옴표 검사 — 한글은 작은따옴표 XML 선언을 파싱 실패"""
    bad_files = []
    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        for name in zf.namelist():
            if not (name.endswith('.xml') or name.endswith('.hpf')):
                continue
            try:
                text = zf.read(name).decode('utf-8')
            except Exception:
                continue
            # <?xml ... ?> 선언에서 작은따옴표 체크
            m = re.match(r"<\?xml[^?]*\?>", text)
            if m and "'" in m.group(0):
                bad_files.append(name)

    if bad_files:
        r.fail('[XML] XML 선언 큰따옴표', f'작은따옴표 파일: {", ".join(bad_files)}')
    else:
        r.ok('[XML] XML 선언 큰따옴표')


def check_namespaces(hwpx_path, r):
    """비표준 네임스페이스 프리픽스(ns0:, ns1: 등) 검사"""
    ns_problems = []
    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        for name in ['Contents/section0.xml', 'Contents/header.xml', 'Contents/content.hpf']:
            if name not in zf.namelist():
                continue
            try:
                text = zf.read(name).decode('utf-8')
            except Exception:
                continue
            matches = re.findall(r'xmlns:(ns\d+)=', text)
            if matches:
                ns_problems.append(f'{name}: {", ".join(set(matches))}')

    if ns_problems:
        r.fail('[XML] 비표준 네임스페이스 프리픽스 없음',
               ' | '.join(ns_problems))
    else:
        r.ok('[XML] 비표준 네임스페이스 프리픽스 없음')


def check_required_ns_declarations(hwpx_path, r):
    """hs:sec 루트 요소의 필수 네임스페이스 선언 완전성 검사"""
    if not HAS_LXML:
        r.warn('[XML] 네임스페이스 선언 완전성 (lxml 없어 건너뜀)')
        return

    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        try:
            section_xml = zf.read('Contents/section0.xml')
        except KeyError:
            r.fail('[XML] section0.xml 읽기 실패')
            return

    try:
        root = etree.fromstring(section_xml)
        declared_uris = set(root.nsmap.values())
        missing_uris = REQUIRED_NS_URIS - declared_uris
        if missing_uris:
            short = [u.split('/')[-1] for u in missing_uris]
            r.fail('[XML] 필수 네임스페이스 선언 완전성', f'누락 URI: {", ".join(short)}')
        else:
            r.ok('[XML] 필수 네임스페이스 선언 완전성')
    except Exception as e:
        r.fail('[XML] section0.xml 파싱 실패', str(e))


def check_charpr(hwpx_path, r):
    """header.xml의 charPr ID=79 존재 여부 + section0.xml 참조 유효성"""
    if not HAS_LXML:
        r.warn('[STYLE] charPr 검사 (lxml 없어 건너뜀)')
        return

    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        try:
            header_xml = zf.read('Contents/header.xml')
            section_xml = zf.read('Contents/section0.xml')
        except KeyError as e:
            r.fail('[STYLE] 파일 읽기 실패', str(e))
            return

    try:
        header_root = etree.fromstring(header_xml)
        valid_ids = {cp.get('id') for cp in header_root.iter(f'{HH}charPr')}

        if '79' in valid_ids:
            r.ok('[STYLE] charPr ID=79 존재 (기본 검정 스타일)')
        else:
            r.warn('[STYLE] charPr ID=79 없음',
                   f'존재하는 ID: {", ".join(sorted(valid_ids, key=lambda x: int(x) if x.isdigit() else 0)[:10])}...')

        # section0에서 charPrIDRef 참조 유효성
        sec_root = etree.fromstring(section_xml)
        invalid_refs = set()
        for run in sec_root.iter(f'{HP}run'):
            ref = run.get('charPrIDRef')
            if ref and ref not in valid_ids:
                invalid_refs.add(ref)

        if invalid_refs:
            r.fail('[STYLE] charPrIDRef 유효 ID 참조',
                   f'잘못된 참조: {", ".join(sorted(invalid_refs)[:5])}')
        else:
            r.ok('[STYLE] charPrIDRef 유효 ID 참조')

    except Exception as e:
        r.fail('[STYLE] charPr 검사 실패', str(e))


def check_images(hwpx_path, r):
    """이미지 일관성 검사: BinData ↔ content.hpf ↔ section0.xml"""
    if not HAS_LXML:
        r.warn('[IMAGE] 이미지 검사 (lxml 없어 건너뜀)')
        return

    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        namelist = zf.namelist()
        try:
            hpf_xml = zf.read('Contents/content.hpf')
            section_xml = zf.read('Contents/section0.xml')
        except KeyError as e:
            r.warn('[IMAGE] 이미지 검사 건너뜀', str(e))
            return

    # BinData 이미지 파일 목록
    bin_files = {n for n in namelist if n.startswith('BinData/')}
    if not bin_files:
        r.ok('[IMAGE] 이미지 없음 (삽입 없는 경우 정상)')
        return

    # content.hpf에서 등록된 image ID 목록
    try:
        hpf_root = etree.fromstring(hpf_xml)
        manifest_ids = {}
        for item in hpf_root.iter():
            if item.tag.endswith('}item') or item.tag == 'item':
                item_id = item.get('id', '')
                href = item.get('href', '')
                if item_id.startswith('image'):
                    manifest_ids[item_id] = href
    except Exception as e:
        r.fail('[IMAGE] content.hpf 파싱 실패', str(e))
        return

    # section0.xml에서 binaryItemIDRef 목록
    try:
        sec_root = etree.fromstring(section_xml)
        used_ids = set()
        for img in sec_root.iter(f'{HC}img'):
            ref = img.get('binaryItemIDRef')
            if ref:
                used_ids.add(ref)
    except Exception as e:
        r.fail('[IMAGE] section0.xml 파싱 실패', str(e))
        return

    # BinData ↔ manifest 일치
    bin_ids = {Path(f).stem for f in bin_files}  # 'BinData/image1.png' → 'image1'
    manifest_id_set = set(manifest_ids.keys())

    unregistered = bin_ids - manifest_id_set
    if unregistered:
        r.fail('[IMAGE] BinData 파일이 manifest에 등록됨',
               f'미등록: {", ".join(unregistered)}')
    else:
        if bin_ids:
            r.ok('[IMAGE] BinData 파일 manifest 등록 일치', f'{len(bin_ids)}개')

    # section0 참조 → manifest 존재
    dangling = used_ids - manifest_id_set
    if dangling:
        r.fail('[IMAGE] section0.xml binaryItemIDRef가 manifest에 존재',
               f'누락 ID: {", ".join(dangling)}')
    else:
        if used_ids:
            r.ok('[IMAGE] section0.xml 이미지 참조 유효', f'{len(used_ids)}개')

    # manifest에 있지만 BinData에 없는 경우
    orphan_manifest = manifest_id_set - bin_ids
    if orphan_manifest:
        r.warn('[IMAGE] manifest 등록 ID가 BinData에 존재',
               f'BinData 없음: {", ".join(orphan_manifest)}')


def check_markup_residue(hwpx_path, r):
    """fill 후 마크업 잔존 검사 — writer가 의도치 않게 인라인 마크업을 남기거나
    줄바꿈이 텍스트 노드에 그대로 박힌 경우를 검출 (set_cell_rich가 처리했어야 함)."""
    bold_pat = re.compile(r'\*\*[^*\s][^*]*\*\*')
    under_pat = re.compile(r'__[^_\s][^_]*__')
    text_pat = re.compile(r'<hp:t[^>]*>([^<]*)</hp:t>', re.DOTALL)

    issues = 0
    samples = []
    with zipfile.ZipFile(hwpx_path) as zf:
        for name in zf.namelist():
            if not (name.startswith('Contents/section') and name.endswith('.xml')):
                continue
            content = zf.read(name).decode('utf-8', errors='replace')
            for m in text_pat.finditer(content):
                t = m.group(1)
                if not t:
                    continue
                if bold_pat.search(t):
                    issues += 1
                    if len(samples) < 3: samples.append(f'{name}: bold마크업: {t[:40]!r}')
                elif under_pat.search(t):
                    issues += 1
                    if len(samples) < 3: samples.append(f'{name}: underline마크업: {t[:40]!r}')
                elif '\n' in t:
                    issues += 1
                    if len(samples) < 3: samples.append(f'{name}: 줄바꿈잔존: {t[:40]!r}')
    if issues:
        detail = '; '.join(samples) if samples else ''
        r.fail(f'[MARKUP] 텍스트 노드에 마크업/줄바꿈 잔존 {issues}건', detail)
    else:
        r.ok('[MARKUP] 텍스트 노드 마크업/줄바꿈 잔존 없음')


def check_rhwp(hwpx_path, r):
    """@rhwp/core WASM 파서로 실제 파싱 + 렌더링 가능 여부 검증"""
    import subprocess as _sp
    script = Path(__file__).parent / 'validate_rhwp.mjs'
    if not script.exists():
        r.warn('[RHWP] validate_rhwp.mjs 없음 — 건너뜀')
        return

    try:
        proc = _sp.run(
            ['node', str(script), str(hwpx_path), '--json'],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        r.warn('[RHWP] node 없음 — rhwp 검증 건너뜀')
        return
    except _sp.TimeoutExpired:
        r.warn('[RHWP] 타임아웃 (30초)')
        return

    if proc.returncode == 2:
        r.warn('[RHWP] @rhwp/core 미설치 — npm install 실행 필요', proc.stderr.strip()[:120])
        return

    import json as _json
    try:
        result = _json.loads(proc.stdout)
    except (_json.JSONDecodeError, ValueError):
        stderr_short = (proc.stderr or proc.stdout or '').strip()[:200]
        r.warn('[RHWP] 결과 파싱 실패', stderr_short)
        return

    if result.get('ok'):
        r.ok('[RHWP] rhwp 파싱+렌더링 성공', f'{result["pages"]}페이지, SVG {result["svg_length"]}바이트')
    else:
        for err in result.get('errors', []):
            r.fail('[RHWP] ' + err)


def check_diff(hwpx_path, orig_path, r):
    """원본 대비 변경 검사 (--orig 제공 시): linesegarray + 변경률"""
    if not HAS_LXML:
        r.warn('[DIFF] diff 검사 (lxml 없어 건너뜀)')
        return

    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        mod_xml = zf.read('Contents/section0.xml')
    with zipfile.ZipFile(orig_path, 'r') as zf:
        orig_xml = zf.read('Contents/section0.xml')

    try:
        mod_root = etree.fromstring(mod_xml)
        orig_root = etree.fromstring(orig_xml)
    except Exception as e:
        r.fail('[DIFF] XML 파싱 실패', str(e))
        return

    def get_texts(root):
        return [''.join(t.text or '' for t in p.iter(f'{HP}t'))
                for p in root.iter(f'{HP}p')]

    mod_texts = get_texts(mod_root)
    orig_texts = get_texts(orig_root)

    changed_indices = []
    for i, (m, o) in enumerate(zip(mod_texts, orig_texts)):
        if m != o and m.strip():
            changed_indices.append(i)

    total = len(orig_texts)
    changed = len(changed_indices)

    if total == 0:
        r.warn('[DIFF] 단락 개수 0개')
        return

    change_pct = changed / total * 100

    if change_pct == 0:
        r.fail('[DIFF] 텍스트 변경 단락 있음',
               '변경된 단락 0개 — fill이 적용되지 않았을 수 있음')
    elif change_pct < 2:
        r.warn('[DIFF] 텍스트 변경 단락 있음',
               f'{changed}/{total}개 ({change_pct:.1f}%) — 채우기가 매우 적음')
    else:
        r.ok('[DIFF] 텍스트 변경 단락', f'{changed}/{total}개 ({change_pct:.1f}%)')

    # 변경된 단락의 linesegarray 검사
    mod_paras = list(mod_root.iter(f'{HP}p'))
    bad_lineseg = 0
    for i in changed_indices:
        if i >= len(mod_paras):
            continue
        p = mod_paras[i]
        lsas = p.findall(f'{HP}linesegarray')
        # 빈 linesegarray가 1개 있어야 함
        if len(lsas) != 1 or len(list(lsas[0])) > 0:
            bad_lineseg += 1

    if bad_lineseg > 0:
        r.fail('[DIFF] 변경 단락 linesegarray 빈 태그로 교체',
               f'{bad_lineseg}/{changed}개 단락에서 lineseg 미처리')
    else:
        r.ok('[DIFF] 변경 단락 linesegarray 빈 태그로 교체')


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def validate(hwpx_path, orig_path=None, use_rhwp=False):
    print(f'\nHWPX 검증: {hwpx_path}')
    if orig_path:
        print(f'원본 비교: {orig_path}')
    print('─' * 60)

    r = Result()

    if not Path(hwpx_path).exists():
        print(f'{FAIL} 파일을 찾을 수 없습니다: {hwpx_path}')
        return 1

    try:
        check_zip_structure(hwpx_path, r)
        check_xml_declarations(hwpx_path, r)
        check_namespaces(hwpx_path, r)
        check_required_ns_declarations(hwpx_path, r)
        check_charpr(hwpx_path, r)
        check_images(hwpx_path, r)
        check_markup_residue(hwpx_path, r)

        if use_rhwp:
            check_rhwp(hwpx_path, r)

        if orig_path:
            if not Path(orig_path).exists():
                r.warn('[DIFF] 원본 파일 없음 — diff 검사 건너뜀', orig_path)
            else:
                check_diff(hwpx_path, orig_path, r)

    except zipfile.BadZipFile:
        print(f'{FAIL} ZIP 파일이 손상되었거나 유효하지 않습니다.')
        return 1
    except Exception as e:
        print(f'{FAIL} 검증 중 예외 발생: {e}')
        import traceback
        traceback.print_exc()
        return 1

    fail_count = r.print_all()

    if fail_count == 0:
        print('\n  한글에서 파일을 열어 육안으로도 확인하세요.')
    else:
        print(f'\n  {fail_count}개 문제를 수정한 후 다시 검증하세요.')

    return fail_count


def main():
    parser = argparse.ArgumentParser(
        description='HWPX 파일 검증 — 알려진 문제를 사전에 검출합니다.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('hwpx', help='검증할 HWPX 파일 경로')
    parser.add_argument('--orig', metavar='원본.hwpx',
                        help='원본 양식 파일 (diff 기반 linesegarray 검사용)')
    parser.add_argument('--rhwp', action='store_true',
                        help='@rhwp/core WASM 파서로 파싱+렌더링 검증 (node 필요)')
    args = parser.parse_args()

    exit_code = validate(args.hwpx, args.orig, use_rhwp=args.rhwp)
    sys.exit(0 if exit_code == 0 else 1)


if __name__ == '__main__':
    main()
