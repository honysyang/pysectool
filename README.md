# Python 源文件打包工具

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

## 项目简介

`python-packager` 是一个 Python 源码保护/打包工具，可将 Python 源文件或整个包目录打包为：

- 动态库：`.pyd`（Windows）/ `.so`（Linux/macOS）
- 可执行文件：`.exe`（Windows）/ 无后缀可执行文件（Unix）
- 含依赖的 ZIP 包

打包过程基于 [Cython](https://cython.org/) 或 [PyInstaller](https://pyinstaller.org/)，可在一定程度上提高源码被直接阅读的难度。

> ⚠️ 注意：Cython/PyInstaller 打包只能提高逆向门槛，无法做到绝对防反编译或反汇编。如需更高强度保护，请结合代码混淆、加密、授权校验等手段。

## 项目结构

```plaintext
pysectool/
├── src/
│   └── pysectool/          # 核心包
│       ├── __init__.py
│       ├── __main__.py     # python -m pysectool
│       ├── cli.py          # 命令行入口
│       ├── packager.py     # 打包编排器
│       ├── builder.py      # Cython / PyInstaller 构建器
│       ├── deps.py         # 依赖分析
│       ├── utils.py        # 工具函数
│       └── exceptions.py   # 自定义异常
├── tests/                  # 单元测试
├── examples/               # 示例文件
│   ├── example1.py
│   ├── main.py
│   └── banner.txt
├── README.md
├── pyproject.toml
├── setup.py
└── .gitignore
```

## 安装

```bash
# 现代方式（推荐）
pip install -e ".[all]"

# 或兼容旧版
python setup.py install
```

### 可选依赖

- 打包为 `.pyd` / `.so`：`pip install Cython`
- 打包为可执行文件：`pip install pyinstaller`

## 使用说明

```bash
python-packager <source_path> -o <output_dir> -f <format> [--no-deps] [--no-optimize] [-b banner_file]
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `source_path` | 要打包的 Python 源文件或文件夹路径 |
| `-o, --output` | 输出目录 |
| `-f, --format` | 打包格式：`pyd`、`so`、`exe`，默认为 `so` |
| `--no-deps` | 不包含依赖分析 |
| `--no-optimize` | 关闭 Cython 优化选项 |
| `-b, --banner` | banner 文件路径，打包后导入时会先输出该 banner |

## 用例

### 用例 1：将单个 Python 文件打包为 .so

```bash
python-packager examples/example1.py -o ./dist -f so
```

生成 `dist/example1.cpython-xxx-x86_64-linux-gnu.so`，可在其他程序中导入：

```python
import example1

if __name__ == "__main__":
    example1.check_ping()
```

### 用例 2：自定义 banner

```bash
python-packager examples/example1.py -o ./dist -f so -b examples/banner.txt
```

导入生成的 `.so` 时会先输出 banner。

### 用例 3：打包整个 Python 包目录

```bash
python-packager my_package/ -o ./dist -f so
```

### 用例 4：打包为可执行文件

```bash
python-packager examples/example1.py -o ./dist -f exe
```

## 开发

```bash
# 运行测试
python -m unittest discover -s tests

# 运行静态检查
pylint src tests
```

## 安全说明

示例 `examples/example1.py` 中对用户输入进行了严格的 IP 格式校验，禁止通过输入注入额外命令。请勿在真实工具中把用户输入直接拼接到 `subprocess` 调用中。

## 扩展方向

本项目预留了扩展接口，可在打包流程中集成：

- 源码混淆
- 运行时代码加密/解密
- 反调试检测
- 授权与指纹校验

## 许可证

GNU General Public License v3 (GPLv3)
