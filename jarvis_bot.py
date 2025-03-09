from telegram import Update, Bot
from telegram.ext  import (Updater, CommandHandler, MessageHandler, Filters, CallbackContext)
import configparser 
from loguru import logger
import requests
from utils.ChatGPT_HKBU import HKBU_ChatGPT
from utils.books_searcher import GoogleBooksSearcher
from telegram.utils.request import Request
import json


class JatvisBot:
    def __init__(self, config_path):
        # Load config file
        self.config=configparser.ConfigParser()
        self.config.read(config_path)
        self.chatgpt = HKBU_ChatGPT(self.config)
        self.books_searcher = GoogleBooksSearcher()

        # Telegram updater 
        self.check_network()
        self._init_telegram()
        self.updater = Updater(
            bot=self.telegram_chatbot,
            use_context=True
        )
        
        self._setup_handlers()

    def _init_telegram(self):
        proxy_config = {
            'proxy_url': self.config.get('PROXY', 'url', fallback=None),
            'connect_timeout': 10,
            'read_timeout': 10,
            'con_pool_size': 20
        } if self.config.getboolean('PROXY', 'enable', fallback=False) else {}

        request = Request(**proxy_config)
        self.telegram_chatbot = Bot(
            token=self.config['TELEGRAM']['ACCESS_TOKEN'],
            request=request
        )
        self._setup_handlers()
   
    def check_network(self):
        response = requests.get(f"https://api.telegram.org/bot{self.config['TELEGRAM']['ACCESS_TOKEN']}/getMe") 
        logger.debug(response.text)
    
    def _setup_handlers(self):
        self.updater = Updater(bot=self.telegram_chatbot, use_context=True)
        """Register all message handlers"""
        dispatcher = self.updater.dispatcher
        
        # Command processor
        dispatcher.add_handler(
            CommandHandler("search", 
                           self._books_search_handler))
        
        # Message handler
        dispatcher.add_handler(MessageHandler(
            Filters.text & (~Filters.command),
            self._chatgpt_handler
        ))

    def start(self):
        """Start up the server"""
        logger.info("Starting bot...")
        self.updater.start_polling()
        logger.info("Ready!")
        self.updater.idle()

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
        """ChatGPT api handler"""
        user_input = update.message.text
        logger.info(f"Processing ChatGPT request: {user_input}")
        response = self.chatgpt.submit(user_input)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response
        )

    def _books_search_handler(self, update: Update, context: CallbackContext):
            """google books search handler"""
            # user_input = update.message.text
            user_input = update.message.text
            user_id = update.effective_user.id
            logger.debug(f"Books searching request: {user_input}")
            self.search_prompt = f"请从用户需求提取以下信息(JSON格式), 用户需求: {user_input} \
               格式：{self.books_searcher.query_format}，注意，返回的结果必须我能直接转成dict的"
            extracted = self.chatgpt.submit(self.search_prompt)
            logger.debug(f"Extracted: {extracted}")
            query = parse_json_string(extracted)
            logger.debug(f"query: {query}")
            response = self.books_searcher.search(query)
            logger.debug(f"Response: {response}")
            self.result_prompt = f"请从下面返回的查询的数据整理出合适的回答(附带超链接), 查询的数据：{response}"
            result = self.chatgpt.submit(self.result_prompt)
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
