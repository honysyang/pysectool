"""工具函数与数据文件收集测试。"""

import tempfile
import unittest
from pathlib import Path

from pysectool.exceptions import PythonPackagerError
from pysectool.utils import BannerLoader, DataCollector


class TestBannerLoader(unittest.TestCase):
    """测试 BannerLoader。"""

    def test_missing_banner_returns_empty(self) -> None:
        """banner 文件不存在时应返回空字符串。"""
        loader = BannerLoader(Path("/nonexistent/banner.txt"))
        self.assertEqual(loader.load(), "")

    def test_valid_banner_loads(self) -> None:
        """合法 banner 应返回带换行的字符串。"""
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("print('hello')\n", encoding="utf-8")
            loader = BannerLoader(banner)
            self.assertIn("print('hello')", loader.load())

    def test_invalid_banner_raises(self) -> None:
        """非法 Python 语法应抛出异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            banner = Path(tmp) / "banner.txt"
            banner.write_text("def broken(\n", encoding="utf-8")
            loader = BannerLoader(banner)
            with self.assertRaises(PythonPackagerError):
                loader.load()


class TestDataCollector(unittest.TestCase):
    """测试 DataCollector。"""

    def test_collects_non_python_files(self) -> None:
        """应收集目录下的非 Python 文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "data").mkdir()
            (pkg / "data" / "config.json").write_text("{}", encoding="utf-8")
            (pkg / "templates").mkdir()
            (pkg / "templates" / "base.html").write_text("<html></html>", encoding="utf-8")

            collector = DataCollector(pkg)
            files = collector.collect()
            rel_paths = [str(rel) for _, rel in files]

            self.assertIn("data/config.json", rel_paths)
            self.assertIn("templates/base.html", rel_paths)
            self.assertNotIn("__init__.py", rel_paths)

    def test_excludes_pycache_and_pyc(self) -> None:
        """应排除 __pycache__ 和 .pyc 文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            pycache = pkg / "__pycache__"
            pycache.mkdir()
            (pycache / "module.cpython-313.pyc").write_text("", encoding="utf-8")
            (pkg / "module.py").write_text("", encoding="utf-8")

            collector = DataCollector(pkg)
            files = collector.collect()
            self.assertEqual(files, [])

    def test_excludes_sensitive_files(self) -> None:
        """应默认排除 .env、secrets 等敏感文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / ".env").write_text("KEY=secret", encoding="utf-8")
            (pkg / "secrets.json").write_text("{}", encoding="utf-8")
            (pkg / "config.json").write_text("{}", encoding="utf-8")

            collector = DataCollector(pkg)
            files = collector.collect()
            rel_paths = [str(rel) for _, rel in files]

            self.assertIn("config.json", rel_paths)
            self.assertNotIn(".env", rel_paths)
            self.assertNotIn("secrets.json", rel_paths)

    def test_custom_exclude_patterns(self) -> None:
        """自定义排除模式应生效。"""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "keep.json").write_text("{}", encoding="utf-8")
            (pkg / "skip.log").write_text("", encoding="utf-8")

            collector = DataCollector(pkg, exclude_patterns=["*.log"])
            files = collector.collect()
            rel_paths = [str(rel) for _, rel in files]

            self.assertIn("keep.json", rel_paths)
            self.assertNotIn("skip.log", rel_paths)

    def test_single_file_returns_empty(self) -> None:
        """单文件源路径不应返回数据文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("x = 1", encoding="utf-8")
            collector = DataCollector(src)
            self.assertEqual(collector.collect(), [])
