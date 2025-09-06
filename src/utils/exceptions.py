"""自定义异常类"""

from typing import Optional, Any


class BeatSaberDownloaderError(Exception):
    """基础异常类"""
    pass


class ConfigError(BeatSaberDownloaderError):
    """配置相关错误"""
    pass


class AudioProcessingError(BeatSaberDownloaderError):
    """音频处理错误"""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        super().__init__(f"处理音频文件 {file_path} 时出错: {message}")


class BeatSaverAPIError(BeatSaberDownloaderError):
    """BeatSaver API错误"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Any] = None):
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(f"BeatSaver API错误: {message}")


class NetworkError(BeatSaberDownloaderError):
    """网络相关错误"""
    def __init__(self, message: str, retry_count: int = 0):
        self.retry_count = retry_count
        super().__init__(f"网络错误 (重试次数: {retry_count}): {message}")


class MatchingError(BeatSaberDownloaderError):
    """匹配算法错误"""
    pass


class DownloadError(BeatSaberDownloaderError):
    """下载相关错误"""
    def __init__(self, url: str, message: str):
        self.url = url
        super().__init__(f"下载失败 {url}: {message}")


class BeatmapParsingError(BeatSaberDownloaderError):
    """铺面解析错误"""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        super().__init__(f"解析铺面文件 {file_path} 时出错: {message}")


class FileOrganizationError(BeatSaberDownloaderError):
    """文件组织错误"""
    def __init__(self, source_path: str, target_path: str, message: str):
        self.source_path = source_path
        self.target_path = target_path
        super().__init__(f"文件组织失败 {source_path} -> {target_path}: {message}")