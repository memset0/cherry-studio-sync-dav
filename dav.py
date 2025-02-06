import os
import random
import shutil
import tempfile
import zipfile
import json
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
from wsgidav import util
from wsgiref.util import FileWrapper
from data import merge_data_json

# --- 自定义配置 ---
# 从环境变量读取用户名，如果不存在则使用默认值 'admin'
USERNAME = os.environ.get('USERNAME', 'admin')
PASSWORD = os.environ.get('PASSWORD', 'admin')

# 数据目录（与 dav.py 同级）
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# 确保数据目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- 上传回调函数 (示例) ---

def upload(folder):
    """
    处理上传并解压后的文件目录。

    Args:
        folder: 解压后的文件所在的目录路径。
    """
    print(f"Upload processing completed. Files are in: {folder}")
    
    """
    Step 1: 文件处理
    - 对于${folder}/Data文件夹（注意大写）中的文件，拷贝到${folder}/DATA_DIR的对应位置中
    - 如果已经存在同名文件则跳过
    - 需要递归处理
    """
    
    # 检查 Data 文件夹是否存在
    data_folder = os.path.join(folder, "Data")
    if not os.path.exists(data_folder):
        print(f"Warning: Data folder not found in {folder}")
        return

    # 递归处理文件
    for root, _, files in os.walk(data_folder):
        # 计算相对路径，用于在目标目录中创建相同的目录结构
        rel_path = os.path.relpath(root, data_folder)
        target_dir = os.path.join(DATA_DIR, 'Data', rel_path)

        # 确保目标目录存在
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # 处理每个文件
        for file in files:
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_dir, file)

            # 如果目标文件不存在，则复制
            if not os.path.exists(target_file):
                print(f"Copying {os.path.relpath(source_file, folder)} to {os.path.relpath(target_file, DATA_DIR)}")
                shutil.copy2(source_file, target_file)
            else:
                print(f"Skipping {os.path.relpath(source_file, folder)} (already exists)")
    
    """
    Step 2: 处理 data.json
    - 检查 DATA_DIR 中是否存在 data.json 文件，如果不存在直接拷贝过去
    - 否则：
        - 分别读取两个 data.json 文件，转换为字典，保存到 local_json, upload_json 中
        - 调用 merge_data_json(local_json, upload_json) 函数进行合并，返回值也是字典
        - 将字典转换为 json 并保存到 DATA_DIR 中的 data.json 文件中
    """
    # 检查上传的文件中是否包含 data.json
    upload_json_path = os.path.join(folder, "data.json")
    if not os.path.exists(upload_json_path):
        print("Warning: data.json not found in uploaded files")
        return

    # 目标 data.json 路径
    local_json_path = os.path.join(DATA_DIR, "data.json")

    try:
        # 如果本地不存在 data.json，直接复制
        if not os.path.exists(local_json_path):
            print("Local data.json not found, copying uploaded file")
            shutil.copy2(upload_json_path, local_json_path)
            return

        # 读取两个 json 文件
        with open(local_json_path, 'r', encoding='utf-8') as f:
            local_json = json.load(f)
        with open(upload_json_path, 'r', encoding='utf-8') as f:
            upload_json = json.load(f)

        # 合并 json 数据
        merged_json = merge_data_json(local_json, upload_json)

        # 保存合并后的数据
        with open(local_json_path, 'w', encoding='utf-8') as f:
            json.dump(merged_json, f, ensure_ascii=False, indent=2)
        print("Successfully merged data.json files")

    except Exception as e:
        print(f"Error processing data.json: {e}")


class DataDirCollection(DAVCollection):
    """用于提供对 data 目录的访问的虚拟集合"""

    def get_member_names(self):
        return []  # 不列出 data 目录下的实际文件

    def get_member(self, name):
        return DAVNonCollection(self.path + name, self.environ)
    

class RootCollection(DAVCollection):
    """自定义根目录"""

    def get_member_names(self):
        # 只显示一个虚拟的 zip 文件
        return ["cherry-studio.backup.zip"]

    def get_member(self, name):
        if name == "cherry-studio.backup.zip":
            return BackupZipResource(self.path + name, self.environ)
        # 对其他所有路径返回一个只读的资源
        return DAVNonCollection(self.path + name, self.environ)


class BackupZipResource(DAVNonCollection):
    """虚拟的 ZIP 文件资源（用于下载）"""

    def __init__(self, path, environ):
        super().__init__(path, environ)
        self.data_dir = DATA_DIR  # 数据目录

    def get_etag(self):
        """返回资源的 ETag"""
        return None  # 动态生成的内容，不需要 ETag

    def is_collection(self):
        return False

    def support_ranges(self):
        return False

    def support_etag(self):
        return False

    def get_content_length(self):
        """返回文件大小"""
        try:
            temp_zip_path = tempfile.mktemp(suffix=".zip")
            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(self.data_dir):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, self.data_dir)
                        zipf.write(abs_path, rel_path)
            
            size = os.path.getsize(temp_zip_path)
            os.remove(temp_zip_path)
            return size

        except Exception as e:
            print(f"Error getting content length: {e}")
            if os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except:
                    pass
            return None

    def get_content_type(self):
        return "application/zip"

    def get_creation_date(self):
        return None

    def get_display_name(self):
        return "cherry-studio.backup.zip"

    def get_last_modified(self):
        return None

    def is_readable(self):
        return True

    def is_writable(self):
        return True  # 允许写入

    def begin_write(self, content_type=None):
        """准备接收上传文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.zip_file_path = os.path.join(self.temp_dir, "uploaded.zip")
        return open(self.zip_file_path, "wb")

    def end_write(self, with_errors):
        """处理上传完成的文件"""
        if with_errors:
            if hasattr(self, 'temp_dir') and self.temp_dir:
                shutil.rmtree(self.temp_dir)
            return

        try:
            if not zipfile.is_zipfile(self.zip_file_path):
                raise Exception("Uploaded file is not a zip file")

            # 先解压到临时目录
            extract_dir = os.path.join(self.temp_dir, "extracted")
            os.makedirs(extract_dir)
            with zipfile.ZipFile(self.zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # 调用上传回调函数
            upload(extract_dir)

            # # 解压到数据目录
            # with zipfile.ZipFile(self.zip_file_path, 'r') as zip_ref:
            #     zip_ref.extractall(self.data_dir)

        except Exception as e:
            print(f"Error processing uploaded file: {e}")
        finally:
            if hasattr(self, 'temp_dir') and self.temp_dir:
                shutil.rmtree(self.temp_dir)

    def get_content(self):
        """生成 ZIP 文件并作为响应内容"""
        temp_zip_path = tempfile.mktemp(suffix=".zip")

        try:
            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(self.data_dir):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, self.data_dir)
                        zipf.write(abs_path, rel_path)
            
            # 直接返回文件对象，不使用 FileWrapper
            return open(temp_zip_path, "rb")

        except Exception as e:
            print(f"Error creating zip file: {e}")
            if os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except:
                    pass
            return None  # 返回空响应


class CustomProvider(DAVProvider):
    def __init__(self):
        super().__init__()

    def get_resource_inst(self, path, environ):
        """根据路径返回自定义资源实例"""
        
        # 虚拟的根目录
        if path == "/" or path == "":
            return RootCollection("/", environ)
        
        # 只处理虚拟的备份文件路径
        if path == "/cherry-studio.backup.zip":
            return BackupZipResource(path, environ)

        # 其他所有路径都返回只读资源
        return DAVNonCollection(path, environ)

# --- WSGI 应用配置 ---

config = {
    "provider_mapping": {"/": CustomProvider()},
    "verbose": 3,  # 调试级别
    # "logging": {
    #     "enable_loggers": [], # 不输出多余信息
    # },
    
    # 添加用户认证配置
    "simple_dc": {
        "user_mapping": {
            "*": {  # 对所有路径生效
                USERNAME: {  # 用户名
                    "password": PASSWORD,  # 密码
                    "description": "WebDAV Admin",
                    "roles": ["admin", "write", "read"]
                }
            }
        }
    },
    
    # 默认域名
    "http_authenticator": {
        "domain_controller": None,  # 使用默认的域控制器
        "accept_basic": True,       # 允许基本认证
        "accept_digest": False,     # 不使用摘要认证
        "default_to_digest": False  # 默认使用基本认证
    },
}

# --- 启动服务器 ---

if __name__ == "__main__":
    from wsgidav.wsgidav_app import WsgiDAVApp
    from cheroot import wsgi

    app = WsgiDAVApp(config)

    server_args = {
        "bind_addr": ("127.0.0.1", 8080),
        "wsgi_app": app,
    }
    server = wsgi.Server(**server_args)
    print("Server start at http://127.0.0.1:8080/")
    try:
        server.start()
    except KeyboardInterrupt:
        print("Server stopped.")
        server.stop()
