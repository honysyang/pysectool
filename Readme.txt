Python 源文件打包工具

这个工具可以将 Python 源文件打包成动态库（如 .pyd 或 .so）或可执行文件（.exe），
并且可以选择包含所有依赖项。

安装方法:
1. 克隆或下载此项目
2. 进入项目目录
3. 运行: python setup.py install

使用方法:
python-packager your_script.py [选项]

选项:
  -o, --output      指定输出目录
  -f, --format      指定打包格式，可选: pyd, so, exe (默认: pyd)
  --no-deps         不包含依赖
  --no-optimize     不优化代码

示例:
1. 将 script.py 打包为动态库:
   python-packager script.py

2. 将 script.py 打包为可执行文件:
   python-packager script.py -f exe

3. 将 script.py 打包为动态库并输出到 dist 目录:
   python-packager script.py -o dist

依赖:
- 打包为动态库需要安装 Cython: pip install Cython
- 打包为可执行文件需要安装 PyInstaller: pip install pyinstaller    