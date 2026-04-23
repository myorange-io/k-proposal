#!/usr/bin/env node
/**
 * @rhwp/core 기반 HWP/HWPX 스타일 카탈로그 추출기
 *
 * 입력 파일을 순회하며:
 * - 본문/표 셀에서 사용된 charShape(글자 모양) 패턴을 모두 수집
 * - charShapeId별 props + 사용 빈도 + 위치 샘플 + 셀 매핑
 * - 휴리스틱 역할(suggestedRoles): bodyDefault / bodyEmphasis / heading1 / heading2 / tableHeader
 *
 * 사용법:
 *   node scripts/extract_style_catalog.mjs <file.hwp|hwpx> [--out path/to/catalog.json]
 *   node scripts/extract_style_catalog.mjs <file> --json   # stdout으로 JSON
 *
 * 출력 카탈로그 형식 (proposal-analyze가 _workspace/00_input/style_catalog.json으로 저장):
 *   {
 *     "meta": { pages, sections, totalBodyParas, totalTables, totalCells, totalCellParas },
 *     "charShapeCatalog": [{ id, fontFamily, fontSize, bold, italic, underline,
 *                            textColor, bodyCount, cellCount, samples[] }],
 *     "cellStyles": [{ table_index, row, col, cell_para_idx, charShapeId, sampleText }],
 *     "suggestedRoles": { bodyDefault, bodyEmphasis, heading1, heading2, tableHeader, tableBody }
 *   }
 */
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { resolve } from 'path';

// canvas measureText 폴백 (Node 환경, 정확도 낮아도 파싱엔 충분)
globalThis.measureTextWidth = (font, text) => {
  const m = font.match(/(\d+(?:\.\d+)?)\s*px/);
  const fs = m ? parseFloat(m[1]) : 16;
  let w = 0;
  for (const ch of text) {
    const c = ch.codePointAt(0);
    const cjk = (c >= 0x3000 && c <= 0x9FFF) || (c >= 0xAC00 && c <= 0xD7AF) || (c >= 0xF900 && c <= 0xFAFF);
    w += cjk ? fs : fs * 0.5;
  }
  return w;
};

const args = process.argv.slice(2);
const filePath = args.find(a => !a.startsWith('--'));
const outIdx = args.indexOf('--out');
const outPath = outIdx >= 0 ? args[outIdx + 1] : null;
const jsonStdout = args.includes('--json');

if (!filePath) {
  console.error('usage: node extract_style_catalog.mjs <file.hwp|hwpx> [--out path] [--json]');
  process.exit(2);
}

const { default: init, HwpDocument } = await import('@rhwp/core');
const wasmPath = new URL('../node_modules/@rhwp/core/rhwp_bg.wasm', import.meta.url);
await init({ module_or_path: readFileSync(fileURLToPath(wasmPath)) });

const doc = new HwpDocument(new Uint8Array(readFileSync(resolve(filePath))));
const pages = doc.pageCount();
const secCount = doc.getSectionCount();

// charShapeId → 통합 패턴 (본문/셀 합산)
const byId = new Map();
function recordChar(propsJson, sampleText, location, source /* 'body'|'cell' */) {
  let props;
  try { props = JSON.parse(propsJson); } catch { return null; }
  const id = props.charShapeId;
  if (id == null) return null;
  if (!byId.has(id)) {
    byId.set(id, {
      id,
      fontFamily: props.fontFamily,
      fontSize: props.fontSize,
      bold: !!props.bold,
      italic: !!props.italic,
      underline: !!props.underline,
      textColor: props.textColor,
      bodyCount: 0,
      cellCount: 0,
      samples: [],
    });
  }
  const e = byId.get(id);
  if (source === 'body') e.bodyCount++; else e.cellCount++;
  if (e.samples.length < 5 && sampleText && sampleText.trim()) {
    e.samples.push({ source, loc: location, text: sampleText.slice(0, 80) });
  }
  return id;
}

const cellStyles = [];  // [{ table_index, row, col, cell_para_idx, charShapeId, sampleText }]

let totalBodyParas = 0, totalTables = 0, totalCells = 0, totalCellParas = 0;
let tableIndex = -1;

for (let sec = 0; sec < secCount; sec++) {
  let pCount;
  try { pCount = doc.getParagraphCount(sec); } catch { continue; }
  for (let p = 0; p < pCount; p++) {
    totalBodyParas++;
    let txt = '';
    try { txt = doc.getTextRange(sec, p, 0, 200) || ''; } catch {}
    try {
      const cp = doc.getCharPropertiesAt(sec, p, 0);
      recordChar(cp, txt, `body s${sec}/p${p}`, 'body');
    } catch {}

    let positionsRaw;
    try { positionsRaw = doc.getControlTextPositions(sec, p); } catch { continue; }
    let positions;
    try { positions = JSON.parse(positionsRaw); } catch { continue; }
    if (!Array.isArray(positions) || positions.length === 0) continue;

    for (let ctrlIdx = 0; ctrlIdx < positions.length; ctrlIdx++) {
      let dims;
      try { dims = JSON.parse(doc.getTableDimensions(sec, p, ctrlIdx)); } catch { continue; }
      if (!dims || dims.cellCount == null) continue;
      tableIndex++;
      totalTables++;
      const cols = dims.colCount;
      for (let cell = 0; cell < dims.cellCount; cell++) {
        totalCells++;
        const row = Math.floor(cell / cols);
        const col = cell % cols;
        let cpc;
        try { cpc = doc.getCellParagraphCount(sec, p, ctrlIdx, cell); } catch { continue; }
        for (let cpi = 0; cpi < cpc; cpi++) {
          totalCellParas++;
          let cellText = '';
          try { cellText = doc.getTextInCell(sec, p, ctrlIdx, cell, cpi, 0, 200) || ''; } catch {}
          let cellCharId = null;
          try {
            const ccp = doc.getCellCharPropertiesAt(sec, p, ctrlIdx, cell, cpi, 0);
            cellCharId = recordChar(ccp, cellText, `t${tableIndex}/r${row}/c${col}/cp${cpi}`, 'cell');
          } catch {}
          if (cellCharId != null) {
            cellStyles.push({
              section: sec,
              parent_para_idx: p,
              control_idx: ctrlIdx,
              table_index: tableIndex,
              cell_idx: cell,
              row, col,
              cell_para_idx: cpi,
              charShapeId: cellCharId,
              sampleText: cellText.slice(0, 60),
            });
          }
        }
      }
    }
  }
}

// 휴리스틱: 카탈로그에서 역할 자동 추론
function suggestRoles(catalog) {
  const list = [...catalog.values()];
  const total = (e) => e.bodyCount + e.cellCount;
  // 본문 기본: 가장 많이 등장하는 일반(non-bold) 본문 패턴 (bodyCount > 0)
  const bodyDefault = list
    .filter(e => !e.bold && e.bodyCount > 0)
    .sort((a, b) => b.bodyCount - a.bodyCount)[0]?.id;
  // 본문 강조: 같은 폰트/크기의 bold 변형 (bodyCount > 0, bold)
  const ref = list.find(e => e.id === bodyDefault);
  const bodyEmphasis = ref ? list
    .filter(e => e.bold && e.fontFamily === ref.fontFamily && e.fontSize === ref.fontSize && e.bodyCount > 0)
    .sort((a, b) => b.bodyCount - a.bodyCount)[0]?.id : undefined;
  // 헤딩1: 가장 큰 폰트 + 본문에 등장
  const headings = list
    .filter(e => e.bodyCount > 0)
    .sort((a, b) => b.fontSize - a.fontSize);
  const heading1 = headings[0]?.id;
  const heading2 = headings.find(e => e.id !== heading1 && e.fontSize >= (ref?.fontSize ?? 1200) + 200)?.id;
  // 표 머리글: bold + cellCount > 0 + 셀에서 가장 많이 등장
  const tableHeader = list
    .filter(e => e.bold && e.cellCount > 0)
    .sort((a, b) => b.cellCount - a.cellCount)[0]?.id;
  // 표 본문: non-bold + cellCount > 0 + 셀에서 가장 많이 등장
  const tableBody = list
    .filter(e => !e.bold && e.cellCount > 0)
    .sort((a, b) => b.cellCount - a.cellCount)[0]?.id;
  return { bodyDefault, bodyEmphasis, heading1, heading2, tableHeader, tableBody };
}

const charShapeCatalog = [...byId.values()].sort((a, b) =>
  (b.bodyCount + b.cellCount) - (a.bodyCount + a.cellCount)
);
const suggestedRoles = suggestRoles(byId);

const catalog = {
  meta: { source: filePath, pages, sections: secCount, totalBodyParas, totalTables, totalCells, totalCellParas },
  charShapeCatalog,
  cellStyles,
  suggestedRoles,
};

const json = JSON.stringify(catalog, null, 2);

if (jsonStdout) {
  process.stdout.write(json);
} else {
  const dest = outPath || '/tmp/style_catalog.json';
  writeFileSync(resolve(dest), json);
  console.error(`wrote ${dest} — ${charShapeCatalog.length} charShapes, ${cellStyles.length} cell entries`);
  console.error(`suggested roles: ${JSON.stringify(suggestedRoles)}`);
  console.error(`top-5 charShapes:`);
  for (const e of charShapeCatalog.slice(0, 5)) {
    const flags = [e.bold && 'B', e.italic && 'I', e.underline && 'U'].filter(Boolean).join('') || '—';
    console.error(`  cs=${String(e.id).padStart(3)}  ${e.fontFamily.padEnd(10)} ${(e.fontSize/100).toFixed(0)}pt ${flags.padStart(3)}  body=${e.bodyCount} cell=${e.cellCount}`);
  }
}
