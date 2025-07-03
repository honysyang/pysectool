from setuptools import setup

with open('Readme.txt', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='python-packager',
    version='0.1.0',
    description='安全增强的Python源文件打包工具',
    long_description=long_description,
    long_description_content_type='text/plain',
    author='yangzhongjie',
    py_modules=['packager'],
    install_requires=[
        # 基础依赖
        'setuptools',
        'wheel',
        'pycryptodome>=3.10',  # 添加加密依赖
        'psutil>=5.9',         # 添加系统监控依赖
    ],
    extras_require={
        # 可选依赖
        'cython': ['Cython>=0.29'],
        'pyinstaller': ['PyInstaller>=5.0'],
    },
    entry_points={
        'console_scripts': [
            'python-packager = packager:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Security',
        'Topic :: Software Development :: Build Tools',
    ],
    python_requires='>=3.7',
    project_urls={
        'Source': 'https://github.com/honysyang/pysectool',  # 替换为实际项目链接
    },
)
