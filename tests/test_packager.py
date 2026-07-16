"""打包编排器集成测试。"""

import tempfile
import unittest
from pathlib import Path

from pysectool import packager
from pysectool.exceptions import PythonPackagerError
from pysectool.packager import PythonPackager


class TestModuleImport(unittest.TestCase):
    """验证核心模块可以正常导入。"""

    def test_packager_module_imports(self) -> None:
        """pysectool.packager 应暴露 PythonPackager。"""
        self.assertTrue(hasattr(packager, "PythonPackager"))


class TestValidation(unittest.TestCase):
    """测试参数校验。"""

    def test_missing_source_raises(self) -> None:
        """源路径不存在时应抛出异常。"""
        with self.assertRaises(PythonPackagerError):
            PythonPackager("/nonexistent/path/file.py")

    def test_unsupported_format_raises(self) -> None:
        """不支持的格式应抛出异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.py"
            src.write_text("pass", encoding="utf-8")
            with self.assertRaises(PythonPackagerError):
                PythonPackager(src, package_format="zip")

    def test_exe_with_directory_raises(self) -> None:
        """exe 格式不支持目录入口。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            with self.assertRaises(PythonPackagerError):
                PythonPackager(pkg, package_format="exe")

    def test_non_python_file_raises(self) -> None:
        """非 .py 文件应抛出异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.txt"
            src.write_text("pass", encoding="utf-8")
            with self.assertRaises(PythonPackagerError):
                PythonPackager(src)


class TestOrchestration(unittest.TestCase):
    """测试打包编排流程。"""

    def test_dependency_analysis_step(self) -> None:
        """analyze_dependencies 应返回第三方依赖集合。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text("import requests\n", encoding="utf-8")
            packager_instance = PythonPackager(src, output_dir=tmp, package_format="so")
            deps = packager_instance.analyze_dependencies()
            self.assertIn("requests", deps)

    def test_invalid_banner_raises(self) -> None:
        """无效 banner 应在构造时抛出异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("def broken(\n", encoding="utf-8")
            src = Path(tmp) / "module.py"
            src.write_text("x = 1\n", encoding="utf-8")
            with self.assertRaises(PythonPackagerError):
                PythonPackager(src, output_dir=tmp, package_format="so", banner_file=banner)
