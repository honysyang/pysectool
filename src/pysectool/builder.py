"""打包后端：Cython 动态库 / PyInstaller 可执行文件。"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pysectool.exceptions import PythonPackagerError
from pysectool.utils import cython_module_name, DataCollector


class SourcePreparer:
    """准备用于编译的源文件（复制、插入 banner、重命名为 .pyx）。"""

    def __init__(self, source_path: Path, banner: str) -> None:
        self.source_path = source_path
        self.banner = banner
        self.is_directory = source_path.is_dir()

    def prepare(self, temp_dir: Path) -> tuple[Path, list[Path]]:
        """把源文件/文件夹复制到临时目录，插入 banner，重命名为 .pyx。"""
        src_dir = temp_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

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
            if self.banner:
                original = py_file.read_text(encoding="utf-8")
                py_file.write_text(self.banner + original, encoding="utf-8")

            pyx_file = py_file.with_suffix(".pyx")
            py_file.rename(pyx_file)
            pyx_files.append(pyx_file)

        return src_dir, pyx_files


class CythonBuilder:
    """使用 Cython 打包为动态库。"""

    def __init__(
        self,
        source_path: Path,
        output_dir: Path,
        optimize: bool,
        banner: str,
        exclude_data: list[str] | None = None,
    ) -> None:
        self.source_path = source_path
        self.output_dir = output_dir
        self.optimize = optimize
        self.banner = banner
        self.exclude_data = exclude_data or []

    @staticmethod
    def _check_cython() -> None:
        if importlib.util.find_spec("Cython") is None:
            raise PythonPackagerError(
                "需要安装 Cython 才能打包为动态库，请运行: pip install Cython"
            )

    @staticmethod
    def generate_setup(
        src_dir: Path,
        pyx_files: list[Path],
        package_name: str,
        optimize: bool,
    ) -> Path:
        """生成用于 Cython 编译的 setup.py。"""
        extensions = []
        for pyx in pyx_files:
            extensions.append(
                {
                    "name": cython_module_name(pyx, src_dir),
                    "source": str(pyx.relative_to(src_dir)).replace(os.sep, "/"),
                }
            )

        compiler_directives = {"language_level": sys.version_info.major}
        if optimize:
            compiler_directives.update(
                {
                    "optimize.use_switch": True,
                    "wraparound": False,
                    "boundscheck": False,
                }
            )

        extra_compile_args = ["-O3"] if optimize else []
        extra_link_args = []

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

    def build(self) -> Path:
        """执行 Cython 打包。"""
        self._check_cython()
        print(f"正在使用 Cython 打包 {self.source_path} 为 so/pyd...")

        package_name = (
            self.source_path.name if self.source_path.is_dir() else self.source_path.stem
        )
        ext = ".pyd" if os.name == "nt" else ".so"

        with tempfile.TemporaryDirectory(prefix="python_packager_") as tmp:
            temp_dir = Path(tmp)
            src_dir, pyx_files = SourcePreparer(self.source_path, self.banner).prepare(
                temp_dir
            )
            setup_py = self.generate_setup(src_dir, pyx_files, package_name, self.optimize)

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

            dyn_libs = list(build_lib.rglob(f"*{ext}"))
            if not dyn_libs:
                raise PythonPackagerError("找不到生成的动态库文件")

            for dyn_lib in dyn_libs:
                rel = dyn_lib.relative_to(build_lib)
                output_file = self.output_dir / rel
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dyn_lib, output_file)
                print(f"成功生成: {output_file}")

            self._copy_data_files()
            return self.output_dir

    def _copy_data_files(self) -> None:
        """将源目录中的数据文件复制到输出目录，保持相对结构。"""
        if self.source_path.is_file():
            return

        collector = DataCollector(self.source_path, self.exclude_data)
        data_files = collector.collect()
        if not data_files:
            return

        print(f"正在复制 {len(data_files)} 个数据文件...")
        for src_file, rel_path in data_files:
            # 数据文件应放在与编译后的包同级目录下，保持包内相对路径
            output_file = self.output_dir / self.source_path.name / rel_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, output_file)
            print(f"  复制: {output_file}")


class PyInstallerBuilder:
    """使用 PyInstaller 打包为可执行文件。"""

    def __init__(
        self,
        source_path: Path,
        output_dir: Path,
        optimize: bool,
        include_deps: bool,
    ) -> None:
        self.source_path = source_path
        self.output_dir = output_dir
        self.optimize = optimize
        self.include_deps = include_deps

    @staticmethod
    def _check_pyinstaller() -> None:
        if importlib.util.find_spec("PyInstaller") is None:
            raise PythonPackagerError(
                "需要安装 PyInstaller 才能打包为可执行文件，请运行: pip install pyinstaller"
            )

    def build(self) -> Path:
        """执行 PyInstaller 打包。"""
        self._check_pyinstaller()
        print(f"正在使用 PyInstaller 打包 {self.source_path} 为可执行文件...")

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
                output_file = self.output_dir / f"{output_name}{ext}"

            if output_file.exists():
                print(f"成功生成: {output_file}")
                return output_file

            raise PythonPackagerError("找不到生成的可执行文件")
