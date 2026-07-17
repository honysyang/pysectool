"""路径与参数校验。"""

from __future__ import annotations

import os
from pathlib import Path

from pysectool.exceptions import PythonPackagerError


def safe_resolve_path(path: str | Path, must_exist: bool = True) -> Path:
    """安全解析路径，拒绝目录穿越。

    Args:
        path: 输入路径。
        must_exist: 是否要求路径必须存在。

    Returns:
        规范化后的绝对路径。

    Raises:
        PythonPackagerError: 路径非法或不存在时。
    """
    raw = Path(path)

    # 先按字符串检查明显的穿越模式（未解析前）
    for part in raw.parts:
        if part == "..":
            raise PythonPackagerError(f"路径包含目录穿越（..）: {path}")

    try:
        resolved = raw.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise PythonPackagerError(f"路径不存在: {path}") from exc
    except OSError as exc:
        raise PythonPackagerError(f"无法解析路径: {path}: {exc}") from exc

    # resolve 后再次检查，防止通过符号链接等方式穿越到预期范围外
    for part in resolved.parts:
        if part == "..":
            raise PythonPackagerError(f"解析后的路径仍包含目录穿越（..）: {path}")

    return resolved


def validate_output_dir(
    output_dir: Path, source_path: Path, *, clean: bool = False
) -> None:
    """校验输出目录是否合法且可写。

    Args:
        output_dir: 输出目录。
        source_path: 源路径，用于检测输出是否在源目录内部。
        clean: 是否启用了 --clean，用于安全限制。

    Raises:
        PythonPackagerError: 输出目录不合法或不可写时。
    """
    if output_dir.exists() and not output_dir.is_dir():
        raise PythonPackagerError(f"输出路径已存在但不是目录: {output_dir}")

    # 拒绝符号链接：防止 --clean 通过链接误删其他目录
    if output_dir.is_symlink():
        raise PythonPackagerError(
            f"输出目录不能是符号链接: {output_dir}"
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PythonPackagerError(f"无法创建输出目录: {output_dir}: {exc}") from exc

    # 检查可写性
    if not os.access(output_dir, os.W_OK):
        raise PythonPackagerError(f"输出目录没有写入权限: {output_dir}")

    # 避免把输出放到源目录内部，造成循环或污染源码
    try:
        output_dir.relative_to(source_path)
        raise PythonPackagerError(
            f"输出目录不能位于源路径内部: {output_dir} 在 {source_path} 下"
        )
    except ValueError:
        pass

    # 安全限制：默认输出目录与源码目录相同时，禁止 --clean
    if clean and _is_default_output_dir(output_dir, source_path):
        raise PythonPackagerError(
            "--clean 与默认输出目录（源路径所在目录）组合存在误删源码的风险，"
            "请显式指定 -o/--output 为一个独立目录"
        )


def _is_default_output_dir(output_dir: Path, source_path: Path) -> bool:
    """判断输出目录是否为默认的源路径所在目录。"""
    default = source_path.parent if source_path.is_file() else source_path
    try:
        return output_dir.resolve() == default.resolve()
    except OSError:
        return False


def validate_source_path(source_path: Path) -> None:
    """校验源路径基本安全性。

    Raises:
        PythonPackagerError: 路径非法时。
    """
    if not source_path.exists():
        raise PythonPackagerError(f"源路径不存在: {source_path}")

    if not source_path.is_file() and not source_path.is_dir():
        raise PythonPackagerError(f"源路径既不是文件也不是目录: {source_path}")
