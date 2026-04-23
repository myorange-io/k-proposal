#!/usr/bin/env python3
"""
초안 ↔ HWPX 완전성 감사(content completeness audit).

초안 마크다운에서 섹션별 앵커 토큰(숫자+단위, 긴 한글 구절, 영문 고유명사)을 추출하고,
생성된 HWPX의 모든 텍스트와 대조하여 누락률을 계산한다.

exit code:
  0 — 누락률이 임계치 미만 (감사 통과)
  1 — 누락률이 임계치 이상 (감사 실패)
  2 — 실행 오류

사용:
  python scripts/audit_completeness.py --draft draft.md --hwpx out.hwpx
  python scripts/audit_completeness.py --draft draft.md --hwpx out.hwpx --threshold 15 --strict
  python scripts/audit_completeness.py --draft draft.md --hwpx out.hwpx --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

# ─────────────────────────────────────────────
# 텍스트 정규화
# ─────────────────────────────────────────────
_MARKDOWN_CODE = re.compile(r'`[^`]*`')
_MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_MARKDOWN_STAR = re.compile(r'\*+')
_MARKDOWN_HEAD = re.compile(r'^\s*[#\-]+\s*', re.M)
_MARKDOWN_GLYPH = re.compile(r'[☑☐◦○◆◇■□▪▫]')
_PUNCT_STRIP = re.compile(r'[\s\.\,\;\:\(\)\[\]\{\}\/\\\-\"\'`~!@#$%^&=+?<>|]')


def strip_markdown(s: str) -> str:
    s = _MARKDOWN_CODE.sub('', s)
    s = _MARKDOWN_LINK.sub(r'\1', s)
    s = _MARKDOWN_STAR.sub('', s)
    s = _MARKDOWN_HEAD.sub('', s)
    s = _MARKDOWN_GLYPH.sub('', s)
    return s


def norm(s: str) -> str:
    """공백·구두점·대소문자 무시한 비교용 정규화."""
    return _PUNCT_STRIP.sub('', strip_markdown(s)).lower()


# ─────────────────────────────────────────────
# HWPX → 평문
# ─────────────────────────────────────────────
def extract_hwpx_text(hwpx_path: Path) -> str:
    """HWPX ZIP 내부 Contents/section*.xml의 모든 텍스트를 평문으로 반환."""
    pieces: list[str] = []
    with zipfile.ZipFile(hwpx_path, 'r') as zf:
        for name in sorted(zf.namelist()):
            if not name.startswith('Contents/') or not name.endswith('.xml'):
                continue
            if 'section' not in Path(name).name and 'header' not in Path(name).name:
                continue
            raw = zf.read(name).decode('utf-8', errors='replace')
            text = re.sub(r'<[^>]+>', ' ', raw)
            pieces.append(text)
    return re.sub(r'\s+', ' ', '\n'.join(pieces))


# ─────────────────────────────────────────────
# 초안 섹션 분할 + 앵커 추출
# ─────────────────────────────────────────────
_HEADING = re.compile(r'^(#{1,4})\s+(.+)$')


def split_sections(draft_text: str) -> list[tuple[str, str]]:
    """마크다운을 (heading_path, body) 튜플 리스트로 분할."""
    sections: list[tuple[str, str]] = []
    path: list[str] = []
    buf: list[str] = []

    def flush():
        if buf:
            body = '\n'.join(buf).strip()
            if body:
                sections.append((' / '.join(path), body))

    for line in draft_text.splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            buf.clear()
            level = len(m.group(1))
            path[:] = path[:level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return sections


_ANCHOR_NUM = re.compile(
    r'\d+(?:[.,]\d+)*\s*(?:%|억|만원|천원|원|명|건|개|년|월|일|시간|배|점|주|개월|주차)'
)
_ANCHOR_KO = re.compile(r'[가-힣]{6,}')
_ANCHOR_EN = re.compile(r'\b[A-Z][A-Za-z0-9]{2,}\b')

_EN_STOP = {'and', 'the', 'for', 'with', 'this', 'that', 'from'}


def extract_anchors(body: str, max_n: int = 10) -> list[str]:
    """본문에서 고유성 높은 앵커 토큰 추출 (긴 순서대로 최대 N개)."""
    clean = strip_markdown(body)
    toks: set[str] = set()
    toks.update(_ANCHOR_NUM.findall(clean))
    toks.update(_ANCHOR_KO.findall(clean))
    for t in _ANCHOR_EN.findall(clean):
        if t.lower() not in _EN_STOP:
            toks.add(t)
    return sorted(toks, key=len, reverse=True)[:max_n]


# ─────────────────────────────────────────────
# 감사
# ─────────────────────────────────────────────
def audit(draft_path: Path, hwpx_path: Path, *, max_anchors: int = 10,
          section_warn_threshold: float = 0.5) -> dict:
    """누락률 감사. 결과를 dict로 반환."""
    draft = draft_path.read_text(encoding='utf-8')
    hwpx_text = extract_hwpx_text(hwpx_path)
    hwpx_norm = norm(hwpx_text)

    sections = split_sections(draft)

    total_present = total_missing = 0
    section_reports: list[dict] = []

    for path, body in sections:
        anchors = extract_anchors(body, max_n=max_anchors)
        if len(anchors) < 2:
            continue
        present = [t for t in anchors if norm(t) in hwpx_norm]
        missing = [t for t in anchors if norm(t) not in hwpx_norm]
        total_present += len(present)
        total_missing += len(missing)
        miss_rate = len(missing) / len(anchors) if anchors else 0.0
        if miss_rate >= section_warn_threshold and len(missing) >= 2:
            section_reports.append({
                'section': path,
                'body_len': len(body),
                'anchors': len(anchors),
                'present': len(present),
                'missing': missing,
                'miss_rate': round(miss_rate, 3),
            })

    total = total_present + total_missing
    section_reports.sort(key=lambda r: (-r['miss_rate'], -r['body_len']))

    return {
        'draft': str(draft_path),
        'hwpx': str(hwpx_path),
        'draft_chars': len(draft),
        'hwpx_chars': len(hwpx_text),
        'sections_scanned': len(sections),
        'total_anchors': total,
        'present': total_present,
        'missing': total_missing,
        'miss_rate_pct': round(100 * total_missing / total, 1) if total else 0.0,
        'critical_sections': section_reports,
    }


# ─────────────────────────────────────────────
# 출력
# ─────────────────────────────────────────────
def print_human(report: dict) -> None:
    print('=' * 70)
    print('CONTENT COMPLETENESS AUDIT')
    print('=' * 70)
    print(f'Draft  : {report["draft"]}')
    print(f'HWPX   : {report["hwpx"]}')
    print(f'본문 크기: 초안 {report["draft_chars"]:,}자  →  HWPX {report["hwpx_chars"]:,}자')
    if report['draft_chars']:
        ratio = 100 * report['hwpx_chars'] / report['draft_chars']
        print(f'         (HWPX/초안 = {ratio:.0f}%)')
    print(f'섹션 스캔: {report["sections_scanned"]}개')
    print(f'앵커 검사: {report["total_anchors"]}개')
    print(f'  present: {report["present"]} ({100 - report["miss_rate_pct"]:.0f}%)')
    print(f'  missing: {report["missing"]} ({report["miss_rate_pct"]:.0f}%)')
    print('=' * 70)

    crits = report['critical_sections']
    if not crits:
        print('\n✓ 크리티컬 섹션 없음 — 모든 섹션이 50% 이상 반영됨')
        return
    print(f'\n⚠️  누락률 50% 이상 섹션: {len(crits)}개\n')
    for i, r in enumerate(crits, 1):
        rate = int(r['miss_rate'] * 100)
        print(f'[{i}] {r["section"]}')
        print(f'    본문 {r["body_len"]}자 · 앵커 {r["anchors"]}개 · 누락 {len(r["missing"])}개 ({rate}%)')
        for t in r['missing'][:8]:
            print(f'    ✗ {t[:80]}')
        print()


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(description='초안 ↔ HWPX 완전성 감사')
    p.add_argument('--draft', required=True, type=Path, help='초안 마크다운 경로')
    p.add_argument('--hwpx', required=True, type=Path, help='생성된 HWPX 경로')
    p.add_argument('--threshold', type=float, default=20.0,
                   help='허용 누락률 %% (기본 20.0). 이 값 이상이면 exit 1')
    p.add_argument('--max-anchors', type=int, default=10,
                   help='섹션당 검사 앵커 수 (기본 10)')
    p.add_argument('--strict', action='store_true',
                   help='크리티컬 섹션이 하나라도 있으면 exit 1')
    p.add_argument('--json', action='store_true', help='JSON 리포트 출력')
    args = p.parse_args()

    if not args.draft.exists():
        print(f'오류: 초안 파일 없음: {args.draft}', file=sys.stderr)
        return 2
    if not args.hwpx.exists():
        print(f'오류: HWPX 파일 없음: {args.hwpx}', file=sys.stderr)
        return 2

    try:
        report = audit(args.draft, args.hwpx, max_anchors=args.max_anchors)
    except Exception as e:
        print(f'감사 실행 오류: {e}', file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    fail = report['miss_rate_pct'] >= args.threshold
    if args.strict and report['critical_sections']:
        fail = True
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
