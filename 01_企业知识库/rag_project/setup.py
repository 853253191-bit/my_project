"""
Python 包安装配置（setup.py）

主要功能：
- 将 rag_project 注册为可安装 Python 包（enterprise-rag）
- 便于 pip install -e . 后在其他环境中 import src 模块

如何调用（在 rag_project 根目录）：
  pip install -e .
  # 或仅查看包信息
  pip show enterprise-rag
"""
from setuptools import find_packages, setup

setup(
    name="enterprise-rag",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
)
