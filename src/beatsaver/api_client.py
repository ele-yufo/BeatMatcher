"""BeatSaver API客户端"""

import asyncio
from typing import Optional, Dict, Any, List
import httpx
from loguru import logger

from ..utils.config import Config
from ..utils.exceptions import BeatSaverAPIError, NetworkError


class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self, delay: float):
        self.delay = delay
        self.last_request = 0.0
    
    async def acquire(self):
        """获取请求许可"""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_request
        
        if elapsed < self.delay:
            wait_time = self.delay - elapsed
            await asyncio.sleep(wait_time)
        
        self.last_request = asyncio.get_event_loop().time()


class BeatSaverAPIClient:
    """BeatSaver API客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        
        # 初始化HTTP客户端
        self.client = httpx.AsyncClient(
            base_url=config.beatsaver.base_url,
            timeout=httpx.Timeout(config.beatsaver.timeout),
            follow_redirects=True,
            headers={
                "User-Agent": config.beatsaver.user_agent,
                "Accept": "application/json",
            },
            limits=httpx.Limits(
                max_keepalive_connections=config.network.connection_pool_size,
                max_connections=config.network.connection_pool_size * 2,
            ),
        )
        
        # 速率限制器
        self.rate_limiter = RateLimiter(config.beatsaver.request_delay)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def search_maps(
        self,
        query: str,
        auto_mapper: Optional[bool] = None,
        ranked: Optional[bool] = None,
        min_nps: Optional[float] = None,
        max_nps: Optional[float] = None,
        sort_order: str = "Relevance",
        page: int = 0,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """搜索铺面
        
        Args:
            query: 搜索查询字符串
            auto_mapper: 是否只搜索自动生成的谱面
            ranked: 是否只搜索排位谱面
            min_nps: 最小每秒方块数
            max_nps: 最大每秒方块数
            sort_order: 排序方式 (Relevance, Latest, Rating, etc.)
            page: 页码 (从0开始)
            per_page: 每页数量 (最大100)
            
        Returns:
            Dict: API响应数据
        """
        params = {
            "q": query,
            "sortOrder": sort_order,
        }
        # 只在非默认值时添加可选参数
        if per_page != 20:
            params["size"] = min(per_page, 100)  # API限制最大100
        
        # 可选参数
        if auto_mapper is not None:
            params["automapper"] = str(auto_mapper).lower()
        if ranked is not None:
            params["ranked"] = str(ranked).lower()
        if min_nps is not None:
            params["minNps"] = min_nps
        if max_nps is not None:
            params["maxNps"] = max_nps
        
        return await self._make_request("GET", f"/search/text/{page}", params=params)
    
    async def get_map_by_id(self, map_id: str) -> Dict[str, Any]:
        """根据ID获取铺面详情
        
        Args:
            map_id: 铺面ID
            
        Returns:
            Dict: 铺面数据
        """
        return await self._make_request("GET", f"/maps/id/{map_id}")
    
    async def get_map_by_hash(self, map_hash: str) -> Dict[str, Any]:
        """根据hash获取铺面详情
        
        Args:
            map_hash: 铺面hash
            
        Returns:
            Dict: 铺面数据
        """
        return await self._make_request("GET", f"/maps/hash/{map_hash}")
    
    async def get_user_maps(self, user_id: int, page: int = 0, per_page: int = 20) -> Dict[str, Any]:
        """获取用户的铺面
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 用户铺面数据
        """
        params = {
            "from": page * per_page,
            "size": min(per_page, 50),  # 用户铺面API限制最大50
        }
        
        return await self._make_request("GET", f"/maps/uploader/{user_id}", params=params)
    
    async def download_map(self, map_id: str) -> bytes:
        """下载铺面文件
        
        Args:
            map_id: 铺面ID
            
        Returns:
            bytes: 铺面ZIP文件数据
        """
        # 应用速率限制
        await self.rate_limiter.acquire()
        
        download_url = self.config.beatsaver.download_endpoint.format(id=map_id)
        
        for attempt in range(self.config.beatsaver.max_retries + 1):
            try:
                self.logger.debug(f"下载铺面 (尝试 {attempt + 1}): {map_id}")
                
                response = await self.client.get(download_url)
                
                if response.status_code == 200:
                    return response.content
                elif response.status_code == 404:
                    raise BeatSaverAPIError(f"铺面不存在: {map_id}", response.status_code)
                elif response.status_code == 429:
                    # 速率限制，等待更长时间
                    wait_time = (attempt + 1) * self.config.network.retry_delay
                    self.logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
                    
            except httpx.TimeoutException:
                if attempt < self.config.beatsaver.max_retries:
                    wait_time = (attempt + 1) * self.config.network.retry_delay
                    self.logger.warning(f"下载超时，{wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise NetworkError(f"下载超时: {map_id}", attempt)
            
            except httpx.RequestError as e:
                if attempt < self.config.beatsaver.max_retries:
                    wait_time = (attempt + 1) * self.config.network.retry_delay
                    self.logger.warning(f"网络错误 {e}，{wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise NetworkError(f"网络请求失败: {e}", attempt)
        
        raise BeatSaverAPIError(f"下载失败，已重试 {self.config.beatsaver.max_retries} 次: {map_id}")
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发起API请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            json_data: JSON数据
            
        Returns:
            Dict: 解析后的JSON响应
        """
        # 应用速率限制
        await self.rate_limiter.acquire()
        
        for attempt in range(self.config.network.max_retries + 1):
            try:
                self.logger.debug(f"API请求 (尝试 {attempt + 1}): {method} {endpoint}")
                self.logger.debug(f"参数: {params}")
                
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json_data,
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # 速率限制
                    wait_time = (attempt + 1) * self.config.network.retry_delay * self.config.network.backoff_factor
                    self.logger.warning(f"遇到速率限制，等待 {wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    error_data = None
                    try:
                        error_data = response.json()
                    except:
                        pass
                    raise BeatSaverAPIError(
                        f"API请求失败: {response.status_code} {response.reason_phrase}",
                        response.status_code,
                        error_data
                    )
                    
            except httpx.TimeoutException:
                if attempt < self.config.network.max_retries:
                    wait_time = (attempt + 1) * self.config.network.retry_delay
                    self.logger.warning(f"请求超时，{wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise NetworkError(f"请求超时: {endpoint}", attempt)
            
            except httpx.RequestError as e:
                if attempt < self.config.network.max_retries:
                    wait_time = (attempt + 1) * self.config.network.retry_delay
                    self.logger.warning(f"网络错误 {e}，{wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise NetworkError(f"网络请求失败: {e}", attempt)
        
        raise BeatSaverAPIError(f"请求失败，已重试 {self.config.network.max_retries} 次: {endpoint}")