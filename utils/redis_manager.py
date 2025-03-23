import redis
import json
from typing import Dict, List, Optional
from loguru import logger

class RedisManager:
    _instance = None

    def __new__(cls, config=None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.init_redis(config)
        return cls._instance
    

    def init_redis(self, config):
        """初始化 Redis 连接"""
        self.root_key = config["REDIS"]["ROOT_KEY"]
        self.root_key = config["REDIS"]["ROOT_KEY"]
        self.redis_conn = redis.Redis(
            host=config['REDIS']['HOST'],
            port=int(config['REDIS']['REDISPORT']),
            password=config['REDIS']['PASSWORD'],
            decode_responses=True,
            username=config['REDIS']['USER_NAME']
        )
        # 检查根键是否存在，不存在则初始化空字典（序列化为 JSON）
        if not self.redis_conn.exists(self.root_key):
            self.redis_conn.set(self.root_key, json.dumps({}))  # 序列化字典
            logger.info(f"Redis connected and root key '{self.root_key}' created.")
        else:
            # 获取所有以 root_key 开头的键（注意：需要调整实际存储结构）
            all_keys = self.redis_conn.keys(f"{self.root_key}:*")
            logger.info(f"Redis connected. Found {len(all_keys)} keys under '{self.root_key}': {all_keys}")