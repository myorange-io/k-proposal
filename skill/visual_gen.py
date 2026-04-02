#!/usr/bin/env python3
"""
시각 자료 생성기 v2
- 브랜드 색상 자동 추출 (로고/IR/소개서 이미지에서) + 가독성 자동 보정
- 한글 폰트 자동 탐색 (Pretendard 우선)
- --count N: 색상 팔레트 변형 N개 생성
- 차트 타입: bar, horizontal_bar, line, area, pie, donut, stacked_bar, grouped_bar, infographic
- Gemini 이미지 생성 (variants 지원)
- Mermaid 다이어그램
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


def load_env():
    env_path = Path.cwd()
    for _ in range(5):
        env_file = env_path / '.env'
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        os.environ.setdefault(key.strip(), value.strip())
            return
        env_path = env_path.parent


load_env()


# ─────────────────────────────────────────────
# 기본 팔레트 (브랜드 추출 실패 시 폴백)
# ─────────────────────────────────────────────
DEFAULT_PALETTES = [
    {
        'primary': '#FF6D00', 'secondary': '#2563EB',
        'accent': '#FF9E40', 'accent2': '#60A5FA', 'muted': '#93C5FD',
        'dark': '#1A1A1A', 'bg': '#FFFFFF', 'bg_alt': '#F5F5F5',
        'label': 'default',
    },
    {
        'primary': '#1D4ED8', 'secondary': '#0EA5E9',
        'accent': '#3B82F6', 'accent2': '#7DD3FC', 'muted': '#BAE6FD',
        'dark': '#1E3A5F', 'bg': '#FFFFFF', 'bg_alt': '#F0F9FF',
        'label': 'blue',
    },
    {
        'primary': '#111827', 'secondary': '#374151',
        'accent': '#6B7280', 'accent2': '#9CA3AF', 'muted': '#D1D5DB',
        'dark': '#111827', 'bg': '#FFFFFF', 'bg_alt': '#F9FAFB',
        'label': 'mono',
    },
]


# ─────────────────────────────────────────────
# 색상 유틸리티
# ─────────────────────────────────────────────
def hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*[max(0, min(255, int(v))) for v in rgb])


def relative_luminance(rgb):
    vals = []
    for c in rgb:
        c = c / 255.0
        vals.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def contrast_ratio(fg_rgb, bg_rgb=(255, 255, 255)):
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_readable(hex_color, bg_rgb=(255, 255, 255), min_contrast=3.5):
    """WCAG 기준 미달 색상을 어둡게/밝게 조정해 가독성 확보"""
    rgb = list(hex_to_rgb(hex_color))
    if contrast_ratio(rgb, bg_rgb) >= min_contrast:
        return hex_color

    bg_lum = relative_luminance(bg_rgb)
    if bg_lum > 0.5:  # 밝은 배경 → 어둡게
        for _ in range(40):
            if contrast_ratio(rgb, bg_rgb) >= min_contrast:
                break
            rgb = [max(0, c - 8) for c in rgb]
    else:              # 어두운 배경 → 밝게
        for _ in range(40):
            if contrast_ratio(rgb, bg_rgb) >= min_contrast:
                break
            rgb = [min(255, c + 8) for c in rgb]
    return rgb_to_hex(rgb)


def is_near_white(rgb, threshold=215):
    return all(c >= threshold for c in rgb)


def is_near_black(rgb, threshold=40):
    return all(c <= threshold for c in rgb)


# ─────────────────────────────────────────────
# 브랜드 색상 추출
# ─────────────────────────────────────────────
def extract_brand_colors(image_path):
    """이미지(로고/소개서 표지)에서 브랜드 색상 추출 후 가독성 보정"""
    try:
        from PIL import Image
        import colorsys

        img = Image.open(image_path).convert('RGB')
        img.thumbnail((200, 200))

        # 양자화로 대표 색상 추출
        quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        palette_raw = quantized.getpalette()[:16 * 3]

        colors = []
        for i in range(0, len(palette_raw), 3):
            rgb = (palette_raw[i], palette_raw[i + 1], palette_raw[i + 2])
            if not is_near_white(rgb) and not is_near_black(rgb):
                colors.append(rgb)

        if not colors:
            return None

        # 채도 높은 순 정렬
        def saturation(rgb):
            r, g, b = [c / 255.0 for c in rgb]
            import colorsys as cs
            _, s, _ = cs.rgb_to_hls(r, g, b)
            return s

        colors.sort(key=saturation, reverse=True)

        # 상위 5개 색상을 가독성 보정 (흰 배경 기준)
        brand = [ensure_readable(rgb_to_hex(c)) for c in colors[:5]]

        palette = {
            'primary':   brand[0],
            'secondary': brand[1] if len(brand) > 1 else '#2563EB',
            'accent':    brand[2] if len(brand) > 2 else '#FF9E40',
            'accent2':   brand[3] if len(brand) > 3 else '#60A5FA',
            'muted':     brand[4] if len(brand) > 4 else '#93C5FD',
            'dark': '#1A1A1A', 'bg': '#FFFFFF', 'bg_alt': '#F5F5F5',
            'label': f'brand:{Path(image_path).name}',
        }
        print(f"브랜드 색상 추출: {image_path}")
        print(f"  주 색상: {palette['primary']}, {palette['secondary']}, {palette['accent']}")
        return palette

    except ImportError:
        print("색상 추출에 Pillow 필요: pip install Pillow", file=sys.stderr)
        return None
    except Exception as e:
        print(f"색상 추출 실패 ({image_path}): {e}", file=sys.stderr)
        return None


def find_brand_image(search_dirs=None):
    """현재 폴더에서 로고/소개서/IR 이미지 자동 탐색"""
    if search_dirs is None:
        search_dirs = [Path.cwd()]

    priority_patterns = [
        '*로고*', '*logo*', '*brand*', '*브랜드*',
        '*소개서*', '*IR*', '*ir_*', '*pitch*',
    ]
    image_exts = {'.png', '.jpg', '.jpeg', '.webp'}

    for pattern in priority_patterns:
        for d in search_dirs:
            for p in sorted(Path(d).rglob(pattern)):
                if p.suffix.lower() in image_exts:
                    return str(p)

    # 패턴 없으면 첫 번째 이미지
    for d in search_dirs:
        for ext in image_exts:
            matches = sorted(Path(d).glob(f'*{ext}'))
            if matches:
                return str(matches[0])
    return None


def build_palettes(brand_image=None):
    """브랜드 이미지에서 추출한 팔레트 + 기본 변형 2개, 최대 3개 반환"""
    palettes = []
    if brand_image:
        extracted = extract_brand_colors(brand_image)
        if extracted:
            palettes.append(extracted)
    for p in DEFAULT_PALETTES:
        if len(palettes) >= 3:
            break
        palettes.append(p)
    return palettes[:3]


# ─────────────────────────────────────────────
# 한글 폰트 탐색
# ─────────────────────────────────────────────
FONT_PRIORITY = [
    'Pretendard', 'Pretendard Variable',
    'NotoSansKR', 'Noto Sans KR', 'Noto Sans CJK KR',
    'AppleSDGothicNeo', 'Apple SD Gothic Neo',
    'MalgunGothic', 'Malgun Gothic',
    'NanumGothic', 'Nanum Gothic',
    'AppleGothic', 'Apple Gothic',
]

FONT_FILE_PATTERNS = [
    ('Pretendard',      ['*Pretendard*.ttf', '*Pretendard*.otf']),
    ('NotoSansKR',      ['*NotoSansKR*.ttf', '*NotoSansCJK*.ttc', '*NotoSans*KR*.otf']),
    ('AppleSDGothicNeo',['AppleSDGothicNeo*.ttc']),
    ('MalgunGothic',    ['malgun*.ttf', 'Malgun*.ttf']),
    ('NanumGothic',     ['*NanumGothic*.ttf', '*Nanum*Gothic*.ttf']),
    ('AppleGothic',     ['AppleGothic*.ttf']),
]

FONT_SEARCH_DIRS = [
    Path.home() / 'Library' / 'Fonts',
    Path('/Library/Fonts'),
    Path('/System/Library/Fonts'),
    Path('/System/Library/Fonts/Supplemental'),
    Path('/usr/share/fonts'),
    Path('/usr/local/share/fonts'),
    Path('C:/Windows/Fonts'),
    Path.home() / '.fonts',
    Path.home() / '.local' / 'share' / 'fonts',
]


def find_korean_font():
    """한글 폰트 탐색 (우선순위: Pretendard → NotoSansKR → AppleSDGothicNeo → Malgun → Nanum → AppleGothic)"""
    import matplotlib.font_manager as fm

    available = {f.name.lower(): f.name for f in fm.fontManager.ttflist}
    for name in FONT_PRIORITY:
        if name.lower() in available:
            return available[name.lower()]

    for font_name, patterns in FONT_FILE_PATTERNS:
        for search_dir in FONT_SEARCH_DIRS:
            if not search_dir.exists():
                continue
            for pattern in patterns:
                matches = list(search_dir.glob(pattern)) or list(search_dir.rglob(pattern))
                if matches:
                    try:
                        fm.fontManager.addfont(str(matches[0]))
                        prop = fm.FontProperties(fname=str(matches[0]))
                        return prop.get_name()
                    except Exception:
                        pass

    print("⚠️  한글 폰트를 찾지 못했습니다. 텍스트가 깨질 수 있습니다.", file=sys.stderr)
    print("   Pretendard 설치: https://github.com/orioncactus/pretendard/releases", file=sys.stderr)
    return None


_font_initialized = False


def setup_matplotlib():
    """matplotlib 초기화 (한글 폰트 + 스타일)"""
    global _font_initialized
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if not _font_initialized:
        font_name = find_korean_font()
        if font_name:
            plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False
        _font_initialized = True

    return plt


# ─────────────────────────────────────────────
# 공통 스타일 + 유틸
# ─────────────────────────────────────────────
def apply_base_style(plt, palette):
    plt.rcParams.update({
        'axes.spines.top':   False,
        'axes.spines.right': False,
        'axes.edgecolor':    '#DDDDDD',
        'axes.grid':         True,
        'grid.alpha':        0.25,
        'grid.color':        '#DDDDDD',
        'figure.facecolor':  'white',
        'axes.facecolor':    palette['bg'],
    })


def color_cycle(palette, n):
    pool = [palette['primary'], palette['secondary'],
            palette['accent'], palette['accent2'], palette['muted']]
    return [pool[i % len(pool)] for i in range(n)]


def add_source_footer(fig, source):
    if source:
        fig.text(0.99, 0.01, source,
                 ha='right', va='bottom', fontsize=8,
                 color='#888888', style='italic')


def value_fmt(v):
    if isinstance(v, float) and v == int(v):
        return f'{int(v):,}'
    if isinstance(v, (int, float)):
        return f'{v:,}'
    return str(v)


def label_bar(ax, bars, y_vals, horizontal=False, dark='#1A1A1A', max_val=None):
    """바 차트 값 라벨 (겹침 방지)"""
    if max_val is None:
        max_val = max(abs(v) for v in y_vals) if y_vals else 1
    offset = max_val * 0.015
    for bar, val in zip(bars, y_vals):
        if horizontal:
            ax.text(bar.get_width() + offset,
                    bar.get_y() + bar.get_height() / 2,
                    value_fmt(val),
                    va='center', ha='left',
                    fontweight='bold', fontsize=10, color=dark)
        else:
            ax.text(bar.get_x() + bar.get_width() / 2.,
                    bar.get_height() + offset,
                    value_fmt(val),
                    ha='center', va='bottom',
                    fontweight='bold', fontsize=10, color=dark)


# ─────────────────────────────────────────────
# 차트 타입별 드로잉
# ─────────────────────────────────────────────
def draw_chart(ax, chart_config, palette):
    """단일 축에 차트 드로잉. generate_matplotlib / generate_infographic 공용."""
    import numpy as np

    chart_type = chart_config.get('type', 'bar')
    x = chart_config.get('x', [])
    y = chart_config.get('y', [])
    dark = palette['dark']
    colors = color_cycle(palette, max(len(x), len(chart_config.get('series', {}))))

    ax.set_facecolor(palette['bg'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.25, color='#DDDDDD')

    if chart_type == 'bar':
        bars = ax.bar(x, y, color=colors[:len(x)], edgecolor='white', linewidth=0.5, width=0.6)
        label_bar(ax, bars, y, dark=dark)

    elif chart_type == 'horizontal_bar':
        bars = ax.barh(x, y, color=colors[:len(x)], edgecolor='white', linewidth=0.5, height=0.6)
        label_bar(ax, bars, y, horizontal=True, dark=dark)
        ax.invert_yaxis()

    elif chart_type == 'line':
        ax.plot(x, y, marker='o', linewidth=2.5, color=palette['primary'],
                markersize=8, markerfacecolor='white',
                markeredgecolor=palette['primary'], markeredgewidth=2)
        max_y = max(abs(v) for v in y) if y else 1
        for xi, yi in zip(x, y):
            ax.annotate(value_fmt(yi), (xi, yi),
                        textcoords='offset points', xytext=(0, 12),
                        ha='center', fontweight='bold', fontsize=10, color=dark)

    elif chart_type == 'area':
        idx = range(len(x))
        ax.fill_between(idx, y, alpha=0.2, color=palette['primary'])
        ax.plot(idx, y, marker='o', linewidth=2.5, color=palette['primary'],
                markersize=7, markerfacecolor='white',
                markeredgecolor=palette['primary'], markeredgewidth=2)
        ax.set_xticks(list(idx))
        ax.set_xticklabels(x)
        for xi, yi in zip(idx, y):
            ax.annotate(value_fmt(yi), (xi, yi),
                        textcoords='offset points', xytext=(0, 12),
                        ha='center', fontweight='bold', fontsize=10, color=dark)

    elif chart_type in ('pie', 'donut'):
        labels = chart_config.get('labels', x)
        pie_colors = color_cycle(palette, len(y))
        wedge_kw = {'edgecolor': 'white', 'linewidth': 2}
        if chart_type == 'donut':
            wedge_kw['width'] = 0.55
        wedges, texts, autotexts = ax.pie(
            y, labels=labels, autopct='%1.1f%%',
            colors=pie_colors, wedgeprops=wedge_kw,
            textprops={'fontsize': 10, 'color': dark},
            startangle=90)
        for at in autotexts:
            at.set_fontweight('bold')
            at.set_fontsize(10)
        if chart_type == 'donut':
            center_text = chart_config.get('center_text', '')
            if center_text:
                ax.text(0, 0, center_text, ha='center', va='center',
                        fontsize=13, fontweight='bold', color=dark)

    elif chart_type == 'stacked_bar':
        series = chart_config.get('series', {})
        s_colors = color_cycle(palette, len(series))
        bottom = [0.0] * len(x)
        max_total = max(sum(row) for row in zip(*series.values())) if series else 1
        for (name, vals), color in zip(series.items(), s_colors):
            bars = ax.bar(x, vals, bottom=bottom, label=name,
                          color=color, edgecolor='white', linewidth=0.5, width=0.6)
            for bar, val, bot in zip(bars, vals, bottom):
                if val > max_total * 0.04:  # 너무 작은 셀 라벨 생략
                    ax.text(bar.get_x() + bar.get_width() / 2.,
                            bot + val / 2,
                            value_fmt(val),
                            ha='center', va='center',
                            fontsize=8, color='white', fontweight='bold')
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.legend(loc='upper left', frameon=False, fontsize=9)

    elif chart_type == 'grouped_bar':
        series = chart_config.get('series', {})
        n_groups = len(x)
        n_series = len(series)
        width = 0.75 / n_series
        group_pos = np.arange(n_groups)
        s_colors = color_cycle(palette, n_series)
        all_vals = [v for vals in series.values() for v in vals]
        max_val = max(all_vals) if all_vals else 1
        for idx, ((name, vals), color) in enumerate(zip(series.items(), s_colors)):
            offset = (idx - n_series / 2 + 0.5) * width
            bars = ax.bar(group_pos + offset, vals, width=width * 0.9,
                          label=name, color=color, edgecolor='white', linewidth=0.5)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2.,
                        bar.get_height() + max_val * 0.015,
                        value_fmt(val),
                        ha='center', va='bottom', fontsize=8, color=dark, fontweight='bold')
        ax.set_xticks(group_pos)
        ax.set_xticklabels(x)
        ax.legend(loc='upper left', frameon=False, fontsize=9)

    # 축 라벨 (파이/도넛 제외)
    if chart_type not in ('pie', 'donut'):
        ax.set_xlabel(chart_config.get('xlabel', ''), fontsize=10, color='#666666')
        ax.set_ylabel(chart_config.get('ylabel', ''), fontsize=10, color='#666666')
        ax.tick_params(colors='#666666', labelsize=9)

    # 제목
    title = chart_config.get('title', '')
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', color=dark, pad=14)


# ─────────────────────────────────────────────
# 인포그래픽
# ─────────────────────────────────────────────
def generate_infographic(config, output_path, palette, plt):
    """KPI 수치 카드 (상단) + 차트 (하단) 인포그래픽"""
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec

    kpis = config.get('kpis', [])
    chart_cfg = config.get('chart', None)
    source = config.get('source', '')
    title = config.get('title', '')
    dark = palette['dark']
    n_kpi = max(len(kpis), 1)

    fig = plt.figure(figsize=(12, 8 if chart_cfg else 5))
    fig.patch.set_facecolor('white')

    if chart_cfg:
        gs = gridspec.GridSpec(2, n_kpi, height_ratios=[1, 2.2], hspace=0.45, wspace=0.25)
    else:
        gs = gridspec.GridSpec(1, n_kpi, wspace=0.25)

    kpi_colors = color_cycle(palette, n_kpi)

    for i, kpi in enumerate(kpis):
        ax = fig.add_subplot(gs[0, i])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        color = kpi_colors[i]

        # 카드 배경
        card = mpatches.FancyBboxPatch(
            (0.05, 0.05), 0.90, 0.90,
            boxstyle='round,pad=0.04',
            facecolor=palette['bg_alt'], edgecolor=color, linewidth=1.8)
        ax.add_patch(card)

        # 상단 색상 바
        top_bar = mpatches.FancyBboxPatch(
            (0.05, 0.80), 0.90, 0.15,
            boxstyle='round,pad=0.02',
            facecolor=color, edgecolor='none')
        ax.add_patch(top_bar)

        # 수치 (큼직하게)
        ax.text(0.5, 0.50, kpi.get('value', ''),
                ha='center', va='center',
                fontsize=21, fontweight='bold', color=dark)

        # 라벨
        label_text = kpi.get('label', '')
        ax.text(0.5, 0.22, label_text,
                ha='center', va='center',
                fontsize=9, color='#555555')

    # 하단 차트
    if chart_cfg:
        ax_chart = fig.add_subplot(gs[1, :])
        draw_chart(ax_chart, chart_cfg, palette)

    if title:
        fig.suptitle(title, fontsize=19, fontweight='bold', color=dark, y=0.99)

    add_source_footer(fig, source)

    out = Path(output_path)
    if not out.suffix:
        out = out.with_suffix('.png')
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"인포그래픽 생성 완료: {out}")
    return True


# ─────────────────────────────────────────────
# Matplotlib 메인 엔트리
# ─────────────────────────────────────────────
def generate_matplotlib(chart_config, output_path, palette=None):
    plt = setup_matplotlib()
    if palette is None:
        palette = DEFAULT_PALETTES[0]

    apply_base_style(plt, palette)

    if chart_config.get('type') == 'infographic':
        return generate_infographic(chart_config, output_path, palette, plt)

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('white')

    draw_chart(ax, chart_config, palette)
    add_source_footer(fig, chart_config.get('source', ''))

    has_source = bool(chart_config.get('source', ''))
    plt.tight_layout(rect=[0, 0.04 if has_source else 0, 1, 1])

    out = Path(output_path)
    if not out.suffix:
        out = out.with_suffix('.png')
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"차트 생성 완료: {out}  [팔레트: {palette['label']}]")
    return True


def generate_variants(chart_config, output_path, count=3, brand_image=None):
    """N개의 팔레트 변형 생성 (브랜드 추출 + 기본 팔레트 혼합)"""
    palettes = build_palettes(brand_image)
    out = Path(output_path)
    stem = out.stem
    suffix = out.suffix or '.png'

    results = []
    for i, palette in enumerate(palettes[:count]):
        variant_path = out.parent / f'{stem}_v{i + 1}{suffix}'
        success = generate_matplotlib(chart_config, str(variant_path), palette)
        if success:
            results.append((str(variant_path), palette['label']))

    if results:
        print(f"\n총 {len(results)}개 변형 생성:")
        for path, label in results:
            print(f"  [{label}] {path}")
    return len(results) > 0


# ─────────────────────────────────────────────
# Gemini 이미지 생성
# ─────────────────────────────────────────────
def generate_gemini_image(prompt, output_path, style=None, api_key=None, count=1):
    key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not key:
        print("오류: GEMINI_API_KEY 환경변수를 설정하세요", file=sys.stderr)
        print("  https://aistudio.google.com/apikey 에서 발급", file=sys.stderr)
        return False

    # Gemini 한국어 렌더링 불안정 → 영문 스타일 프롬프트 사용
    style_prompts = {
        'diagram':    'Technical architecture diagram. Rounded-corner boxes connected by arrows. Light gray box backgrounds with dark text. Orange or blue accent for key nodes. White background. Large, clear labels inside boxes.',
        'infographic':'Business infographic. Data represented with icons and large bold numbers. Card-based layout. Orange/blue accents. Small clear labels. White or light beige background.',
        'flowchart':  'Process flowchart. Rounded-corner boxes and arrows. Left-to-right flow. Current step in orange, others in gray. Short keyword labels. White background.',
        'chart':      'Business chart. Orange/blue color palette. Clean axes and labels. Values shown on data points. White background. Large bold title.',
        'timeline':   'Horizontal timeline. Orange line with year/period markers. Each event as a card below the line. White background. Short keyword text.',
        'service':    'Service overview. 3-4 cards arranged horizontally. Each card: icon + title + one-line description. Light gray card background with rounded corners. Orange or blue icons.',
        'comparison': 'Comparison table. Left column: item names, right 2 columns: subjects. Header with orange background and white text. Clean grid. White background.',
    }

    design_guide = """
[Design system — apply strictly]
- Colors: orange (#FF6D00) accent, black (#1A1A1A) text, white (#FFFFFF) background
- Minimal, generous whitespace, rounded corner cards, grid alignment
- Clean, trustworthy SaaS aesthetic

[Text rendering — critical]
- All text must be sharp, large, and high-contrast
- Use English labels only (Korean text may render incorrectly)
- Minimize text; use short keywords/labels only
- No text overlap with other visual elements
"""

    base_prompt = f"{prompt}\n\n{design_guide}"
    if style and style in style_prompts:
        base_prompt += f"\nStyle: {style_prompts[style]}"
    else:
        base_prompt += "\nStyle: Professional business document visual. White background, clean readable design."

    variant_suffixes = [
        '',
        ' Variant 2: slightly different layout arrangement and color emphasis.',
        ' Variant 3: alternative composition with different visual hierarchy.',
    ]

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        models_to_try = [
            "gemini-2.0-flash-exp-image-generation",
            "gemini-2.0-flash-exp",
            "gemini-2.0-flash",
        ]

        out_base = Path(output_path)
        stem = out_base.stem
        success_count = 0

        for v_idx in range(count):
            full_prompt = base_prompt + variant_suffixes[min(v_idx, len(variant_suffixes) - 1)]

            response = None
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=['TEXT', 'IMAGE'],
                        ),
                    )
                    if response.candidates:
                        break
                except Exception:
                    continue

            if not response or not response.candidates:
                print(f"변형 {v_idx + 1}: 응답 없음", file=sys.stderr)
                continue

            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    ext_map = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}
                    ext = ext_map.get(part.inline_data.mime_type, '.png')

                    if count == 1:
                        out = out_base if out_base.suffix else out_base.with_suffix(ext)
                    else:
                        out = out_base.parent / f'{stem}_v{v_idx + 1}{ext}'

                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(
                        base64.b64decode(image_data) if isinstance(image_data, str) else image_data
                    )
                    print(f"이미지 생성 완료: {out}")
                    success_count += 1
                    break

        return success_count > 0

    except ImportError:
        print("google-genai 패키지 필요: pip install google-genai", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Gemini API 오류: {e}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────
# Mermaid 다이어그램
# ─────────────────────────────────────────────
def generate_mermaid(mermaid_code, output_path, theme='default'):
    out = Path(output_path)
    if not out.suffix:
        out = out.with_suffix('.png')

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
        f.write(mermaid_code)
        mmd_path = f.name

    try:
        cmd = ['mmdc', '-i', mmd_path, '-o', str(out), '-t', theme, '-b', 'white']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Mermaid 다이어그램 생성: {out}")
            return True
        print(f"mmdc 오류: {result.stderr}", file=sys.stderr)
        if result.returncode == 127 or 'not found' in result.stderr.lower():
            print("설치: npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("mmdc 없음. 설치: npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return False
    finally:
        os.unlink(mmd_path)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='시각 자료 생성기 v2')
    subparsers = parser.add_subparsers(dest='command')

    # gemini
    p_g = subparsers.add_parser('gemini', help='Gemini 이미지 생성 (아키텍처, 개념도 등)')
    p_g.add_argument('prompt', help='생성할 이미지 설명 (영문 권장)')
    p_g.add_argument('-o', '--output', required=True)
    p_g.add_argument('--style', choices=[
        'diagram', 'infographic', 'flowchart', 'chart', 'timeline', 'service', 'comparison'
    ])
    p_g.add_argument('--count', type=int, default=1, metavar='N',
                     help='생성할 변형 수 (기본 1, 최대 3)')
    p_g.add_argument('--api-key')

    # mermaid
    p_m = subparsers.add_parser('mermaid', help='Mermaid 다이어그램')
    p_m.add_argument('code', help='Mermaid 코드 문자열')
    p_m.add_argument('-o', '--output', required=True)
    p_m.add_argument('--theme', default='default',
                     choices=['default', 'dark', 'forest', 'neutral'])

    # chart (matplotlib)
    p_c = subparsers.add_parser('chart', help='Matplotlib 차트 / 인포그래픽')
    p_c.add_argument('config', help='차트 설정 JSON 파일 경로')
    p_c.add_argument('-o', '--output', required=True)
    p_c.add_argument('--count', type=int, default=1, metavar='N',
                     help='팔레트 변형 수 (기본 1, 최대 3). 1이면 단일 파일')
    p_c.add_argument('--brand-image', metavar='PATH',
                     help='브랜드 색상 추출용 이미지 파일 (로고/소개서)')
    p_c.add_argument('--auto-brand', action='store_true',
                     help='현재 폴더에서 로고/소개서 이미지 자동 탐색')

    args = parser.parse_args()

    if args.command == 'gemini':
        generate_gemini_image(args.prompt, args.output,
                              args.style, args.api_key, args.count)

    elif args.command == 'mermaid':
        generate_mermaid(args.code, args.output, args.theme)

    elif args.command == 'chart':
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)

        brand_image = args.brand_image
        if args.auto_brand and not brand_image:
            brand_image = find_brand_image()
            if brand_image:
                print(f"브랜드 이미지 자동 탐색: {brand_image}")

        if args.count > 1:
            generate_variants(config, args.output, args.count, brand_image)
        else:
            palette = None
            if brand_image:
                palette = extract_brand_colors(brand_image) or DEFAULT_PALETTES[0]
            generate_matplotlib(config, args.output, palette)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
