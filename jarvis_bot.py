from telegram import Update, Bot
from telegram.ext  import (Updater, CommandHandler, MessageHandler, Filters, CallbackContext)
import configparser 
from loguru import logger
import requests
from ChatGPT_HKBU import HKBU_ChatGPT
from telegram.utils.request import Request



class JatvisBot:
    def __init__(self, config_path):
        # Load config file
        self.config=configparser.ConfigParser()
        self.config.read(config_path)
        self.cache_data = {}
        # Telegram updater 
        self.check_network()
        request = Request(
            proxy_url='http://127.0.0.1:7897',  # HTTP代理地址
            connect_timeout=10,
            read_timeout=10,
            con_pool_size=20
        )
        bot = Bot(
            token=self.config['TELEGRAM']['ACCESS_TOKEN'],
            request=request 
        )
        self.updater = Updater(
            bot=bot,
            use_context=True
        )
        self.chatgpt = HKBU_ChatGPT(self.config)
        
        self._setup_handlers()

   
    def check_network(self):
        response = requests.get(f"https://api.telegram.org/bot{self.config['TELEGRAM']['ACCESS_TOKEN']}/getMe") 
        logger.debug(response.text)
    
    def _setup_handlers(self):
        """Register all message handlers"""
        dispatcher = self.updater.dispatcher
        
        # Command processor
        dispatcher.add_handler(CommandHandler("add", self._add_command))
        
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

    def _add_command(self, update: Update, context: CallbackContext):
        """process /add command"""
        try:
            keyword = context.args[0]
            logger.info(f"Add Keyword '{keyword}'")
            self.cache_data[keyword] = self.cache_data[keyword] + 1 if keyword in self.cache_data else 1
            update.message.reply_text(
                f"'{keyword}' have {self.cache_data[keyword]} times"
            )
        except (IndexError, ValueError):
            update.message.reply_text("usage: /add <keyword>")

    def _chatgpt_handler(self, update: Update, context: CallbackContext):
        """处理ChatGPT请求"""
        user_input = update.message.text
        logger.info(f"Processing ChatGPT request: {user_input}")
        response = self.chatgpt.submit(user_input)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response
        )

if __name__=='__main__':
    logger.info("All starting")
    bot = JatvisBot('config.ini')
    bot.start()
