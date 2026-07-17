"""路径与参数校验测试。"""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from pysectool.exceptions import PythonPackagerError
from pysectool.validation import (
    safe_resolve_path,
    validate_output_dir,
    validate_source_path,
)


class TestSafeResolvePath(unittest.TestCase):
    """测试 safe_resolve_path。"""

    def test_resolves_existing_path(self) -> None:
        """应返回规范化后的绝对路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "file.py"
            src.write_text("pass", encoding="utf-8")
            resolved = safe_resolve_path(src)
            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved.name, "file.py")

    def test_rejects_traversal(self) -> None:
        """应拒绝包含 .. 的路径。"""
        with self.assertRaises(PythonPackagerError):
            safe_resolve_path("../../etc/passwd")

    def test_missing_path_when_required(self) -> None:
        """must_exist=True 时路径不存在应报错。"""
        with self.assertRaises(PythonPackagerError):
            safe_resolve_path("/nonexistent/path/file.py")

    def test_missing_path_when_optional(self) -> None:
        """must_exist=False 时路径不存在应返回绝对路径。"""
        resolved = safe_resolve_path("/nonexistent/path/dir", must_exist=False)
        self.assertTrue(resolved.is_absolute())


class TestValidateSourcePath(unittest.TestCase):
    """测试 validate_source_path。"""

    def test_valid_file(self) -> None:
        """合法文件不应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.py"
            src.write_text("pass", encoding="utf-8")
            validate_source_path(src)

    def test_valid_directory(self) -> None:
        """合法目录不应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            validate_source_path(pkg)

    def test_missing_raises(self) -> None:
        """不存在的路径应报错。"""
        with self.assertRaises(PythonPackagerError):
            validate_source_path(Path("/nonexistent"))


class TestValidateOutputDir(unittest.TestCase):
    """测试 validate_output_dir。"""

    def test_creates_directory(self) -> None:
        """输出目录不存在时应自动创建。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.py"
            src.write_text("pass", encoding="utf-8")
            output = Path(tmp) / "new_output"
            validate_output_dir(output, src)
            self.assertTrue(output.is_dir())

    def test_rejects_inside_source(self) -> None:
        """输出目录在源路径内部时应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "project"
            src_dir.mkdir()
            src = src_dir / "main.py"
            src.write_text("pass", encoding="utf-8")
            output = src_dir / "dist"
            with self.assertRaises(PythonPackagerError):
                validate_output_dir(output, src_dir)

    def test_rejects_readonly_directory(self) -> None:
        """只读输出目录应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.py"
            src.write_text("pass", encoding="utf-8")
            output = Path(tmp) / "readonly"
            output.mkdir()
            os.chmod(output, stat.S_IRUSR | stat.S_IXUSR)
            try:
                with self.assertRaises(PythonPackagerError):
                    validate_output_dir(output, src)
            finally:
                os.chmod(output, stat.S_IRWXU)

    def test_rejects_symlink_output(self) -> None:
        """输出目录是符号链接时应报错，防止误删链接目标。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.py"
            src.write_text("pass", encoding="utf-8")
            real_dir = Path(tmp) / "real_dir"
            real_dir.mkdir()
            link = Path(tmp) / "output_link"
            link.symlink_to(real_dir)
            with self.assertRaises(PythonPackagerError):
                validate_output_dir(link, src)

    def test_rejects_clean_with_default_output(self) -> None:
        """--clean 与默认输出目录（源路径所在目录）组合时应报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "project"
            src_dir.mkdir()
            src = src_dir / "main.py"
            src.write_text("pass", encoding="utf-8")
            with self.assertRaises(PythonPackagerError):
                validate_output_dir(src_dir, src, clean=True)

    def test_allows_clean_with_explicit_output(self) -> None:
        """--clean 与显式独立输出目录组合时应通过。"""
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "project"
            src_dir.mkdir()
            src = src_dir / "main.py"
            src.write_text("pass", encoding="utf-8")
            output = Path(tmp) / "dist"
            validate_output_dir(output, src, clean=True)
            self.assertTrue(output.is_dir())
