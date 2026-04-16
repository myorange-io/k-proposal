# HWPX 저수준 XML 구조 참조

> 이 문서는 HWPX 파일의 내부 구조, 네임스페이스, 단위 변환, XML 요소 등 저수준 조작이 필요할 때 참조한다.

## 문서 구조 (ZIP 패키지)

```
template.hwpx (ZIP)
├── mimetype                    ← 반드시 첫 엔트리, ZIP_STORED 압축
├── Contents/content.hpf        ← OPF manifest (이미지 등록 필수)
├── Contents/section0.xml       ← 본문, 표, 이미지(pic), 텍스트
├── Contents/header.xml         ← 스타일(charPr, paraPr), 폰트
├── BinData/                    ← 이미지 파일 (image1.png 등)
├── META-INF/manifest.xml       ← ODF manifest
├── META-INF/container.xml      ← rootfile 경로
├── Preview/                    ← 미리보기
├── version.xml
├── settings.xml                ← 문서 설정
└── (section1.xml, ...)         ← 추가 섹션
```

## XML 네임스페이스 매핑

| 네임스페이스 URI | 표준 프리픽스 | 사용 위치 |
|-----------------|-------------|----------|
| `http://www.hancom.co.kr/hwpml/2011/head` | `hh` | header.xml |
| `http://www.hancom.co.kr/hwpml/2011/core` | `hc` | header.xml, section*.xml |
| `http://www.hancom.co.kr/hwpml/2011/paragraph` | `hp` | header.xml, section*.xml |
| `http://www.hancom.co.kr/hwpml/2011/section` | `hs` | section*.xml |
| `http://www.hancom.co.kr/hwpml/2011/app` | `ha` | 문서 메타 |
| `http://www.hancom.co.kr/hwpml/2016/paragraph` | `hp10` | 2016 확장 |
| `http://www.idpf.org/2007/opf/` | `opf` | manifest |

**⚠️ 중요**: 한글은 `<hs:sec>` 루트에 모든 표준 네임스페이스(ha, hp, hp10, hs, hc, hh, hhs, hm, hpf, dc, opf, ooxmlchart, hwpunitchar, epub, config 등 16개)가 선언되어 있어야 파일을 파싱한다. lxml/ElementTree가 "사용되지 않는" 네임스페이스 선언을 자동 제거하면 파일이 열리지 않는다.

## HWPUNIT 단위 변환

```
1mm ≈ 283.46 HWPUNIT   (7200 HWPUNIT = 1 inch)
1cm = 2835 HWPUNIT
1px ≈ 75 HWPUNIT       (96 dpi 기준)
```

### 주요 변환표

| 항목 | mm | HWPUNIT |
|------|-----|---------|
| A4 너비 | 210 | 59528 |
| A4 높이 | 297 | 84186 |
| 20mm 여백 | 20 | 5669 |
| 15mm 여백 | 15 | 4252 |
| 10mm 여백 | 10 | 2835 |

## header.xml 주요 요소

### 글꼴 정의 (fontfaces)

글꼴은 `<hh:fontface lang="HANGUL|LATIN|...">` 그룹 내에서 id로 참조:

```xml
<hh:fontface lang="HANGUL" fontCnt="8">
  <hh:font id="0" face="함초롬돋움" type="TTF" isEmbedded="0"/>
  <hh:font id="1" face="함초롬바탕" type="TTF" isEmbedded="0"/>
  <hh:font id="2" face="휴먼명조" type="TTF" isEmbedded="0"/>
  <hh:font id="3" face="HY헤드라인M" type="TTF" isEmbedded="0"/>
</hh:fontface>
```

### 글자 속성 (charPr)

```xml
<hh:charPr id="5" height="1600" textColor="#000000" ...>
  <hh:fontRef hangul="3" .../>  <!-- hangul="3" → HY헤드라인M -->
  <hh:bold .../>
  <hh:underline type="BOTTOM" shape="SOLID" color="#000000"/>
</hh:charPr>
```

- `height`: 1/100pt 단위 (1600 = 16pt)
- `textColor`: 글자 색상
- `fontRef hangul="N"`: HANGUL fontface 내 id=N 글꼴 참조

### 문단 속성 (paraPr)

```xml
<hh:paraPr id="28">
  <hh:align horizontal="JUSTIFY" vertical="BASELINE"/>
  <hh:heading type="NONE" idRef="0" level="0"/>
  <hh:margin><hc:intent value="-2606" unit="HWPUNIT"/></hh:margin>
  <hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>
  <hp:spacing before="0" after="0" .../>
</hh:paraPr>
```

### 테두리/배경 (borderFill)

```xml
<hh:borderFill id="9">
  <hh:leftBorder type="SOLID" width="0.12 mm" color="#006699"/>
  <hh:fillBrush>
    <hh:windowBrush faceColor="#193AAA" .../>
  </hh:fillBrush>
</hh:borderFill>
```

## section0.xml 주요 요소

### 페이지 설정

```xml
<hp:pagePr landscape="WIDELY" width="59528" height="84188" gutterType="LEFT_ONLY">
  <hp:margin header="4251" footer="4251" gutter="0"
             left="5669" right="5669" top="4251" bottom="4251"/>
</hp:pagePr>
```

### 문단 (paragraph)

```xml
<hp:p id="..." paraPrIDRef="28" styleIDRef="0" pageBreak="0">
  <hp:run charPrIDRef="5">
    <hp:t>본문 텍스트</hp:t>
  </hp:run>
  <hp:linesegarray/>  <!-- 필수: 없으면 한글이 파일 거부 -->
</hp:p>
```

- `paraPrIDRef`: header.xml의 paraPr id 참조
- `charPrIDRef`: header.xml의 charPr id 참조
- `pageBreak="1"`: 이 문단 앞에서 페이지 나눔

### 테이블

```xml
<hp:tbl ... rowCnt="1" colCnt="3" borderFillIDRef="5">
  <hp:sz width="47688" widthRelTo="ABSOLUTE" height="2832" .../>
  <hp:pos treatAsChar="1" horzAlign="LEFT" .../>
  <hp:tr>
    <hp:tc borderFillIDRef="9">
      <hp:subList vertAlign="CENTER">
        <hp:p paraPrIDRef="3">
          <hp:run charPrIDRef="24"><hp:t>텍스트</hp:t></hp:run>
        </hp:p>
      </hp:subList>
      <hp:cellAddr colAddr="0" rowAddr="0"/>
      <hp:cellSz width="3327" height="2832"/>
    </hp:tc>
  </hp:tr>
</hp:tbl>
```

### 이미지 삽입 (3단계)

**1단계**: content.hpf manifest에 등록
```xml
<opf:item id="image1" href="BinData/image1.png"
          media-type="image/png" isEmbeded="1"/>
```

**2단계**: BinData/ 폴더에 실제 파일 복사

**3단계**: section0.xml에 hp:pic XML 생성
```xml
<hp:p>
  <hp:run>
    <hp:pic id="1" instid="1" ...>
      <hp:offset x="0" y="0"/>
      <hp:orgSz width="..." height="..."/>
      <hp:curSz width="..." height="..."/>
      ...
      <hc:img binaryItemIDRef="image1" bright="0" contrast="0"
              effect="REAL_PIC" alpha="0"/>
    </hp:pic>
  </hp:run>
</hp:p>
```

## 알려진 한계 및 해결책

| 문제 | 원인 | 해결 |
|------|------|------|
| 빈 페이지 표시 | 네임스페이스 프리픽스 ns0:/ns1: 자동 생성 | fix_namespaces 후처리 |
| 글자 겹침 | linesegarray에 기존 줄 레이아웃 데이터 잔존 | diff 기반 linesegarray 빈 태그 교체 |
| 파란색 글자 | 원본 가이드 텍스트 charPrIDRef 유지 | charPrIDRef → 79(검정) 변경 |
| XML 선언 오류 | lxml이 작은따옴표 사용 | 큰따옴표로 정규표현식 치환 |
| ZIP 깨짐 | mimetype이 DEFLATED로 변경 | 원본 ZIP 메타데이터 복원 |
| 파일 미열림 | 네임스페이스 선언 누락 (16개 필수) | register_namespace + fix_namespaces |

## 누름틀(ClickHere) Field API

HWPX에서 누름틀은 사용자 입력 필드로, 한컴 웹 에디터의 `HwpCtrl.GetFieldList()` / `PutFieldText()` API로 프로그래밍 가능하다.

### XML 구조

```xml
<hp:fieldBegin type="CLICK_HERE" name="회사명"
               command="Name:회사명&#0;Guide:회사명을 입력하세요&#0;" .../>
<hp:run charPrIDRef="5">
  <hp:t>여기를 클릭하세요</hp:t>
</hp:run>
<hp:fieldEnd type="CLICK_HERE" .../>
```

- `fieldBegin` / `fieldEnd` 쌍이 한 문단(`<hp:p>`) 내에 존재
- `command` 속성: null-separated `Name:`, `Guide:` 키-값 쌍
- `type`: `CLICK_HERE`, `ClickHere`, 또는 `clickHere` (한컴 버전별 차이)
- 대안 형태: `<hp:ctrl ctrlId="clck">` (구형 HWP 바이너리 변환 시)

### 프로그래밍 접근

| 환경 | API | 비고 |
|------|-----|------|
| hwpx_handler.py | `detect_fields()` / `fill_field(name, value)` | XML 직접 조작 |
| @rhwp/core (WASM) | `getFieldList()` / `setFieldValueByName()` | rhwp hwpctl 호환 |
| 한컴 HwpCtrl | `GetFieldList()` / `PutFieldText()` | ActiveX/JavaScript |

## 폰트 폴백 매핑

한컴 전용 폰트가 없는 환경에서 렌더링/검증할 때 사용하는 오픈소스 대체 폰트:

| 한컴 폰트 | 대체 폰트 (오픈소스) | 유형 |
|-----------|---------------------|------|
| 한컴바탕 / 한양신명조 | Noto Serif KR | 명조(세리프) |
| 한컴돋움 / 한양고딕 | Noto Sans KR | 고딕(산세리프) |
| 함초롬바탕 | Source Serif KR | 명조 |
| 함초롬돋움 | Source Sans KR | 고딕 |
| 휴먼명조 | NanumMyeongjo | 명조 |
| HY헤드라인M | NanumSquareRound Bold | 제목 |
| 한컴 소망M | NanumGothic Bold | 본문 강조 |

> 출처: rhwp 프로젝트의 `fonts.rs` 폰트 로더가 위 매핑을 사용한다.

## HWP 5.0 바이너리 vs HWPX 비교

| 항목 | HWP 5.0 (바이너리) | HWPX (XML) |
|------|-------------------|------------|
| 파일 구조 | OLE2 Compound File (CFBF) | ZIP + XML (OASIS OPF 기반) |
| 파서 필요도 | 바이너리 레코드 파싱 (복잡) | XML 파싱 (표준 도구 사용 가능) |
| 스트림 구조 | FileHeader, DocInfo, BodyText/Section0, BinData 등 | mimetype, Contents/header.xml, section0.xml 등 |
| 한글 지원 | 2002~ 모든 버전 | 2014~ (2021부터 기본 포맷) |
| 프로그래밍 접근 | pyhwp(Python), rhwp(Rust/WASM) | lxml/ElementTree + zipfile, rhwp |
| 제약사항 | 바이너리 구조 변경 위험 높음 | XML 수정 후 ZIP 재패키징 가능 |

`@rhwp/core` WASM 파서는 HWP 5.0 바이너리와 HWPX를 모두 파싱할 수 있어, HWP→HWPX 변환 없이 바이너리 HWP 파일의 내용 검증이 가능하다.

## LINE_SEG 재계산 로드맵

### 현재 워크어라운드

텍스트를 수정하면 기존 `<hp:linesegarray>` 데이터와 실제 텍스트 길이가 불일치하여 글자가 겹치거나 잘린다. 현재 해결책:

1. **diff 기반 빈 태그 교체**: `postprocess_hwpx.py`에서 원본 대비 변경된 단락의 `<hp:linesegarray>` 내용을 비워 한글이 열 때 재계산하도록 강제
2. **단락별 초기화**: `hwpx_handler.py`의 `set_cell_text()`에서 텍스트 변경 시 해당 단락의 linesegarray를 빈 `<hp:linesegarray/>` 태그로 교체

### 한계

- 한글 프로그램이 파일을 열기 전까지 실제 줄 레이아웃을 알 수 없음
- 미리보기(Preview/) 이미지가 실제 내용과 불일치할 수 있음
- 페이지 나눔 위치를 프로그래밍으로 예측 불가

### rhwp v1.0 대기 사항

rhwp 프로젝트 로드맵에 `reflow_line_segs` API가 포함되어 있다. 구현되면:

1. `@rhwp/core`로 수정된 문서를 로드
2. `reflow_line_segs(page_idx)` 호출로 텍스트 레이아웃 재계산
3. 계산된 LINE_SEG 데이터를 HWPX XML에 기록
4. 한글에서 열기 전에도 정확한 줄 레이아웃 보장

> **모니터링**: https://github.com/edwardkim/rhwp/releases 확인.
> 구현 시 `postprocess_hwpx.py`의 diff 기반 lineseg 처리를 rhwp 기반으로 전환한다.

## rhwp 프로젝트 참조

- **GitHub**: https://github.com/edwardkim/rhwp
- **npm**: `@rhwp/core` (WASM 파서/렌더러), `@rhwp/editor` (편집 기능)
- **기능**: HWP 5.0 바이너리 + HWPX 파싱, SVG/HTML/Canvas 렌더링, Field API, hwpctl 호환 레이어
- **활용 위치**: `scripts/validate_rhwp.mjs` (빌드 결과물 WASM 검증)

## 호환성 참고

- **HWPX ↔ HWP**: python-hwpx/lxml은 HWPX만 처리. 레거시 `.hwp`는 `@rhwp/core` 또는 kordoc으로 처리
- **한컴오피스 버전**: HWPX는 2014 이후 지원, 2021년부터 기본 포맷
- **python-hwpx**: HwpxDocument.open()은 복잡한 양식 파싱 실패 가능 → ZIP-level 직접 조작이 안전
- **@rhwp/core**: Node.js WASM 환경에서 HWP/HWPX 파싱+렌더링 검증. `measureTextWidth` 콜백 필요
