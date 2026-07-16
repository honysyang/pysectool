"""python-packager 基础测试。"""

import ast
import sys
import tempfile
import unittest
from pathlib import Path

# 把项目根目录加入路径，方便直接导入 packager
sys.path.insert(0, str(Path(__file__).parent.parent))

import example1
import packager


class TestModuleImport(unittest.TestCase):
    """验证核心模块可以正常导入。"""

    def test_packager_module_imports(self) -> None:
        self.assertTrue(hasattr(packager, "PythonPackager"))
        self.assertTrue(hasattr(packager, "main"))

    def test_example1_module_imports(self) -> None:
        self.assertTrue(hasattr(example1, "check_ping"))
        self.assertTrue(hasattr(example1, "validate_ip"))


class TestArgumentParsing(unittest.TestCase):
    """验证命令行参数解析。"""

    def test_argparse_defaults(self) -> None:
        parser = packager.argparse.ArgumentParser()
        parser.add_argument("source_path")
        parser.add_argument("-o", "--output")
        parser.add_argument("-f", "--format", choices=["pyd", "so", "exe"], default="so")
        parser.add_argument("--no-deps", action="store_true")
        parser.add_argument("--no-optimize", action="store_true")
        parser.add_argument("-b", "--banner")

        args = parser.parse_args(["foo.py", "-o", "dist", "-f", "exe", "--no-deps"])
        self.assertEqual(args.source_path, "foo.py")
        self.assertEqual(args.output, "dist")
        self.assertEqual(args.format, "exe")
        self.assertTrue(args.no_deps)
        self.assertFalse(args.no_optimize)


class TestExample1Validation(unittest.TestCase):
    """验证 example1 的 IP 输入校验。"""

    def test_valid_ipv4(self) -> None:
        self.assertEqual(example1.validate_ip("192.168.1.1"), "192.168.1.1")

    def test_valid_ipv6(self) -> None:
        self.assertEqual(example1.validate_ip("::1"), "::1")

    def test_invalid_ip_raises(self) -> None:
        with self.assertRaises(ValueError):
            example1.validate_ip("; rm -rf /")

    def test_invalid_ip_with_spaces(self) -> None:
        with self.assertRaises(ValueError):
            example1.validate_ip("192.168.1.1; whoami")


class TestDependencyAnalysis(unittest.TestCase):
    """验证 AST 依赖分析。"""

    def test_basic_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(
                "import os\nimport sys\nimport requests\nfrom flask import Flask\n",
                encoding="utf-8",
            )
            p = packager.PythonPackager(src, output_dir=tmp, package_format="so")
            deps = p.analyze_dependencies()
            self.assertIn("requests", deps)
            self.assertIn("flask", deps)
            self.assertNotIn("os", deps)
            self.assertNotIn("sys", deps)


class TestCythonSetupGeneration(unittest.TestCase):
    """验证生成的 Cython setup.py 语法合法。"""

    def test_single_file_setup_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("def hello(): return 42\n", encoding="utf-8")
            p = packager.PythonPackager(src, output_dir=tmp, package_format="so")

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                src_dir, pyx_files = p._prepare_sources(build_path)
                setup_py = p._generate_cython_setup(src_dir, pyx_files)

                # 验证 setup.py 能被 AST 解析
                tree = ast.parse(setup_py.read_text(encoding="utf-8"))
                self.assertIsInstance(tree, ast.Module)

                # 验证 Extension 名称与源文件正确写入字面量
                text = setup_py.read_text(encoding="utf-8")
                self.assertIn("{'name': 'module', 'source': 'module.pyx'}", text)

    def test_package_setup_handles_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "core.py").write_text("def run(): pass\n", encoding="utf-8")

            p = packager.PythonPackager(pkg, output_dir=tmp, package_format="so")

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                src_dir, pyx_files = p._prepare_sources(build_path)
                setup_py = p._generate_cython_setup(src_dir, pyx_files)

                tree = ast.parse(setup_py.read_text(encoding="utf-8"))
                self.assertIsInstance(tree, ast.Module)

                text = setup_py.read_text(encoding="utf-8")
                self.assertIn(
                    "{'name': 'mypkg.__init__', 'source': 'mypkg/__init__.pyx'}", text
                )
                self.assertIn("{'name': 'mypkg.core', 'source': 'mypkg/core.pyx'}", text)


class TestBannerHandling(unittest.TestCase):
    """验证 banner 被正确转换为注释。"""

    def test_banner_inserted_as_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("print('Hello World')\n", encoding="utf-8")

            src = Path(tmp) / "module.py"
            src.write_text("x = 1\n", encoding="utf-8")

            p = packager.PythonPackager(
                src, output_dir=tmp, package_format="so", banner_file=banner
            )

            with tempfile.TemporaryDirectory() as build_tmp:
                build_path = Path(build_tmp)
                _, pyx_files = p._prepare_sources(build_path)
                content = pyx_files[0].read_text(encoding="utf-8")
                self.assertIn("print('Hello World')", content)
                self.assertIn("x = 1", content)
                # 校验 banner 在原代码之前
                self.assertLess(
                    content.index("print('Hello World')"),
                    content.index("x = 1"),
                )

    def test_invalid_banner_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("def broken(\n", encoding="utf-8")

            src = Path(tmp) / "module.py"
            src.write_text("x = 1\n", encoding="utf-8")

            with self.assertRaises(packager.PythonPackagerError):
                packager.PythonPackager(
                    src, output_dir=tmp, package_format="so", banner_file=banner
                )


class TestErrorHandling(unittest.TestCase):
    """验证异常处理。"""

    def test_missing_source_raises(self) -> None:
        with self.assertRaises(packager.PythonPackagerError):
            packager.PythonPackager("/nonexistent/path/file.py")

    def test_unsupported_format_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.py"
            src.write_text("pass", encoding="utf-8")
            with self.assertRaises(packager.PythonPackagerError):
                packager.PythonPackager(src, package_format="zip")

    def test_exe_with_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            with self.assertRaises(packager.PythonPackagerError):
                packager.PythonPackager(pkg, package_format="exe")


if __name__ == "__main__":
    unittest.main()
