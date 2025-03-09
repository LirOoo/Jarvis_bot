import requests
from abc import ABC, abstractmethod

# 定义BooksSearcher的抽象基类
class BooksSearcher(ABC):
    @abstractmethod
    def __init__(self):
        self.search_url = ""
        self.query_format = {}
    
    def search(self, query):
        pass

        
class GoogleBooksSearcher(BooksSearcher):
    def __init__(self):
        self.search_url = "https://www.googleapis.com/books/v1/volumes"
        self.query_format = {
            "keywords": ["keyword1", "keyword2"],
            "language": "zh/en"
        }


    def search(self, params):
        # 实现Google Books API调用
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