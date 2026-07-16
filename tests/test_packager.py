"""打包编排器集成测试。"""

import importlib
import importlib.util
import sys
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

    def test_traversal_source_rejected(self) -> None:
        """源路径包含目录穿越时应抛出异常。"""
        with self.assertRaises(PythonPackagerError):
            PythonPackager("../../etc/passwd")


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


@unittest.skipUnless(importlib.util.find_spec("Cython") is not None, "需要安装 Cython")
class TestPackagerWithDataFiles(unittest.TestCase):
    """带数据文件的项目打包集成测试。"""

    def test_directory_build_keeps_data_files(self) -> None:
        """目录打包后数据文件应保留并可读取。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "myproject"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("__version__ = '1.0'\n", encoding="utf-8")
            (pkg / "core.py").write_text(
                "from pathlib import Path\n"
                "def read_config():\n"
                "    return (Path(__file__).parent / 'data' / 'config.json').read_text()\n",
                encoding="utf-8",
            )
            (pkg / "data").mkdir()
            (pkg / "data" / "config.json").write_text('{"env": "prod"}', encoding="utf-8")

            output_dir = Path(tmp) / "dist"
            packager_instance = PythonPackager(
                pkg, output_dir=output_dir, package_format="so"
            )
            packager_instance.run()

            sys.path.insert(0, str(output_dir))
            core = importlib.import_module("myproject.core")  # pylint: disable=import-error

            self.assertEqual(core.read_config(), '{"env": "prod"}')


@unittest.skipUnless(importlib.util.find_spec("Cython") is not None, "需要安装 Cython")
class TestPackagerStability(unittest.TestCase):
    """打包稳定性测试。"""

    def test_clean_clears_output_dir(self) -> None:
        """--clean 应在打包前清空输出目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("__version__ = '1.0'\n", encoding="utf-8")

            output_dir = Path(tmp) / "dist"
            output_dir.mkdir()
            (output_dir / "old_file.txt").write_text("old", encoding="utf-8")
            (output_dir / "old_dir").mkdir()

            packager_instance = PythonPackager(
                pkg, output_dir=output_dir, package_format="so", clean=True
            )
            packager_instance.run()

            self.assertFalse((output_dir / "old_file.txt").exists())
            self.assertFalse((output_dir / "old_dir").exists())
            self.assertTrue(
                list(output_dir.glob("pkg/*.so")) or list(output_dir.glob("pkg/*.pyd"))
            )

    def test_failed_build_does_not_pollute_output(self) -> None:
        """构建失败时不应污染输出目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bad.py"
            # 写入 Cython 无法编译的内容
            src.write_text("def foo( -> pass\n", encoding="utf-8")
            output_dir = Path(tmp) / "dist"

            packager_instance = PythonPackager(
                src, output_dir=output_dir, package_format="so"
            )
            with self.assertRaises(PythonPackagerError):
                packager_instance.run()

            # 输出目录应不存在或为空
            if output_dir.exists():
                self.assertEqual(list(output_dir.iterdir()), [])
