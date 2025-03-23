import configparser
import requests
from loguru import logger
from utils.redis_manager import RedisManager
from utils.user_info import UserInfo, UsersManager

class HKBU_ChatGPT():
    """封装 ChatGPT 请求的专用类"""
    def __init__(self,config_='./config.ini'):
        """初始化配置
        参数：
            config_ - 配置路径或 ConfigParser 对象
        """
        if type(config_) == str:
            self.config = configparser.ConfigParser()
            self.config.read(config_)
        elif type(config_) == configparser.ConfigParser:
            self.config = config_
        self.root_key = self.config["REDIS"]["ROOT_KEY"]
        self.redis_manager = RedisManager(self.config)  # Redis 连接管理器
        self.users_maneger = UsersManager(self.config)

    def submit(self, message, user_id):
        """提交消息到 ChatGPT API
        参数：
            message - 用户输入的文本
        返回：
            ChatGPT 生成的回复内容
        """
        # if user_id not in self.user_conversations:
        #     self.user_conversations[user_id] = []
        # self.user_conversations[user_id].append({"role": "user", "content": message})
        
        
        # 构造 API 请求 URL
        url = (self.config['CHATGPT']['BASICURL']) + \
        "/deployments/" + (self.config['CHATGPT']['MODELNAME']) + \
        "/chat/completions/?api-version=" + \
        (self.config['CHATGPT']['APIVERSION'])

        # 设置请求头和载荷
        headers = { 'Content-Type': 'application/json', 'api-key': (self.config['CHATGPT']['ACCESS_TOKEN']) }
        logger.debug(self.users_maneger.user_info_dict.keys())
        logger.debug(f"User_id: {user_id}, {type(user_id)}")
        if user_id not in self.users_maneger.user_info_dict.keys():
            user_info = UserInfo(self.config, user_id)
            self.users_maneger.user_info_dict[user_id] = user_info
            logger.debug(f"User {user_id} info created.")

        user_info = self.users_maneger.user_info_dict[user_id]
        user_info.add_conversation({"role": "user", "content": message})
        # 发送 POST 请求
        massage_with_context = user_info.get_conversations()
        logger.debug(f"massage_with_context: {massage_with_context}")
        response = requests.post(url, json={"messages": massage_with_context}, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            assistant_response = data['choices'][0]['message']['content']
            user_info.add_conversation({"role": "assistant", "content": assistant_response})
            user_info.trim_conversations()
            return assistant_response
        else:
            user_info.trim_conversations()
            return f'Error: API request failed with status code {response.status_code}'
        
if __name__ == '__main__':
    ChatGPT_test = HKBU_ChatGPT()
    while True:
        user_input = input("Typing anything to ChatGPT:\t")
        response = ChatGPT_test.submit(user_input)
        print(response)