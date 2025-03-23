from utils.redis_manager import RedisManager
import json

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

