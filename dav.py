import os
import random
import shutil
import tempfile
import zipfile
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
from wsgidav import util
from wsgiref.util import FileWrapper

# --- 自定义配置 ---

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
        folder:  解压后的文件所在的目录路径。
    """
    print(f"Upload processing completed. Files are in: {folder}")
    # 在这里添加你对上传文件的进一步处理逻辑
    # 示例：遍历文件
    for root, _, files in os.walk(folder):
        for file in files:
            print(f"  - File: {os.path.join(root, file)}")



class CustomResource(DAVNonCollection):
    """自定义的非集合资源（用于处理上传）"""

    def __init__(self, path, environ):
        super().__init__(path, environ)
        self.temp_dir = None  # 临时目录

    def get_etag(self):
        """返回资源的 ETag"""
        return None  # 上传资源不需要 ETag

    def create_empty_resource(self, name):
        # 创建空资源（这里实际上不创建，因为我们只处理上传的 zip）
        return None

    def create_collection(self, name):
        # 不允许创建集合
        return None
    
    def handle_content_written(self, total_size):
        pass # 不需要做任何事情

    def begin_write(self, content_type=None):
        # 准备接收上传文件，创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        # 假设所有上传的文件都会到这个zipfile
        self.zip_file_path = os.path.join(self.temp_dir, "uploaded.zip")  
        return open(self.zip_file_path, "wb")

    def end_write(self, with_errors):
        if with_errors:
            # 上传出错，清理临时目录
            if self.temp_dir:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            return

        # 检查是否为 zip 文件
        if not zipfile.is_zipfile(self.zip_file_path):
            print("Error: Uploaded file is not a zip file.")
            if self.temp_dir:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            return

        # 解压 zip 文件
        try:
            with zipfile.ZipFile(self.zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
        except Exception as e:
            print(f"Error extracting zip file: {e}")
            if self.temp_dir:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            return

        # 调用 upload 函数
        if self.temp_dir:
            upload(self.temp_dir)

            #  (可选) 上传处理完成后，清理临时目录
            # shutil.rmtree(self.temp_dir)
            # self.temp_dir = None


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

            # 解压到数据目录
            with zipfile.ZipFile(self.zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.data_dir)

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
        
        # 虚拟的下载文件
        if path == "/cherry-studio.backup.zip":
            return BackupZipResource(path, environ)

        # 所有其他路径都视为上传请求, 交给 CustomResource 处理
        return CustomResource(path, environ)

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
                "admin": {  # 用户名
                    "password": "password",  # 密码
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
    print("服务器已启动：http://127.0.0.1:8080/")
    try:
        server.start()
    except KeyboardInterrupt:
        print("服务器关闭")
        server.stop()
