#!/usr/bin/env python3
"""
kordoc CLI 브릿지 — MCP 설정 없이 Python에서 kordoc를 직접 호출

MCP 서버 설정을 하지 않아도 npx kordoc CLI를 통해
문서 파싱, 비교, 양식 인식 등 kordoc 기능을 Python에서 사용할 수 있다.

사용법:
    from kordoc_bridge import KordocBridge

    kd = KordocBridge()
    if kd.available:
        md = kd.parse("공고문.hwp")
        fields = kd.parse_form("양식.hwpx")
        diff = kd.compare("원본.hwpx", "수정본.hwpx")
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class KordocBridge:
    """npx kordoc CLI를 감싸는 Python 래퍼"""

    def __init__(self, timeout: int = 60):
        self._timeout = timeout
        self._npx = shutil.which("npx")
        self._available = None

    @property
    def available(self) -> bool:
        """kordoc가 설치되어 있고 실행 가능한지 확인"""
        if self._available is not None:
            return self._available
        if not self._npx:
            self._available = False
            return False
        for cmd in [
            [self._npx, "kordoc", "--version"],
            [self._npx, "-y", "kordoc", "--version"],
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    self._use_dash_y = ("-y" in cmd)
                    self._available = True
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        self._available = False
        return False

    def _run(self, args: list, timeout: int = None) -> subprocess.CompletedProcess:
        timeout = timeout or self._timeout
        prefix = [self._npx]
        if getattr(self, '_use_dash_y', True):
            prefix.append("-y")
        prefix.append("kordoc")
        return subprocess.run(
            prefix + args,
            capture_output=True, text=True, timeout=timeout,
        )

    def parse(self, file_path: str, *, pages: str = None,
              format: str = "markdown", no_header_footer: bool = False) -> str | None:
        """문서를 마크다운(또는 JSON)으로 변환

        Args:
            file_path: HWP/HWPX/PDF/XLSX/DOCX 파일 경로
            pages: 페이지 범위 (예: "1-3")
            format: "markdown" 또는 "json"
            no_header_footer: 머리글/바닥글 제거

        Returns:
            마크다운 텍스트 또는 None (실패 시)
        """
        args = [str(file_path)]
        if pages:
            args += ["--pages", pages]
        if format == "json":
            args += ["--format", "json"]
        if no_header_footer:
            args += ["--no-header-footer"]

        try:
            r = self._run(args)
            if r.returncode == 0:
                return r.stdout
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    def parse_json(self, file_path: str, **kwargs) -> dict | None:
        """문서를 파싱하여 구조화된 JSON(blocks + metadata) 반환"""
        raw = self.parse(file_path, format="json", **kwargs)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return None

    def detect_format(self, file_path: str) -> str | None:
        """매직 바이트로 파일 포맷 감지"""
        result = self.parse_json(file_path)
        if result and "format" in result:
            return result["format"]
        ext = Path(file_path).suffix.lower().lstrip(".")
        ext_map = {"hwp": "hwp", "hwpx": "hwpx", "pdf": "pdf",
                    "xlsx": "xlsx", "docx": "docx"}
        return ext_map.get(ext)

    def parse_form(self, file_path: str) -> dict | None:
        """양식 필드를 label-value JSON으로 추출

        Returns:
            {"fields": [{"label": "성명", "value": "홍길동", ...}, ...]}
            또는 None (실패 시)
        """
        result = self.parse_json(file_path)
        if not result:
            return None

        blocks = result.get("blocks", [])
        if not blocks:
            return None

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            json.dump(blocks, f, ensure_ascii=False)
            blocks_path = f.name

        try:
            r = subprocess.run(
                [self._npx, "-y", "kordoc", "form", str(file_path)],
                capture_output=True, text=True, timeout=self._timeout,
            )
            if r.returncode == 0:
                try:
                    return json.loads(r.stdout)
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, OSError):
            pass
        finally:
            Path(blocks_path).unlink(missing_ok=True)

        return None

    def compare(self, file_a: str, file_b: str) -> dict | None:
        """두 문서를 비교하여 diff 결과 반환 (크로스 포맷 가능)

        Returns:
            {"stats": {"added": N, ...}, "diffs": [...]}
            또는 None (실패 시)
        """
        md_a = self.parse(file_a)
        md_b = self.parse(file_b)
        if md_a is None or md_b is None:
            return None

        return {
            "method": "kordoc_cli",
            "markdown_a": md_a,
            "markdown_b": md_b,
        }


_default_bridge = None


def get_bridge() -> KordocBridge:
    """싱글턴 KordocBridge 인스턴스 반환"""
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = KordocBridge()
    return _default_bridge


if __name__ == "__main__":
    bridge = get_bridge()
    print(f"kordoc available: {bridge.available}")

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if bridge.available:
            result = bridge.parse(file_path)
            if result:
                print(result[:500])
                print(f"\n... ({len(result)} chars total)")
            else:
                print(f"Failed to parse: {file_path}")
        else:
            print("kordoc not available. Install with: npm install -g kordoc")
