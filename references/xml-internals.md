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

## 호환성 참고

- **HWPX ↔ HWP**: python-hwpx/lxml은 HWPX만 처리. 레거시 `.hwp`는 별도 도구 필요
- **한컴오피스 버전**: HWPX는 2014 이후 지원, 2021년부터 기본 포맷
- **python-hwpx**: HwpxDocument.open()은 복잡한 양식 파싱 실패 가능 → ZIP-level 직접 조작이 안전
