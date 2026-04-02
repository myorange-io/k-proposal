#!/usr/bin/env python3
"""HWPX 파일에 이미지를 삽입하는 모듈.

3단계 프로세스:
  1. BinData/에 이미지 파일 복사 + 고유 ID 생성
  2. Contents/content.hpf manifest에 opf:item 등록
  3. Contents/section0.xml에 hp:p > hp:run > hp:pic > hc:img XML 생성

TypeScript 원본: merryAI/hwpx-report-automation의 buildPicXml() 로직을 Python(lxml)으로 포팅.
"""

import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from lxml import etree

# ── 네임스페이스 ──
NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "opf": "http://www.idpf.org/2007/opf/",
}

# MIME 타입 매핑
MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

# HWP 단위 변환: 실제 HWPX 문서 기준 A4(21cm) = 59528 HWPUNIT
# 따라서 1cm = 59528/21.0 ≈ 2834.67 HWPUNIT
CM_TO_HWPUNIT = 59528.0 / 21.0  # ~2834.67


def _get_image_dimensions(image_path: str) -> tuple[int, int]:
    """이미지 파일의 픽셀 크기를 반환한다. PIL이 있으면 사용, 없으면 PNG 헤더 파싱."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except ImportError:
        pass
    # PNG 헤더에서 직접 읽기 (fallback)
    with open(image_path, "rb") as f:
        header = f.read(32)
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        import struct
        w = struct.unpack(">I", header[16:20])[0]
        h = struct.unpack(">I", header[20:24])[0]
        return (w, h)
    # 기본값
    return (640, 480)


def _find_next_image_number(zip_path: str) -> int:
    """기존 HWPX에서 imageN 형태의 최대 번호를 찾아 다음 번호를 반환한다."""
    max_num = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            # BinData/imageN.ext 패턴
            m = re.match(r"BinData/image(\d+)\.\w+", name)
            if m:
                max_num = max(max_num, int(m.group(1)))
        # content.hpf에서 id="imageN" 패턴도 확인
        try:
            hpf_xml = zf.read("Contents/content.hpf").decode("utf-8")
            for m in re.finditer(r'id="image(\d+)"', hpf_xml):
                max_num = max(max_num, int(m.group(1)))
        except KeyError:
            pass
    return max_num + 1


def _find_max_pic_instid(section_xml: bytes) -> tuple[int, int]:
    """section XML에서 hp:pic의 최대 id와 instid를 찾는다."""
    max_pic_id = 0
    max_inst_id = 0
    root = etree.fromstring(section_xml)
    for pic in root.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}pic"):
        pid = pic.get("id")
        iid = pic.get("instid")
        if pid and pid.isdigit():
            max_pic_id = max(max_pic_id, int(pid))
        if iid and iid.isdigit():
            max_inst_id = max(max_inst_id, int(iid))
    return max_pic_id, max_inst_id


def _build_pic_element(
    image_id: str,
    pic_id: int,
    inst_id: int,
    width_hwp: int,
    height_hwp: int,
    original_width_hwp: int,
    original_height_hwp: int,
    filename: str,
) -> etree._Element:
    """hp:pic XML 요소를 lxml으로 생성한다.

    TypeScript buildPicXml() 함수의 정확한 포팅.
    treatAsChar="1"로 인라인(글자처럼 취급) 삽입.
    """
    HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
    HC = "{http://www.hancom.co.kr/hwpml/2011/core}"

    center_x = max(1, width_hwp // 2)
    center_y = max(1, height_hwp // 2)

    pic = etree.Element(
        f"{HP}pic",
        attrib={
            "id": str(pic_id),
            "zOrder": "0",
            "numberingType": "PICTURE",
            "textWrap": "SQUARE",
            "textFlow": "BOTH_SIDES",
            "lock": "0",
            "dropcapstyle": "None",
            "href": "",
            "groupLevel": "0",
            "instid": str(inst_id),
            "reverse": "0",
        },
    )

    etree.SubElement(pic, f"{HP}offset", x="0", y="0")
    etree.SubElement(pic, f"{HP}orgSz", width=str(original_width_hwp), height=str(original_height_hwp))
    etree.SubElement(pic, f"{HP}curSz", width=str(width_hwp), height=str(height_hwp))
    etree.SubElement(pic, f"{HP}flip", horizontal="0", vertical="0")
    etree.SubElement(
        pic,
        f"{HP}rotationInfo",
        angle="0",
        centerX=str(center_x),
        centerY=str(center_y),
        rotateimage="1",
    )

    # renderingInfo
    rendering = etree.SubElement(pic, f"{HP}renderingInfo")
    for matrix_name in ("transMatrix", "scaMatrix", "rotMatrix"):
        etree.SubElement(
            rendering,
            f"{HC}{matrix_name}",
            e1="1", e2="0", e3="0", e4="0", e5="1", e6="0",
        )

    # imgRect
    img_rect = etree.SubElement(pic, f"{HP}imgRect")
    etree.SubElement(img_rect, f"{HC}pt0", x="0", y="0")
    etree.SubElement(img_rect, f"{HC}pt1", x=str(original_width_hwp), y="0")
    etree.SubElement(img_rect, f"{HC}pt2", x=str(original_width_hwp), y=str(original_height_hwp))
    etree.SubElement(img_rect, f"{HC}pt3", x="0", y=str(original_height_hwp))

    etree.SubElement(
        pic,
        f"{HP}imgClip",
        left="0",
        right=str(original_width_hwp),
        top="0",
        bottom=str(original_height_hwp),
    )
    etree.SubElement(pic, f"{HP}effects")
    etree.SubElement(pic, f"{HP}inMargin", left="0", right="0", top="0", bottom="0")
    etree.SubElement(
        pic,
        f"{HP}imgDim",
        dimwidth=str(original_width_hwp),
        dimheight=str(original_height_hwp),
    )

    # hc:img — 핵심: binaryItemIDRef로 BinData 파일 참조
    etree.SubElement(
        pic,
        f"{HC}img",
        binaryItemIDRef=image_id,
        bright="0",
        contrast="0",
        effect="REAL_PIC",
        alpha="0",
    )

    # hp:sz — 표시 크기
    etree.SubElement(
        pic,
        f"{HP}sz",
        width=str(width_hwp),
        widthRelTo="ABSOLUTE",
        height=str(height_hwp),
        heightRelTo="ABSOLUTE",
        protect="0",
    )

    # hp:pos — treatAsChar="1"로 글자처럼 취급
    etree.SubElement(
        pic,
        f"{HP}pos",
        treatAsChar="1",
        affectLSpacing="0",
        flowWithText="1",
        allowOverlap="0",
        holdAnchorAndSO="0",
        vertRelTo="PARA",
        horzRelTo="PARA",
        vertAlign="TOP",
        horzAlign="LEFT",
        vertOffset="0",
        horzOffset="0",
    )

    etree.SubElement(pic, f"{HP}outMargin", left="0", right="0", top="0", bottom="0")

    # shapeComment
    comment = etree.SubElement(pic, f"{HP}shapeComment")
    comment.text = filename

    return pic


def insert_image_to_hwpx(
    hwpx_path: str,
    output_path: str,
    image_path: str,
    after_table_index: int | None = None,
    width_cm: float = 14,
) -> dict:
    """HWPX 파일에 이미지를 삽입한다.

    Args:
        hwpx_path: 원본 HWPX 파일 경로
        output_path: 출력 HWPX 파일 경로
        image_path: 삽입할 이미지 파일 경로
        after_table_index: 이 인덱스의 테이블 다음에 삽입 (0-based). None이면 문서 끝.
        width_cm: 이미지 표시 너비 (cm). 높이는 원본 비율 유지.

    Returns:
        dict: 삽입 결과 정보 (image_id, pic_id, width_hwp, height_hwp 등)
    """
    image_path = str(Path(image_path).resolve())
    hwpx_path = str(Path(hwpx_path).resolve())
    output_path = str(Path(output_path).resolve())

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
    if not os.path.exists(hwpx_path):
        raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {hwpx_path}")

    # 이미지 정보
    img_ext = Path(image_path).suffix.lower()
    img_filename = Path(image_path).name
    media_type = MIME_BY_EXT.get(img_ext, "image/png")
    px_w, px_h = _get_image_dimensions(image_path)

    # HWP 단위 변환
    width_hwp = int(round(width_cm * CM_TO_HWPUNIT))
    aspect = px_h / px_w if px_w > 0 else 0.75
    height_hwp = int(round(width_hwp * aspect))

    # 원본 크기 (pixel -> HWPUNIT: 실제 한컴 문서 기준 ~100 HWPUNIT/px)
    # 예: 1286px -> 128580 HWPUNIT (128580/1286 ≈ 100)
    PX_TO_HWPUNIT = 100
    original_width_hwp = max(1, int(round(px_w * PX_TO_HWPUNIT)))
    original_height_hwp = max(1, int(round(px_h * PX_TO_HWPUNIT)))

    # ── 1단계: 고유 ID 생성 ──
    image_number = _find_next_image_number(hwpx_path)
    image_id = f"image{image_number}"
    bin_filename = f"BinData/{image_id}{img_ext}"

    # section XML에서 pic/instid 최대값 탐색
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        section_xml = zf.read("Contents/section0.xml")
    max_pic_id, max_inst_id = _find_max_pic_instid(section_xml)
    pic_id = max_pic_id + 1
    inst_id = max_inst_id + 1

    # ── 임시 파일로 복사 후 수정 ──
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".hwpx")
    os.close(tmp_fd)

    try:
        shutil.copy2(hwpx_path, tmp_path)

        # 기존 ZIP 내용을 모두 읽어 새 ZIP으로 재작성
        entries = {}
        with zipfile.ZipFile(hwpx_path, "r") as zf_in:
            for name in zf_in.namelist():
                entries[name] = zf_in.read(name)

        # ── 2단계: content.hpf manifest에 opf:item 등록 ──
        hpf_xml = entries["Contents/content.hpf"]
        hpf_root = etree.fromstring(hpf_xml)

        # 네임스페이스 감지: opf prefix
        opf_ns = None
        for prefix, uri in hpf_root.nsmap.items():
            if "opf" in (prefix or "") or "idpf" in uri:
                opf_ns = uri
                break
        if opf_ns is None:
            opf_ns = "http://www.idpf.org/2007/opf/"

        # manifest 요소 찾기
        manifest_el = None
        for el in hpf_root.iter():
            if el.tag.endswith("}manifest") or el.tag == "manifest":
                manifest_el = el
                break

        if manifest_el is not None:
            # opf:item 추가
            new_item = etree.SubElement(
                manifest_el,
                f"{{{opf_ns}}}item",
            )
            new_item.set("id", image_id)
            new_item.set("href", bin_filename)
            new_item.set("media-type", media_type)
            new_item.set("isEmbeded", "1")

            # 수정된 content.hpf 저장
            entries["Contents/content.hpf"] = etree.tostring(
                hpf_root, xml_declaration=True, encoding="UTF-8", standalone="yes"
            )

        # ── 3단계: section0.xml에 hp:pic XML 삽입 ──
        sec_root = etree.fromstring(section_xml)

        # hp:p > hp:run > hp:pic 구조의 새 문단 생성
        HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

        # 기존 문서에서 기본 paraPrIDRef, styleIDRef, charPrIDRef 추출
        first_p = sec_root.find(f".//{HP}p")
        default_para_pr = first_p.get("paraPrIDRef", "0") if first_p is not None else "0"
        default_style = first_p.get("styleIDRef", "0") if first_p is not None else "0"
        first_run = sec_root.find(f".//{HP}run")
        default_char_pr = first_run.get("charPrIDRef", "0") if first_run is not None else "0"

        # 새 문단 생성
        new_p = etree.Element(
            f"{HP}p",
            attrib={
                "paraPrIDRef": default_para_pr,
                "styleIDRef": default_style,
                "pageBreak": "0",
                "columnBreak": "0",
                "merged": "0",
            },
        )
        new_run = etree.SubElement(new_p, f"{HP}run", charPrIDRef=default_char_pr)

        # hp:pic 요소 생성
        pic_el = _build_pic_element(
            image_id=image_id,
            pic_id=pic_id,
            inst_id=inst_id,
            width_hwp=width_hwp,
            height_hwp=height_hwp,
            original_width_hwp=original_width_hwp,
            original_height_hwp=original_height_hwp,
            filename=img_filename,
        )
        new_run.append(pic_el)

        # 삽입 위치 결정
        if after_table_index is not None:
            # sec 직계 자식 중 hp:tbl을 포함하는 hp:p를 찾음
            # 실제 HWPX에서 테이블은 hp:p > hp:run > hp:tbl 구조
            table_paragraphs = []
            for child in sec_root:
                if child.tag == f"{HP}p":
                    # 이 p 안에 tbl이 있는지
                    tbls = child.findall(f".//{HP}tbl")
                    if tbls:
                        table_paragraphs.append(child)

            if after_table_index < len(table_paragraphs):
                target_p = table_paragraphs[after_table_index]
                # target_p 다음에 삽입
                parent = target_p.getparent()
                idx = list(parent).index(target_p)
                parent.insert(idx + 1, new_p)
            else:
                # 인덱스가 범위를 넘으면 문서 끝에 삽입
                sec_root.append(new_p)
        else:
            # 문서 끝에 삽입
            sec_root.append(new_p)

        # 수정된 section0.xml 저장
        entries["Contents/section0.xml"] = etree.tostring(
            sec_root, xml_declaration=True, encoding="UTF-8", standalone="yes"
        )

        # ── 1단계 (실행): BinData/에 이미지 파일 추가 ──
        with open(image_path, "rb") as f:
            image_data = f.read()
        entries[bin_filename] = image_data

        # ── 새 ZIP 작성 (mimetype: 반드시 첫 엔트리, ZIP_STORED) ──
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
            # mimetype은 HWPX spec 상 반드시 첫 번째 엔트리, STORED 압축
            if "mimetype" in entries:
                zf_out.writestr("mimetype", entries["mimetype"],
                                compress_type=zipfile.ZIP_STORED)
            for name, data in entries.items():
                if name == "mimetype":
                    continue  # 이미 위에서 처리
                if isinstance(data, bytes):
                    zf_out.writestr(name, data)
                else:
                    zf_out.writestr(name, data)

        result = {
            "image_id": image_id,
            "bin_filename": bin_filename,
            "pic_id": pic_id,
            "inst_id": inst_id,
            "width_hwp": width_hwp,
            "height_hwp": height_hwp,
            "original_px": (px_w, px_h),
            "media_type": media_type,
            "after_table_index": after_table_index,
        }
        return result

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── CLI 실행 ──
if __name__ == "__main__":
    import json

    BASE = "/Users/pengdo/Desktop/Work/02. 지원사업/부산AI실증지원센터 AI기업 사업화 자금 지원사업"
    HWPX = os.path.join(BASE, "[제출용v3] AI 기업 사업화 자금 지원사업.hwpx")
    IMAGE = os.path.join(BASE, "_시각자료/market_size.png")
    OUTPUT = os.path.join(BASE, "_작업파일/test_image_inserted.hwpx")

    print("=" * 60)
    print("HWPX 이미지 삽입 테스트")
    print("=" * 60)

    result = insert_image_to_hwpx(
        hwpx_path=HWPX,
        output_path=OUTPUT,
        image_path=IMAGE,
        after_table_index=None,  # 문서 끝에 삽입
        width_cm=14,
    )

    print(f"\n삽입 결과:")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"\n출력 파일: {OUTPUT}")
    print(f"파일 크기: {os.path.getsize(OUTPUT):,} bytes")
