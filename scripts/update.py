import os
import time
import random
import requests

from zhihu import Parser
from datetime import datetime

cookies = {}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

# download image from url
def download(url: str):
    n = 0
    while n < 10:
        try:
            response = requests.get(
                url, timeout=10, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(e)
            time.sleep(random.choice([1, 2, 3, 4]))
            n += 1


def request(url: str, series: tuple[str, int] | None = None):
    n = 0
    while n < 20:
        try:
            response = requests.get(
                url, timeout=10, headers=headers)
            response.raise_for_status()

            parser = Parser()
            article = parser.parse_article_from_json(response.text)
            created = datetime.fromtimestamp(article.created)
            updated = datetime.fromtimestamp(article.updated)

            result = (f"---\n"
                      f"title: '{article.title}'\n"
                      f"date: {created}\n"
                      f"updated: {updated}\n")

            if series is not None:
                result += (f"series: ['{series[0]}']\n"
                           f"series_order: {series[1]}\n")

            result += f"---\n\n" + article.content.dump()
            return result, article.cover
        except Exception as e:
            print(e)
            time.sleep(random.choice([1, 2, 3, 4]))
            n += 10


def main():
    # load_cookies()
    path = os.path.dirname(__file__)
    import articles

    urls = {}
    for article in articles.all:
        urls[article.url] = article.url.replace('zhuanlan.zhihu.com/p',
                                                "www.ykiko.me/zh-cn/articles")
    Parser.urls_map = urls

    for article in articles.all:
        hash = article.url.split('/')[-1]
        markdown, cover = request(
            f"https://api.zhihu.com/article/{hash}", article.series)

        dir = os.path.join(path, f'../website/content/zh-cn/articles/{hash}')
        if not os.path.exists(dir):
            os.makedirs(dir)

        # write markdown file
        with open(os.path.join(dir, 'index.md'), 'w', encoding="utf-8") as f:
            f.write(markdown)

        # write cover image
        if cover:
            with open(os.path.join(dir, 'featured.png'), 'wb') as f:
                f.write(download(cover))

        time.sleep(random.choice([1, 2, 3, 4]))

        print(f"Done: {hash}")


if __name__ == "__main__":
    main()
