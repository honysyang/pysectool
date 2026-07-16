"""依赖分析模块。"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Iterable

from pysectool.utils import collect_python_files


class DependencyAnalyzer:
    """基于 AST 的 Python 依赖分析器。"""

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def collect_python_files(self) -> list[Path]:
        """收集待分析的 Python 文件。"""
        return collect_python_files(self.source_path)

    def _extract_imports(self, py_file: Path) -> set[str]:
        """从单个 Python 文件中提取顶层导入模块名。"""
        dependencies: set[str] = set()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            return dependencies

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                dependencies.add(node.module.split(".")[0])

        return dependencies

    def analyze(self) -> set[str]:
        """分析所有源文件的第三方依赖。"""
        dependencies: set[str] = set()
        for py_file in self.collect_python_files():
            dependencies.update(self._extract_imports(py_file))

        stdlib_modules = set(sys.stdlib_module_names)
        project_names = {self.source_path.name, self.source_path.stem}
        return {
            dep
            for dep in dependencies
            if dep not in stdlib_modules and dep not in project_names
        }

    def locate_dependency(
        self, dep: str,
    ) -> tuple[Path, bool] | None:
        """定位依赖在文件系统中的位置。

        Returns:
            (origin_path, is_package) 或 None（找不到时）。
        """
        try:
            spec = importlib.util.find_spec(dep)
        except (ImportError, OSError, ValueError):
            return None

        if not spec or not spec.origin:
            return None

        origin = Path(spec.origin)
        if not origin.is_file():
            return None

        is_package = origin.name == "__init__.py"
        return origin, is_package


def collect_dependency_files(dependencies: Iterable[str]) -> list[tuple[Path, str]]:
    """收集依赖文件，返回 (源路径, zip 内目标路径) 列表。"""
    files: list[tuple[Path, str]] = []
    excluded_suffixes = {".pyc", ".pyo"}
    excluded_dirs = {"__pycache__", "tests", "test", "docs"}
    analyzer = DependencyAnalyzer(Path("."))

    for dep in dependencies:
        located = analyzer.locate_dependency(dep)
        if located is None:
            print(f"  警告: 无法定位依赖 {dep}，跳过")
            continue

        origin, is_package = located
        if is_package:
            package_dir = origin.parent
            for item in package_dir.rglob("*"):
                if not item.is_file():
                    continue
                if item.suffix in excluded_suffixes:
                    continue
                if any(part in excluded_dirs for part in item.relative_to(package_dir).parts):
                    continue
                rel = f"deps/{dep}/{item.relative_to(package_dir)}"
                files.append((item, rel))
        elif origin.suffix in {".py", ".so", ".pyd"}:
            files.append((origin, f"deps/{origin.name}"))
        else:
            print(f"  警告: 依赖 {dep} 类型未知，跳过")

    return files
