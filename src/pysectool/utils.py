"""通用工具函数。"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from pysectool.exceptions import PythonPackagerError


def collect_python_files(path: Path) -> list[Path]:
    """收集路径下的所有 Python 文件。"""
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.py"))


def cython_module_name(pyx_file: Path, base_dir: Path) -> str:
    """根据 pyx 相对路径生成 Cython Extension 名称。

    对 __init__.pyx 使用 pkg.__init__ 作为 Extension 名，可让 Cython 直接生成
    pkg/__init__.so，从而被 Python 识别为正常的包。
    """
    rel = pyx_file.relative_to(base_dir)
    return ".".join(rel.with_suffix("").parts)


class BannerLoader:
    """banner 文件加载与校验。"""

    def __init__(self, banner_file: Path | None) -> None:
        self.banner_file = banner_file

    def load(self) -> str:
        """读取 banner 文件并校验其是否为可执行 Python 代码。"""
        if not self.banner_file or not self.banner_file.exists():
            return ""

        try:
            banner = self.banner_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise PythonPackagerError(f"读取 banner 文件失败: {exc}") from exc

        if not banner.strip():
            return ""

        try:
            compile(banner, self.banner_file.name, "exec")
        except SyntaxError as exc:
            raise PythonPackagerError(f"banner 文件包含无效 Python 语法: {exc}") from exc

        return f"\n{banner}\n"


class DataCollector:
    """收集项目目录中的数据文件/资源文件。"""

    DEFAULT_EXCLUDES: tuple[str, ...] = (
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".git*",
        ".env*",
        "*.secret",
        "secrets.*",
        "*.egg-info",
        ".DS_Store",
        "Thumbs.db",
    )

    def __init__(
        self, source_path: Path, exclude_patterns: list[str] | None = None
    ) -> None:
        self.source_path = source_path
        self.exclude_patterns = list(exclude_patterns or [])

    def _is_excluded(self, rel_path: Path) -> bool:
        """判断相对路径是否匹配排除规则。"""
        parts = rel_path.parts
        str_path = str(rel_path)
        name = rel_path.name

        for pattern in (*self.DEFAULT_EXCLUDES, *self.exclude_patterns):
            # 匹配目录名/文件名，或任意层级的 glob
            if any(fnmatch.fnmatch(part, pattern) for part in parts):
                return True
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(str_path, pattern):
                return True

        return False

    def collect(self) -> list[tuple[Path, Path]]:
        """收集数据文件。

        Returns:
            (源文件绝对路径, 相对于 source_path 的相对路径) 列表。
        """
        if self.source_path.is_file():
            return []

        files: list[tuple[Path, Path]] = []
        for item in sorted(self.source_path.rglob("*")):
            if not item.is_file():
                continue

            rel = item.relative_to(self.source_path)

            # 跳过 Python 源码（这些由 Cython/PyInstaller 处理）
            if rel.suffix.lower() == ".py":
                continue

            if self._is_excluded(rel):
                continue

            files.append((item, rel))

        return files
