# Python 源文件打包工具

## 项目初衷
为保护python源文件程序的知识产权，避免被不法分子直接剽窃

## 项目简介
这是一个 Python 源文件打包工具，支持将 Python 文件打包为动态库（pyd/so）、可执行文件（exe）以及 ZIP 包。工具能够分析依赖并在打包时包含依赖文件。

## 项目结构
```plaintext
    pysectool/ 
      Readme.md 
      Readme.txt 
      build/ 
        lib/ 
          packager.py 
      example.so 
      example1.py 
      example1.so 
      main.py 
      packager.py 
      setup.py 
  ```    

## 打包格式支持
- pyd/so : 使用 Cython 打包为动态库。
- exe : 使用 PyInstaller 打包为可执行文件。
- ZIP : 包含依赖时会自动创建包含主模块和依赖的 ZIP 包。


## 使用说明
```bash
python packager.py <source_file> -o <output_dir> -f <format> [--no-deps] [--no-optimize]
```

## 参数说明
<source_file>: 要打包的 Python 源文件路径。
-o, --output: 输出目录。
-f, --format: 打包格式，支持 pyd, so, exe，默认为 pyd。
--no-deps: 不包含依赖。
--no-optimize: 不优化代码。


## 用例1
```bash
python setup.py install
```

example1.py 内容如下：
```bash
import subprocess
def check_ping(): 
    """要求用户输入 IP 地址，并检测该 IP 是否可以 ping 通"""
    ip = input("请输入要检测的 IP 地址: ")
    try:
        # 在 Linux 系统上使用 ping 命令，发送 4 个数据包
        result = subprocess.run(['ping', '-c', '4', ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"IP {ip} 可以 ping 通。")
        else:
            print(f"IP {ip} 无法 ping 通。")
    except Exception as e:
        print(f"检测过程中出现错误: {e}")

if __name__ == "__main__":
    check_ping()
```

```bash
python-packager example1.py -o . -f so   #生成example1.so
```

main程序调用example1.so

```bash
import example1

if __name__ == "__main__":
    example1.check_ping()
```

```bash
(venv) (base) root@uweic:/home/workspace/pysectool# python main.py 
请输入要检测的 IP 地址: 10.1.2.100
IP 10.1.2.100 可以 ping 通。
```
