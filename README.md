# Python 源文件打包工具

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)

> 将 Python 源码打包为动态库（.so/.pyd）或可执行文件（.exe），保护源码不被直接阅读。

## 快速开始

```bash
# 1. 安装（推荐 editable + 全部可选依赖）
pip install -e ".[all]"

# 2. 打包单个文件为 .so
python-packager examples/example1.py -o ./dist -f so

# 3. 运行打包后的程序
cd dist && python -c "import example1; example1.check_ping()"
```

## 项目简介

`python-packager` 是一个 Python 源码保护/打包工具，可将 Python 源文件或整个包目录打包为：

- 动态库：`.pyd`（Windows）/ `.so`（Linux/macOS）
- 可执行文件：`.exe`（Windows）/ 无后缀可执行文件（Unix）
- 含依赖的 ZIP 包

打包过程基于 [Cython](https://cython.org/) 或 [PyInstaller](https://pyinstaller.org/)，可在一定程度上提高源码被直接阅读的难度。

> ⚠️ **注意**：Cython/PyInstaller 打包只能提高逆向门槛，无法做到绝对防反编译或反汇编。如需更高强度保护，请结合代码混淆、加密、授权校验等手段。

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
├── pyproject.toml          # 现代构建配置
├── setup.py                # 兼容旧版安装
├── .pylintrc
└── .gitignore
```

## 安装

### 推荐方式

```bash
pip install -e ".[all]"
```

### 兼容旧版

```bash
python setup.py install
```

### 可选依赖

如果不需要同时安装 Cython 和 PyInstaller，可以按需选择：

```bash
# 仅 Cython（用于 .so/.pyd）
pip install -e ".[cython]"

# 仅 PyInstaller（用于 .exe/可执行文件）
pip install -e ".[pyinstaller]"
```

## 使用说明

### 命令行

```bash
python-packager <source_path> -o <output_dir> -f <format> [--no-deps] [--no-optimize] [-b banner_file]
```

| 参数 | 说明 |
|------|------|
| `source_path` | 要打包的 Python 源文件或文件夹路径 |
| `-o, --output` | 输出目录 |
| `-f, --format` | 打包格式：`pyd`、`so`、`exe`，默认根据平台自动选择（Windows 为 `pyd`，其他为 `so`） |
| `--deps` / `--no-deps` | 是否包含依赖分析（默认 `--deps`） |
| `--optimize` / `--no-optimize` | 是否开启 Cython 优化（默认 `--optimize`） |
| `-b, --banner` | banner 文件路径，打包后导入时会先输出该 banner |
| `--exclude-data` | 排除的数据文件 glob 模式（可多次使用，如 `--exclude-data '*.log'`） |
| `--clean` | 打包前清空输出目录 |
| `-v, --verbose` | 输出 DEBUG 级别详细日志 |
| `-q, --quiet` | 只输出错误信息 |

也支持模块方式运行：

```bash
python -m pysectool examples/example1.py -o ./dist -f so
```

### Python API

```python
from pysectool import PythonPackager

packager = PythonPackager(
    source_path="examples/example1.py",
    output_dir="./dist",
    package_format="so",
    include_deps=True,
    optimize=True,
    banner_file="examples/banner.txt",
)
result = packager.run()
print(f"输出: {result}")
```

## 用例

### 用例 1：将单个 Python 文件打包为动态库

```bash
# Linux/macOS 默认生成 .so，Windows 默认生成 .pyd
python-packager examples/example1.py -o ./dist
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

### 用例 3：打包整个 Python 包目录（自动保留数据文件）

```bash
python-packager my_package/ -o ./dist --clean
```

目录结构会被保留，生成的动态库可直接作为包导入。包内的数据文件（如 `.json`、`.yaml`、模板、图片等）会自动复制到输出目录，保持相对路径不变：

```python
import my_package
import my_package.core

# 如果源码中通过 __file__ 或 importlib.resources 读取数据文件，路径无需修改
```

> 默认会自动排除 `__pycache__`、`.pyc`、`.git*`、`.env*`、`secrets.*` 等文件。如需额外排除某些数据文件，使用 `--exclude-data`：
>
> ```bash
> python-packager my_package/ -o ./dist -f so --exclude-data '*.log' --exclude-data 'drafts/*'
> ```

### 用例 4：打包为可执行文件

```bash
python-packager examples/example1.py -o ./dist -f exe
```

## 日志控制

```bash
# 查看详细日志
python-packager examples/example1.py -o ./dist -v

# 静默模式，只输出错误
python-packager examples/example1.py -o ./dist -q
```

## 稳定性特性

- **路径安全**：自动拒绝包含目录穿越（`..`）的输入路径
- **输出目录校验**：构建前检查输出目录是否可写，避免构建到一半失败
- **原子输出**：先写入临时 staging 目录，成功后再发布到最终输出目录
- **失败回滚**：构建失败时自动清理临时产物，不污染输出目录
- **完整错误信息**：子进程失败时同时输出 stdout 与 stderr

## 开发与测试

```bash
# 运行单元测试
python -m unittest discover -s tests

# 运行静态检查
pylint src tests

# 编译检查
find src tests examples -name '*.py' -exec python -m py_compile {} \;
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
