"""tests package - 将 src 目录加入路径以便直接导入 pysectool。"""

import sys
from pathlib import Path

from pysectool.log import configure_logging

_PROJECT_ROOT = Path(__file__).parent.parent
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

# 测试期间默认静默日志，避免污染输出
configure_logging(quiet=True)
