import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import argparse
import importlib.util
import zipfile

class PythonPackager:
    """Python 源文件打包工具"""
    
    def __init__(self, source_file, output_dir=None, package_format='pyd', 
                 include_deps=True, optimize=True):
        """初始化打包器
        
        Args:
            source_file: 源 Python 文件路径
            output_dir: 输出目录，默认为源文件所在目录
            package_format: 打包格式，支持 'pyd'、'so'、'exe'
            include_deps: 是否包含依赖
            optimize: 是否优化代码
        """
        self.source_file = Path(source_file).absolute()
        self.output_dir = Path(output_dir).absolute() if output_dir else self.source_file.parent
        self.package_format = package_format
        self.include_deps = include_deps
        self.optimize = optimize
        
        # 确保源文件存在
        if not self.source_file.exists():
            raise FileNotFoundError(f"源文件不存在: {self.source_file}")
            
        # 确保源文件是 Python 文件
        if self.source_file.suffix.lower() != '.py':
            raise ValueError(f"源文件必须是 Python 文件 (.py)，但得到: {self.source_file.suffix}")
            
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 临时目录
        self.temp_dir = Path(tempfile.mkdtemp(prefix='python_packager_'))
        
    def __del__(self):
        """清理临时目录"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def analyze_dependencies(self):
        """分析源文件的依赖"""
        print("正在分析依赖...")
        # 简单实现，实际应该使用更复杂的依赖分析
        dependencies = set()
        
        # 使用 ast 解析 Python 文件获取导入语句
        try:
            import ast
            with open(self.source_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
                
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        dependencies.add(name.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dependencies.add(node.module.split('.')[0])
        except Exception as e:
            print(f"依赖分析失败: {e}")
            print("将尝试打包而不考虑依赖...")
            dependencies = set()
            
        # 排除 Python 标准库
        stdlib_modules = set(sys.stdlib_module_names)
        dependencies = {dep for dep in dependencies if dep not in stdlib_modules}
        
        print(f"找到 {len(dependencies)} 个外部依赖: {', '.join(dependencies) if dependencies else '无'}")
        return dependencies
    
    def package_with_cython(self):
        """使用 Cython 打包为动态库"""
        print(f"正在使用 Cython 打包 {self.source_file} 为 {self.package_format}...")
        
        # 复制源文件到临时目录
        temp_source = self.temp_dir / self.source_file.name
        shutil.copy2(self.source_file, temp_source)
        
        # 生成 setup.py
        setup_py = self.temp_dir / "setup.py"
        module_name = self.source_file.stem
        
        with open(setup_py, 'w', encoding='utf-8') as f:
            f.write(f"""
from setuptools import setup
from Cython.Build import cythonize
import os

# 优化选项
extra_compile_args = []
extra_link_args = []

{'if os.name == "nt":\n    # Windows 平台选项\n    extra_compile_args += ["/O2"]\nelse:\n    # Linux/macOS 平台选项\n    extra_compile_args += ["-O3", "-ffast-math"]' if self.optimize else ''}

setup(
    name='{module_name}',
    ext_modules=cythonize(
        "{self.source_file.name}",
        compiler_directives={{
            'language_level': {sys.version_info.major},
            {'"optimize.use_switch": True,' if self.optimize else ''}
            {'"wraparound": False,' if self.optimize else ''}
            {'"boundscheck": False,' if self.optimize else ''}
        }},
        # extra_compile_args=extra_compile_args,
        # extra_link_args=extra_link_args
    ),
)
""")
        
        # 确定输出文件扩展名
        if self.package_format == 'pyd' and os.name == 'nt':
            ext = '.pyd'
        elif self.package_format == 'so' and os.name != 'nt':
            ext = '.so'
        else:
            ext = '.pyd' if os.name == 'nt' else '.so'
            
        # 运行 setup.py build_ext
        try:
            cmd = [
                sys.executable, 
                "setup.py", 
                "build_ext", 
                "--inplace",
                "--build-temp", str(self.temp_dir / "build_temp"),
                "--build-lib", str(self.temp_dir / "build_lib")
            ]
            
            subprocess.run(cmd, cwd=self.temp_dir, check=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 查找生成的动态库文件
            build_lib_dir = self.temp_dir / "build_lib"
            for root, _, files in os.walk(build_lib_dir):
                for file in files:
                    if file.endswith(ext):
                        source_dyn_lib = Path(root) / file
                        output_file = self.output_dir / f"{module_name}{ext}"
                        shutil.copy2(source_dyn_lib, output_file)
                        print(f"成功生成: {output_file}")
                        return output_file
            
            raise FileNotFoundError("找不到生成的动态库文件")
            
        except subprocess.CalledProcessError as e:
            print(f"打包失败: {e.stderr.decode('utf-8') if e.stderr else e}")
            raise
        except Exception as e:
            print(f"打包过程中发生错误: {e}")
            raise
    
    def package_with_pyinstaller(self):
        """使用 PyInstaller 打包为可执行文件"""
        print(f"正在使用 PyInstaller 打包 {self.source_file} 为可执行文件...")
        
        try:
            # 确定输出文件名
            output_name = self.source_file.stem
            
            # 构建 PyInstaller 命令
            cmd = [
                sys.executable, 
                "-m", "PyInstaller",
                "--name", output_name,
                "--distpath", str(self.output_dir),
                "--workpath", str(self.temp_dir / "work"),
                "--specpath", str(self.temp_dir),
            ]
            
            if self.optimize:
                cmd.extend(["--strip", "--optimize", "2"])
                
            if not self.include_deps:
                cmd.append("--onefile")
                
            cmd.append(str(self.source_file))
            
            # 执行命令
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 确定输出文件路径
            if self.include_deps:
                output_file = self.output_dir / f"{output_name}.exe" if os.name == 'nt' else self.output_dir / output_name
            else:
                output_file = self.output_dir / output_name / f"{output_name}.exe" if os.name == 'nt' else self.output_dir / output_name / output_name
                
            if output_file.exists():
                print(f"成功生成: {output_file}")
                return output_file
            else:
                # 尝试查找可能的输出文件
                for file in self.output_dir.glob(f"{output_name}*"):
                    if file.is_file() and (file.suffix == '.exe' or os.access(file, os.X_OK)):
                        print(f"成功生成: {file}")
                        return file
                
                raise FileNotFoundError("找不到生成的可执行文件")
                
        except subprocess.CalledProcessError as e:
            print(f"打包失败: {e.stderr.decode('utf-8') if e.stderr else e}")
            raise
        except Exception as e:
            print(f"打包过程中发生错误: {e}")
            raise
    
    def create_zip_package(self, files, output_file):
        """创建 ZIP 包
        
        Args:
            files: 要包含的文件列表，格式为 [(源路径, 目标路径), ...]
            output_file: 输出 ZIP 文件路径
        """
        print(f"正在创建 ZIP 包: {output_file}")
        
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for src, dst in files:
                zipf.write(src, dst)
                
        print(f"成功创建 ZIP 包: {output_file}")
        return output_file
    
    def run(self):
        """执行打包过程"""
        try:
            # 分析依赖
            if self.include_deps:
                dependencies = self.analyze_dependencies()
            else:
                dependencies = set()
                
            # 根据打包格式选择打包方法
            if self.package_format in ('pyd', 'so'):
                # 需要安装 Cython
                try:
                    import Cython
                except ImportError:
                    print("错误: 需要安装 Cython 才能打包为动态库。")
                    print("请运行: pip install Cython")
                    return None
                    
                output_file = self.package_with_cython()
                
            elif self.package_format == 'exe':
                # 需要安装 PyInstaller
                try:
                    import PyInstaller
                except ImportError:
                    print("错误: 需要安装 PyInstaller 才能打包为可执行文件。")
                    print("请运行: pip install pyinstaller")
                    return None
                    
                output_file = self.package_with_pyinstaller()
                
            else:
                raise ValueError(f"不支持的打包格式: {self.package_format}")
                
            # 如果需要包含依赖，创建 ZIP 包
            if self.include_deps and dependencies:
                # 收集依赖文件
                dependency_files = []
                
                for dep in dependencies:
                    try:
                        spec = importlib.util.find_spec(dep)
                        if spec and spec.origin:
                            origin = Path(spec.origin)
                            if origin.is_file():
                                # 模块是单个文件
                                dependency_files.append((origin, f"deps/{origin.name}"))
                            else:
                                # 模块是包
                                package_dir = origin.parent
                                for root, _, files in os.walk(package_dir):
                                    for file in files:
                                        file_path = Path(root) / file
                                        rel_path = file_path.relative_to(package_dir.parent)
                                        dependency_files.append((file_path, f"deps/{rel_path}"))
                    except Exception as e:
                        print(f"无法包含依赖 {dep}: {e}")
                        continue
                
                # 添加主模块
                if output_file:
                    main_module_name = f"{self.source_file.stem}{output_file.suffix}"
                    dependency_files.append((output_file, main_module_name))
                
                # 创建 ZIP 包
                zip_output = self.output_dir / f"{self.source_file.stem}_with_deps.zip"
                self.create_zip_package(dependency_files, zip_output)
                return zip_output
                
            return output_file
            
        except Exception as e:
            print(f"打包失败: {e}")
            return None

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Python 源文件打包工具')
    parser.add_argument('source_file', help='要打包的 Python 源文件')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-f', '--format', choices=['pyd', 'so', 'exe'], default='pyd',
                        help='打包格式，默认为 pyd')
    parser.add_argument('--no-deps', action='store_true', help='不包含依赖')
    parser.add_argument('--no-optimize', action='store_true', help='不优化代码')
    
    args = parser.parse_args()
    
    packager = PythonPackager(
        source_file=args.source_file,
        output_dir=args.output,
        package_format=args.format,
        include_deps=not args.no_deps,
        optimize=not args.no_optimize
    )
    
    result = packager.run()
    
    if result:
        print(f"\n打包成功! 输出文件: {result}")
    else:
        print("\n打包失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()    