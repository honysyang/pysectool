"""pysectool - Python 源文件打包工具。

支持将单个 Python 文件或整个 Python 包目录打包为：
- 动态库：.pyd (Windows) / .so (Linux/macOS)
- 可执行文件：.exe (Windows) / 无后缀可执行文件 (Unix)
- 含依赖的 ZIP 包
"""

from pysectool.cli import main
from pysectool.exceptions import PythonPackagerError
from pysectool.packager import PythonPackager

__version__ = "0.2.0"

__all__ = [
    "PythonPackager",
    "PythonPackagerError",
    "main",
    "__version__",
]
