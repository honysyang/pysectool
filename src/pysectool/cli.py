"""命令行入口。"""

from __future__ import annotations

import argparse
import sys

from pysectool.exceptions import PythonPackagerError
from pysectool.packager import PythonPackager


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Python 源文件/文件夹打包工具")
    parser.add_argument("source_path", help="要打包的 Python 源文件或文件夹")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument(
        "-f",
        "--format",
        choices=["pyd", "so", "exe"],
        default="so",
        help="打包格式，默认为 so",
    )
    parser.add_argument("--no-deps", action="store_true", help="不包含依赖")
    parser.add_argument("--no-optimize", action="store_true", help="不优化代码")
    parser.add_argument("-b", "--banner", help="banner 文件路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        packager = PythonPackager(
            source_path=args.source_path,
            output_dir=args.output,
            package_format=args.format,
            include_deps=not args.no_deps,
            optimize=not args.no_optimize,
            banner_file=args.banner,
        )
        result = packager.run()
    except PythonPackagerError as exc:
        print(f"\n打包失败: {exc}")
        return 1

    if result:
        print(f"\n打包成功! 输出: {result}")
        return 0

    print("\n打包失败!")
    return 1


if __name__ == "__main__":
    sys.exit(main())
