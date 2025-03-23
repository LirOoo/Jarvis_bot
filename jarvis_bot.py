from telegram import Update, Bot
from telegram.ext  import (Updater, CommandHandler, MessageHandler, Filters, CallbackContext)
import configparser 
from loguru import logger
import requests
from utils.ChatGPT_HKBU import HKBU_ChatGPT
from utils.books_searcher import GoogleBooksSearcher
from telegram.utils.request import Request
import json
import redis

# Telegram 聊天机器人主程序
# 功能：集成 ChatGPT 对话和 Google 图书搜索功能
# 主要流程：

# 读取配置文件
# 初始化网络连接
# 设置消息处理器
# 启动轮询服务

class JatvisBot:
    """核心机器人类，负责功能整合和消息处理"""
    def __init__(self, config_path):
        # Load config file
        self.config=configparser.ConfigParser()
        self.config.read(config_path)

        # 初始化 redis
        self.root_key = self.config["REDIS"]["ROOT_KEY"]
        self.redis_ins = redis.Redis(
            host=(self.config['REDIS']['HOST']), 
            password=(self.config['REDIS']['PASSWORD']), 
            port=(self.config['REDIS']['REDISPORT']), 
            decode_responses=(self.config['REDIS']['DECODE_RESPONSE']), 
            username=(self.config['REDIS']['USER_NAME']))
        
        # all_keys = self.redis_ins.keys('*')
        # logger.debug(f'Redis keys: {all_keys}')

        self.chatgpt = HKBU_ChatGPT(self.config) # ChatGPT 对话模块
        self.books_searcher = GoogleBooksSearcher() # 图书搜索模块

        # 初始化 Telegram 连接
        self.check_network() # 网络连通性测试
        self._init_telegram() # 创建机器人实例
        # 设置消息处理器
        self.updater = Updater(
            bot=self.telegram_chatbot,
            use_context=True
        )
        
        self._setup_handlers()

    def _init_telegram(self):
        """配置 Telegram 代理参数"""
        proxy_config = {
            'proxy_url': self.config.get('PROXY', 'url', fallback=None),
            'connect_timeout': 10,
            'read_timeout': 10,
            'con_pool_size': 20
        } if self.config.getboolean('PROXY', 'enable', fallback=False) else {}

        # 创建带代理配置的 Bot 实例
        request = Request(**proxy_config)
        self.telegram_chatbot = Bot(
            token=self.config['TELEGRAM']['ACCESS_TOKEN'],
            request=request
        )
        self._setup_handlers()
   
    def check_network(self):
        """测试 Telegram API 连通性"""
        response = requests.get(f"https://api.telegram.org/bot{self.config['TELEGRAM']['ACCESS_TOKEN']}/getMe") 
        logger.debug(response.text)
    
    def _setup_handlers(self):
        """注册消息处理回调函数"""
        self.updater = Updater(bot=self.telegram_chatbot, use_context=True)
        """Register all message handlers"""
        dispatcher = self.updater.dispatcher
        
        # 注册 命令处理器
        dispatcher.add_handler( # 注册 /search
            CommandHandler("search", 
                           self._books_search_handler))
        
        # 注册普通文本消息处理器（排除命令）
        dispatcher.add_handler(MessageHandler(
            Filters.text & (~Filters.command),
            self._chatgpt_handler
        ))

    def start(self):
        """启动机器人服务"""
        logger.info("Starting bot...")
        self.updater.start_polling()  # 开始轮询消息
        logger.info("Ready!")
        self.updater.idle() # 保持运行状态

    # def _add_command_handler(self, update: Update, context: CallbackContext):
    #     """process /add command"""
    #     try:
    #         keyword = context.args[0]
    #         logger.info(f"Add Keyword '{keyword}'")
    #         self.cache_data[keyword] = self.cache_data[keyword] + 1 if keyword in self.cache_data else 1
    #         update.message.reply_text(
    #             f"'{keyword}' have {self.cache_data[keyword]} times"
    #         )
    #     except (IndexError, ValueError):
    #         update.message.reply_text("usage: /add <keyword>")

    def _chatgpt_handler(self, update: Update, context: CallbackContext):
        """处理普通文本消息（调用 ChatGPT）"""
        user_input = update.message.text
        user_id = str(update.effective_user.id)  # 获取用户唯一ID
        logger.info(f"Processing ChatGPT request: {user_input}")
        response = self.chatgpt.submit(user_input, user_id)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response
        )

    def _books_search_handler(self, update: Update, context: CallbackContext):
            """处理 /search 命令（图书搜索）"""
            # user_input = update.message.text
            user_input = update.message.text
            user_id = update.effective_user.id
            logger.debug(f"Books searching request: {user_input}")

            # 使用 ChatGPT 提取结构化查询参数
            self.search_prompt = f"请从用户需求提取以下信息(JSON格式), 用户需求: {user_input} \
               格式：{self.books_searcher.query_format}，注意，返回的结果必须我能直接转成dict的"
            extracted = self.chatgpt.submit(self.search_prompt, user_id)
            logger.debug(f"Extracted: {extracted}")
            
            # 解析并执行图书搜索
            query = parse_json_string(extracted)
            logger.debug(f"query: {query}")
            response = self.books_searcher.search(query)
            logger.debug(f"Response: {response}")
            
            # 使用 ChatGPT 整理搜索结果
            self.result_prompt = f"请从下面返回的查询的数据整理出合适的回答(附带超链接), 查询的数据：{response}"
            result = self.chatgpt.submit(self.result_prompt, user_id)
            context.bot.send_message(
                chat_id=user_id,
                text=result
            )
    

def parse_json_string(json_str):
    """解析包含JSON结构的字符串，提取最外层{}间的内容并转为字典"""
    # 定位第一个'{'和最后一个'}'的位置
    start_idx = json_str.find('{')
    end_idx = json_str.rfind('}')

    # 检查是否找到有效区间
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        logger.error(f"JSON结构识别失败 | 原始内容: {json_str}")
        return {}

    try:
        # 提取并解析JSON内容
        json_snippet = json_str[start_idx:end_idx+1]
        return json.loads(json_snippet)
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败 | 错误: {e} | 片段内容: {json_snippet}")
        return {}
    
    
if __name__=='__main__':
    logger.info("All starting")
    bot = JatvisBot('config.ini')
    bot.start()
