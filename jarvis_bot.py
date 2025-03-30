from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext  import (Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext)
import configparser 
from loguru import logger
import requests
from utils.ChatGPT_HKBU import HKBU_ChatGPT
from utils.books_searcher import GoogleBooksSearcher
from utils.user_info import UserInfo, UsersManager
from telegram.utils.request import Request
import json
import redis
import sys
from gensim.models import Word2Vec
from sklearn.metrics.pairwise import cosine_similarity
import os

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
        self.users_manager = UsersManager(self.config)

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
        self.users_maneger = UsersManager(self.config)

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
        dispatcher.add_handler( # 注册 /recommend 命令
            CommandHandler("recommend", 
                           self._recommend_handler)) 
        
        dispatcher.add_handler( # 注册设置用户名命令
            CommandHandler("set_username", self._set_username_handler)
        )
        # 注册普通文本消息处理器（排除命令）
        dispatcher.add_handler(MessageHandler(
            Filters.text & (~Filters.command),
            self._chatgpt_handler
        ))
        # 注册 callback query 处理器
        dispatcher.add_handler(
            CallbackQueryHandler(
                self._handle_add_friend, 
                pattern="add_friend_"))

    def start(self):
        """启动机器人服务"""
        logger.info("Starting bot...")

        # 获取端口，默认为 8080
        port = int(os.environ.get("PORT", 8080))

        self.updater.start_polling()  # 开始轮询消息
        logger.info("Ready!")
        self.updater.idle() # 保持运行状态

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
            user_id = str(update.effective_user.id)
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
    

    def _recommend_handler(self, update: Update, context: CallbackContext):
        """处理 /recommend 命令（用户推荐）"""
        user_id = str(update.effective_user.id)
        logger.debug(f"User {user_id} requested recommendations")
        
        # 获取当前用户的兴趣向量
        user_info = self.users_manager.user_info_dict.get(user_id)
        if not user_info:
            update.message.reply_text("无法找到您的兴趣信息，请先进行一些互动或搜索书籍。")
            return
        
        user_vector = user_info.get_interests_vector()
        if user_vector is None:
            update.message.reply_text("您尚未提供足够的兴趣信息，请先进行搜索或聊天。")
            return

        # 查找其他相似用户（计算兴趣向量之间的余弦相似度）
        matching_users = self._find_matching_users(user_id, user_vector)

        # 如果找到匹配的用户，返回其简介和按钮
        if matching_users:
            match_text = "以下是与您兴趣相似的用户：\n"
            
            keyboard = []
            for user in matching_users:
                # Add an inline button for each user with user_id as callback data
                button = InlineKeyboardButton(
                    f"用户名: {user['username']}",
                    callback_data=f"add_friend_{user['username']}"
                )
                keyboard.append([button])  # Add button to keyboard layout
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(match_text, reply_markup=reply_markup)
        else:
            update.message.reply_text("抱歉，暂时没有找到与您兴趣相似的用户。")

    def _find_matching_users(self, query_user_id, user_vector: list) -> list:
        """根据兴趣匹配其他用户"""
        all_users = self.users_manager.user_info_dict
        matching_users = []

        for user_id, user_info in all_users.items():
            if query_user_id == user_info.user_id:  # Skip the current user
                continue
            other_user_vector = user_info.load_interests_vector()
            logger.debug(f"Found user with id {user_info.user_id}: {type(other_user_vector)}")
            if other_user_vector is not None:
                # 计算兴趣向量之间的余弦相似度
                similarity = cosine_similarity([user_vector], [other_user_vector])
                logger.debug(f"query_user_id: { query_user_id}, id {user_id} similarity: {similarity}")
                if similarity > 0.7:  # 可以根据需要调整相似度阈值
                    matching_users.append({
                        'username': user_id,
                    })
            else:
                logger.debug(f"User {user_id} interests vector is None")
        return matching_users


    def _handle_add_friend(self, update: Update, context: CallbackContext):
        query = update.callback_query
        user_id = str(update.effective_user.id)
        target_id = query.data.split("_")[-1]  # 从回调数据中提取目标用户名
        logger.info(f"User {user_id} wants to add user {target_id} as a friend")
        
        
        user_info = self.users_manager.user_info_dict.get(user_id)
        target_user_info = self.users_manager.user_info_dict.get(target_id)
        if not target_user_info:
            context.bot.send_message(
                chat_id=user_id,
                text=f"无法找到用户名为 {target_id} 的用户，可能是该用户未与机器人互动。"
            )
            return
        
        username = user_info.get_username()
        if username:
            chat_link = f"https://t.me/{username}"  # 查询者的聊天链接
            
            # 确认点击按钮
            query.answer()
            
            try:
                # 发送聊天链接给候选人（目标用户）
                context.bot.send_message(
                    chat_id=target_id,  # 发送给目标用户
                    text=f"用户 {user_id} 想要加您为好友，您可以通过点击以下链接直接与他聊天：\n{chat_link}\n\n如果您愿意和此用户建立联系，请点击链接，或者忽略此消息。"
                )
                
                # 发送消息给查询方，告知他们链接已发送
                context.bot.send_message(
                    chat_id=user_id,
                    text=f"您已请求添加 {target_id} 为好友！链接已发送给对方，等待对方的回应。"
                )
                
            except Exception as e:
                logger.error(f"Error sending message to {target_id}: {str(e)}")
                context.bot.send_message(
                    chat_id=user_id,
                    text=f"无法向 {target_id} 发送消息，可能是对方未与机器人互动或已屏蔽此机器人。"
                )
        else:
            context.bot.send_message(
                chat_id=user_id,
                text=f"您还没有设置用户名，无法生成链接给对方联系，请先去设置用户名吧。"
            )


    def _set_username_handler(self, update: Update, context: CallbackContext):
        """处理 /set_username 命令（设置用户名）"""
        user_id = str(update.effective_user.id)
        user_input = update.message.text.strip().split()  # 获取用户输入的用户名
        if len(user_input) <= 1:
            update.message.reply_text("请输入一个有效的用户名。")
        user_name = user_input[1]
        # 判断用户输入是否有效
        if not user_name or len(user_name) < 3:
            update.message.reply_text("请输入一个有效的用户名（至少3个字符）。")
            return
        
        # 存储用户名到用户信息
        user_info = self.users_manager.user_info_dict.get(user_id)
        if not user_info:
            user_info = UserInfo(self.config, user_id)
            self.user_info_dict[user_id] = user_info
            
            
        self.users_manager.user_info_dict[user_id].set_username(user_name)
        update.message.reply_text(f"用户名设置为：{user_name}")
        
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
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")  # 设置终端日志等级为 INFO
    logger.add("logfile.log", level="DEBUG", rotation="200 MB", compression="zip")  # 当文件超过 500 MB 时会进行滚动，并且压缩旧日志
    logger.info("*"*50+"All starting"+"*"*50)
    bot = JatvisBot('config.ini')
    bot.start()
