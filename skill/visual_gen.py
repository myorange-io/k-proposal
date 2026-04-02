#!/usr/bin/env python3
"""
시각 자료 생성기
- 나노 바나나 프로 (Google Gemini Image Generation)
- Mermaid 다이어그램 (오프라인 대안)
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


def load_env():
    """현재 디렉토리 또는 상위 디렉토리에서 .env 파일을 찾아 환경변수 로드"""
    env_path = Path.cwd()
    for _ in range(5):  # 최대 5단계 상위까지 탐색
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


def generate_gemini_image(prompt, output_path, style=None, api_key=None):
    """나노 바나나 프로 (Gemini) 이미지 생성

    Gemini 2.0 Flash의 이미지 생성 기능을 사용합니다.
    API 키: GEMINI_API_KEY 환경변수 또는 --api-key 인자
    """
    key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not key:
        print("오류: GEMINI_API_KEY 환경변수를 설정하세요", file=sys.stderr)
        print("  export GEMINI_API_KEY='your-api-key'", file=sys.stderr)
        print("  https://aistudio.google.com/apikey 에서 발급 가능", file=sys.stderr)
        return False

    # 오렌지임팩트 브랜드 디자인 시스템
    brand_guide = """
[브랜드 디자인 시스템 - 반드시 적용]
- 주요 색상: 오렌지(#FF6D00) 포인트, 블랙(#1A1A1A) 텍스트, 화이트(#FFFFFF) 배경
- 보조 색상: 라이트 베이지(#FFF5F0) 배경, 블루(#2563EB) 기술/기능 강조, 라이트 그레이(#F5F5F5) 카드
- 디자인 원칙: 미니멀, 여백 충분, 둥근 모서리 카드, 그리드 기반 정렬
- 아이콘: 단색 라인 아이콘, 블루 원형 배지 안에 화이트 아이콘
- 레이아웃: 카드형 UI, 충분한 패딩, 섹션 간 명확한 구분
- 전체적 느낌: 깔끔하고 신뢰감 있는 SaaS 프로덕트 스타일

[텍스트 렌더링 규칙 - 매우 중요]
- 한국어/영어 텍스트는 반드시 선명하고 읽기 쉽게 렌더링
- 텍스트가 뭉개지거나 흐릿해지지 않도록 충분히 큰 폰트 사이즈 사용
- 텍스트 양은 최소화하고, 핵심 키워드만 배치
- 텍스트 위에 다른 요소가 겹치지 않도록 배치
- 복잡한 문장 대신 짧은 라벨/키워드 위주로 구성
- 텍스트 배경에 충분한 명암 대비 확보 (흰 배경에 검은 글씨, 오렌지 배경에 흰 글씨)
"""

    # 스타일별 프롬프트 보강
    style_prompts = {
        'diagram': '기술 아키텍처 다이어그램. 둥근 모서리의 박스들을 화살표로 연결. 박스는 라이트 그레이 배경에 검은 텍스트. 주요 노드는 오렌지 또는 블루 강조. 흰색 배경. 박스 안 텍스트는 크고 선명하게.',
        'infographic': '비즈니스 인포그래픽. 데이터를 아이콘+숫자로 표현. 카드형 레이아웃. 오렌지/블루 포인트 색상. 숫자는 크고 굵게, 라벨은 작지만 선명하게. 흰색 또는 라이트 베이지 배경.',
        'flowchart': '프로세스 플로우차트. 둥근 모서리 박스와 화살표. 단계별로 좌에서 우 또는 위에서 아래로 배치. 현재 단계는 오렌지, 나머지는 그레이. 각 박스 안 텍스트는 짧은 키워드만. 흰색 배경.',
        'chart': '비즈니스 차트. 오렌지/블루 색상 팔레트. 깔끔한 축과 라벨. 데이터 포인트에 값 표시. 흰색 배경. 제목은 크고 굵게.',
        'timeline': '수평 타임라인. 오렌지 라인 위에 연도/시기 표시. 각 이벤트는 카드형으로 아래에 배치. 흰색 배경. 텍스트는 짧은 키워드 위주.',
        'service': '서비스 소개 레이아웃. 3~4개의 카드가 가로로 나열. 각 카드에 아이콘+제목+한줄 설명. 카드는 라이트 그레이 배경에 둥근 모서리. 오렌지 또는 블루 아이콘.',
        'comparison': '비교 테이블. 왼쪽 열은 항목명, 오른쪽 2열은 비교 대상. 헤더는 오렌지 배경에 흰 글씨. 셀은 깔끔한 그리드. 흰색 배경.',
    }

    if style and style in style_prompts:
        full_prompt = f"{prompt}\n\n{brand_guide}\n스타일: {style_prompts[style]}"
    elif style:
        full_prompt = f"{prompt}\n\n{brand_guide}\n스타일: {style}"
    else:
        full_prompt = f"{prompt}\n\n{brand_guide}\n스타일: 전문적인 비즈니스 문서에 삽입할 시각 자료. 흰색 배경, 깔끔하고 읽기 쉬운 디자인."

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        # 이미지 생성 가능한 모델 (우선순위 순)
        models_to_try = [
            "gemini-2.0-flash-exp-image-generation",
            "gemini-2.0-flash-exp",
            "gemini-2.0-flash",
        ]

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
            print("오류: 모든 모델에서 응답 생성 실패", file=sys.stderr)
            return False

        # 응답에서 이미지 추출
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type

                # 확장자 결정
                ext_map = {
                    'image/png': '.png',
                    'image/jpeg': '.jpg',
                    'image/webp': '.webp',
                }
                ext = ext_map.get(mime_type, '.png')

                out = Path(output_path)
                if not out.suffix:
                    out = out.with_suffix(ext)

                out.write_bytes(
                    base64.b64decode(image_data)
                    if isinstance(image_data, str)
                    else image_data
                )
                print(f"이미지 생성 완료: {out}")
                return True

        print("경고: 응답에 이미지가 없습니다. 텍스트 응답:", file=sys.stderr)
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                print(part.text, file=sys.stderr)
        return False

    except ImportError:
        print("google-genai 패키지가 필요합니다:", file=sys.stderr)
        print("  pip install google-genai", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Gemini API 오류: {e}", file=sys.stderr)
        return False


def generate_mermaid(mermaid_code, output_path, theme='default'):
    """Mermaid 다이어그램을 이미지로 변환 (mmdc CLI 필요)

    설치: npm install -g @mermaid-js/mermaid-cli
    """
    out = Path(output_path)
    if not out.suffix:
        out = out.with_suffix('.png')

    # Mermaid 코드를 임시 파일에 저장
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
        f.write(mermaid_code)
        mmd_path = f.name

    try:
        # mmdc 실행
        cmd = ['mmdc', '-i', mmd_path, '-o', str(out), '-t', theme, '-b', 'white']
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Mermaid 다이어그램 생성: {out}")
            return True
        else:
            print(f"mmdc 오류: {result.stderr}", file=sys.stderr)

            # mmdc가 없는 경우 안내
            if 'not found' in result.stderr.lower() or result.returncode == 127:
                print("mermaid-cli를 설치하세요:", file=sys.stderr)
                print("  npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
            return False
    except FileNotFoundError:
        print("mmdc 명령을 찾을 수 없습니다.", file=sys.stderr)
        print("설치: npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return False
    finally:
        os.unlink(mmd_path)


def generate_matplotlib(chart_config, output_path):
    """Matplotlib 차트 생성 (오프라인, API 불필요)

    chart_config 예시:
    {
        "type": "bar",
        "title": "연도별 매출 추이",
        "x": ["2024", "2025", "2026(E)"],
        "y": [5.2, 8.1, 15.0],
        "xlabel": "연도",
        "ylabel": "매출액(억원)"
    }
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        # 한글 폰트 설정
        font_paths = [
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',      # macOS
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',  # Linux
            'C:/Windows/Fonts/malgun.ttf',                       # Windows
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                prop = fm.FontProperties(fname=fp)
                plt.rcParams['font.family'] = prop.get_name()
                break

        plt.rcParams['axes.unicode_minus'] = False

        # 오렌지임팩트 브랜드 색상
        ORANGE = '#FF6D00'
        ORANGE_LIGHT = '#FF9E40'
        BLUE = '#2563EB'
        BLUE_LIGHT = '#60A5FA'
        DARK = '#1A1A1A'
        GRAY = '#F5F5F5'
        BEIGE = '#FFF5F0'

        brand_colors = [ORANGE, BLUE, ORANGE_LIGHT, BLUE_LIGHT, '#93C5FD']

        # 스타일 설정
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        plt.rcParams['axes.edgecolor'] = '#DDDDDD'
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3
        plt.rcParams['grid.color'] = '#DDDDDD'

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        chart_type = chart_config.get('type', 'bar')
        x = chart_config.get('x', [])
        y = chart_config.get('y', [])
        colors = chart_config.get('colors', brand_colors)

        if chart_type == 'bar':
            bars = ax.bar(x, y, color=colors[:len(x)], width=0.6,
                          edgecolor='white', linewidth=0.5)
            for bar, val in zip(bars, y):
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                        f'{val}', ha='center', va='bottom',
                        fontweight='bold', fontsize=12, color=DARK)
        elif chart_type == 'line':
            ax.plot(x, y, marker='o', linewidth=2.5, color=ORANGE,
                    markersize=8, markerfacecolor='white',
                    markeredgecolor=ORANGE, markeredgewidth=2)
            for xi, yi in zip(x, y):
                ax.annotate(f'{yi}', (xi, yi), textcoords="offset points",
                            xytext=(0, 12), ha='center',
                            fontweight='bold', fontsize=11, color=DARK)
        elif chart_type == 'pie':
            labels = chart_config.get('labels', x)
            wedges, texts, autotexts = ax.pie(
                y, labels=labels, autopct='%1.1f%%',
                colors=colors[:len(y)],
                wedgeprops={'edgecolor': 'white', 'linewidth': 2},
                textprops={'fontsize': 11, 'color': DARK})
            for autotext in autotexts:
                autotext.set_fontweight('bold')
                autotext.set_fontsize(11)

        if chart_type != 'pie':
            ax.set_xlabel(chart_config.get('xlabel', ''),
                          fontsize=11, color='#666666')
            ax.set_ylabel(chart_config.get('ylabel', ''),
                          fontsize=11, color='#666666')
            ax.tick_params(colors='#666666', labelsize=10)

        ax.set_title(chart_config.get('title', ''),
                     fontsize=16, fontweight='bold', color=DARK, pad=20)
        plt.tight_layout()

        out = Path(output_path)
        if not out.suffix:
            out = out.with_suffix('.png')
        plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"차트 생성 완료: {out}")
        return True

    except ImportError:
        print("matplotlib 패키지가 필요합니다:", file=sys.stderr)
        print("  pip install matplotlib", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description='시각 자료 생성기')
    subparsers = parser.add_subparsers(dest='command', help='생성 방법')

    # Gemini (나노 바나나 프로)
    p_gemini = subparsers.add_parser('gemini',
        help='나노 바나나 프로 (Gemini) 이미지 생성')
    p_gemini.add_argument('prompt', help='생성할 이미지 설명')
    p_gemini.add_argument('-o', '--output', required=True, help='출력 파일 경로')
    p_gemini.add_argument('--style', choices=[
        'diagram', 'infographic', 'flowchart', 'chart', 'timeline'
    ], help='이미지 스타일')
    p_gemini.add_argument('--api-key', help='Gemini API 키')

    # Mermaid
    p_mermaid = subparsers.add_parser('mermaid',
        help='Mermaid 다이어그램 생성')
    p_mermaid.add_argument('code', help='Mermaid 코드')
    p_mermaid.add_argument('-o', '--output', required=True, help='출력 파일 경로')
    p_mermaid.add_argument('--theme', default='default',
        choices=['default', 'dark', 'forest', 'neutral'])

    # Matplotlib 차트
    p_chart = subparsers.add_parser('chart',
        help='Matplotlib 차트 생성')
    p_chart.add_argument('config', help='차트 설정 JSON 파일 경로')
    p_chart.add_argument('-o', '--output', required=True, help='출력 파일 경로')

    args = parser.parse_args()

    if args.command == 'gemini':
        generate_gemini_image(args.prompt, args.output, args.style, args.api_key)
    elif args.command == 'mermaid':
        generate_mermaid(args.code, args.output, args.theme)
    elif args.command == 'chart':
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        generate_matplotlib(config, args.output)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
