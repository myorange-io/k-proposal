#!/usr/bin/env python3
"""
HWPX 정부지원사업 양식 핸들러
- 양식 분석 (analyze)
- 셀 읽기 (read-cell)
- 테이블 일괄 읽기 (read-table)
- 양식 채우기 (fill, --validate 지원)
- 행 추가 (add-rows, --template-row 지원)
- 작성요령 삭제 (remove-guides)
- 이미지 삽입 (insert-image) ← 완전 구현: manifest 등록 + pic XML 생성
- 단락 삽입 (insert-text) ← NEW: 테이블 밖 서술 영역에 텍스트 삽입
"""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from lxml import etree
    USING_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree
    USING_LXML = False

NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
    'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
    'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
    'ha': 'http://www.hancom.co.kr/hwpml/2011/app',
    'hpf': 'http://www.hancom.co.kr/schema/2011/hpf',
    'opf': 'http://www.idpf.org/2007/opf/',
}

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HC = '{http://www.hancom.co.kr/hwpml/2011/core}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
HS = '{http://www.hancom.co.kr/hwpml/2011/section}'
OPF = '{http://www.idpf.org/2007/opf/}'

# HWPX 단위: 1 HWP unit = 7200 / inch, 1 inch = 96 px → 1 px ≈ 75 HWP units
HWPUNIT_PER_PX = 75
HWPUNIT_PER_CM = 2835  # 7200 / 2.54


def _px_to_hwpunit(px):
    return int(px * HWPUNIT_PER_PX)


def _get_image_dimensions(image_path):
    """이미지 파일의 가로×세로 픽셀 크기를 반환 (PIL 없이)"""
    path = Path(image_path)
    ext = path.suffix.lower()
    with open(path, 'rb') as f:
        data = f.read(32)

    if ext == '.png':
        # PNG: offset 16에 width(4B) height(4B) big-endian
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', data[16:24])
            return w, h
    elif ext in ('.jpg', '.jpeg'):
        # JPEG: SOI 마커 후 SOF0/SOF2 찾기
        with open(path, 'rb') as f:
            f.read(2)  # SOI
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    break
                if marker[0] != 0xFF:
                    break
                m = marker[1]
                if m in (0xC0, 0xC2):  # SOF0 or SOF2
                    f.read(3)  # length(2) + precision(1)
                    h, w = struct.unpack('>HH', f.read(4))
                    return w, h
                else:
                    length = struct.unpack('>H', f.read(2))[0]
                    f.read(length - 2)
    elif ext == '.bmp':
        # BMP: offset 18에 width(4B) height(4B) little-endian
        if data[:2] == b'BM':
            with open(path, 'rb') as f:
                f.seek(18)
                w, h = struct.unpack('<II', f.read(8))
                return w, abs(h)

    return None, None


class HwpxHandler:
    def __init__(self, hwpx_path):
        self.hwpx_path = Path(hwpx_path)
        self.temp_dir = None
        self.section_trees = {}
        self._content_hpf_tree = None
        self._header_tree = None

    def extract(self):
        """HWPX 파일을 임시 디렉토리에 압축 해제"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix='hwpx_'))
        with zipfile.ZipFile(self.hwpx_path, 'r') as zf:
            zf.extractall(self.temp_dir)
        with zipfile.ZipFile(self.hwpx_path, 'r') as zf:
            self._original_namelist = zf.namelist()
            # 원본 ZIP 엔트리 메타데이터 보존 (압축 방식 등)
            self._original_zipinfo = {info.filename: info for info in zf.infolist()}
        # 모든 섹션 파일 파싱
        contents_dir = self.temp_dir / 'Contents'
        for section_file in sorted(contents_dir.glob('section*.xml')):
            idx = int(section_file.stem.replace('section', ''))
            self._section_raw = getattr(self, '_section_raw', {})
            self._section_raw[idx] = section_file.read_bytes()
            tree = etree.parse(str(section_file))
            self.section_trees[idx] = tree
        # content.hpf 파싱
        hpf_path = contents_dir / 'content.hpf'
        if hpf_path.exists():
            self._content_hpf_tree = etree.parse(str(hpf_path))
        # header.xml 파싱
        header_path = contents_dir / 'header.xml'
        if header_path.exists():
            self._header_tree = etree.parse(str(header_path))
        return self

    def _serialize_xml(self, tree_or_root):
        """XML을 바이트로 직렬화 (namespace prefix 보존)"""
        if hasattr(tree_or_root, 'getroot'):
            root = tree_or_root.getroot()
        else:
            root = tree_or_root
        if USING_LXML:
            return etree.tostring(
                root, xml_declaration=True,
                encoding='UTF-8', standalone=True)
        else:
            # stdlib ET: namespace prefix 보존이 불완전할 수 있음
            # 원본 XML에서 prefix를 복원하는 후처리
            import io
            buf = io.BytesIO()
            tree = etree.ElementTree(root)
            tree.write(buf, xml_declaration=True, encoding='UTF-8')
            return buf.getvalue()

    def _fix_namespace_prefixes(self, xml_bytes, original_bytes):
        """직렬화 후 namespace prefix가 바뀌었으면 원본 기준으로 복원

        lxml은 prefix를 보존하지만, stdlib ET는 ns0, ns1 등으로 바꿀 수 있음.
        원본 XML의 prefix 선언을 기준으로 치환한다.
        """
        if USING_LXML:
            return xml_bytes  # lxml은 prefix 보존됨

        xml_str = xml_bytes.decode('utf-8')
        orig_str = original_bytes.decode('utf-8') if original_bytes else ''

        # 원본에서 xmlns:prefix="uri" 추출
        orig_prefixes = dict(re.findall(r'xmlns:(\w+)="([^"]+)"', orig_str))
        # 직렬화 결과에서 xmlns:nsN="uri" 추출
        new_prefixes = dict(re.findall(r'xmlns:(ns\d+)="([^"]+)"', xml_str))

        for ns_name, uri in new_prefixes.items():
            # 원본에서 이 URI의 원래 prefix 찾기
            for orig_prefix, orig_uri in orig_prefixes.items():
                if orig_uri == uri:
                    # ns0 → hp 등으로 치환
                    xml_str = xml_str.replace(f'xmlns:{ns_name}=', f'xmlns:{orig_prefix}=')
                    xml_str = xml_str.replace(f'<{ns_name}:', f'<{orig_prefix}:')
                    xml_str = xml_str.replace(f'</{ns_name}:', f'</{orig_prefix}:')
                    break

        return xml_str.encode('utf-8')

    def save(self, output_path):
        """수정된 내용을 새 HWPX 파일로 저장"""
        if not self.temp_dir:
            raise RuntimeError("먼저 extract()를 호출하세요")

        output = Path(output_path)
        same_file = output.resolve() == self.hwpx_path.resolve()
        tmp_out = output.with_suffix('.hwpx.tmp') if same_file else output

        contents_dir = self.temp_dir / 'Contents'

        # 섹션 XML 저장 (namespace prefix 보존 + 자기종결 태그 형식 복원)
        for idx, tree in self.section_trees.items():
            section_file = contents_dir / f'section{idx}.xml'
            xml_bytes = self._serialize_xml(tree)
            original = self._section_raw.get(idx, b'')
            xml_bytes = self._fix_namespace_prefixes(xml_bytes, original)
            # lxml은 자기종결 태그에 공백을 추가(<tag />)하지만
            # 한글 HWPX 원본은 공백 없이(<tag/>) 사용. 원본 형식에 맞춤.
            xml_bytes = xml_bytes.replace(b' />', b'/>')
            section_file.write_bytes(xml_bytes)

        # content.hpf 저장
        if self._content_hpf_tree:
            hpf_path = contents_dir / 'content.hpf'
            hpf_bytes = self._serialize_xml(self._content_hpf_tree)
            hpf_path.write_bytes(hpf_bytes)

        # header.xml 저장
        if self._header_tree:
            header_path = contents_dir / 'header.xml'
            header_bytes = self._serialize_xml(self._header_tree)
            header_path.write_bytes(header_bytes)

        # ZIP 재패키징 (writestr(info, payload)로 원본 메타데이터 보존)
        orig_info = getattr(self, '_original_zipinfo', {})
        written = set()
        with zipfile.ZipFile(tmp_out, 'w') as zf:
            # mimetype 반드시 첫 엔트리 (STORED)
            mimetype_path = self.temp_dir / 'mimetype'
            if mimetype_path.exists():
                info = orig_info.get('mimetype', zipfile.ZipInfo('mimetype'))
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, mimetype_path.read_bytes())
                written.add('mimetype')

            # 원본 순서대로 기록 (원본 ZipInfo 메타데이터 보존)
            for arcname in getattr(self, '_original_namelist', []):
                if arcname in written:
                    continue
                file_path = self.temp_dir / arcname
                if file_path.exists() and file_path.is_file():
                    info = orig_info.get(arcname)
                    if info is not None:
                        zf.writestr(info, file_path.read_bytes())
                    else:
                        zf.write(file_path, arcname)
                    written.add(arcname)

            # 새로 추가된 파일
            for root_dir, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = Path(root_dir) / file
                    arcname = str(file_path.relative_to(self.temp_dir))
                    if arcname not in written:
                        zf.write(file_path, arcname)

        if same_file:
            tmp_out.replace(output)

        print(f"저장 완료: {output}")

    def cleanup(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def get_tables(self, section=0):
        tree = self.section_trees.get(section)
        if tree is None:
            return []
        return tree.getroot().findall(f'.//{HP}tbl')

    def get_cell(self, table, row, col):
        rows = table.findall(f'{HP}tr')
        if row >= len(rows):
            return None
        cells = rows[row].findall(f'{HP}tc')
        if col >= len(cells):
            return None
        return cells[col]

    def get_cell_text(self, cell):
        texts = []
        for t in cell.findall(f'.//{HP}t'):
            if t.text:
                texts.append(t.text)
        return ''.join(texts)

    def get_cell_span(self, cell):
        span = cell.find(f'{HP}cellSpan')
        if span is not None:
            return int(span.get('colSpan', '1')), int(span.get('rowSpan', '1'))
        return 1, 1

    def get_table_cell_map(self, table):
        """테이블의 전체 셀 맵 생성"""
        rows = table.findall(f'{HP}tr')
        result = []
        hidden_cells = set()

        for ri, row in enumerate(rows):
            cells = row.findall(f'{HP}tc')
            logical_col = 0
            for ci, cell in enumerate(cells):
                while (ri, logical_col) in hidden_cells:
                    logical_col += 1
                cs, rs = self.get_cell_span(cell)
                for dr in range(rs):
                    for dc in range(cs):
                        if dr == 0 and dc == 0:
                            continue
                        hidden_cells.add((ri + dr, logical_col + dc))
                logical_col += 1

        for ri, row in enumerate(rows):
            cells = row.findall(f'{HP}tc')
            actual_cell_count = len(cells)
            logical_col = 0
            for ci, cell in enumerate(cells):
                while (ri, logical_col) in hidden_cells:
                    logical_col += 1
                cs, rs = self.get_cell_span(cell)
                text = self.get_cell_text(cell)
                result.append({
                    'row': ri, 'col': ci, 'logical_col': logical_col,
                    'text': text, 'colspan': cs, 'rowspan': rs,
                    'writable': True, 'hidden': False,
                    'actual_cells_in_row': actual_cell_count,
                })
                logical_col += 1
        return result

    def set_cell_text(self, cell, text, preserve_style=True):
        """셀의 텍스트를 설정 (바이트 보존 접근법)

        핵심 원칙: XML 구조를 건드리지 않고 기존 <hp:t> 요소의 텍스트만 교체.
        - 기존 run의 charPrIDRef, paraPrIDRef 등 모든 스타일 속성 보존
        - 텍스트 변경 후 linesegarray를 삭제하여 한글이 줄 레이아웃을 재계산하도록 함
        - 글자 겹침 문제 방지 (lineseg 캐시가 텍스트 길이와 불일치하면 겹침 발생)

        빈 셀(<hp:t> 없음)인 경우에만 기존 run 내에 <hp:t>를 생성한다.
        기존 run도 없으면 최소한의 구조를 생성한다.
        """
        sublists = cell.findall(f'{HP}subList')
        if not sublists:
            return False
        sublist = sublists[0]
        paragraphs = sublist.findall(f'{HP}p')
        if not paragraphs:
            return False

        first_p = paragraphs[0]

        # Case 1: 기존 <hp:t>가 있으면 텍스트만 교체 (가장 안전)
        all_t_elems = list(first_p.iter(f'{HP}t'))
        if all_t_elems:
            # 첫 번째 <hp:t>에 텍스트 설정, 나머지는 비우기
            all_t_elems[0].text = text
            for t_elem in all_t_elems[1:]:
                t_elem.text = ''
            # linesegarray를 빈 태그로 교체 — 한글이 열 때 줄 레이아웃 재계산 유도 (merryAI 방식)
            for p in paragraphs:
                for lsa in p.findall(f'{HP}linesegarray'):
                    p.remove(lsa)
                etree.SubElement(p, f'{HP}linesegarray')
            # charPrIDRef를 검정색 맑은고딕(79)으로 변경 (파란색 가이드 스타일 제거)
            if not preserve_style:
                for run in first_p.iter(f'{HP}run'):
                    run.set('charPrIDRef', '79')
            return True

        # Case 2: <hp:t>가 없지만 <hp:run>이 있으면, run 안에 <hp:t> 생성
        first_run = first_p.find(f'{HP}run')
        if first_run is not None:
            new_t = etree.SubElement(first_run, f'{HP}t')
            new_t.text = text
            return True

        # Case 3: <hp:run>도 없으면 최소한의 구조 생성 (다른 paragraph에서 스타일 복사)
        # 같은 테이블 내 다른 셀에서 run 속성을 가져옴
        run_attribs = {}
        table = cell.getparent()
        while table is not None and not table.tag.endswith('}tbl'):
            table = table.getparent()
        if table is not None:
            for existing_run in table.iter(f'{HP}run'):
                if existing_run.attrib:
                    run_attribs = dict(existing_run.attrib)
                    break

        new_run = etree.SubElement(first_p, f'{HP}run')
        if preserve_style and run_attribs:
            for key, val in run_attribs.items():
                new_run.set(key, val)
        new_t = etree.SubElement(new_run, f'{HP}t')
        new_t.text = text

        # linesegarray가 없으면 추가 (한글 HWPX 필수 요소)
        if first_p.find(f'{HP}linesegarray') is None:
            # 같은 테이블의 다른 paragraph에서 linesegarray 복사 시도
            donor_lsa = None
            if table is not None:
                for other_p in table.iter(f'{HP}p'):
                    lsa = other_p.find(f'{HP}linesegarray')
                    if lsa is not None:
                        donor_lsa = lsa
                        break
            if donor_lsa is not None:
                first_p.append(copy.deepcopy(donor_lsa))
            else:
                new_lineseg = etree.SubElement(first_p, f'{HP}linesegarray')
                seg = etree.SubElement(new_lineseg, f'{HP}lineseg')
                seg.set('textpos', '0')
                seg.set('vertpos', '0')
                seg.set('vertsize', '1000')
                seg.set('textheight', '1000')
                seg.set('baseline', '850')
                seg.set('spacing', '300')
                seg.set('horzpos', '0')
                seg.set('horzsize', '0')
                seg.set('flags', '393216')
        return True

    def add_rows(self, table, count=1, template_row=None):
        """테이블에 행 추가"""
        rows = table.findall(f'{HP}tr')
        if len(rows) < 2:
            return False
        if template_row is not None:
            if template_row >= len(rows):
                print(f"경고: template_row {template_row} 없음 (총 {len(rows)}행)", file=sys.stderr)
                return False
            tmpl = rows[template_row]
        else:
            best_row, best_cell_count = 1, 0
            for ri in range(1, len(rows)):
                cc = len(rows[ri].findall(f'{HP}tc'))
                if cc > best_cell_count:
                    best_cell_count = cc
                    best_row = ri
            tmpl = rows[best_row]

        row_count = int(table.get('rowCnt', str(len(rows))))
        for i in range(count):
            new_row = copy.deepcopy(tmpl)
            for cell in new_row.findall(f'{HP}tc'):
                cell_addr = cell.find(f'{HP}cellAddr')
                if cell_addr is not None:
                    cell_addr.set('rowIndex', str(row_count + i))
                for t in cell.findall(f'.//{HP}t'):
                    t.text = ''
            table.append(new_row)
        table.set('rowCnt', str(row_count + count))
        return True

    def remove_element(self, section, table_index):
        tree = self.section_trees.get(section)
        if tree is None:
            return False
        root = tree.getroot()
        tables = root.findall(f'.//{HP}tbl')
        if table_index >= len(tables):
            return False
        self._remove_element_recursive(root, tables[table_index])
        return True

    def _remove_element_recursive(self, parent, target):
        for child in list(parent):
            if child is target:
                parent.remove(child)
                return True
            if self._remove_element_recursive(child, target):
                return True
        return False

    # ================================================================
    # [기능 1] 이미지 삽입 — 완전 구현
    # ================================================================

    def _next_image_id(self):
        """기존 이미지 ID 확인하고 다음 번호 반환"""
        bindata_dir = self.temp_dir / 'BinData'
        if not bindata_dir.exists():
            return 1
        existing = list(bindata_dir.glob('image*'))
        if not existing:
            return 1
        nums = []
        for f in existing:
            m = re.match(r'image(\d+)', f.stem)
            if m:
                nums.append(int(m.group(1)))
        return max(nums) + 1 if nums else 1

    def _unique_id(self):
        """고유 ID 생성 (HWPX pic/instid 용)"""
        return int(hashlib.md5(os.urandom(16)).hexdigest()[:8], 16)

    def _register_image_in_manifest(self, image_arcname, media_type):
        """content.hpf manifest에 이미지 아이템 등록"""
        if self._content_hpf_tree is None:
            print("경고: content.hpf 없음, manifest 등록 생략", file=sys.stderr)
            return None

        root = self._content_hpf_tree.getroot()
        manifest = root.find(f'{OPF}manifest')
        if manifest is None:
            return None

        # ID 결정 (imageN)
        image_id = Path(image_arcname).stem  # e.g., "image3"

        # 중복 체크
        for item in manifest.findall(f'{OPF}item'):
            if item.get('id') == image_id:
                return image_id  # 이미 등록됨

        # 새 아이템 추가
        new_item = etree.SubElement(manifest, f'{OPF}item')
        new_item.set('id', image_id)
        new_item.set('href', image_arcname)
        new_item.set('media-type', media_type)
        new_item.set('isEmbeded', '1')  # Hancom 스펙의 오타 그대로 사용

        return image_id

    def _build_pic_xml(self, image_id, width_hwp, height_hwp, org_width_hwp, org_height_hwp):
        """<hp:pic> XML 요소 생성"""
        pic_id = str(self._unique_id())
        inst_id = str(self._unique_id())

        pic = etree.Element(f'{HP}pic')
        pic.set('id', pic_id)
        pic.set('zOrder', '0')
        pic.set('numberingType', 'PICTURE')
        pic.set('textWrap', 'TOP_AND_BOTTOM')
        pic.set('textFlow', 'BOTH_SIDES')
        pic.set('lock', '0')
        pic.set('dropcapstyle', 'None')
        pic.set('href', '')
        pic.set('groupLevel', '0')
        pic.set('instid', inst_id)
        pic.set('reverse', '0')

        # offset
        offset = etree.SubElement(pic, f'{HP}offset')
        offset.set('x', '0')
        offset.set('y', '0')

        # orgSz (원본 크기)
        org_sz = etree.SubElement(pic, f'{HP}orgSz')
        org_sz.set('width', str(org_width_hwp))
        org_sz.set('height', str(org_height_hwp))

        # curSz (현재 표시 크기)
        cur_sz = etree.SubElement(pic, f'{HP}curSz')
        cur_sz.set('width', str(width_hwp))
        cur_sz.set('height', str(height_hwp))

        # flip
        flip = etree.SubElement(pic, f'{HP}flip')
        flip.set('horizontal', '0')
        flip.set('vertical', '0')

        # rotationInfo
        rot = etree.SubElement(pic, f'{HP}rotationInfo')
        rot.set('angle', '0')
        rot.set('centerX', str(width_hwp // 2))
        rot.set('centerY', str(height_hwp // 2))
        rot.set('rotateimage', '1')

        # renderingInfo
        ri = etree.SubElement(pic, f'{HP}renderingInfo')

        scale_x = round(width_hwp / org_width_hwp, 6) if org_width_hwp else 1
        scale_y = round(height_hwp / org_height_hwp, 6) if org_height_hwp else 1

        trans = etree.SubElement(ri, f'{HC}transMatrix')
        trans.set('e1', '1')
        trans.set('e2', '0')
        trans.set('e3', '0')
        trans.set('e4', '0')
        trans.set('e5', '1')
        trans.set('e6', '0')

        sca = etree.SubElement(ri, f'{HC}scaMatrix')
        sca.set('e1', str(scale_x))
        sca.set('e2', '0')
        sca.set('e3', '0')
        sca.set('e4', '0')
        sca.set('e5', str(scale_y))
        sca.set('e6', '0')

        rot_m = etree.SubElement(ri, f'{HC}rotMatrix')
        rot_m.set('e1', '1')
        rot_m.set('e2', '0')
        rot_m.set('e3', '0')
        rot_m.set('e4', '0')
        rot_m.set('e5', '1')
        rot_m.set('e6', '0')

        # img 참조
        img = etree.SubElement(pic, f'{HC}img')
        img.set('binaryItemIDRef', image_id)
        img.set('bright', '0')
        img.set('contrast', '0')
        img.set('effect', 'REAL_PIC')
        img.set('alpha', '0')

        # imgRect
        img_rect = etree.SubElement(pic, f'{HP}imgRect')
        for name, x, y in [('pt0', 0, 0), ('pt1', org_width_hwp, 0),
                            ('pt2', org_width_hwp, org_height_hwp), ('pt3', 0, org_height_hwp)]:
            pt = etree.SubElement(img_rect, f'{HC}{name}')
            pt.set('x', str(x))
            pt.set('y', str(y))

        # imgClip
        img_clip = etree.SubElement(pic, f'{HP}imgClip')
        img_clip.set('left', '0')
        img_clip.set('right', str(org_width_hwp))
        img_clip.set('top', '0')
        img_clip.set('bottom', str(org_height_hwp))

        # inMargin
        in_margin = etree.SubElement(pic, f'{HP}inMargin')
        for d in ('left', 'right', 'top', 'bottom'):
            in_margin.set(d, '0')

        # imgDim
        img_dim = etree.SubElement(pic, f'{HP}imgDim')
        img_dim.set('dimwidth', str(org_width_hwp))
        img_dim.set('dimheight', str(org_height_hwp))

        # effects (빈 요소)
        etree.SubElement(pic, f'{HP}effects')

        # sz (표시 크기)
        sz = etree.SubElement(pic, f'{HP}sz')
        sz.set('width', str(width_hwp))
        sz.set('widthRelTo', 'ABSOLUTE')
        sz.set('height', str(height_hwp))
        sz.set('heightRelTo', 'ABSOLUTE')
        sz.set('protect', '0')

        # pos (배치 정보)
        pos = etree.SubElement(pic, f'{HP}pos')
        pos.set('treatAsChar', '1')
        pos.set('affectLSpacing', '0')
        pos.set('flowWithText', '1')
        pos.set('allowOverlap', '0')
        pos.set('holdAnchorAndSO', '0')
        pos.set('vertRelTo', 'PARA')
        pos.set('horzRelTo', 'PARA')
        pos.set('vertAlign', 'TOP')
        pos.set('horzAlign', 'LEFT')
        pos.set('vertOffset', '0')
        pos.set('horzOffset', '0')

        # outMargin
        out_margin = etree.SubElement(pic, f'{HP}outMargin')
        for d in ('left', 'right', 'top', 'bottom'):
            out_margin.set(d, '0')

        return pic

    def insert_image(self, section, after_table_index, image_path,
                     width_cm=None, height_cm=None):
        """이미지를 HWPX에 완전히 삽입

        1. BinData/에 파일 복사
        2. content.hpf manifest에 등록
        3. section XML에 <hp:pic> 포함 단락 삽입

        Args:
            section: 섹션 인덱스
            after_table_index: 이 테이블 다음에 삽입 (-1이면 문서 끝)
            image_path: 이미지 파일 경로
            width_cm: 표시 너비 (cm). None이면 원본 크기 기준 최대 16cm
            height_cm: 표시 높이 (cm). None이면 비율 유지
        """
        if not self.temp_dir:
            raise RuntimeError("먼저 extract()를 호출하세요")

        img_path = Path(image_path)
        if not img_path.exists():
            print(f"이미지 파일 없음: {image_path}", file=sys.stderr)
            return False

        # 1. BinData에 복사
        bindata_dir = self.temp_dir / 'BinData'
        bindata_dir.mkdir(exist_ok=True)
        next_num = self._next_image_id()
        ext = img_path.suffix.lower()
        dest_name = f'image{next_num}{ext}'
        dest_path = bindata_dir / dest_name
        shutil.copy2(img_path, dest_path)

        # 미디어 타입 결정
        media_types = {
            '.png': 'image/png', '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', '.bmp': 'image/bmp',
            '.gif': 'image/gif', '.tif': 'image/tiff',
            '.tiff': 'image/tiff',
        }
        media_type = media_types.get(ext, 'image/png')

        # 2. manifest 등록
        image_id = self._register_image_in_manifest(
            f'BinData/{dest_name}', media_type)
        if image_id is None:
            image_id = f'image{next_num}'
        print(f"이미지 등록: {dest_name} (id={image_id})")

        # 3. 크기 계산
        org_w_px, org_h_px = _get_image_dimensions(img_path)
        if org_w_px is None:
            org_w_px, org_h_px = 800, 600  # fallback

        org_w_hwp = _px_to_hwpunit(org_w_px)
        org_h_hwp = _px_to_hwpunit(org_h_px)

        if width_cm is not None:
            disp_w_hwp = int(width_cm * HWPUNIT_PER_CM)
            if height_cm is not None:
                disp_h_hwp = int(height_cm * HWPUNIT_PER_CM)
            else:
                disp_h_hwp = int(disp_w_hwp * org_h_px / org_w_px)
        else:
            # 최대 16cm 너비로 자동 조정
            max_w_hwp = int(16 * HWPUNIT_PER_CM)
            if org_w_hwp > max_w_hwp:
                disp_w_hwp = max_w_hwp
                disp_h_hwp = int(max_w_hwp * org_h_px / org_w_px)
            else:
                disp_w_hwp = org_w_hwp
                disp_h_hwp = org_h_hwp

        # 4. <hp:pic> 요소 생성
        pic_elem = self._build_pic_xml(
            image_id, disp_w_hwp, disp_h_hwp, org_w_hwp, org_h_hwp)

        # 5. section XML에 pic을 포함하는 단락 삽입
        tree = self.section_trees.get(section)
        if tree is None:
            return False
        root = tree.getroot()

        # 삽입할 위치 결정
        insert_after = None
        if after_table_index >= 0:
            tables = root.findall(f'.//{HP}tbl')
            if after_table_index < len(tables):
                # 테이블을 포함하는 최상위 <hp:p> 찾기
                target_tbl = tables[after_table_index]
                insert_after = self._find_top_level_parent(root, target_tbl)

        # pic을 감싸는 <hp:p> > <hp:run> 구조 생성
        # 기존 단락에서 스타일 복제
        existing_p = root.find(f'{HP}p')
        new_p = self._clone_paragraph_structure(existing_p)

        # run 안에 pic 넣기
        run = new_p.find(f'{HP}run')
        if run is None:
            run = etree.SubElement(new_p, f'{HP}run')
        run.append(pic_elem)

        # 삽입
        if insert_after is not None:
            children = list(root)
            idx = children.index(insert_after)
            root.insert(idx + 1, new_p)
        else:
            root.append(new_p)

        print(f"이미지 삽입 완료: {org_w_px}x{org_h_px}px → {disp_w_hwp/HWPUNIT_PER_CM:.1f}x{disp_h_hwp/HWPUNIT_PER_CM:.1f}cm")
        return True

    def _find_top_level_parent(self, root, descendant):
        """root의 직계 자식 중 descendant를 포함하는 것을 찾기"""
        for child in root:
            if child is descendant:
                return child
            if self._contains(child, descendant):
                return child
        return None

    def _contains(self, parent, target):
        for child in parent:
            if child is target:
                return True
            if self._contains(child, target):
                return True
        return False

    # ================================================================
    # [기능 2] 단락 삽입 — 테이블 밖 서술 영역
    # ================================================================

    def _clone_paragraph_structure(self, source_p):
        """기존 단락을 복제하고 텍스트만 비움 (스타일 상속)"""
        if source_p is None:
            # 소스가 없으면 최소 구조 생성
            new_p = etree.Element(f'{HP}p')
            new_p.set('id', '0')
            new_p.set('paraPrIDRef', '0')
            new_p.set('styleIDRef', '0')
            run = etree.SubElement(new_p, f'{HP}run')
            run.set('charPrIDRef', '0')
            t = etree.SubElement(run, f'{HP}t')
            t.text = ''
            return new_p

        new_p = copy.deepcopy(source_p)
        # 텍스트 비우기
        for t in new_p.findall(f'.//{HP}t'):
            t.text = ''
        # pic/tbl 등 비텍스트 요소 제거
        for run in new_p.findall(f'{HP}run'):
            for elem in list(run):
                if elem.tag not in (f'{HP}t',):
                    # charPrIDRef 등 속성은 run에 있으므로 제거 대상은 pic, tbl 등
                    if elem.tag in (f'{HP}pic', f'{HP}tbl', f'{HP}draw',
                                    f'{HP}container', f'{HP}ole'):
                        run.remove(elem)
        # ID 갱신
        new_p.set('id', str(self._unique_id()))
        return new_p

    def insert_text(self, section, after_table_index, text, before_table_index=None):
        """테이블 밖에 텍스트 단락을 삽입

        기존 단락의 스타일을 복제하여 새 단락을 생성한다.
        여러 줄은 각각 별도 <hp:p> 단락으로 생성된다.

        Args:
            section: 섹션 인덱스
            after_table_index: 이 테이블 뒤에 삽입 (-1이면 문서 끝)
            text: 삽입할 텍스트 (줄바꿈으로 여러 단락)
            before_table_index: 이 테이블 앞에 삽입 (after보다 우선)
        """
        tree = self.section_trees.get(section)
        if tree is None:
            return False
        root = tree.getroot()

        # 삽입 위치 결정
        insert_idx = None
        if before_table_index is not None:
            tables = root.findall(f'.//{HP}tbl')
            if before_table_index < len(tables):
                parent_p = self._find_top_level_parent(root, tables[before_table_index])
                if parent_p is not None:
                    insert_idx = list(root).index(parent_p)
        elif after_table_index >= 0:
            tables = root.findall(f'.//{HP}tbl')
            if after_table_index < len(tables):
                parent_p = self._find_top_level_parent(root, tables[after_table_index])
                if parent_p is not None:
                    insert_idx = list(root).index(parent_p) + 1

        # 스타일 소스 단락 찾기 (가장 가까운 텍스트 단락)
        source_p = None
        for p in root.findall(f'{HP}p'):
            # 테이블이나 이미지를 포함하지 않는 순수 텍스트 단락
            if p.find(f'.//{HP}tbl') is None and p.find(f'.//{HP}pic') is None:
                text_content = ''.join(t.text or '' for t in p.findall(f'.//{HP}t'))
                if text_content.strip():
                    source_p = p
                    break

        # 줄 단위로 단락 생성
        lines = text.split('\n')
        inserted = 0

        for line in lines:
            new_p = self._clone_paragraph_structure(source_p)
            # 텍스트 설정
            t_elem = new_p.find(f'.//{HP}t')
            if t_elem is not None:
                t_elem.text = line
            else:
                run = new_p.find(f'{HP}run')
                if run is None:
                    run = etree.SubElement(new_p, f'{HP}run')
                t_elem = etree.SubElement(run, f'{HP}t')
                t_elem.text = line

            if insert_idx is not None:
                root.insert(insert_idx + inserted, new_p)
            else:
                root.append(new_p)
            inserted += 1

        print(f"텍스트 삽입: {inserted}개 단락")
        return True

    # ================================================================
    # analyze
    # ================================================================

    def analyze(self, table_filter=None, show_all_rows=False):
        for section_idx, tree in self.section_trees.items():
            root = tree.getroot()
            tables = root.findall(f'.//{HP}tbl')
            print(f"\n{'='*60}")
            print(f"Section {section_idx}: {len(tables)}개 테이블")
            print(f"{'='*60}")

            for i, tbl in enumerate(tables):
                if table_filter is not None:
                    targets = table_filter if isinstance(table_filter, list) else [table_filter]
                    if i not in targets:
                        continue

                rows = tbl.findall(f'{HP}tr')
                cols = tbl.get('colCnt', '?')
                row_cnt = tbl.get('rowCnt', str(len(rows)))

                nested_count = 0
                for row in rows:
                    for cell in row.findall(f'{HP}tc'):
                        nested_count += len(cell.findall(f'.//{HP}tbl'))

                preview_texts = []
                for t in tbl.findall(f'.//{HP}t'):
                    if t.text and t.text.strip():
                        preview_texts.append(t.text.strip())
                        if len(preview_texts) >= 3:
                            break

                nested_mark = f" [중첩테이블 {nested_count}개]" if nested_count else ""
                print(f"\n  T{i}: {row_cnt}행 x {cols}열{nested_mark}")
                print(f"  미리보기: {' | '.join(preview_texts)}")

                max_rows = len(rows) if show_all_rows else min(3, len(rows))
                for j, row in enumerate(rows[:max_rows]):
                    cells = row.findall(f'{HP}tc')
                    cell_info = []
                    for k, cell in enumerate(cells):
                        text = self.get_cell_text(cell)[:40]
                        cs, rs = self.get_cell_span(cell)
                        span_info = f'[{cs}x{rs}]' if cs != 1 or rs != 1 else ''
                        marker = ' ✎' if not text.strip() else ''
                        cell_info.append(f'c{k}:"{text}"{span_info}{marker}')
                    joined = " | ".join(cell_info)
                    print(f"    R{j} ({len(cells)}셀): {joined}")

                if len(rows) > max_rows:
                    print(f"    ... ({len(rows) - max_rows}행 더)")


# ================================================================
# CLI Commands
# ================================================================

def cmd_analyze(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    table_filter = args.table if hasattr(args, 'table') and args.table is not None else None
    handler.analyze(table_filter=table_filter, show_all_rows=getattr(args, 'all_rows', False))
    handler.cleanup()


def cmd_read_cell(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    tables = handler.get_tables(args.section)
    if args.table >= len(tables):
        print(f"테이블 인덱스 {args.table} 없음 (총 {len(tables)}개)", file=sys.stderr)
        handler.cleanup()
        return
    cell = handler.get_cell(tables[args.table], args.row, args.col)
    if cell is None:
        print(f"셀 ({args.row}, {args.col}) 없음", file=sys.stderr)
    else:
        print(handler.get_cell_text(cell))
    handler.cleanup()


def cmd_read_table(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    tables = handler.get_tables(args.section)
    if args.table >= len(tables):
        print(f"테이블 인덱스 {args.table} 없음 (총 {len(tables)}개)", file=sys.stderr)
        handler.cleanup()
        return

    tbl = tables[args.table]
    cell_map = handler.get_table_cell_map(tbl)

    if args.json:
        result = {
            'table_index': args.table,
            'rows': int(tbl.get('rowCnt', '0')),
            'cols': int(tbl.get('colCnt', '0')),
            'cells': cell_map,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        rows_data = int(tbl.get('rowCnt', '0'))
        cols_data = int(tbl.get('colCnt', '0'))
        print(f"T{args.table}: {rows_data}행 x {cols_data}열")
        print(f"{'─'*70}")
        current_row = -1
        for c in cell_map:
            if c['row'] != current_row:
                current_row = c['row']
                print(f"\n  R{current_row} ({c['actual_cells_in_row']}셀):")
            text_preview = c['text'][:50].replace('\n', '↵')
            span = f" [{c['colspan']}x{c['rowspan']}]" if c['colspan'] != 1 or c['rowspan'] != 1 else ''
            empty_mark = ' ✎빈셀' if not c['text'].strip() else ''
            print(f"    c{c['col']} → \"{text_preview}\"{span}{empty_mark}")
    handler.cleanup()


def cmd_fill(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tables = handler.get_tables(args.section)
    validate_only = getattr(args, 'validate', False)
    errors, ok_count = [], 0

    for item in data.get('cells', []):
        ti, r, c = item['table_index'], item['row'], item['col']
        if ti >= len(tables):
            errors.append(f"✗ T{ti}[{r},{c}] — 테이블 {ti} 없음 (총 {len(tables)}개)")
            continue
        cell = handler.get_cell(tables[ti], r, c)
        if cell is None:
            tbl_rows = tables[ti].findall(f'{HP}tr')
            if r >= len(tbl_rows):
                errors.append(f"✗ T{ti}[{r},{c}] — 행 {r} 없음 (총 {len(tbl_rows)}행)")
            else:
                ac = len(tbl_rows[r].findall(f'{HP}tc'))
                errors.append(f"✗ T{ti}[{r},{c}] — 열 {c} 없음 (이 행은 {ac}셀: c0~c{ac-1})")
            continue
        ok_count += 1
        if not validate_only:
            handler.set_cell_text(cell, item['text'], preserve_style=item.get('preserve_style', True))
            print(f"T{ti}[{r},{c}] = \"{item['text'][:30]}...\"")

    if validate_only:
        print(f"\n검증 결과: {ok_count}개 OK, {len(errors)}개 오류")
        for e in errors:
            print(f"  {e}")
        if errors:
            print(f"\n오류를 수정한 후 --validate 없이 다시 실행하세요.")
        else:
            print(f"\n모든 셀 검증 통과!")
    else:
        if errors:
            print(f"\n경고: {len(errors)}개 셀 건너뜀:", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
        handler.save(args.output)
    handler.cleanup()


def cmd_add_rows(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    tables = handler.get_tables(args.section)
    if args.table >= len(tables):
        print(f"테이블 인덱스 {args.table} 없음", file=sys.stderr)
        handler.cleanup()
        return
    template_row = getattr(args, 'template_row', None)
    handler.add_rows(tables[args.table], args.count, template_row=template_row)
    info = f" (R{template_row} 기준)" if template_row is not None else " (자동 감지)"
    print(f"T{args.table}에 {args.count}행 추가{info}")
    handler.save(args.output)
    handler.cleanup()


def cmd_remove_guides(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    guide_indices = sorted([4, 9, 11, 16, 18], reverse=True)
    for idx in guide_indices:
        if handler.remove_element(0, idx):
            print(f"T{idx} 삭제 완료")
        else:
            print(f"T{idx} 삭제 실패", file=sys.stderr)
    handler.save(args.output)
    handler.cleanup()


def cmd_insert_image(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()
    handler.insert_image(
        0, args.after_table, args.image,
        width_cm=args.width, height_cm=args.height)
    handler.save(args.output)
    handler.cleanup()


def cmd_insert_text(args):
    handler = HwpxHandler(args.hwpx_file)
    handler.extract()

    # 텍스트 소스: --text 또는 --file
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = args.text

    before = getattr(args, 'before_table', None)
    handler.insert_text(0, args.after_table, text, before_table_index=before)
    handler.save(args.output)
    handler.cleanup()


def main():
    parser = argparse.ArgumentParser(description='HWPX 정부지원사업 양식 핸들러')
    subparsers = parser.add_subparsers(dest='command', help='명령')

    # analyze
    p = subparsers.add_parser('analyze', help='양식 구조 분석')
    p.add_argument('hwpx_file')
    p.add_argument('--table', '-t', type=int, default=None)
    p.add_argument('--all-rows', '-a', action='store_true')

    # read-cell
    p = subparsers.add_parser('read-cell', help='셀 텍스트 읽기')
    p.add_argument('hwpx_file')
    p.add_argument('--table', '-t', type=int, required=True)
    p.add_argument('--row', '-r', type=int, required=True)
    p.add_argument('--col', '-c', type=int, required=True)
    p.add_argument('--section', '-s', type=int, default=0)

    # read-table
    p = subparsers.add_parser('read-table', help='테이블 전체 일괄 읽기')
    p.add_argument('hwpx_file')
    p.add_argument('--table', '-t', type=int, required=True)
    p.add_argument('--section', '-s', type=int, default=0)
    p.add_argument('--json', '-j', action='store_true')

    # fill
    p = subparsers.add_parser('fill', help='양식 채우기')
    p.add_argument('hwpx_file')
    p.add_argument('output')
    p.add_argument('--data', '-d', required=True)
    p.add_argument('--section', '-s', type=int, default=0)
    p.add_argument('--validate', '-v', action='store_true')

    # add-rows
    p = subparsers.add_parser('add-rows', help='테이블에 행 추가')
    p.add_argument('hwpx_file')
    p.add_argument('output')
    p.add_argument('--table', '-t', type=int, required=True)
    p.add_argument('--count', '-n', type=int, default=1)
    p.add_argument('--template-row', type=int, default=None)
    p.add_argument('--section', '-s', type=int, default=0)

    # remove-guides
    p = subparsers.add_parser('remove-guides', help='작성요령 삭제')
    p.add_argument('hwpx_file')
    p.add_argument('output')

    # insert-image (UPGRADED: 완전 구현)
    p = subparsers.add_parser('insert-image', help='이미지 삽입 (manifest 등록 + pic XML 생성)')
    p.add_argument('hwpx_file')
    p.add_argument('output')
    p.add_argument('--image', '-i', required=True, help='이미지 파일 경로')
    p.add_argument('--after-table', type=int, required=True, help='이 테이블 뒤에 삽입 (-1=문서 끝)')
    p.add_argument('--width', type=float, default=None, help='표시 너비 (cm)')
    p.add_argument('--height', type=float, default=None, help='표시 높이 (cm)')

    # insert-text (NEW)
    p = subparsers.add_parser('insert-text', help='테이블 밖에 텍스트 단락 삽입')
    p.add_argument('hwpx_file')
    p.add_argument('output')
    p.add_argument('--after-table', type=int, required=True, help='이 테이블 뒤에 삽입 (-1=문서 끝)')
    p.add_argument('--before-table', type=int, default=None, help='이 테이블 앞에 삽입 (우선)')
    p.add_argument('--text', type=str, default=None, help='삽입할 텍스트')
    p.add_argument('--file', '-f', type=str, default=None, help='텍스트 파일에서 읽기')

    args = parser.parse_args()

    commands = {
        'analyze': cmd_analyze,
        'read-cell': cmd_read_cell,
        'read-table': cmd_read_table,
        'fill': cmd_fill,
        'add-rows': cmd_add_rows,
        'remove-guides': cmd_remove_guides,
        'insert-image': cmd_insert_image,
        'insert-text': cmd_insert_text,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
