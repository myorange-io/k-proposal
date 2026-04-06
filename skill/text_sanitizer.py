#!/usr/bin/env python3
"""
한국어 텍스트 정제 유틸리티

kordoc의 텍스트 정제 로직을 Python으로 포팅.
HWPX/HWP에서 추출한 텍스트의 한국어 특화 정제를 수행한다.

사용법:
    from text_sanitizer import sanitize_korean_text, remove_hwp_alt_text
    clean = sanitize_korean_text("현 장 대 응 단 장")  # → "현장대응단장"
"""

import re


HWP_SHAPE_ALT_TEXT_RE = re.compile(
    r'(?:모서리가 둥근 |둥근 )?'
    r'(?:사각형|직사각형|정사각형|원|타원|삼각형|이등변 삼각형|직각 삼각형|'
    r'선|직선|곡선|화살표|굵은 화살표|이중 화살표|'
    r'오각형|육각형|팔각형|별|[4-8]점별|십자|십자형|구름|구름형|'
    r'마름모|도넛|평행사변형|사다리꼴|부채꼴|호|반원|물결|번개|하트|빗금|'
    r'블록 화살표|수식|표|그림|개체|그리기\s?개체|묶음\s?개체|글상자|'
    r'수식\s?개체|OLE\s?개체)\s?입니다\.?'
)

OLE_ALT_TEXT_RE = re.compile(
    r'그림입니다\.?\s*(?:원본\s*그림의\s*(?:이름|크기)[^\n]*'
    r'(?:\n[^\n]*원본\s*그림의\s*(?:이름|크기)[^\n]*)*)?'
)

OLE_REMNANT_RE = re.compile(
    r'원본\s*그림의\s*(?:이름|크기)\s*:[^\n]*'
    r'(?:\n\s*원본\s*그림의\s*(?:이름|크기)\s*:[^\n]*)*'
)

KOREAN_CHAR_RE = re.compile(r'[\uAC00-\uD7AF\u3131-\u318E]')


def fix_uniform_spacing(text: str) -> str:
    """균등배분 공백 복원: "현 장 대 응 단 장" → "현장대응단장"

    30자 이하 텍스트에서 70%+ 토큰이 한글 1글자이면 균등배분으로 판단.
    """
    if len(text) > 30 or ' ' not in text:
        return text

    tokens = text.split(' ')
    if len(tokens) < 3:
        return text

    korean_single_count = sum(
        1 for t in tokens
        if len(t) == 1 and KOREAN_CHAR_RE.match(t)
    )

    if korean_single_count / len(tokens) >= 0.7:
        return ''.join(tokens)

    return text


def remove_hwp_alt_text(text: str) -> str:
    """HWP 도형/개체 자동생성 대체텍스트 제거 (26종 패턴)"""
    result = OLE_ALT_TEXT_RE.sub('', text)
    result = HWP_SHAPE_ALT_TEXT_RE.sub('', result)
    result = OLE_REMNANT_RE.sub('', result)
    return result.strip()


def remove_toc_page_numbers(text: str) -> str:
    """목차 리더 탭 이후 페이지번호 제거"""
    leader_idx = text.find('\x1F')
    if leader_idx >= 0:
        return text[:leader_idx]
    return text


def normalize_heading_pattern(text: str) -> str:
    """제N조/장/절 패턴 정규화 — 균등배분 공백 허용"""
    compact = text.replace(' ', '')
    if re.match(r'^제\d+[조장절편]', compact) and len(text) <= 50:
        return compact
    return text


def detect_heading_level(text: str, base_font_size: float = 0,
                         font_size: float = 0) -> int:
    """폰트 크기 비율 + 한국어 패턴으로 heading level 감지

    Returns:
        0 = heading 아님, 1-3 = heading level
    """
    if not text.strip() or len(text) > 200:
        return 0

    level = 0

    if base_font_size > 0 and font_size > 0:
        ratio = font_size / base_font_size
        if ratio >= 1.5:
            level = 1
        elif ratio >= 1.3:
            level = 2
        elif ratio >= 1.15:
            level = 3

    compact = text.replace(' ', '')
    if re.match(r'^제\d+[조장절편]', compact) and len(text) <= 50:
        if level == 0:
            level = 3

    return level


def sanitize_korean_text(text: str) -> str:
    """한국어 텍스트 종합 정제

    1. HWP 도형/OLE 대체텍스트 제거
    2. 균등배분 공백 복원
    3. 연속 공백 정리
    """
    result = remove_hwp_alt_text(text)
    result = remove_toc_page_numbers(result)
    result = re.sub(r'[ \t]+', ' ', result).strip()
    result = fix_uniform_spacing(result)
    return result


def sanitize_blocks(blocks: list) -> list:
    """블록 리스트의 텍스트를 일괄 정제

    Args:
        blocks: [{"type": "paragraph"|"table"|..., "text": "..."}, ...]

    Returns:
        정제된 블록 리스트 (빈 텍스트 블록은 필터링)
    """
    cleaned = []
    for block in blocks:
        if "text" in block and block["text"]:
            block["text"] = sanitize_korean_text(block["text"])
            if block["text"]:
                cleaned.append(block)
        else:
            cleaned.append(block)
    return cleaned


if __name__ == "__main__":
    import sys

    test_cases = [
        ("현 장 대 응 단 장", "현장대응단장"),
        ("사각형입니다.", ""),
        ("그림입니다. 원본 그림의 이름: test.png", ""),
        ("제 1 장  총 칙", "제1장총칙"),
        ("정상적인 텍스트입니다", "정상적인 텍스트입니다"),
        ("  공백   정리   테스트  ", "공백 정리 테스트"),
    ]

    print("=== 한국어 텍스트 정제 테스트 ===\n")
    all_pass = True
    for input_text, expected in test_cases:
        result = sanitize_korean_text(input_text)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"{status} \"{input_text}\" → \"{result}\"", end="")
        if result != expected:
            print(f"  (expected: \"{expected}\")", end="")
        print()

    sys.exit(0 if all_pass else 1)
