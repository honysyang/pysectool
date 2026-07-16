from setuptools import setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="python-packager",
    version="0.2.0",
    description="Python 源文件打包工具（支持 .so/.pyd/.exe）",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="yangzhongjie",
    py_modules=["packager"],
    install_requires=[
        "setuptools",
        "wheel",
    ],
    extras_require={
        "cython": ["Cython>=0.29"],
        "pyinstaller": ["PyInstaller>=5.0"],
        "all": ["Cython>=0.29", "PyInstaller>=5.0"],
    },
    entry_points={
        "console_scripts": [
            "python-packager = packager:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Security",
        "Topic :: Software Development :: Build Tools",
    ],
    python_requires=">=3.9",
    project_urls={
        "Source": "https://github.com/honysyang/pysectool",
    },
)
