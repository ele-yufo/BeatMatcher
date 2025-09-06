"""配置模块测试"""

import pytest
import tempfile
import yaml
from pathlib import Path

from src.utils.config import Config, ConfigError


class TestConfig:
    """配置测试类"""
    
    def test_default_config(self):
        """测试默认配置"""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "logging": {"level": "INFO"},
                "beatsaver": {"base_url": "https://api.beatsaver.com"},
                "matching": {"artist_weight": 0.6, "title_weight": 0.4},
                "scoring": {
                    "download_count_weight": 0.3,
                    "rating_weight": 0.4,
                    "upvote_ratio_weight": 0.2,
                    "recency_weight": 0.1
                },
                "difficulty": {
                    "categories": {
                        "easy": {"min": 0, "max": 4, "folder": "Easy"},
                        "medium": {"min": 4, "max": 7, "folder": "Medium"},
                        "hard": {"min": 7, "max": 999, "folder": "Hard"}
                    }
                },
                "files": {"supported_audio_formats": [".mp3", ".flac"]},
                "network": {"max_retries": 3},
                "performance": {"max_concurrent_tasks": 5}
            }, f)
            config_path = f.name
        
        try:
            config = Config(config_path)
            
            # 验证基本配置
            assert config.logging.level == "INFO"
            assert config.beatsaver.base_url == "https://api.beatsaver.com"
            assert config.matching.artist_weight == 0.6
            assert config.matching.title_weight == 0.4
            
            # 验证配置验证
            assert config.validate() == True
            
        finally:
            Path(config_path).unlink()
    
    def test_invalid_weights(self):
        """测试无效权重配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "matching": {"artist_weight": 0.8, "title_weight": 0.4},  # 权重和 > 1.0
                "scoring": {
                    "download_count_weight": 0.3,
                    "rating_weight": 0.4,
                    "upvote_ratio_weight": 0.2,
                    "recency_weight": 0.1
                },
                "difficulty": {
                    "categories": {
                        "easy": {"min": 0, "max": 4, "folder": "Easy"}
                    }
                }
            }, f)
            config_path = f.name
        
        try:
            config = Config(config_path)
            
            with pytest.raises(ConfigError):
                config.validate()
                
        finally:
            Path(config_path).unlink()
    
    def test_missing_config_file(self):
        """测试配置文件缺失"""
        with pytest.raises(ConfigError):
            Config("nonexistent_config.yaml")
    
    def test_config_get_method(self):
        """测试配置获取方法"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "test_section": {
                    "nested_value": "test_value",
                    "number_value": 42
                }
            }, f)
            config_path = f.name
        
        try:
            config = Config(config_path)
            
            # 测试获取嵌套值
            assert config.get("test_section.nested_value") == "test_value"
            assert config.get("test_section.number_value") == 42
            
            # 测试默认值
            assert config.get("nonexistent.key", "default") == "default"
            
        finally:
            Path(config_path).unlink()