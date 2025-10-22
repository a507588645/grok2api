"""配置管理器"""

import toml
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    """配置管理器"""

    def __init__(self) -> None:
        """初始化"""

        # 配置文件路径
        self.config_path: Path = Path(__file__).parents[2] / "data" / "setting.toml"

        # 确保配置文件存在（某些平台会使用空数据卷覆盖 /app/data，导致默认文件丢失）
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            default_config: Dict[str, Any] = {
                "grok": {
                    "api_key": "",
                    "proxy_url": "",
                    "temporary": True,
                    "cf_clearance": "",
                    "x_statsig_id": "ZTpUeXBlRXJyb3I6IENhbm5vdCByZWFkIHByb3BlcnRpZXMgb2YgdW5kZWZpbmVkIChyZWFkaW5nICdjaGlsZE5vZGVzJyk=",
                    "filtered_tags": "xaiartifact,xai:tool_usage_card,grok:render",
                    "stream_chunk_timeout": 120,
                    "stream_total_timeout": 600,
                    "stream_first_response_timeout": 30,
                    "proxy_pool_enabled": False,
                    "proxy_pool_protocol": "all",
                    "proxy_pool_count": 5,
                    "proxy_pool_auto_validate": True,
                },
                "global": {
                    "base_url": "",
                    "log_level": "DEBUG",
                    "image_mode": "url",
                    "admin_password": "admin",
                    "admin_username": "admin",
                    "image_cache_max_size_mb": 512,
                    "video_cache_max_size_mb": 1024,
                },
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(toml.dumps(default_config))

        # 加载配置
        self.global_config: Dict[str, Any] = self.load("global")
        self.grok_config: Dict[str, Any] = self.load("grok")
        self._storage = None

    def set_storage(self, storage) -> None:
        """设置存储实例"""
        self._storage = storage

    def load(self, section: str) -> Dict[str, Any]:
        """配置加载器"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = toml.load(f)[section]

                # 自动将 SOCKS5 转换为 SOCKS5H
                if section == "grok" and "proxy_url" in config:
                    proxy_url = config["proxy_url"]
                    if proxy_url and proxy_url.startswith("socks5://"):
                        config["proxy_url"] = proxy_url.replace("socks5://", "socks5h://", 1)

                # 自动为 CF Clearance 添加前缀
                if section == "grok" and "cf_clearance" in config:
                    cf_clearance = config["cf_clearance"]
                    if cf_clearance and not cf_clearance.startswith("cf_clearance="):
                        config["cf_clearance"] = f"cf_clearance={cf_clearance}"

                return config
        except Exception as e:
            raise Exception(f"[Setting] 配置加载失败: {e}")
    
    async def reload(self) -> None:
        """重新加载配置（用于从存储同步后）"""
        self.global_config = self.load("global")
        self.grok_config = self.load("grok")

    async def save(self, global_config: Dict[str, Any] = None, grok_config: Dict[str, Any] = None) -> None:
        """保存配置到存储"""
        if not self._storage:
            # 如果没有设置存储，使用传统文件保存方式
            import aiofiles
            async with aiofiles.open(self.config_path, "r", encoding="utf-8") as f:
                content = await f.read()
                config = toml.loads(content)
            
            if global_config:
                config["global"].update(global_config)
            if grok_config:
                # 处理 cf_clearance，移除前缀后保存
                processed_grok_config = grok_config.copy()
                if "cf_clearance" in processed_grok_config:
                    cf_clearance = processed_grok_config["cf_clearance"]
                    if cf_clearance and cf_clearance.startswith("cf_clearance="):
                        processed_grok_config["cf_clearance"] = cf_clearance.replace("cf_clearance=", "", 1)
                config["grok"].update(processed_grok_config)
            
            async with aiofiles.open(self.config_path, "w", encoding="utf-8") as f:
                await f.write(toml.dumps(config))
        else:
            # 使用存储抽象层
            config_data = await self._storage.load_config()
            
            if global_config:
                config_data["global"].update(global_config)
            if grok_config:
                # 处理 cf_clearance，移除前缀后保存
                processed_grok_config = grok_config.copy()
                if "cf_clearance" in processed_grok_config:
                    cf_clearance = processed_grok_config["cf_clearance"]
                    if cf_clearance and cf_clearance.startswith("cf_clearance="):
                        processed_grok_config["cf_clearance"] = cf_clearance.replace("cf_clearance=", "", 1)
                config_data["grok"].update(processed_grok_config)
            
            await self._storage.save_config(config_data)
        
        # 重新加载配置
        await self.reload()
    
    def get_service_proxy(self) -> str:
        """获取服务代理URL（用于 client 和 upload）"""
        return self.grok_config.get("proxy_url", "")
    
    def get_cache_proxy(self) -> str:
        """获取缓存代理URL（用于 cache）
        
        逻辑：
        - 如果只设置了 proxy_url，缓存和服务都使用 proxy_url
        - 如果同时设置了 proxy_url 和 cache_proxy_url，缓存使用 cache_proxy_url
        """
        cache_proxy = self.grok_config.get("cache_proxy_url", "")
        service_proxy = self.grok_config.get("proxy_url", "")
        
        # 如果设置了 cache_proxy_url，优先使用
        if cache_proxy:
            return cache_proxy
        
        # 否则使用 proxy_url（服务代理）
        return service_proxy

# 全局设置
setting = ConfigManager()

if __name__ == "__main__":
    print(setting.global_config)
    print(setting.grok_config)