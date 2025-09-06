"""配置管理模块"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, validator
from .exceptions import ConfigError


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/beatsaber_downloader.log"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    rotation: str = "10 MB"
    retention: str = "7 days"


class BeatSaverConfig(BaseModel):
    base_url: str = "https://api.beatsaver.com"
    search_endpoint: str = "/search/text"
    download_endpoint: str = "/maps/id/{id}/download"
    request_delay: float = 1.0
    max_retries: int = 3
    timeout: int = 30
    user_agent: str = "BeatSaber-Downloader/1.0"


class MatchingConfig(BaseModel):
    artist_weight: float = 0.6
    title_weight: float = 0.4
    minimum_similarity: float = 0.7
    normalize_case: bool = True
    remove_special_chars: bool = True
    fuzzy_ratio_threshold: int = 80
    
    @validator('artist_weight', 'title_weight')
    def weight_validation(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('权重必须在0到1之间')
        return v


class ScoringConfig(BaseModel):
    download_count_weight: float = 0.3
    rating_weight: float = 0.4
    upvote_ratio_weight: float = 0.2
    recency_weight: float = 0.1
    minimum_rating: float = 0.5
    minimum_downloads: int = 10
    
    @validator('download_count_weight', 'rating_weight', 'upvote_ratio_weight', 'recency_weight')
    def weight_validation(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('权重必须在0到1之间')
        return v


class DifficultyCategory(BaseModel):
    min: float
    max: float
    folder: str


class DifficultyConfig(BaseModel):
    categories: Dict[str, DifficultyCategory]


class FilesConfig(BaseModel):
    supported_audio_formats: list = [".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac"]
    download_timeout: int = 300
    max_concurrent_downloads: int = 3
    organize_by_difficulty: bool = True
    preserve_original_structure: bool = False


class NetworkConfig(BaseModel):
    connection_pool_size: int = 10
    connect_timeout: int = 10
    read_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0
    backoff_factor: float = 2.0


class PerformanceConfig(BaseModel):
    max_concurrent_tasks: int = 5
    max_cache_size: int = 1000
    show_progress: bool = True


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/settings.yaml"
        self._config_data: Dict[str, Any] = {}
        self.load_config()
        
        # 初始化各个配置模块
        self.logging = LoggingConfig(**self._config_data.get("logging", {}))
        self.beatsaver = BeatSaverConfig(**self._config_data.get("beatsaver", {}))
        self.matching = MatchingConfig(**self._config_data.get("matching", {}))
        self.scoring = ScoringConfig(**self._config_data.get("scoring", {}))
        self.difficulty = DifficultyConfig(**self._config_data.get("difficulty", {}))
        self.files = FilesConfig(**self._config_data.get("files", {}))
        self.network = NetworkConfig(**self._config_data.get("network", {}))
        self.performance = PerformanceConfig(**self._config_data.get("performance", {}))
    
    def load_config(self) -> None:
        """加载配置文件"""
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            raise ConfigError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigError(f"加载配置文件失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return self.logging.level
    
    @property
    def log_file(self) -> str:
        """获取日志文件路径"""
        return self.logging.file
    
    def validate(self) -> bool:
        """验证配置完整性"""
        try:
            # 检查权重和是否为1.0
            matching_total = self.matching.artist_weight + self.matching.title_weight
            if abs(matching_total - 1.0) > 0.01:
                raise ConfigError(f"匹配权重和不等于1.0: {matching_total}")
            
            scoring_total = (self.scoring.download_count_weight + 
                           self.scoring.rating_weight + 
                           self.scoring.upvote_ratio_weight + 
                           self.scoring.recency_weight)
            if abs(scoring_total - 1.0) > 0.01:
                raise ConfigError(f"评分权重和不等于1.0: {scoring_total}")
            
            return True
        except Exception as e:
            raise ConfigError(f"配置验证失败: {e}")