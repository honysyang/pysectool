"""通用工具函数。"""

from __future__ import annotations

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
