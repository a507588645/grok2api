"""代理池自动获取模块"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

import requests
from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import setting

# 代理池 API 配置
PROXY_POOL_API = "https://proxy.scdn.io/api/get_proxy.php"
DEFAULT_PROXY_COUNT = 5  # 默认获取的代理数量
MAX_PROXY_COUNT = 20  # 最大获取的代理数量

# 支持的代理协议类型
SUPPORTED_PROTOCOLS = ["http", "https", "socks4", "socks5", "all"]


class ProxyPool:
    """管理代理池的自动获取、验证与刷新"""

    _lock = asyncio.Lock()
    _proxy_list: List[Dict[str, str]] = []  # 存储可用代理列表

    @staticmethod
    async def fetch_proxies(protocol: str = "all", count: int = DEFAULT_PROXY_COUNT) -> List[str]:
        """从代理池API获取代理列表
        
        Args:
            protocol: 代理协议类型 (http, https, socks4, socks5, all)
            count: 获取代理数量
            
        Returns:
            代理IP地址列表，格式如 ["192.168.1.1:8080", ...]
        """
        async with ProxyPool._lock:
            # 验证参数
            if protocol not in SUPPORTED_PROTOCOLS:
                logger.warning(f"[ProxyPool] 不支持的协议类型: {protocol}，使用默认值 'all'")
                protocol = "all"
            
            if count < 1 or count > MAX_PROXY_COUNT:
                logger.warning(f"[ProxyPool] 代理数量超出范围: {count}，调整为 {DEFAULT_PROXY_COUNT}")
                count = DEFAULT_PROXY_COUNT
            
            try:
                logger.debug(f"[ProxyPool] 开始获取代理 - 协议: {protocol}, 数量: {count}")
                
                # 调用代理池API
                params = {"protocol": protocol, "count": count}
                
                # 使用同步requests库（因为代理池API是外部服务）
                response = requests.get(PROXY_POOL_API, params=params, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"[ProxyPool] API请求失败，状态码: {response.status_code}")
                    return []
                
                data = response.json()
                
                if data.get("code") != 200:
                    logger.error(f"[ProxyPool] API返回错误: {data.get('message', '未知错误')}")
                    return []
                
                proxies = data.get("data", {}).get("proxies", [])
                logger.info(f"[ProxyPool] 成功获取 {len(proxies)} 个代理")
                
                return proxies
                
            except requests.exceptions.Timeout:
                logger.error("[ProxyPool] API请求超时")
                return []
            except requests.exceptions.RequestException as e:
                logger.error(f"[ProxyPool] API请求异常: {e}")
                return []
            except Exception as e:
                logger.error(f"[ProxyPool] 获取代理失败: {e}")
                return []

    @staticmethod
    async def validate_proxy(proxy: str, protocol: str = "http", test_url: str = "https://grok.com/rest/health") -> bool:
        """验证代理是否可用
        
        Args:
            proxy: 代理地址，格式如 "192.168.1.1:8080"
            protocol: 代理协议类型
            test_url: 测试URL
            
        Returns:
            代理是否可用
        """
        try:
            # 构建完整的代理URL
            if protocol == "all":
                # 如果协议是all，尝试使用http
                proxy_url = f"http://{proxy}"
            elif protocol in ["socks4", "socks5"]:
                # socks代理需要特殊处理
                proxy_url = f"{protocol}://{proxy}"
            else:
                proxy_url = f"{protocol}://{proxy}"
            
            logger.debug(f"[ProxyPool] 验证代理: {proxy_url}")
            
            proxies = {"http": proxy_url, "https": proxy_url}
            
            # 使用curl_cffi进行异步请求测试
            async with AsyncSession() as session:
                try:
                    resp = await session.get(
                        test_url,
                        proxies=proxies,
                        timeout=10,
                        allow_redirects=True
                    )
                    
                    # 检查状态码，200-399都认为是成功的
                    if 200 <= resp.status_code < 400:
                        logger.debug(f"[ProxyPool] 代理可用: {proxy} (状态码: {resp.status_code})")
                        return True
                    else:
                        logger.debug(f"[ProxyPool] 代理不可用: {proxy} (状态码: {resp.status_code})")
                        return False
                        
                except Exception as e:
                    logger.debug(f"[ProxyPool] 代理验证失败: {proxy} - {type(e).__name__}: {e}")
                    return False
                    
        except Exception as e:
            logger.debug(f"[ProxyPool] 代理验证异常: {proxy} - {e}")
            return False

    @staticmethod
    async def fetch_and_validate(protocol: str = "all", count: int = DEFAULT_PROXY_COUNT, 
                                 validate: bool = True) -> List[Dict[str, str]]:
        """获取并验证代理列表
        
        Args:
            protocol: 代理协议类型
            count: 获取代理数量
            validate: 是否验证代理可用性
            
        Returns:
            代理列表，每个代理包含 url, address, protocol, valid 等信息
        """
        proxies = await ProxyPool.fetch_proxies(protocol, count)
        
        if not proxies:
            logger.warning("[ProxyPool] 未获取到任何代理")
            return []
        
        result = []
        
        for proxy in proxies:
            proxy_info = {
                "address": proxy,
                "protocol": protocol,
                "valid": None,  # 未验证
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if validate:
                # 异步验证代理
                is_valid = await ProxyPool.validate_proxy(proxy, protocol)
                proxy_info["valid"] = is_valid
                
                # 构建完整的代理URL
                if protocol in ["socks4", "socks5"]:
                    # socks代理，需要使用socks5h以支持DNS解析
                    if protocol == "socks5":
                        proxy_info["url"] = f"socks5h://{proxy}"
                    else:
                        proxy_info["url"] = f"{protocol}://{proxy}"
                elif protocol == "all":
                    # 默认使用http
                    proxy_info["url"] = f"http://{proxy}"
                else:
                    proxy_info["url"] = f"{protocol}://{proxy}"
            else:
                # 不验证，默认构建URL
                if protocol in ["socks4", "socks5"]:
                    if protocol == "socks5":
                        proxy_info["url"] = f"socks5h://{proxy}"
                    else:
                        proxy_info["url"] = f"{protocol}://{proxy}"
                elif protocol == "all":
                    proxy_info["url"] = f"http://{proxy}"
                else:
                    proxy_info["url"] = f"{protocol}://{proxy}"
            
            result.append(proxy_info)
        
        # 如果启用验证，优先返回可用的代理
        if validate:
            valid_count = sum(1 for p in result if p["valid"])
            logger.info(f"[ProxyPool] 验证完成 - 总数: {len(result)}, 可用: {valid_count}")
        
        return result

    @staticmethod
    async def refresh_proxies(protocol: str = "all", count: int = DEFAULT_PROXY_COUNT, 
                             validate: bool = True) -> List[Dict[str, str]]:
        """刷新并获取新的代理列表
        
        Args:
            protocol: 代理协议类型
            count: 获取代理数量
            validate: 是否验证代理可用性
            
        Returns:
            代理列表
        """
        logger.info(f"[ProxyPool] 刷新代理池 - 协议: {protocol}, 数量: {count}, 验证: {validate}")
        
        proxies = await ProxyPool.fetch_and_validate(protocol, count, validate)
        
        if proxies:
            ProxyPool._proxy_list = proxies
            logger.info(f"[ProxyPool] 代理池已更新，当前 {len(ProxyPool._proxy_list)} 个代理")
            
            # 保存到配置（可选）
            try:
                await setting.save(grok_config={
                    "proxy_pool_last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "proxy_pool_count": len(proxies)
                })
            except Exception as e:
                logger.warning(f"[ProxyPool] 保存代理池信息到配置失败: {e}")
        
        return proxies

    @staticmethod
    def get_proxy_list() -> List[Dict[str, str]]:
        """获取当前代理列表
        
        Returns:
            当前缓存的代理列表
        """
        return ProxyPool._proxy_list

    @staticmethod
    def clear_proxy_list() -> None:
        """清空代理列表"""
        ProxyPool._proxy_list = []
        logger.info("[ProxyPool] 代理池已清空")
