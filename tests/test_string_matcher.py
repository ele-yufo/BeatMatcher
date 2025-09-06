"""字符串匹配测试"""

import pytest
from src.matching.string_matcher import StringMatcher


class TestStringMatcher:
    """字符串匹配器测试类"""
    
    def setup_method(self):
        """测试方法初始化"""
        self.matcher = StringMatcher(normalize_case=True, remove_special_chars=True)
    
    def test_exact_match(self):
        """测试完全匹配"""
        assert self.matcher.similarity("test", "test") == 1.0
        assert self.matcher.similarity("Test", "TEST") == 1.0  # 大小写不敏感
    
    def test_similar_strings(self):
        """测试相似字符串"""
        # 基本相似度
        similarity = self.matcher.similarity("hello world", "hello word")
        assert 0.8 < similarity < 1.0
        
        # 顺序不同但单词相同
        similarity = self.matcher.similarity("world hello", "hello world")
        assert similarity > 0.8
    
    def test_special_characters(self):
        """测试特殊字符处理"""
        # 特殊字符应该被忽略
        similarity = self.matcher.similarity("hello-world!", "hello world")
        assert similarity > 0.9
    
    def test_normalize_artist_name(self):
        """测试艺术家名称标准化"""
        # DJ前缀
        assert self.matcher.normalize_artist_name("DJ Snake") == "snake"
        
        # 合作标记
        assert self.matcher.normalize_artist_name("Artist A feat. Artist B") == "artist a"
        assert self.matcher.normalize_artist_name("Artist A & Artist B") == "artist a"
        
        # The前缀
        assert self.matcher.normalize_artist_name("The Beatles") == "beatles"
    
    def test_normalize_title(self):
        """测试标题标准化"""
        # 移除版本信息
        normalized = self.matcher.normalize_title("Song Name (Remix)")
        assert "remix" not in normalized.lower()
        
        # 移除括号中的版本信息
        normalized = self.matcher.normalize_title("Song Name [Radio Edit]")
        assert "radio" not in normalized.lower() or "edit" not in normalized.lower()
    
    def test_fuzzy_match(self):
        """测试模糊匹配"""
        choices = ["hello world", "hello world 2", "goodbye world", "hello universe"]
        matches = self.matcher.fuzzy_match("hello world", choices, limit=3)
        
        assert len(matches) <= 3
        assert matches[0][0] == "hello world"  # 完全匹配应该排第一
        assert matches[0][1] == 1.0  # 完全匹配分数应该是1.0
    
    def test_extract_keywords(self):
        """测试关键词提取"""
        keywords = self.matcher.extract_keywords("The Quick Brown Fox Jumps")
        
        # 应该过滤掉停用词
        assert "the" not in [kw.lower() for kw in keywords]
        assert "quick" in [kw.lower() for kw in keywords]
        assert "brown" in [kw.lower() for kw in keywords]
    
    def test_contains_keywords(self):
        """测试关键词包含检查"""
        text = "This is a sample text for testing"
        keywords = ["sample", "testing"]
        
        assert self.matcher.contains_keywords(text, keywords, min_match_ratio=0.5)
        assert self.matcher.contains_keywords(text, keywords, min_match_ratio=1.0)
        
        # 部分匹配
        keywords = ["sample", "missing", "testing"]
        assert self.matcher.contains_keywords(text, keywords, min_match_ratio=0.5)
        assert not self.matcher.contains_keywords(text, keywords, min_match_ratio=1.0)
    
    def test_empty_strings(self):
        """测试空字符串处理"""
        assert self.matcher.similarity("", "") == 0.0
        assert self.matcher.similarity("test", "") == 0.0
        assert self.matcher.similarity("", "test") == 0.0
    
    def test_preprocess_string(self):
        """测试字符串预处理"""
        # 测试内部方法
        processed = self.matcher._preprocess_string("Hello, World!")
        expected = "hello world"  # 移除特殊字符，转小写
        assert processed == expected
        
        # 测试多个空格合并
        processed = self.matcher._preprocess_string("hello    world")
        assert processed == "hello world"