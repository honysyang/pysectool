"""打包后端模块测试。"""

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

from pysectool.builder import CythonBuilder, SourcePreparer
from pysectool.utils import BannerLoader


class TestSourcePreparer(unittest.TestCase):
    """测试 SourcePreparer。"""

    def test_prepares_single_file(self) -> None:
        """应正确复制单文件并重命名为 .pyx。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("x = 1\n", encoding="utf-8")

            preparer = SourcePreparer(src, "")
            build_tmp = Path(tmp) / "build"
            src_dir, pyx_files = preparer.prepare(build_tmp)

            self.assertEqual(len(pyx_files), 1)
            self.assertEqual(pyx_files[0].name, "module.pyx")
            self.assertIn("x = 1", pyx_files[0].read_text(encoding="utf-8"))
            self.assertEqual(src_dir.name, "src")

    def test_inserts_banner(self) -> None:
        """应在文件开头插入 banner。"""
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("print('Hello')\n", encoding="utf-8")
            src = Path(tmp) / "module.py"
            src.write_text("x = 1\n", encoding="utf-8")

            preparer = SourcePreparer(src, BannerLoader(banner).load())
            build_tmp = Path(tmp) / "build"
            _, pyx_files = preparer.prepare(build_tmp)

            content = pyx_files[0].read_text(encoding="utf-8")
            self.assertIn("print('Hello')", content)
            self.assertIn("x = 1", content)
            self.assertLess(content.index("print('Hello')"), content.index("x = 1"))

    def test_prepares_directory(self) -> None:
        """应正确处理目录下的多个 Python 文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "core.py").write_text("def run(): pass\n", encoding="utf-8")

            preparer = SourcePreparer(pkg, "")
            build_tmp = Path(tmp) / "build"
            _, pyx_files = preparer.prepare(build_tmp)

            self.assertEqual(len(pyx_files), 2)
            self.assertTrue(any(p.name == "__init__.pyx" for p in pyx_files))
            self.assertTrue(any(p.name == "core.pyx" for p in pyx_files))


class TestCythonBuilder(unittest.TestCase):
    """测试 CythonBuilder。"""

    def test_generate_setup_is_valid_python(self) -> None:
        """生成的 setup.py 应为合法 Python 代码。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("def hello(): return 42\n", encoding="utf-8")
            builder = CythonBuilder(src, Path(tmp), optimize=True, banner="")

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                src_dir, pyx_files = SourcePreparer(src, "").prepare(build_path)
                setup_py = builder.generate_setup(src_dir, pyx_files, "module", True)

                tree = ast.parse(setup_py.read_text(encoding="utf-8"))
                self.assertIsInstance(tree, ast.Module)

    def test_setup_contains_module_literal(self) -> None:
        """生成的 setup.py 应包含正确的模块名与源文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("def hello(): return 42\n", encoding="utf-8")
            builder = CythonBuilder(src, Path(tmp), optimize=True, banner="")

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                src_dir, pyx_files = SourcePreparer(src, "").prepare(build_path)
                setup_py = builder.generate_setup(src_dir, pyx_files, "module", True)

                text = setup_py.read_text(encoding="utf-8")
                self.assertIn("{'name': 'module', 'source': 'module.pyx'}", text)

    def test_package_init_extension_name(self) -> None:
        """__init__.py 对应的 Extension 名应为 pkg.__init__。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "core.py").write_text("def run(): pass\n", encoding="utf-8")
            builder = CythonBuilder(pkg, Path(tmp), optimize=True, banner="")

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                src_dir, pyx_files = SourcePreparer(pkg, "").prepare(build_path)
                setup_py = builder.generate_setup(src_dir, pyx_files, "mypkg", True)

                text = setup_py.read_text(encoding="utf-8")
                self.assertIn(
                    "{'name': 'mypkg.__init__', 'source': 'mypkg/__init__.pyx'}", text
                )
                self.assertIn("{'name': 'mypkg.core', 'source': 'mypkg/core.pyx'}", text)


@unittest.skipUnless(importlib.util.find_spec("Cython") is not None, "需要安装 Cython")
class TestCythonBuilderIntegration(unittest.TestCase):
    """CythonBuilder 集成测试（需要 Cython）。"""

    def test_build_copies_data_files(self) -> None:
        """打包目录时应自动复制数据文件到输出目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("__version__ = '1.0'\n", encoding="utf-8")
            (pkg / "data").mkdir()
            (pkg / "data" / "config.json").write_text('{"key": "value"}', encoding="utf-8")

            output_dir = Path(tmp) / "dist"
            builder = CythonBuilder(pkg, output_dir, optimize=True, banner="")
            builder.build()

            copied_data = output_dir / "mypkg" / "data" / "config.json"
            self.assertTrue(copied_data.exists())
            self.assertEqual(
                copied_data.read_text(encoding="utf-8"),
                '{"key": "value"}',
            )

    def test_build_respects_exclude_data(self) -> None:
        """--exclude-data 应排除指定数据文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "keep.json").write_text("{}", encoding="utf-8")
            (pkg / "skip.log").write_text("log", encoding="utf-8")

            output_dir = Path(tmp) / "dist"
            builder = CythonBuilder(
                pkg, output_dir, optimize=True, banner="", exclude_data=["*.log"]
            )
            builder.build()

            self.assertTrue((output_dir / "mypkg" / "keep.json").exists())
            self.assertFalse((output_dir / "mypkg" / "skip.log").exists())
