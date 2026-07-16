"""依赖分析模块测试。"""

import tempfile
import unittest
from pathlib import Path

from pysectool.deps import DependencyAnalyzer, collect_dependency_files


class TestDependencyAnalyzer(unittest.TestCase):
    """测试 DependencyAnalyzer。"""

    def test_extracts_third_party_imports(self) -> None:
        """应正确提取第三方依赖并排除标准库。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(
                "import os\nimport sys\nimport requests\nfrom flask import Flask\n",
                encoding="utf-8",
            )
            analyzer = DependencyAnalyzer(src)
            deps = analyzer.analyze()
            self.assertIn("requests", deps)
            self.assertIn("flask", deps)
            self.assertNotIn("os", deps)
            self.assertNotIn("sys", deps)

    def test_empty_for_stdlib_only(self) -> None:
        """仅导入标准库时应返回空集合。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text("import os\nimport sys\n", encoding="utf-8")
            analyzer = DependencyAnalyzer(src)
            self.assertEqual(analyzer.analyze(), set())

    def test_handles_directory(self) -> None:
        """应能分析整个目录下的多个文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "a.py").write_text("import requests\n", encoding="utf-8")
            (pkg / "b.py").write_text("from flask import Flask\n", encoding="utf-8")
            analyzer = DependencyAnalyzer(pkg)
            deps = analyzer.analyze()
            self.assertIn("requests", deps)
            self.assertIn("flask", deps)


class TestCollectDependencyFiles(unittest.TestCase):
    """测试 collect_dependency_files。"""

    def test_collects_package_files(self) -> None:
        """应收集整个包目录下的文件。"""
        files = collect_dependency_files(["packaging"])
        # 至少包含 __init__.py 和一个子模块
        paths = [dst for _, dst in files]
        self.assertTrue(any("deps/packaging/__init__.py" in p for p in paths))
        self.assertTrue(any("deps/packaging/version.py" in p for p in paths))

    def test_ignores_pycache(self) -> None:
        """应排除 __pycache__ 目录。"""
        files = collect_dependency_files(["packaging"])
        paths = [dst for _, dst in files]
        self.assertFalse(any("__pycache__" in p for p in paths))

    def test_unknown_dependency_skipped(self) -> None:
        """找不到的依赖应被跳过而不报错。"""
        files = collect_dependency_files(["this_module_definitely_does_not_exist"])
        self.assertEqual(files, [])
