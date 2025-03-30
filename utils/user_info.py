from utils.redis_manager import RedisManager
import json
from loguru import logger
from gensim.models import Word2Vec
import jieba
import numpy as np

# 核心是一个{user_id: UserInfo}实例的的字典，全局唯一（单例模式）
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
        self.create_model_and_vw()


    # create model and calculate vw for every user
    def create_model_and_vw(self):
        """为每个用户创建 Word2Vec 模型并计算兴趣向量"""
        logger.info("开始为每个用户创建模型和计算兴趣向量")
        for user_id, user_info in self.user_info_dict.items():
            logger.info(f"正在处理用户 {user_id} 的兴趣向量")
            if user_info.load_interests_vector() is None:
                # 获取该用户的所有对话历史
                conversations = user_info.get_conversations()
                all_keywords = []
                
                # 从对话历史中提取所有关键词
                for convo in conversations:
                    message = convo.get('content', '')
                    keywords = list(jieba.cut(message))  # 使用jieba分词
                    all_keywords.extend(keywords)
                
                if all_keywords:
                    # 使用提取的关键词训练 Word2Vec 模型
                    model = Word2Vec([all_keywords], vector_size=100, window=5, min_count=1, workers=4)
                    user_info.model = model  # 更新用户的 Word2Vec 模型
                    
                    # 计算并保存兴趣向量
                    interests_vector = user_info.calculate_interests_vector()
                    if interests_vector is not None:
                        user_info.save_interests_vector()  # 将兴趣向量保存到Redis
                    else:
                        logger.warning(f"用户 {user_id} 的兴趣向量计算失败。")
                else:
                    logger.warning(f"用户 {user_id} 没有有效的对话历史，跳过兴趣向量计算。")
        
        logger.info("所有用户的兴趣向量计算完成")
        



# 所有user相关的读写都在UserInfo类内
class UserInfo(object):
    def __init__(self, config, user_id):
        self.user_id = str(user_id)
        self.redis = RedisManager(config)
        self.conversation_key = f"{self.redis.root_key}:{self.user_id}:conversations"
        self.max_conversations = 8
        self.interest_key = f"{self.redis.root_key}:{self.user_id}:interests_vector"
        self.username_key = f"{self.redis.root_key}:{self.user_id}:username"  # 新增字段
        self.model = None  # Gensim Word2Vec model



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
        self._extract_and_update_interests(message['content'])


    def _extract_and_update_interests(self, message: str):
        """从消息中提取兴趣关键词并存储到 Redis"""
        keywords = list(jieba.cut(message))  # 使用 jieba 分词，返回一个列表
        if self.model is None:
            self.model = Word2Vec([keywords], vector_size=100, window=5, min_count=1, workers=4)
        else:
            self.model.build_vocab([keywords], update=True)
            self.model.train([keywords], total_examples=1, epochs=10)
        self.save_interests_vector()

    def calculate_interests_vector(self):
        """返回当前用户的兴趣向量"""
        if self.model and self.model.wv:
            # 计算当前用户的兴趣向量（简单地将所有词向量求平均）
            words = list(self.model.wv.index_to_key)
            logger.debug(f"word: {words}")
            vectors = [self.model.wv[word] for word in words]
            for word, wv in zip(words, vectors):
                logger.debug(f"wv: {word} {wv.shape}")
            if vectors:
                avg_vector = np.sum(vectors, axis=0) / len(vectors)
                logger.debug(f"Average vector shape: {avg_vector.shape}")
            return avg_vector  # 直接返回 numpy 数组
        else:
            
            logger.error(f"Word2Vec model not found., model is {self.model is not None}, is {getattr(self.model, 'wv', None) is not None}")
            return None  # 未找到 Word2Vec model
    
    def get_interests_vector(self):
        word_vector = self.load_interests_vector()
        return word_vector if word_vector is not None else self.calculate_interests_vector()  # 若 Redis 未保存兴趣向量，则重新计算并返回


    def save_interests_vector(self):
        """保存兴趣向量到 Redis"""
        if self.model:
            interests_vector = self.calculate_interests_vector()
            self.redis.redis_conn.set(self.interest_key, json.dumps(interests_vector.tolist()))
        else:
            logger.error("Try to save interest vector, but no model is available")


    def load_interests_vector(self):
        """从 Redis 加载兴趣向量"""
        stored_vector = self.redis.redis_conn.get(self.interest_key)
        if stored_vector:
            return np.array(json.loads(stored_vector))
        return None
    

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

    def set_username(self, username: str):
        """保存用户名到 Redis"""
        self.redis.redis_conn.set(self.username_key, username)

    # 获取用户名
    def get_username(self):
        """从 Redis 加载用户名"""
        return self.redis.redis_conn.get(self.username_key)
    
    def trim_conversations(self) -> None:
        """修剪对话列表，保留最近的 max_length 条消息"""
        self.redis.redis_conn .ltrim(self.conversation_key, -self.max_conversations, -1)
