from utils.redis_manager import RedisManager
import json
from loguru import logger

class UsersManager():
    _instance = None

    def __new__(cls, config=None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.init_users_manager(config)
        return cls._instance
    
    def init_users_manager(self, config=None):
        self.root_key = config["REDIS"]["ROOT_KEY"]
        self.redis = RedisManager(config)
        pattern = f"{self.root_key}:*"  # 构造匹配模式
        self.user_info_dict = {}
        for key in self.redis.redis_conn.scan_iter(match=pattern):
            try:
                # 示例键结构: "root_key:123:conversations" 或 "root_key:456:profile"
                key_str = key
                parts = key_str.split(':')
                
                # 确保至少包含 root_key 和 user_id 两部分
                if len(parts) >= 2:
                    user_id = parts[1]
                    user_info = UserInfo(config, user_id)
                    self.user_info_dict[user_id] = user_info
            except Exception as e:
                logger.error(f"解析键 {key} 时出错: {str(e)}")
                continue
        

class UserInfo(object):
    def __init__(self, config, user_id):
        self.user_id = user_id
        self.redis = RedisManager(config)
        self.conversation_key = f"{self.redis.root_key}:{self.user_id}:conversations"
        self.max_conversations = 8

    # ---------- List 操作 ----------
    def add_conversation(self, message: dict, direction: str = 'right') -> None:
        """向对话列表添加消息
        :param message:  消息内容（字典格式，如 {"role": "user", "content": "Hello"}）
        :param direction: 插入方向，'left'（最新消息在前）或 'right'（最新消息在后）
        """
        serialized = json.dumps(message)
        if direction == 'left':
            self.redis.redis_conn .lpush(self.conversation_key, serialized)
        else:
            self.redis.redis_conn .rpush(self.conversation_key, serialized)

    def get_conversations(self, start: int = 0, end: int = -1) -> list:
        """获取对话历史（支持分页）
        :param start: 起始索引（0 表示第一个元素）
        :param end:   结束索引（-1 表示最后一个元素）
        :return: 反序列化的消息列表
        """
        data = self.redis.redis_conn .lrange(self.conversation_key, start, end)
        return [json.loads(item) for item in data]

    def get_conversation_count(self) -> int:
        """获取对话消息总数"""
        return self.redis.redis_conn .llen(self.conversation_key)

    def trim_conversations(self) -> None:
        """修剪对话列表，保留最近的 max_length 条消息"""
        self.redis.redis_conn .ltrim(self.conversation_key, -self.max_conversations, -1)

