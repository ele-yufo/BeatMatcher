"""BeatSaver搜索功能"""

from typing import List, Optional, Dict, Any
from loguru import logger

from .api_client import BeatSaverAPIClient
from .models import BeatSaverMap
from ..utils.config import Config
from ..utils.exceptions import BeatSaverAPIError


class BeatSaverSearcher:
    """BeatSaver搜索器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        self.api_client = BeatSaverAPIClient(config)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.api_client.close()
    
    async def search(
        self,
        title: str,
        artist: str,
        max_results: int = 20,
        sort_by: str = "Relevance"
    ) -> List[BeatSaverMap]:
        """搜索铺面
        
        Args:
            title: 歌曲标题
            artist: 艺术家
            max_results: 最大结果数量
            sort_by: 排序方式
            
        Returns:
            List[BeatSaverMap]: 搜索结果列表
        """
        # 构建搜索查询
        query = self._build_search_query(title, artist)
        
        self.logger.info(f"搜索铺面: {query}")
        
        try:
            # 执行搜索
            response = await self.api_client.search_maps(
                query=query,
                sort_order=sort_by,
                per_page=min(max_results, 100)  # API限制最大100
            )
            
            # 解析结果
            maps = self._parse_search_results(response)
            
            self.logger.info(f"找到 {len(maps)} 个铺面")
            return maps
            
        except BeatSaverAPIError as e:
            self.logger.error(f"搜索失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"搜索出现意外错误: {e}")
            return []
    
    async def search_by_title_only(self, title: str, max_results: int = 20) -> List[BeatSaverMap]:
        """仅根据标题搜索
        
        Args:
            title: 歌曲标题
            max_results: 最大结果数量
            
        Returns:
            List[BeatSaverMap]: 搜索结果列表
        """
        self.logger.info(f"根据标题搜索铺面: {title}")
        
        try:
            response = await self.api_client.search_maps(
                query=title,
                sort_order="Relevance",
                per_page=min(max_results, 100)
            )
            
            maps = self._parse_search_results(response)
            self.logger.info(f"找到 {len(maps)} 个铺面")
            return maps
            
        except BeatSaverAPIError as e:
            self.logger.error(f"搜索失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"搜索出现意外错误: {e}")
            return []
    
    async def search_by_artist_only(self, artist: str, max_results: int = 20) -> List[BeatSaverMap]:
        """仅根据艺术家搜索
        
        Args:
            artist: 艺术家
            max_results: 最大结果数量
            
        Returns:
            List[BeatSaverMap]: 搜索结果列表
        """
        self.logger.info(f"根据艺术家搜索铺面: {artist}")
        
        try:
            response = await self.api_client.search_maps(
                query=artist,
                sort_order="Relevance",
                per_page=min(max_results, 100)
            )
            
            maps = self._parse_search_results(response)
            self.logger.info(f"找到 {len(maps)} 个铺面")
            return maps
            
        except BeatSaverAPIError as e:
            self.logger.error(f"搜索失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"搜索出现意外错误: {e}")
            return []
    
    async def search_multiple_queries(
        self,
        queries: List[str],
        max_results_per_query: int = 10
    ) -> List[BeatSaverMap]:
        """执行多个搜索查询
        
        Args:
            queries: 查询字符串列表
            max_results_per_query: 每个查询的最大结果数
            
        Returns:
            List[BeatSaverMap]: 合并的搜索结果
        """
        all_maps = []
        seen_ids = set()
        
        for query in queries:
            self.logger.debug(f"执行查询: {query}")
            
            try:
                response = await self.api_client.search_maps(
                    query=query,
                    sort_order="Relevance",
                    per_page=max_results_per_query
                )
                
                maps = self._parse_search_results(response)
                
                # 去重
                for beatmap in maps:
                    if beatmap.id not in seen_ids:
                        all_maps.append(beatmap)
                        seen_ids.add(beatmap.id)
                        
            except Exception as e:
                self.logger.warning(f"查询 '{query}' 失败: {e}")
                continue
        
        self.logger.info(f"多查询搜索完成，共找到 {len(all_maps)} 个唯一铺面")
        return all_maps
    
    async def get_map_details(self, map_id: str) -> Optional[BeatSaverMap]:
        """获取铺面详细信息
        
        Args:
            map_id: 铺面ID
            
        Returns:
            Optional[BeatSaverMap]: 铺面信息，失败返回None
        """
        try:
            response = await self.api_client.get_map_by_id(map_id)
            return BeatSaverMap.from_dict(response)
            
        except BeatSaverAPIError as e:
            self.logger.error(f"获取铺面详情失败 {map_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取铺面详情出现意外错误 {map_id}: {e}")
            return None
    
    def _build_search_query(self, title: str, artist: str) -> str:
        """构建搜索查询字符串
        
        Args:
            title: 歌曲标题
            artist: 艺术家
            
        Returns:
            str: 搜索查询字符串
        """
        # 清理字符串
        title = title.strip()
        artist = artist.strip()
        
        # 移除一些可能影响搜索的字符
        special_chars = ['(', ')', '[', ']', '{', '}', '"', "'"]
        for char in special_chars:
            title = title.replace(char, ' ')
            artist = artist.replace(char, ' ')
        
        # 构建查询
        if artist.lower() != "unknown artist" and artist:
            # 包含艺术家和标题
            query = f"{artist} {title}"
        else:
            # 只有标题
            query = title
        
        # 清理多余空格
        query = ' '.join(query.split())
        
        return query
    
    def _parse_search_results(self, response: Dict[str, Any]) -> List[BeatSaverMap]:
        """解析搜索结果
        
        Args:
            response: API响应数据
            
        Returns:
            List[BeatSaverMap]: 铺面列表
        """
        maps = []
        
        # 检查响应格式
        if "docs" not in response:
            self.logger.warning("API响应中缺少 'docs' 字段")
            return maps
        
        docs = response["docs"]
        if not isinstance(docs, list):
            self.logger.warning("API响应中 'docs' 不是列表")
            return maps
        
        # 解析每个铺面
        for doc in docs:
            try:
                beatmap = BeatSaverMap.from_dict(doc)
                maps.append(beatmap)
                
            except Exception as e:
                self.logger.warning(f"解析铺面数据失败: {e}")
                self.logger.debug(f"问题数据: {doc}")
                continue
        
        return maps
    
    async def close(self):
        """关闭搜索器"""
        await self.api_client.close()