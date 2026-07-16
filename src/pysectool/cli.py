"""命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys

from pysectool.exceptions import PythonPackagerError
from pysectool.log import configure_logging, get_logger
from pysectool.packager import PythonPackager

logger = get_logger()


def _default_format() -> str:
    """根据操作系统返回默认打包格式。"""
    return "pyd" if os.name == "nt" else "so"


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    default_fmt = _default_format()
    parser = argparse.ArgumentParser(
        description=(
            "Python 源文件/文件夹打包工具。\n\n"
            "示例:\n"
            "  python-packager examples/example1.py -o ./dist\n"
            "  python-packager my_project/ -o ./dist -f so --clean"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source_path", help="要打包的 Python 源文件或文件夹")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument(
        "-f",
        "--format",
        choices=["pyd", "so", "exe"],
        default=default_fmt,
        help=f"打包格式，默认为 {default_fmt} (当前平台)",
    )

    # 依赖与优化：保留旧的双否定参数以兼容，同时提供正向参数
    deps_group = parser.add_mutually_exclusive_group()
    deps_group.add_argument(
        "--deps", action="store_true", dest="include_deps", help="包含依赖（默认）"
    )
    deps_group.add_argument(
        "--no-deps", action="store_false", dest="include_deps", help="不包含依赖"
    )

    opt_group = parser.add_mutually_exclusive_group()
    opt_group.add_argument(
        "--optimize", action="store_true", dest="optimize", help="开启优化（默认）"
    )
    opt_group.add_argument(
        "--no-optimize", action="store_false", dest="optimize", help="关闭优化"
    )

    parser.add_argument("-b", "--banner", help="banner 文件路径")
    parser.add_argument(
        "--exclude-data",
        action="append",
        default=[],
        help="排除的数据文件 glob 模式（可多次使用）",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="打包前清空输出目录",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出详细日志（DEBUG 级别）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只输出错误信息",
    )

    parser.set_defaults(include_deps=True, optimize=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = create_parser()
    args = parser.parse_args(argv)

    configure_logging(verbose=args.verbose, quiet=args.quiet)

    try:
        packager = PythonPackager(
            source_path=args.source_path,
            output_dir=args.output,
            package_format=args.format,
            include_deps=args.include_deps,
            optimize=args.optimize,
            banner_file=args.banner,
            exclude_data=args.exclude_data,
            clean=args.clean,
        )
        result = packager.run()
    except PythonPackagerError as exc:
        # 部分错误在构造阶段抛出，尚未进入日志流程，因此这里统一记录
        logger.error("打包失败: %s", exc)
        return 1

    if result:
        print(f"\n打包成功! 输出: {result}")
        return 0

    print("\n打包失败!")
    return 1


if __name__ == "__main__":
    sys.exit(main())
