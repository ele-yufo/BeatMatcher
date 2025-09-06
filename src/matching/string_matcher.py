"""字符串匹配工具"""

import re
from typing import Tuple, List
from fuzzywuzzy import fuzz, process
from loguru import logger


class StringMatcher:
    """字符串匹配器"""
    
    def __init__(self, normalize_case: bool = True, remove_special_chars: bool = True):
        self.normalize_case = normalize_case
        self.remove_special_chars = remove_special_chars
        self.logger = logger.bind(name=self.__class__.__name__)
    
    def similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度
        
        Args:
            str1: 字符串1
            str2: 字符串2
            
        Returns:
            float: 相似度分数 (0.0-1.0)
        """
        if not str1 or not str2:
            return 0.0
        
        # 预处理字符串
        processed_str1 = self._preprocess_string(str1)
        processed_str2 = self._preprocess_string(str2)
        
        if processed_str1 == processed_str2:
            return 1.0
        
        # 计算多种相似度指标
        ratio = fuzz.ratio(processed_str1, processed_str2) / 100.0
        partial_ratio = fuzz.partial_ratio(processed_str1, processed_str2) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(processed_str1, processed_str2) / 100.0
        token_set_ratio = fuzz.token_set_ratio(processed_str1, processed_str2) / 100.0
        
        # 综合评分（token_set_ratio权重最高，适合处理顺序差异）
        score = (ratio * 0.2 + 
                partial_ratio * 0.2 + 
                token_sort_ratio * 0.3 + 
                token_set_ratio * 0.3)
        
        return min(score, 1.0)
    
    def fuzzy_match(self, query: str, choices: List[str], limit: int = 5) -> List[Tuple[str, float]]:
        """模糊匹配
        
        Args:
            query: 查询字符串
            choices: 候选字符串列表
            limit: 返回结果数量限制
            
        Returns:
            List[Tuple[str, float]]: (匹配字符串, 相似度分数) 列表
        """
        if not query or not choices:
            return []
        
        processed_query = self._preprocess_string(query)
        processed_choices = [self._preprocess_string(choice) for choice in choices]
        
        # 使用fuzzywuzzy进行模糊匹配
        matches = process.extract(
            processed_query,
            processed_choices,
            scorer=fuzz.token_set_ratio,
            limit=limit
        )
        
        # 转换分数到0-1范围，并映射回原始字符串
        results = []
        choice_map = {self._preprocess_string(choice): choice for choice in choices}
        
        for match, score in matches:
            original_choice = choice_map.get(match, match)
            normalized_score = score / 100.0
            results.append((original_choice, normalized_score))
        
        return results
    
    def extract_keywords(self, text: str) -> List[str]:
        """提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 关键词列表
        """
        processed_text = self._preprocess_string(text)
        
        # 分割单词
        words = processed_text.split()
        
        # 过滤短单词和常见停用词
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'feat', 'ft', 'featuring', 'vs', 'versus', 'remix', 'version', 'ver', 'edit', 'mix'}
        
        keywords = []
        for word in words:
            if len(word) >= 2 and word.lower() not in stop_words:
                keywords.append(word)
        
        return keywords
    
    def contains_keywords(self, text: str, keywords: List[str], min_match_ratio: float = 0.5) -> bool:
        """检查文本是否包含足够的关键词
        
        Args:
            text: 待检查的文本
            keywords: 关键词列表
            min_match_ratio: 最小匹配比例
            
        Returns:
            bool: 是否匹配
        """
        if not keywords:
            return True
        
        text_lower = self._preprocess_string(text).lower()
        matched_count = 0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in text_lower:
                matched_count += 1
        
        match_ratio = matched_count / len(keywords)
        return match_ratio >= min_match_ratio
    
    def normalize_artist_name(self, artist: str) -> str:
        """标准化艺术家名称
        
        Args:
            artist: 原始艺术家名称
            
        Returns:
            str: 标准化后的艺术家名称
        """
        if not artist:
            return ""
        
        normalized = artist.strip()
        
        # 移除常见的前缀和后缀
        prefixes = ['DJ ', 'Dr. ', 'Mr. ', 'Ms. ', 'Mrs. ', 'The ']
        suffixes = [' Jr.', ' Sr.', ' III', ' Jr', ' Sr']
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        # 处理合作艺术家的标记
        collaboration_markers = [' feat. ', ' ft. ', ' featuring ', ' vs. ', ' vs ', ' & ', ' and ', ' x ', ' X ']
        for marker in collaboration_markers:
            if marker in normalized:
                # 取主要艺术家（第一个）
                normalized = normalized.split(marker)[0].strip()
                break
        
        return self._preprocess_string(normalized)
    
    def normalize_title(self, title: str) -> str:
        """标准化歌曲标题
        
        Args:
            title: 原始标题
            
        Returns:
            str: 标准化后的标题
        """
        if not title:
            return ""
        
        normalized = title.strip()
        
        # 移除括号内容（通常是版本信息）
        # 但保留主要部分
        patterns = [
            r'\s*\([^)]*remix[^)]*\)',
            r'\s*\([^)]*version[^)]*\)',
            r'\s*\([^)]*edit[^)]*\)',
            r'\s*\([^)]*mix[^)]*\)',
            r'\s*\([^)]*ver\.[^)]*\)',
            r'\s*\[[^\]]*remix[^\]]*\]',
            r'\s*\[[^\]]*version[^\]]*\]',
            r'\s*\[[^\]]*edit[^\]]*\]',
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # 清理多余空格
        normalized = ' '.join(normalized.split())
        
        return self._preprocess_string(normalized)
    
    def _preprocess_string(self, text: str) -> str:
        """预处理字符串
        
        Args:
            text: 输入字符串
            
        Returns:
            str: 处理后的字符串
        """
        if not text:
            return ""
        
        processed = text.strip()
        
        if self.normalize_case:
            processed = processed.lower()
        
        if self.remove_special_chars:
            # 移除特殊字符，但保留空格、连字符和下划线
            processed = re.sub(r'[^\w\s\-_]', ' ', processed)
            # 将多个连续空格替换为单个空格
            processed = re.sub(r'\s+', ' ', processed)
            processed = processed.strip()
        
        return processed