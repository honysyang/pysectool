"""命令行接口测试。"""

import unittest

from pysectool.cli import create_parser, main


class TestArgumentParser(unittest.TestCase):
    """测试命令行参数解析。"""

    def test_default_format_is_so(self) -> None:
        """默认打包格式应为 so。"""
        parser = create_parser()
        args = parser.parse_args(["foo.py"])
        self.assertEqual(args.format, "so")

    def test_all_args_parsed(self) -> None:
        """应正确解析所有支持的参数。"""
        parser = create_parser()
        args = parser.parse_args(
            ["foo.py", "-o", "dist", "-f", "exe", "--no-deps", "--no-optimize", "-b", "banner.txt"]
        )
        self.assertEqual(args.source_path, "foo.py")
        self.assertEqual(args.output, "dist")
        self.assertEqual(args.format, "exe")
        self.assertTrue(args.no_deps)
        self.assertTrue(args.no_optimize)
        self.assertEqual(args.banner, "banner.txt")

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

    def test_main_returns_error_for_missing_source(self) -> None:
        """源路径不存在时应返回非零退出码。"""
        result = main(["/nonexistent/path/file.py"])
        self.assertEqual(result, 1)
