"""命令行接口测试。"""

import os
import unittest

from pysectool.cli import create_parser, main
from pysectool.log import configure_logging


class TestArgumentParser(unittest.TestCase):
    """测试命令行参数解析。"""

    def test_default_format_follows_platform(self) -> None:
        """默认打包格式应随平台变化。"""
        parser = create_parser()
        args = parser.parse_args(["foo.py"])
        expected = "pyd" if os.name == "nt" else "so"
        self.assertEqual(args.format, expected)

    def test_all_args_parsed(self) -> None:
        """应正确解析所有支持的参数。"""
        parser = create_parser()
        args = parser.parse_args(
            [
                "foo.py",
                "-o",
                "dist",
                "-f",
                "exe",
                "--no-deps",
                "--no-optimize",
                "-b",
                "banner.txt",
                "--clean",
                "--exclude-data",
                "*.log",
                "-v",
            ]
        )
        self.assertEqual(args.source_path, "foo.py")
        self.assertEqual(args.output, "dist")
        self.assertEqual(args.format, "exe")
        self.assertFalse(args.include_deps)
        self.assertFalse(args.optimize)
        self.assertEqual(args.banner, "banner.txt")
        self.assertTrue(args.clean)
        self.assertEqual(args.exclude_data, ["*.log"])
        self.assertTrue(args.verbose)

    def test_invalid_format_rejected(self) -> None:
        """不支持的格式应被 argparse 拒绝。"""
        parser = create_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["foo.py", "-f", "zip"])

    def test_exclude_data_parsed(self) -> None:
        """--exclude-data 应支持多次使用并收集为列表。"""
        parser = create_parser()
        args = parser.parse_args(
            ["foo.py", "--exclude-data", "*.log", "--exclude-data", "temp/*"]
        )
        self.assertEqual(args.exclude_data, ["*.log", "temp/*"])


class TestMainEntry(unittest.TestCase):
    """测试 main 入口。"""

    def tearDown(self) -> None:
        """main() 会配置日志处理器，测试后恢复静默。"""
        configure_logging(quiet=True)

    def test_main_returns_error_for_missing_source(self) -> None:
        """源路径不存在时应返回非零退出码。"""
        result = main(["/nonexistent/path/file.py"])
        self.assertEqual(result, 1)
