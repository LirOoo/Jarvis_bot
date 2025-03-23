import configparser
import requests


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

    def submit(self, message):
        """提交消息到 ChatGPT API
        参数：
            message - 用户输入的文本
        返回：
            ChatGPT 生成的回复内容
        """
        conversation = [{"role": "user", "content": message}]
        # 构造 API 请求 URL
        url = (self.config['CHATGPT']['BASICURL']) + \
        "/deployments/" + (self.config['CHATGPT']['MODELNAME']) + \
        "/chat/completions/?api-version=" + \
        (self.config['CHATGPT']['APIVERSION'])

        # 设置请求头和载荷
        headers = { 'Content-Type': 'application/json',
        'api-key': (self.config['CHATGPT']['ACCESS_TOKEN']) }
        payload = { 'messages': conversation }

        # 发送 POST 请求
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return 'Error:', response
        
if __name__ == '__main__':
    ChatGPT_test = HKBU_ChatGPT()
    while True:
        user_input = input("Typing anything to ChatGPT:\t")
        response = ChatGPT_test.submit(user_input)
        print(response)