from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("claude_local_workspace")

############################# 项目上下文获取
import os
import json
import base64
import logging


logger = logging.getLogger('default')
# 设置项目根目录
# TODO 将参数设置为命令行接收的参数—即路径
# PROJECT_ROOT = "D:\\github\\claude_workspace"
PROJECT_ROOT = "D:\\github"

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
    'logs/**',
    'config.ini',
    'migrations/**',
    'tmp/**'
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


def write_to_file(project_path:str, relative_path:str, file_name:str, write_mode:str="w") -> bool:
    """
        write_mode:
            参考with open的模式、此处可以直接填写、这里默认为"w"模式，也可选a、a+、wb等等
    """
    pass





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
