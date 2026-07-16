"""Python 源文件/文件夹打包工具。

支持将单个 Python 文件或整个 Python 包目录打包为：
- 动态库：.pyd (Windows) / .so (Linux/macOS)
- 可执行文件：.exe (Windows) / 无后缀可执行文件 (Unix)
- 含依赖的 ZIP 包
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


class PythonPackagerError(Exception):
    """打包器自定义异常。"""


class PythonPackager:
    """Python 源文件/文件夹打包器。"""

    def __init__(
        self,
        source_path: str | Path,
        output_dir: str | Path | None = None,
        package_format: str = "so",
        include_deps: bool = True,
        optimize: bool = True,
        banner_file: str | Path | None = None,
    ) -> None:
        """初始化打包器。

        Args:
            source_path: 源 Python 文件或文件夹路径。
            output_dir: 输出目录，默认为源路径所在目录。
            package_format: 打包格式，支持 'pyd'、'so'、'exe'。
            include_deps: 是否包含依赖。
            optimize: 是否优化代码。
            banner_file: banner 文件路径。
        """
        self.source_path = Path(source_path).resolve()
        self.output_dir = Path(output_dir).resolve() if output_dir else self.source_path.parent
        self.package_format = package_format.lower()
        self.include_deps = include_deps
        self.optimize = optimize
        self.banner_file = Path(banner_file).resolve() if banner_file else None

        self._validate_source()
        self._validate_format()

        # 提前读取并校验 banner，失败时快速报错
        self.banner = self._read_banner()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _validate_source(self) -> None:
        """校验源路径。"""
        if not self.source_path.exists():
            raise PythonPackagerError(f"源路径不存在: {self.source_path}")

        self.is_directory = self.source_path.is_dir()

        if not self.is_directory:
            suffixes = [s.lower() for s in self.source_path.suffixes]
            if ".py" not in suffixes:
                raise PythonPackagerError(
                    f"源文件必须是 Python 文件 (.py)，但得到: {self.source_path}"
                )

    def _validate_format(self) -> None:
        """校验输出格式。"""
        supported = {"pyd", "so", "exe"}
        if self.package_format not in supported:
            raise PythonPackagerError(
                f"不支持的打包格式: {self.package_format}，仅支持: {', '.join(sorted(supported))}"
            )

        if self.package_format == "exe":
            # exe 仅支持单个文件入口（与 PyInstaller 习惯一致）
            if self.is_directory:
                raise PythonPackagerError("打包为 exe 暂不支持文件夹入口，请指定单个 .py 文件")

    def _read_banner(self) -> str:
        """读取 banner 文件，并校验其是否为可执行 Python 代码。"""
        if not self.banner_file or not self.banner_file.exists():
            return ""

        try:
            banner = self.banner_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise PythonPackagerError(f"读取 banner 文件失败: {exc}") from exc

        if not banner.strip():
            return ""

        # 校验 banner 是可执行的 Python 语句，避免破坏编译后的模块
        try:
            compile(banner, self.banner_file.name, "exec")
        except SyntaxError as exc:
            raise PythonPackagerError(f"banner 文件包含无效 Python 语法: {exc}") from exc

        return f"\n{banner}\n"

    @staticmethod
    def _collect_python_files(path: Path) -> list[Path]:
        """收集路径下的所有 Python 文件。"""
        if path.is_file():
            return [path]
        return sorted(path.rglob("*.py"))

    def analyze_dependencies(self) -> set[str]:
        """使用 AST 分析源文件的顶层 import 依赖。"""
        print("正在分析依赖...")
        dependencies: set[str] = set()

        for py_file in self._collect_python_files(self.source_path):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                print(f"  警告: 解析 {py_file} 失败，跳过依赖分析: {exc}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    dependencies.add(node.module.split(".")[0])

        # 排除标准库和当前项目自身
        stdlib_modules = set(sys.stdlib_module_names)
        project_names = {self.source_path.name, self.source_path.stem}
        dependencies = {
            dep
            for dep in dependencies
            if dep not in stdlib_modules and dep not in project_names
        }

        print(
            f"找到 {len(dependencies)} 个外部依赖: "
            f"{', '.join(sorted(dependencies)) if dependencies else '无'}"
        )
        if dependencies:
            print(
                "提示: AST 静态分析可能遗漏动态导入或依赖的依赖，"
                "复杂项目建议通过 requirements.txt 补充。"
            )
        return dependencies

    @staticmethod
    def _cython_module_name(pyx_file: Path, base_dir: Path) -> str:
        """根据 pyx 相对路径生成 Cython Extension 名称。

        对 __init__.pyx 使用 pkg.__init__ 作为 Extension 名，可让 Cython 直接生成
        pkg/__init__.so，从而被 Python 识别为正常的包。
        """
        rel = pyx_file.relative_to(base_dir)
        return ".".join(rel.with_suffix("").parts)

    def _prepare_sources(self, temp_dir: Path) -> tuple[Path, list[Path]]:
        """把源文件/文件夹复制到临时目录，插入 banner，重命名为 .pyx。"""
        src_dir = temp_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        banner = self.banner

        if self.is_directory:
            target_dir = src_dir / self.source_path.name
            shutil.copytree(self.source_path, target_dir, dirs_exist_ok=True)
            python_files = sorted(target_dir.rglob("*.py"))
        else:
            target_file = src_dir / self.source_path.name
            shutil.copy2(self.source_path, target_file)
            python_files = [target_file]

        pyx_files: list[Path] = []
        for py_file in python_files:
            if banner:
                original = py_file.read_text(encoding="utf-8")
                py_file.write_text(banner + original, encoding="utf-8")

            pyx_file = py_file.with_suffix(".pyx")
            py_file.rename(pyx_file)
            pyx_files.append(pyx_file)

        return src_dir, pyx_files

    def _generate_cython_setup(self, src_dir: Path, pyx_files: list[Path]) -> Path:
        """生成用于 Cython 编译的 setup.py。"""
        package_name = self.source_path.name if self.is_directory else self.source_path.stem

        extensions = []
        for pyx in pyx_files:
            name = self._cython_module_name(pyx, src_dir)
            source = str(pyx.relative_to(src_dir)).replace(os.sep, "/")
            extensions.append(
                {
                    "name": name,
                    "source": source,
                }
            )

        compiler_directives = {"language_level": sys.version_info.major}
        if self.optimize:
            compiler_directives.update(
                {
                    "optimize.use_switch": True,
                    "wraparound": False,
                    "boundscheck": False,
                }
            )

        extra_compile_args = ["-O3"] if self.optimize else []
        extra_link_args = []

        # 生成 setup.py 中可直接执行的 Python 字面量
        ext_items = ",\n    ".join(
            f"{{'name': {ext['name']!r}, 'source': {ext['source']!r}}}"
            for ext in extensions
        )
        directives_items = ",\n            ".join(
            f"{k!r}: {v!r}" for k, v in compiler_directives.items()
        )

        setup_py = src_dir / "setup.py"
        setup_py.write_text(
            f"""\
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        name=ext['name'],
        sources=[ext['source']],
        extra_compile_args={extra_compile_args!r},
        extra_link_args={extra_link_args!r},
    )
    for ext in [{ext_items}]
]

setup(
    name={package_name!r},
    ext_modules=cythonize(
        extensions,
        compiler_directives={{
            {directives_items}
        }},
    ),
)
""",
            encoding="utf-8",
        )
        return setup_py

    def package_with_cython(self) -> Path:
        """使用 Cython 打包为动态库。"""
        print(f"正在使用 Cython 打包 {self.source_path} 为 {self.package_format}...")

        if importlib.util.find_spec("Cython") is None:
            raise PythonPackagerError(
                "需要安装 Cython 才能打包为动态库，请运行: pip install Cython"
            )

        with tempfile.TemporaryDirectory(prefix="python_packager_") as tmp:
            temp_dir = Path(tmp)
            src_dir, pyx_files = self._prepare_sources(temp_dir)
            setup_py = self._generate_cython_setup(src_dir, pyx_files)

            build_temp = temp_dir / "build_temp"
            build_lib = temp_dir / "build_lib"

            cmd = [
                sys.executable,
                str(setup_py),
                "build_ext",
                "--inplace",
                "--build-temp",
                str(build_temp),
                "--build-lib",
                str(build_lib),
            ]

            try:
                subprocess.run(cmd, cwd=src_dir, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                msg = f"Cython 编译失败:\n{exc.stderr}" if exc.stderr else "Cython 编译失败"
                raise PythonPackagerError(msg) from exc

            ext = ".pyd" if os.name == "nt" else ".so"
            dyn_libs = list(build_lib.rglob(f"*{ext}"))
            if not dyn_libs:
                raise PythonPackagerError("找不到生成的动态库文件")

            for dyn_lib in dyn_libs:
                rel = dyn_lib.relative_to(build_lib)
                output_file = self.output_dir / rel
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dyn_lib, output_file)
                print(f"成功生成: {output_file}")

            return self.output_dir

    def package_with_pyinstaller(self) -> Path:
        """使用 PyInstaller 打包为可执行文件。"""
        print(f"正在使用 PyInstaller 打包 {self.source_path} 为可执行文件...")

        if importlib.util.find_spec("PyInstaller") is None:
            raise PythonPackagerError(
                "需要安装 PyInstaller 才能打包为可执行文件，请运行: pip install pyinstaller"
            )

        output_name = self.source_path.stem
        ext = ".exe" if os.name == "nt" else ""

        with tempfile.TemporaryDirectory(prefix="python_packager_") as tmp:
            temp_dir = Path(tmp)
            workpath = temp_dir / "work"
            specpath = temp_dir

            cmd = [
                sys.executable,
                "-m",
                "PyInstaller",
                "--name",
                output_name,
                "--distpath",
                str(self.output_dir),
                "--workpath",
                str(workpath),
                "--specpath",
                str(specpath),
            ]

            if self.optimize:
                cmd.extend(["--strip", "--optimize", "2"])

            if not self.include_deps:
                cmd.append("--onefile")

            cmd.append(str(self.source_path))

            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                msg = f"PyInstaller 打包失败:\n{exc.stderr}" if exc.stderr else "PyInstaller 打包失败"
                raise PythonPackagerError(msg) from exc

            output_file = self.output_dir / output_name / f"{output_name}{ext}"
            if not output_file.exists() and not self.include_deps:
                # --onefile 时输出在 distpath 根目录
                output_file = self.output_dir / f"{output_name}{ext}"

            if output_file.exists():
                print(f"成功生成: {output_file}")
                return output_file

            raise PythonPackagerError("找不到生成的可执行文件")

    def _collect_dependency_files(self, dependencies: Iterable[str]) -> list[tuple[Path, str]]:
        """收集依赖文件，返回 (源路径, zip 内目标路径) 列表。"""
        files: list[tuple[Path, str]] = []
        excluded_suffixes = {".pyc", ".pyo"}
        excluded_dirs = {"__pycache__", "tests", "test", "docs"}

        for dep in dependencies:
            try:
                spec = importlib.util.find_spec(dep)
                if not spec or not spec.origin:
                    print(f"  警告: 无法定位依赖 {dep}，跳过")
                    continue

                origin = Path(spec.origin)
                if origin.is_file() and origin.name == "__init__.py":
                    # 包：复制包目录下必要文件
                    package_dir = origin.parent
                    for item in package_dir.rglob("*"):
                        if not item.is_file():
                            continue
                        if item.suffix in excluded_suffixes:
                            continue
                        if any(
                            part in excluded_dirs
                            for part in item.relative_to(package_dir).parts
                        ):
                            continue
                        rel = f"deps/{dep}/{item.relative_to(package_dir)}"
                        files.append((item, rel))
                elif origin.is_file() and origin.suffix in {".py", ".so", ".pyd"}:
                    # 单个模块文件
                    files.append((origin, f"deps/{origin.name}"))
                else:
                    print(f"  警告: 依赖 {dep} 类型未知，跳过")
            except (ImportError, OSError, ValueError) as exc:
                print(f"  警告: 处理依赖 {dep} 时出错: {exc}")

        return files

    def create_zip_package(self, files: Iterable[tuple[Path, str]], output_file: Path) -> Path:
        """创建 ZIP 包。"""
        print(f"正在创建 ZIP 包: {output_file}")
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src, dst in files:
                zipf.write(src, dst)
        print(f"成功创建 ZIP 包: {output_file}")
        return output_file

    def run(self) -> Path | None:
        """执行打包过程。"""
        try:
            dependencies = self.analyze_dependencies() if self.include_deps else set()

            if self.package_format in ("pyd", "so"):
                output = self.package_with_cython()
            elif self.package_format == "exe":
                output = self.package_with_pyinstaller()
            else:
                raise PythonPackagerError(f"不支持的打包格式: {self.package_format}")

            if self.include_deps and dependencies:
                dependency_files = self._collect_dependency_files(dependencies)

                if isinstance(output, Path) and output.is_dir():
                    for item in output.rglob("*"):
                        if item.is_file():
                            rel = item.relative_to(output)
                            dependency_files.append((item, str(rel)))
                elif isinstance(output, Path) and output.is_file():
                    dependency_files.append((output, output.name))

                zip_output = self.output_dir / f"{self.source_path.stem}_with_deps.zip"
                return self.create_zip_package(dependency_files, zip_output)

            return output

        except PythonPackagerError:
            raise
        except Exception as exc:
            raise PythonPackagerError(f"打包过程中发生错误: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
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

    args = parser.parse_args(argv)

    packager = PythonPackager(
        source_path=args.source_path,
        output_dir=args.output,
        package_format=args.format,
        include_deps=not args.no_deps,
        optimize=not args.no_optimize,
        banner_file=args.banner,
    )

    try:
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
