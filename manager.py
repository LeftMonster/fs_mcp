############################# 项目上下文获取
import os
import json
import base64
import logging
from pathlib import Path

import ast
from typing import Any, Dict, List

from bs4 import BeautifulSoup, Comment
import re

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("claude_local_workspace")



logger = logging.getLogger('default')
# 设置项目根目录
# TODO 将参数设置为命令行接收的参数—即路径
# PROJECT_ROOT = "D:\\github\\workspace"
PROJECT_ROOT = "D:\\workspace"

# 忽略常见的临时文件、构建目录等
ignore_list = [
    '*.pyc',  # Python编译文件
    '__pycache__',  # Python缓存目录 
    'node_modules',  # Node.js模块目录
    'venv',  # Python虚拟环境
    '.git/**',  # Git目录及其所有内容
    '*.log',  # 日志文件
    'build',  # 构建目录
    'dist',  # 分发目录
    '.DS_Store',  # macOS系统文件
    'SensitiveConfig*',
    's.yaml',
    's*.yaml',
    'logs/**',
    'config.ini',
    'migrations/**',
    'tmp/**',
    'pb2/**',   # 个别涉及的protobuf
]

@mcp.tool()
def get_project_structure(project_path, ignore_patterns=None, ignore_hidden=True) -> dict:
    """
    获取项目文件夹结构的独立函数，支持自定义忽略文件
    已经设定好了一个基本工作路径，只需要给定project_path —— 即项目名，就会自动打开对应的项目文件夹啦！

    Args:
        project_path (str): 项目名
        ignore_patterns (list, optional): 要忽略的文件或目录模式列表，支持通配符
                                         例如: ['*.pyc', '__pycache__', 'node_modules']
        ignore_hidden (bool, optional): 是否忽略隐藏文件（以.开头的文件），默认为True

    Returns:
        dict: 项目的文件夹结构，包含文件和目录信息
    """
    if ignore_patterns is None:
        ignore_patterns = ignore_list
    import fnmatch

    # 默认忽略模式
    if ignore_patterns is None:
        ignore_patterns = []

    def should_ignore(item_name, item_path, is_dir=False):
        """判断是否应该忽略该文件或目录"""
        # 忽略隐藏文件
        if ignore_hidden and item_name.startswith('.'):
            return True

        # 检查是否匹配忽略模式
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(item_name, pattern):
                return True

            # 对目录特殊处理，支持忽略特定目录下的所有内容
            if is_dir and pattern.endswith('/**'):
                dir_pattern = pattern[:-3]  # 去掉 '/**'
                if fnmatch.fnmatch(item_name, dir_pattern):
                    return True

        return False

    def _build_structure(directory_path, relative_path=""):
        """递归构建目录结构"""
        structure = {}

        try:
            items = os.listdir(directory_path)

            for item in items:
                item_path = os.path.join(directory_path, item)
                item_relative_path = os.path.join(relative_path, item).replace('\\', '/')
                is_dir = os.path.isdir(item_path)

                # 检查是否应该忽略
                if should_ignore(item, item_path, is_dir):
                    continue

                if is_dir:
                    # 如果是目录，递归获取其结构
                    children = _build_structure(item_path, item_relative_path)
                    # 只有当子目录非空时才添加
                    if children or include_empty_dirs:
                        structure[item] = {
                            "type": "directory",
                            "path": item_relative_path,
                            "children": children
                        }
                else:
                    # 如果是文件，保存其基本信息
                    file_size = os.path.getsize(item_path)
                    file_ext = os.path.splitext(item)[1].lower()

                    structure[item] = {
                        "type": "file",
                        "path": item_relative_path,
                        "size": file_size,
                        "extension": file_ext
                    }
        except Exception as e:
            print(f"获取目录结构时出错: {str(e)}")

        return structure

    # 确保基础目录存在
    if not os.path.exists(PROJECT_ROOT) or not os.path.isdir(PROJECT_ROOT):
        raise ValueError(f"错误: 基础目录 '{PROJECT_ROOT}' 不存在或不是一个目录")

    base_folder = PROJECT_ROOT + "\\" + project_path
    if not os.path.exists(base_folder) or not os.path.isdir(base_folder):
        raise ValueError(f"错误: 基础目录 '{base_folder}' 不存在或不是一个目录")

    # 是否包含空目录
    global include_empty_dirs
    include_empty_dirs = True

    # 构建并返回结构
    return _build_structure(base_folder)

@mcp.tool()
def read_file_content(project_path, relative_path) -> dict:
    """
    读取指定文件内容的独立函数
    已经设定好了一个基本工作路径，只需要给定project_path —— 即项目名，就会自动打开对应的项目文件夹啦！

    Args:
        project_path (str): 项目名
        relative_path (str): 相对于base_folder的文件路径

    Returns:
        dict: 包含文件内容和类型的字典
        {
            "type": "file" 或 "binary" 或 "directory",
            "extension": 文件扩展名,
            "data": 文件内容或base64编码的二进制内容或目录列表,
            "encoding": 可选，如果是二进制文件则为"base64"
        }

    Raises:
        ValueError: 当路径不安全或不在base_folder内时
        FileNotFoundError: 当文件不存在时
    """
    # 安全检查：确保相对路径不包含 ".."
    if ".." in relative_path:
        raise ValueError("路径中不允许包含'..'")

    base_folder = PROJECT_ROOT + "\\" + project_path

    # 构建绝对路径
    absolute_path = os.path.abspath(os.path.join(base_folder, relative_path))
    print(absolute_path)
    # 确保路径在BASE_FOLDER内
    if not absolute_path.startswith(os.path.abspath(base_folder)):
        raise ValueError(f"访问被拒绝：尝试访问基础目录 '{base_folder}' 之外的内容")

    # 检查文件是否存在
    if not os.path.exists(absolute_path):
        raise FileNotFoundError(f"文件未找到: {relative_path}")

    # 处理目录
    if os.path.isdir(absolute_path):
        files = os.listdir(absolute_path)
        return {
            "type": "directory",
            "data": files
        }

    # 处理文件
    file_ext = os.path.splitext(absolute_path)[1].lower()

    try:
        # 尝试以文本方式读取
        with open(absolute_path, 'r', encoding='utf-8') as file:
            content = file.read()

        return {
            "type": "file",
            "extension": file_ext,
            "data": content
        }
    except UnicodeDecodeError:
        # 如果不是文本文件，以二进制方式读取并进行base64编码
        with open(absolute_path, 'rb') as file:
            binary_content = file.read()
            base64_content = base64.b64encode(binary_content).decode('utf-8')

        return {
            "type": "binary",
            "extension": file_ext,
            "encoding": "base64",
            "data": base64_content
        }



@mcp.tool()
def clean_html(
    html: str,
    remove_tags: list[str] = None,
    remove_attrs: list[str] = None,
    remove_comments: bool = True,
    compress_whitespace: bool = True
) -> str:
    """
    清理 HTML 文本，支持自定义删除标签、属性、注释与压缩空白字符。
    用于在分析过程中、压缩html文档，减少token消耗

    Args:
        html (str): 原始 HTML 文本。
        remove_tags (list[str], optional): 要删除的标签名列表，例如 ['script', 'style']。
        remove_attrs (list[str], optional): 要从所有标签中删除的属性名列表，例如 ['style', 'onclick']。
        remove_comments (bool, optional): 是否删除 HTML 注释。默认为 True。
        compress_whitespace (bool, optional): 是否压缩空白字符（空格、换行）。默认为 True。

    Returns:
        str: 清理后的 HTML 字符串。
    """
    # 默认配置
    remove_tags = remove_tags or ['script', 'style']
    remove_attrs = remove_attrs or ['style']

    soup = BeautifulSoup(html, "html.parser")

    # 删除指定标签
    for tag in soup.find_all(remove_tags):
        tag.decompose()

    # 删除指定属性
    for tag in soup.find_all(True):
        for attr in remove_attrs:
            if attr in tag.attrs:
                del tag.attrs[attr]

    # 删除注释
    if remove_comments:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    # 转为字符串
    cleaned_html = str(soup)

    # 压缩空白字符（多个换行与空格）
    if compress_whitespace:
        cleaned_html = re.sub(r"\s*\n\s*", "\n", cleaned_html)   # 清理多余换行周围空格
        cleaned_html = re.sub(r"[ \t]+", " ", cleaned_html)      # 替换多个空格为1个
        cleaned_html = re.sub(r"\n{2,}", "\n", cleaned_html)     # 多个换行变一个

    return cleaned_html.strip()






def get_arg_info(arg: ast.arg, default: Any, annotation: Any) -> Dict[str, Any]:
    return {
        "name": arg.arg,
        "type": ast.unparse(annotation) if annotation else None,
        "default": ast.unparse(default) if default else None
    }


def extract_class_info(node: ast.ClassDef) -> Dict[str, Any]:
    class_info = {
        "name": node.name,
        "docstring": ast.get_docstring(node),
        "lineno": node.lineno,
        "end_lineno": getattr(node, 'end_lineno', None),
        "methods": [],
        "classes": []
    }

    for child in node.body:
        if isinstance(child, ast.FunctionDef):
            class_info["methods"].append(extract_function_info(child))
        elif isinstance(child, ast.ClassDef):  # 嵌套类
            class_info["classes"].append(extract_class_info(child))

    return class_info


def extract_function_info(node: ast.FunctionDef) -> Dict[str, Any]:
    args_info = []
    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + node.args.defaults

    for arg, default in zip(node.args.args, defaults):
        args_info.append(get_arg_info(arg, default, arg.annotation))

    return {
        "name": node.name,
        "docstring": ast.get_docstring(node),
        "lineno": node.lineno,
        "end_lineno": getattr(node, 'end_lineno', None),
        "args": args_info,
        "returns": ast.unparse(node.returns) if node.returns else None
    }

@mcp.tool()
def analyze_python_file(filepath: str) -> Dict[str, Any]:
    """
    分析 Python 文件，提取函数、类（含嵌套类）、方法、常量等定义结构与元信息。

    Returns:
        dict: 包含所有结构信息。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)
    result = {
        "functions": [],
        "classes": [],
        "constants": []
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            result["functions"].append(extract_function_info(node))
        elif isinstance(node, ast.ClassDef):
            result["classes"].append(extract_class_info(node))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    result["constants"].append({
                        "name": target.id,
                        "lineno": node.lineno,
                        "value": ast.unparse(node.value)
                    })

    return result

@mcp.tool()
def read_lines_from_file(filepath: str, start_line: int, end_line: int) -> str:
    """
    读取 Python 文件中从 start_line 到 end_line 的内容（包含边界）。

    Args:
        filepath (str): 文件路径。
        start_line (int): 起始行（1-based）。
        end_line (int): 结束行（1-based）。

    Returns:
        str: 指定行的代码字符串。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        return ''.join(lines[start_line - 1:end_line])


@mcp.tool()
def write_in_local_file(filepath: str, lines: List[str]) -> None:
    """
    高效地将字符串列表写入本地文件，每行写入一条，限定只能写入当前工作目录及其子目录。

    参数:
        filepath (str): 相对于当前工作目录的目标文件路径。
        lines (List[str]): 要写入的字符串列表，每个字符串代表一行。

    安全性:
        - 防止路径穿越（如 "../"），仅允许在当前目录及其子目录中写入。
        - 自动创建缺失的中间目录。
        - 使用 writelines 写入，性能更优。
    """
    # base_dir = Path(os.getcwd()).resolve()
    # target_path = (base_dir / filepath).resolve()
    base_dir = Path(PROJECT_ROOT).resolve()
    target_path = (base_dir / filepath).resolve()

    # 安全检查，禁止穿越目录
    if not str(target_path).startswith(str(base_dir)):
        raise ValueError(f"非法文件路径：{filepath}")

    # 创建中间目录（如果不存在）
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 writelines + 换行符拼接，减少系统调用，性能更优
    with open(target_path, 'w', encoding='utf-8') as f:
        f.writelines(line + '\n' for line in lines)

# 示例用法
if __name__ == "__main__":
    # try:
    #     # 示例1: 获取项目结构（带忽略模式）
    #     print("获取项目结构...")
    #
    #     structure = get_project_structure("req1", ignore_patterns=ignore_list, ignore_hidden=True)
    #     print(json.dumps(structure, indent=2))
    #
    #     # 示例2: 读取README.md文件内容
    #     print("\n读取README.md文件...")
    #     readme_path = "README.md"  # 相对于PROJECT_ROOT的路径
    #     file_info = read_file_content("req1", "main.py")
    #
    #     if file_info["type"] == "file":
    #         print(f"文件类型: {file_info['extension']}")
    #         # print("内容:")
    #         # print(file_info["data"])
    #     elif file_info["type"] == "binary":
    #         print(f"二进制文件类型: {file_info['extension']}")
    #         print(f"编码方式: {file_info['encoding']}")
    #         print(f"内容长度: {len(file_info['data'])} 字符")
    #     else:
    #         print(f"目录内容: {file_info['data']}")
    #
    # except Exception as e:
    #     print(f"错误: {str(e)}")
    # # Initialize and run the server
    logger.info("ready data")
    mcp.run(transport='stdio')
    logger.info("end execute")
