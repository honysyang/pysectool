"""兼容旧版 python setup.py install 的最小安装入口。

现代安装请优先使用 pyproject.toml：
    pip install -e ".[all]"
"""

from setuptools import setup

setup()
