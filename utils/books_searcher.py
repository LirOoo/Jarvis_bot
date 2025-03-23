import requests
from abc import ABC, abstractmethod

"""
图书搜索模块
抽象基类定义 + Google 图书 API 实现
"""

# 定义BooksSearcher的抽象基类
class BooksSearcher(ABC):
    @abstractmethod
    def __init__(self):
        self.search_url = ""  # API 地址
        self.query_format = {} # 查询参数格式模板
    
    def search(self, query):
        """执行搜索的抽象方法"""
        pass

        
class GoogleBooksSearcher(BooksSearcher):
    def __init__(self):
        """初始化 API 参数"""
        self.search_url = "https://www.googleapis.com/books/v1/volumes"
        self.query_format = {
            "keywords": ["keyword1", "keyword2"],  # 搜索关键词列表
            "language": "zh/en"
        }


    def search(self, params):
        """执行图书搜索
        参数：
            params - 包含 keywords 和 language 的字典
        返回：
            前5条结果的简化列表
        """
        response = requests.get(
            self.search_url,
            params={
                'q': '+'.join(params['keywords']),
                'langRestrict': params['language'],
                'maxResults': 5
            }
        )
        return response.json().get('items', [])[:3]

if __name__=='__main__':
    params = {
        'keywords': ['哲学'],
        'language': ['zh', 'en']
    }
    searcher = GoogleBooksSearcher()
    results = searcher.search(params)
    for book in results:
        print(book)
        # print(book['volumeInfo']['title'])
        # print(book['volumeInfo'].get('authors', ['Unknown']))
        # print(book['volumeInfo'].get('publishedDate', 'Unknown'))
        # print('----------------------------------------')