import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import argparse
import importlib.util
import zipfile
import ast
import glob

class PythonPackager:
    """Python 源文件/文件夹打包工具"""
    
    def __init__(self, source_path, output_dir=None, package_format='so', 
                 include_deps=True, optimize=True, banner_file=None):
        """初始化打包器
        
        Args:
            source_path: 源 Python 文件或文件夹路径
            output_dir: 输出目录，默认为源文件所在目录
            package_format: 打包格式，支持 'pyd'、'so'
            include_deps: 是否包含依赖
            optimize: 是否优化代码
            banner_file: banner 文件路径
        """
        self.source_path = Path(source_path).absolute()
        self.output_dir = Path(output_dir).absolute() if output_dir else self.source_path.parent
        self.package_format = package_format
        self.include_deps = include_deps
        self.optimize = optimize
        self.banner_file = Path(banner_file).absolute() if banner_file else None
        
        # 确保源路径存在
        if not self.source_path.exists():
            raise FileNotFoundError(f"源路径不存在: {self.source_path}")
            
        # 确定源类型（文件或文件夹）
        self.is_directory = self.source_path.is_dir()
        
        # 确保源是 Python 文件或文件夹
        if not self.is_directory and not self.source_path.suffixes[-1].lower() == '.py':
            raise ValueError(f"源文件必须是 Python 文件 (.py)，但得到: {self.source_path.suffixes[-1]}")
            
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 临时目录
        self.temp_dir = Path(tempfile.mkdtemp(prefix='python_packager_'))
        
    def __del__(self):
        """清理临时目录"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def analyze_dependencies(self):
        """分析源文件/文件夹的依赖"""
        print("正在分析依赖...")
        dependencies = set()
        
        # 获取所有 Python 文件
        if self.is_directory:
            python_files = list(self.source_path.rglob('*.py'))
        else:
            python_files = [self.source_path]
            
        # 分析每个文件的依赖
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                    
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            dependencies.add(name.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            dependencies.add(node.module.split('.')[0])
            except Exception as e:
                print(f"依赖分析失败 ({py_file}): {e}")
            
        # 排除 Python 标准库
        stdlib_modules = set(sys.stdlib_module_names)
        dependencies = {dep for dep in dependencies if dep not in stdlib_modules}
        
        print(f"找到 {len(dependencies)} 个外部依赖: {', '.join(dependencies) if dependencies else '无'}")
        return dependencies
    
    def _process_directory(self):
        """处理文件夹，准备用于打包的文件"""
        print(f"正在处理文件夹: {self.source_path}")
        
        # 创建临时目录结构
        temp_src_dir = self.temp_dir / "src"
        temp_src_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制整个源文件夹到临时目录
        shutil.copytree(self.source_path, temp_src_dir / self.source_path.name, dirs_exist_ok=True)
        
        # 获取所有 Python 文件
        python_files = list(temp_src_dir.rglob('*.py'))
        
        # 读取 banner 文件内容
        banner_content = ''
        if self.banner_file and self.banner_file.exists(): 
            try:
                with open(self.banner_file, 'r', encoding='utf-8') as f:
                    banner_content = f.read()
            except Exception as e:
                print(f"读取 banner 文件失败: {e}")
                
        if banner_content:
            banner_content = f'\n{banner_content}\n'
        
        # 处理每个 Python 文件
        pyx_files = []
        for py_file in python_files:
            # 在文件开头添加 banner
            if banner_content:
                with open(py_file, 'r+', encoding='utf-8') as f:
                    content = f.read()
                    f.seek(0, 0)
                    f.write(banner_content + content)
                    f.truncate()
                    
            # 将 .py 文件重命名为 .pyx（Cython 源文件）
            pyx_file = py_file.with_suffix('.pyx')
            py_file.rename(pyx_file)
            pyx_files.append(pyx_file)
            
        return temp_src_dir, pyx_files
    
    def _process_single_file(self):
        """处理单个文件，准备用于打包的文件"""
        print(f"正在处理文件: {self.source_file}")
        
        # 创建临时目录
        temp_src_dir = self.temp_dir / "src"
        temp_src_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制源文件到临时目录
        temp_source = temp_src_dir / self.source_path.name
        shutil.copy2(self.source_path, temp_source)
        
        # 读取 banner 文件内容
        banner_content = ''
        if self.banner_file and self.banner_file.exists(): 
            try:
                with open(self.banner_file, 'r', encoding='utf-8') as f:
                    banner_content = f.read()
            except Exception as e:
                print(f"读取 banner 文件失败: {e}")
                
        if banner_content:
            banner_content = f'\n{banner_content}\n'
        
        # 在文件开头添加 banner
        if banner_content:
            with open(temp_source, 'r+', encoding='utf-8') as f:
                content = f.read()
                f.seek(0, 0)
                f.write(banner_content + content)
                f.truncate()
                
        # 将 .py 文件重命名为 .pyx（Cython 源文件）
        pyx_file = temp_source.with_suffix('.pyx')
        temp_source.rename(pyx_file)
        
        return temp_src_dir, [pyx_file]
    
    def package_with_cython(self):
        """使用 Cython 打包为动态库"""
        print(f"正在使用 Cython 打包 {self.source_path} 为 {self.package_format}...")
        
        # 处理源（文件或文件夹）
        if self.is_directory:
            temp_src_dir, pyx_files = self._process_directory()
        else:
            temp_src_dir, pyx_files = self._process_single_file()
            
        # 获取包名（文件夹名或文件名）
        if self.is_directory:
            package_name = self.source_path.name
        else:
            package_name = self.source_path.stem
            
        # 生成模块列表字符串
        module_list_str = ', '.join([f"'{str(pyx.relative_to(temp_src_dir)).replace(os.sep, '/')}'" for pyx in pyx_files])
        
        # 生成编译器指令
        compiler_directives = [f"'language_level': {sys.version_info.major}"]
        if self.optimize:
            compiler_directives.extend([
                "'optimize.use_switch': True",
                "'wraparound': False",
                "'boundscheck': False"
            ])
        compiler_directives_str = ', '.join(compiler_directives)

        # 提前处理 optimize 的值
        optimize = self.optimize
        extra_compile_args = ["-O3", "-ffast-math"] if optimize else []
        extra_link_args = []

        # 生成 setup.py
        setup_py = temp_src_dir / "setup.py"

        with open(setup_py, 'w', encoding='utf-8') as f:
            f.write("""
from setuptools import setup, Extension
from Cython.Build import cythonize
import os

extensions = [
    Extension(
        name=module_name[:-4].replace('/', '.'),
        sources=[module_name],
        extra_compile_args={extra_compile_args},
        extra_link_args={extra_link_args}
    )
    for module_name in [{module_list_str}]
]

setup(
    name='{package_name}',
    ext_modules=cythonize(
        extensions,
        compiler_directives={{
            {compiler_directives_str}
        }}
    ),
)
""".format(
                package_name=package_name,
                module_list_str=module_list_str,
                compiler_directives_str=compiler_directives_str,
                extra_compile_args=extra_compile_args,
                extra_link_args=extra_link_args
            ))
        
        # 确定输出文件扩展名
        if self.package_format == 'pyd' and os.name == 'nt':
            ext = '.pyd'
        elif self.package_format == 'so' and os.name != 'nt':
            ext = '.so'
        else:
            ext = '.pyd' if os.name == 'nt' else '.so'
            
        # 打印调试信息
        print(f"生成的 setup.py 文件内容:")
        with open(setup_py, 'r', encoding='utf-8') as f:
            print(f.read())
            
        print(f"\n临时源目录中的文件:")
        for root, dirs, files in os.walk(temp_src_dir):
            for file in files:
                print(os.path.join(root, file))
            
        # 运行 setup.py build_ext，在 src 目录下执行命令
        try:
            cmd = [
                sys.executable, 
                "setup.py", 
                "build_ext", 
                "--inplace",
                "--build-temp", str(self.temp_dir / "build_temp"),
                "--build-lib", str(self.temp_dir / "build_lib")
            ]
            
            print(f"\n执行命令: {' '.join(cmd)}")
            print(f"在目录: {temp_src_dir} 中执行")
            
            result = subprocess.run(cmd, cwd=temp_src_dir, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print(f"命令执行结果: {result.returncode}")
            if result.stdout:
                print(f"标准输出:\n{result.stdout.decode('utf-8')}")
            if result.stderr:
                print(f"错误输出:\n{result.stderr.decode('utf-8')}")
            
            # 查找生成的动态库文件
            build_lib_dir = self.temp_dir / "build_lib"

            # 直接使用输出目录，不创建额外的嵌套目录
            output_package_dir = self.output_dir
            output_package_dir.mkdir(parents=True, exist_ok=True)

            # 复制所有生成的 .so/.pyd 文件到输出目录
            dyn_lib_files = list(build_lib_dir.rglob(f'*{ext}'))
            if not dyn_lib_files:
                raise FileNotFoundError("找不到生成的动态库文件")

            for dyn_lib in dyn_lib_files:
                # 保留原有的相对路径
                rel_path = dyn_lib.relative_to(build_lib_dir)
                output_file = output_package_dir / rel_path
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dyn_lib, output_file)
                print(f"成功生成: {output_file}")

            # 复制 __init__.py 文件（如果有），保留原有的相对路径
            for init_file in build_lib_dir.rglob('__init__.py'):
                rel_path = init_file.relative_to(build_lib_dir)
                output_file = output_package_dir / rel_path
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(init_file, output_file)

            print(f"\n所有模块已成功打包到: {output_package_dir}")
            return output_package_dir
            
        except subprocess.CalledProcessError as e:
            print(f"打包失败: {e.stderr.decode('utf-8') if e.stderr else e}")
            raise
        except Exception as e:
            print(f"打包过程中发生错误: {e}")
            raise
    
    def run(self):
        """执行打包过程"""
        try:
            # 分析依赖
            if self.include_deps:
                dependencies = self.analyze_dependencies()
            else:
                dependencies = set()
                
            # 确保打包格式是我们支持的
            if self.package_format not in ('pyd', 'so'):
                raise ValueError(f"文件夹打包只支持 'pyd' 或 'so' 格式，不支持: {self.package_format}")
                
            # 需要安装 Cython
            try:
                import Cython
            except ImportError:
                print("错误: 需要安装 Cython 才能打包为动态库。")
                print("请运行: pip install Cython")
                return None
                
            output_dir = self.package_with_cython()
                
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
                if output_dir:
                    for root, _, files in os.walk(output_dir):
                        for file in files:
                            file_path = Path(root) / file
                            rel_path = file_path.relative_to(output_dir)
                            dependency_files.append((file_path, f"{rel_path}"))
                
                # 创建 ZIP 包
                zip_output = self.output_dir / f"{self.source_path.name}_with_deps.zip"
                self.create_zip_package(dependency_files, zip_output)
                return zip_output
                
            return output_dir
            
        except Exception as e:
            print(f"打包失败: {e}")
            return None

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

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Python 源文件/文件夹打包工具')
    parser.add_argument('source_path', help='要打包的 Python 源文件或文件夹')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-f', '--format', choices=['pyd', 'so'], default='so',
                        help='打包格式，默认为 so')
    parser.add_argument('--no-deps', action='store_true', help='不包含依赖')
    parser.add_argument('--no-optimize', action='store_true', help='不优化代码')
    parser.add_argument('-b', '--banner', help='banner 文件路径')

    args = parser.parse_args()

    packager = PythonPackager(
        source_path=args.source_path,
        output_dir=args.output,
        package_format=args.format,
        include_deps=not args.no_deps,
        optimize=not args.no_optimize,
        banner_file=args.banner
    )
    
    result = packager.run()
    
    if result:
        print(f"\n打包成功! 输出位置: {result}")
    else:
        print("\n打包失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()