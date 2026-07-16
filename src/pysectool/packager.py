"""Python 源文件/文件夹打包编排器。"""

from __future__ import annotations

import zipfile
from pathlib import Path

from pysectool.builder import CythonBuilder, PyInstallerBuilder
from pysectool.deps import DependencyAnalyzer, collect_dependency_files
from pysectool.exceptions import PythonPackagerError
from pysectool.utils import BannerLoader


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
        exclude_data: list[str] | None = None,
    ) -> None:
        """初始化打包器。

        Args:
            source_path: 源 Python 文件或文件夹路径。
            output_dir: 输出目录，默认为源路径所在目录。
            package_format: 打包格式，支持 'pyd'、'so'、'exe'。
            include_deps: 是否包含依赖。
            optimize: 是否优化代码。
            banner_file: banner 文件路径。
            exclude_data: 要排除的数据文件 glob 模式列表。
        """
        self.source_path = Path(source_path).resolve()
        self.output_dir = (
            Path(output_dir).resolve() if output_dir else self.source_path.parent
        )
        self.package_format = package_format.lower()
        self.include_deps = include_deps
        self.optimize = optimize
        self.banner_file = Path(banner_file).resolve() if banner_file else None
        self.exclude_data = exclude_data or []

        self._validate()
        self.banner = BannerLoader(self.banner_file).load()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _validate(self) -> None:
        """校验源路径与输出格式。"""
        if not self.source_path.exists():
            raise PythonPackagerError(f"源路径不存在: {self.source_path}")

        self.is_directory = self.source_path.is_dir()
        if not self.is_directory:
            suffixes = [s.lower() for s in self.source_path.suffixes]
            if ".py" not in suffixes:
                raise PythonPackagerError(
                    f"源文件必须是 Python 文件 (.py)，但得到: {self.source_path}"
                )

        supported = {"pyd", "so", "exe"}
        if self.package_format not in supported:
            raise PythonPackagerError(
                f"不支持的打包格式: {self.package_format}，"
                f"仅支持: {', '.join(sorted(supported))}"
            )

        if self.package_format == "exe" and self.is_directory:
            raise PythonPackagerError("打包为 exe 暂不支持文件夹入口，请指定单个 .py 文件")

    def analyze_dependencies(self) -> set[str]:
        """分析源文件的第三方依赖。"""
        analyzer = DependencyAnalyzer(self.source_path)
        dependencies = analyzer.analyze()
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

    def _build(self) -> Path:
        """根据格式选择构建后端。"""
        if self.package_format in ("pyd", "so"):
            builder = CythonBuilder(
                self.source_path,
                self.output_dir,
                self.optimize,
                self.banner,
                self.exclude_data,
            )
            return builder.build()

        builder = PyInstallerBuilder(
            self.source_path,
            self.output_dir,
            self.optimize,
            self.include_deps,
        )
        return builder.build()

    @staticmethod
    def create_zip_package(
        files: list[tuple[Path, str]], output_file: Path
    ) -> Path:
        """创建 ZIP 包。"""
        print(f"正在创建 ZIP 包: {output_file}")
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src, dst in files:
                zipf.write(src, dst)
        print(f"成功创建 ZIP 包: {output_file}")
        return output_file

    def _collect_output_files(self, output: Path) -> list[tuple[Path, str]]:
        """收集主输出文件到 ZIP 文件列表。"""
        files: list[tuple[Path, str]] = []
        if output.is_dir():
            for item in output.rglob("*"):
                if item.is_file():
                    files.append((item, str(item.relative_to(output))))
        elif output.is_file():
            files.append((output, output.name))
        return files

    def run(self) -> Path | None:
        """执行打包过程。"""
        try:
            dependencies = self.analyze_dependencies() if self.include_deps else set()
            output = self._build()

            if self.include_deps and dependencies:
                dependency_files = collect_dependency_files(dependencies)
                dependency_files.extend(self._collect_output_files(output))
                zip_output = self.output_dir / f"{self.source_path.stem}_with_deps.zip"
                return self.create_zip_package(dependency_files, zip_output)

            return output
        except PythonPackagerError:
            raise
        except Exception as exc:
            raise PythonPackagerError(f"打包过程中发生错误: {exc}") from exc
