"""Cloudflare cf_clearance 自动获取模块"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import setting

# 支持的浏览器配置列表
BROWSER_PROFILES = ["chrome133a", "chrome131", "chrome124", "safari17_2_ios"]

# 多种获取方法的端点配置
ACQUISITION_METHODS = [
    {
        "name": "主页访问法",
        "urls": ["https://grok.com/"],
        "browser": "chrome133a",
        "description": "访问Grok主页获取cf_clearance"
    },
    {
        "name": "静态资源法",
        "urls": ["https://assets.grok.com/favicon.ico"],
        "browser": "chrome133a",
        "description": "通过静态资源域名获取cf_clearance"
    },
    {
        "name": "API端点法",
        "urls": ["https://grok.com/rest/health"],
        "browser": "chrome133a",
        "description": "通过API健康检查端点获取cf_clearance"
    },
    {
        "name": "组合访问法",
        "urls": ["https://grok.com/", "https://assets.grok.com/favicon.ico"],
        "browser": "chrome133a",
        "description": "顺序访问主页和静态资源获取cf_clearance"
    },
    {
        "name": "Safari模拟法",
        "urls": ["https://grok.com/"],
        "browser": "safari17_2_ios",
        "description": "模拟Safari浏览器访问获取cf_clearance"
    },
    {
        "name": "Chrome131回退法",
        "urls": ["https://grok.com/"],
        "browser": "chrome131",
        "description": "使用Chrome 131浏览器配置获取cf_clearance"
    },
    {
        "name": "多端点轮询法",
        "urls": [
            "https://grok.com/",
            "https://assets.grok.com/favicon.ico",
            "https://grok.com/rest/health"
        ],
        "browser": "chrome124",
        "description": "使用Chrome 124轮询多个端点获取cf_clearance"
    },
]


class CloudflareClearance:
    """管理 Cloudflare cf_clearance 的自动获取与刷新"""

    _lock = asyncio.Lock()
    _last_error: Optional[str] = None

    @staticmethod
    def get_available_methods() -> List[Dict[str, str]]:
        """获取所有可用的获取方法列表
        
        Returns:
            方法列表，每个方法包含 name 和 description
        """
        return [
            {"name": m["name"], "description": m.get("description", "")}
            for m in ACQUISITION_METHODS
        ]

    @staticmethod
    def _mask_proxy(proxy_url: str) -> str:
        if not proxy_url:
            return ""
        return proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url

    @staticmethod
    async def ensure() -> Optional[str]:
        """确保已有可用的 cf_clearance，如果没有则尝试自动获取
        
        Returns:
            最新获取到的 cf_clearance 值（不含前缀），若失败返回 None
        """
        current = setting.grok_config.get("cf_clearance", "") or ""
        if current:
            # 已配置，直接返回（去掉前缀）
            if current.startswith("cf_clearance="):
                return current.split("=", 1)[1]
            return current
        return await CloudflareClearance.refresh()

    @staticmethod
    async def refresh() -> Optional[str]:
        """强制刷新 cf_clearance 并保存到配置
        
        使用多种方法依次尝试获取 cf_clearance，提高成功率
        
        Returns:
            新的 cf_clearance 值（不含前缀），若失败返回 None
        """
        async with CloudflareClearance._lock:
            proxy_url = setting.get_service_proxy()
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}
            
            if proxy_url:
                logger.debug(f"[CF] 使用代理获取 cf_clearance: {CloudflareClearance._mask_proxy(proxy_url)}")
            else:
                logger.debug("[CF] 未配置代理，获取 cf_clearance 时禁用环境代理变量")
            
            # 尝试所有配置的获取方法
            for i, method in enumerate(ACQUISITION_METHODS, 1):
                logger.debug(f"[CF] 尝试方法 {i}/{len(ACQUISITION_METHODS)}: {method['name']}")
                
                try:
                    cf_value = await CloudflareClearance._try_method(method, proxies)
                    
                    if cf_value:
                        # 成功获取，保存到配置
                        await setting.save(
                            grok_config={
                                "cf_clearance": f"cf_clearance={cf_value}",
                                "cf_last_error": "",
                                "cf_last_success_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "cf_last_method": method['name']
                            }
                        )
                        CloudflareClearance._last_error = None
                        logger.info(f"[CF] 成功通过 '{method['name']}' 获取并保存 cf_clearance")
                        return cf_value
                    
                except Exception as e:
                    logger.warning(f"[CF] 方法 '{method['name']}' 执行异常: {type(e).__name__}: {e}")
                
                # 在方法之间添加短暂延迟，避免过于频繁的请求
                if i < len(ACQUISITION_METHODS):
                    await asyncio.sleep(0.5)
            
            # 所有方法都失败
            proxy_hint = CloudflareClearance._mask_proxy(proxy_url) if proxy_url else "未使用代理"
            message = (
                f"所有 {len(ACQUISITION_METHODS)} 种自动获取方法均失败。代理: {proxy_hint}。"
                "建议在后台手动配置或更换代理/IP"
            )
            CloudflareClearance._last_error = message
            
            try:
                await setting.save(grok_config={
                    "cf_last_error": message,
                    "cf_last_error_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            except Exception as se:
                logger.warning(f"[CF] 记录失败信息到配置时出错: {se}")
            
            logger.warning("[CF] " + message)
            return None

    @staticmethod
    async def _try_method(method: Dict[str, Any], proxies: Dict[str, str]) -> Optional[str]:
        """尝试单个获取方法
        
        Args:
            method: 方法配置字典
            proxies: 代理配置
            
        Returns:
            cf_clearance 值或 None
        """
        headers = CloudflareClearance._build_headers(method.get("browser", "chrome133a"))
        browser_profile = method.get("browser", "chrome133a")
        urls = method.get("urls", [])
        
        async with AsyncSession() as session:
            for url in urls:
                try:
                    resp = await session.get(
                        url,
                        headers=headers,
                        impersonate=browser_profile,
                        proxies=proxies,
                        allow_redirects=True,
                        timeout=30,
                    )
                    logger.debug(f"[CF] 访问 {url} 返回状态: {resp.status_code}")
                    
                    # 检查是否获取到 cf_clearance
                    cf_value = CloudflareClearance._extract_cf_clearance(session)
                    if cf_value:
                        return cf_value
                        
                except Exception as e:
                    logger.debug(f"[CF] 访问 {url} 失败: {e}")
                    continue
            
            # 最后再检查一次会话中的 cookie
            return CloudflareClearance._extract_cf_clearance(session)
    
    @staticmethod
    def _build_headers(browser: str) -> Dict[str, str]:
        """根据浏览器类型构建请求头
        
        Args:
            browser: 浏览器类型标识
            
        Returns:
            请求头字典
        """
        # Safari iOS 特殊请求头
        if "safari" in browser.lower():
            return {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
            }
        
        # Chrome 默认请求头
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    @staticmethod
    def _extract_cf_clearance(session: AsyncSession) -> Optional[str]:
        """从会话 Cookie 中提取 cf_clearance 值"""
        try:
            for c in session.cookies:
                try:
                    if c.name.lower() == "cf_clearance" and ("grok.com" in (c.domain or "")):
                        return c.value
                except Exception:
                    continue
        except Exception:
            pass
        return None
