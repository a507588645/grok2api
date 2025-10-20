"""Cloudflare cf_clearance 自动获取模块"""

import asyncio
from typing import Optional
from datetime import datetime

from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import setting

IMPERSONATE_BROWSER = "chrome133a"


class CloudflareClearance:
    """管理 Cloudflare cf_clearance 的自动获取与刷新"""

    _lock = asyncio.Lock()
    _last_error: Optional[str] = None

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
        
        Returns:
            新的 cf_clearance 值（不含前缀），若失败返回 None
        """
        async with CloudflareClearance._lock:
            try:
                proxy_url = setting.get_service_proxy()
                # 若未配置代理，明确禁用环境代理
                proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}
                if proxy_url:
                    logger.debug(f"[CF] 使用代理获取 cf_clearance: {CloudflareClearance._mask_proxy(proxy_url)}")
                else:
                    logger.debug("[CF] 未配置代理，获取 cf_clearance 时禁用环境代理变量")

                headers = {
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

                first_status = None
                second_status = None

                async with AsyncSession() as session:
                    # 访问主页尝试通过 Cloudflare 验证
                    resp = await session.get(
                        "https://grok.com/",
                        headers=headers,
                        impersonate=IMPERSONATE_BROWSER,
                        proxies=proxies,
                        allow_redirects=True,
                        timeout=30,
                    )
                    first_status = getattr(resp, "status_code", None)
                    logger.debug(f"[CF] 访问 grok.com 返回状态: {resp.status_code}")

                    # 若未拿到，尝试访问静态资源域名
                    cf_value = CloudflareClearance._extract_cf_clearance(session)
                    if not cf_value:
                        resp2 = await session.get(
                            "https://assets.grok.com/favicon.ico",
                            headers=headers,
                            impersonate=IMPERSONATE_BROWSER,
                            proxies=proxies,
                            allow_redirects=True,
                            timeout=30,
                        )
                        second_status = getattr(resp2, "status_code", None)
                        logger.debug(f"[CF] 访问 assets.grok.com 返回状态: {resp2.status_code}")
                        cf_value = CloudflareClearance._extract_cf_clearance(session)

                if cf_value:
                    # 保存到配置（ConfigManager.save 会自动去掉前缀存储、reload 后添加前缀）
                    await setting.save(
                        grok_config={
                            "cf_clearance": f"cf_clearance={cf_value}",
                            "cf_last_error": "",
                            "cf_last_success_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    )
                    CloudflareClearance._last_error = None
                    logger.info("[CF] 已自动获取并保存 cf_clearance")
                    return cf_value
                else:
                    # 记录失败信息并持久化
                    proxy_hint = CloudflareClearance._mask_proxy(proxy_url) if proxy_url else "未使用代理"
                    message = (
                        f"自动获取 cf_clearance 失败。访问 grok.com 状态: {first_status}; "
                        f"assets.grok.com 状态: {second_status}; 代理: {proxy_hint}。"
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
            except Exception as e:
                # 记录异常详情
                CloudflareClearance._last_error = f"获取 cf_clearance 异常: {type(e).__name__}: {e}"
                try:
                    await setting.save(grok_config={
                        "cf_last_error": CloudflareClearance._last_error,
                        "cf_last_error_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except Exception as se:
                    logger.warning(f"[CF] 记录失败信息到配置时出错: {se}")
                logger.error(f"[CF] 获取 cf_clearance 过程中发生异常: {e}")
                return None

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
