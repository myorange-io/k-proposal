#!/usr/bin/env node
/**
 * @rhwp/core WASM 기반 HWPX/HWP 검증 스크립트
 *
 * 생성된 HWPX 파일을 rhwp WASM 파서로 로드 + 렌더링하여
 * 한글 뷰어에서 열리지 않는 구조적 오류를 빌드 시점에 검출한다.
 *
 * 사용법:
 *   node scripts/validate_rhwp.mjs <파일.hwpx>
 *   node scripts/validate_rhwp.mjs <파일.hwpx> --json
 */

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const filePath = args.find(a => !a.startsWith('--'));

if (!filePath) {
  console.error('Usage: node scripts/validate_rhwp.mjs <file.hwpx|file.hwp> [--json]');
  process.exit(2);
}

const absPath = resolve(filePath);

// Node.js 환경에서 measureTextWidth 폴백: 고정폭 근사치
// 실제 폰트 메트릭 없이도 파싱/렌더링 가능 여부 판별에 충분
globalThis.measureTextWidth = (font, text) => {
  const match = font.match(/(\d+(?:\.\d+)?)\s*px/);
  const fontSize = match ? parseFloat(match[1]) : 16;
  let width = 0;
  for (const ch of text) {
    const code = ch.codePointAt(0);
    // CJK 문자: 전각 폭, 그 외: 반각 폭
    const isCjk = (code >= 0x3000 && code <= 0x9FFF) ||
                  (code >= 0xAC00 && code <= 0xD7AF) ||
                  (code >= 0xF900 && code <= 0xFAFF);
    width += isCjk ? fontSize : fontSize * 0.5;
  }
  return width;
};

async function validate() {
  const result = { ok: false, file: absPath, pages: 0, svg_length: 0, errors: [] };

  try {
    const { default: init, HwpDocument } = await import('@rhwp/core');

    const wasmPath = new URL(
      '../node_modules/@rhwp/core/rhwp_bg.wasm',
      import.meta.url,
    );
    await init({ module_or_path: readFileSync(fileURLToPath(wasmPath)) });

    const fileData = readFileSync(absPath);
    const doc = new HwpDocument(new Uint8Array(fileData));

    result.pages = doc.pageCount();
    if (result.pages === 0) {
      result.errors.push('페이지 수 0 — 파싱은 성공했으나 빈 문서');
    }

    if (result.pages > 0) {
      try {
        const svg = doc.renderPageSvg(0);
        result.svg_length = svg.length;
        if (svg.length < 100) {
          result.errors.push('첫 페이지 SVG 길이 < 100 — 렌더링 실패 의심');
        }
      } catch (renderErr) {
        result.errors.push(`렌더링 실패: ${renderErr.message || renderErr}`);
      }
    }

    result.ok = result.errors.length === 0;
  } catch (err) {
    result.errors.push(`파싱 실패: ${err.message || err}`);
  }

  if (jsonMode) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const icon = result.ok ? '✅' : '❌';
    console.log(`${icon} rhwp 검증: ${result.file}`);
    console.log(`   페이지: ${result.pages}, SVG 길이: ${result.svg_length}`);
    if (result.errors.length > 0) {
      for (const e of result.errors) {
        console.log(`   ❌ ${e}`);
      }
    }
  }

  return result.ok ? 0 : 1;
}

process.exit(await validate());
