"""Python 源文件/文件夹打包编排器。"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from pysectool.builder import CythonBuilder, PyInstallerBuilder
from pysectool.deps import DependencyAnalyzer, collect_dependency_files
from pysectool.exceptions import PythonPackagerError
from pysectool.log import get_logger
from pysectool.utils import BannerLoader
from pysectool.validation import (
    safe_resolve_path,
    validate_output_dir,
    validate_source_path,
)

logger = get_logger()


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
        clean: bool = False,
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
            clean: 是否在打包前清空输出目录。
        """
        self.source_path = safe_resolve_path(source_path, must_exist=True)
        self.output_dir = (
            safe_resolve_path(output_dir, must_exist=False)
            if output_dir
            else self.source_path.parent
        )
        self.package_format = package_format.lower()
        self.include_deps = include_deps
        self.optimize = optimize
        self.banner_file = (
            safe_resolve_path(banner_file, must_exist=True) if banner_file else None
        )
        self.exclude_data = exclude_data or []
        self.clean = clean

        self._validate_format()
        self.banner = BannerLoader(self.banner_file).load()

        # 前置校验输出目录，避免构建到一半才发现不可写
        validate_output_dir(self.output_dir, self.source_path)

    def _validate_format(self) -> None:
        """校验源路径与输出格式。"""
        validate_source_path(self.source_path)

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
        logger.info("正在分析依赖...")
        analyzer = DependencyAnalyzer(self.source_path)
        dependencies = analyzer.analyze()
        logger.info(
            "找到 %d 个外部依赖: %s",
            len(dependencies),
            ", ".join(sorted(dependencies)) if dependencies else "无",
        )
        if dependencies:
            logger.info(
                "提示: AST 静态分析可能遗漏动态导入或依赖的依赖，"
                "复杂项目建议通过 requirements.txt 补充。"
            )
        return dependencies

    def _build(self, staging_dir: Path) -> Path:
        """根据格式选择构建后端，输出到 staging 目录。"""
        if self.package_format in ("pyd", "so"):
            builder = CythonBuilder(
                self.source_path,
                staging_dir,
                self.optimize,
                self.banner,
                self.exclude_data,
            )
            return builder.build()

        builder = PyInstallerBuilder(
            self.source_path,
            staging_dir,
            self.optimize,
            self.include_deps,
        )
        return builder.build()

    @staticmethod
    def create_zip_package(
        files: list[tuple[Path, str]], output_file: Path
    ) -> Path:
        """创建 ZIP 包。"""
        logger.info("正在创建 ZIP 包: %s", output_file)
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src, dst in files:
                zipf.write(src, dst)
        logger.info("成功创建 ZIP 包: %s", output_file)
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

    def _publish_staging(self, staging_dir: Path) -> Path:
        """把 staging 目录的内容发布到最终输出目录。

        如果启用了 --clean，先清空输出目录；否则把 staging 内容合并进去。
        """
        if self.clean and self.output_dir.exists():
            logger.info("--clean 已启用，正在清空输出目录: %s", self.output_dir)
            for item in self.output_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        # 合并 staging 内容到输出目录
        for item in staging_dir.iterdir():
            dest = self.output_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        return self.output_dir

    def run(self) -> Path | None:
        """执行打包过程。"""
        with tempfile.TemporaryDirectory(prefix="python_packager_staging_") as tmp:
            staging_dir = Path(tmp)

            try:
                dependencies = (
                    self.analyze_dependencies() if self.include_deps else set()
                )
                staging_output = self._build(staging_dir)

                if self.include_deps and dependencies:
                    dependency_files = collect_dependency_files(dependencies)
                    dependency_files.extend(
                        self._collect_output_files(staging_output)
                    )
                    zip_output = (
                        self.output_dir / f"{self.source_path.stem}_with_deps.zip"
                    )
                    self.create_zip_package(dependency_files, zip_output)

                self._publish_staging(staging_dir)

                if self.include_deps and dependencies:
                    zip_path = self.output_dir / f"{self.source_path.stem}_with_deps.zip"
                    logger.info("输出已发布到: %s", zip_path)
                    return zip_path

                # 计算发布后的输出路径
                published_output = self.output_dir / staging_output.relative_to(
                    staging_dir
                )
                logger.info("输出已发布到: %s", published_output)
                return published_output

            except PythonPackagerError:
                logger.error("打包失败，staging 目录已清理，未污染输出目录。")
                raise
            except Exception as exc:
                logger.error("打包过程中发生错误: %s", exc)
                raise PythonPackagerError(f"打包过程中发生错误: {exc}") from exc
