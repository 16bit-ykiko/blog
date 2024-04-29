import os
import json
import datetime
import requests
from typing import Iterable
from bs4 import BeautifulSoup, PageElement

urls_map = {}


def image(element: PageElement) -> str:
    noscript = element.find('noscript')
    img = noscript.find('img')
    return f'![img]({img.attrs.get("data-original")})'


def link(element: PageElement) -> str:
    url: str = element['href']

    url = url.replace('//link.zhihu.com/?target=https%3A', "")
    print(url)
    if url in urls_map:

        url = urls_map[url]
    print(url)
    if element.attrs.get('target') == '_blank' and element.attrs.get("data-text") != None:
        return f'[{element.attrs.get("data-text")}]({url})'
    else:
        return f'[{element.text}]({url})'


def paragraph(element: PageElement) -> str:
    result = ""
    for element in element.children:
        match element.name:
            case 'a':
                result += link(element)
            case 'b':
                result += f' **{element.text}** '
            case 'code':
                result += f'`{element.text}`'
            case None:
                result += element.text
    return result


def unordered_list(element: PageElement, tab=0) -> str:
    result = ""
    for element in element.children:
        match element.name:
            case 'li':
                for _ in range(tab):
                    result += '\t'
                result += f'- {paragraph(element)}\n'
            case "ul":
                result += unordered_list(element, tab + 1)
    return result


def code_block(element: PageElement) -> str:
    pre = element.find('pre')
    code = pre.find('code')
    lang: str = code['class'][0]
    lang = lang.replace('language-', '')
    text: str = code.get_text()
    return f'```{lang}\n{text}{"" if text.endswith("\n") else "\n"}```'


def toMarkdown(result: list, elements: Iterable[PageElement]):
    for element in elements:
        match element.name:
            case 'p':
                result.append("\n\n")
                result.append(paragraph(element))
            case 'a':
                if element.attrs["target"] == "_blank":
                    result.append("\n\n - " + link(element))
            case 'h2':
                result.append(f'\n\n## {paragraph(element)}')
            case 'h3':
                result.append(f'\n\n### {paragraph(element)}')
            case 'blockquote':
                result.append("\n\n" + f'> {paragraph(element)}')
            case 'ul':
                result.append("\n\n" + unordered_list(element))
            case 'div':
                if element.attrs['class'][0] == 'highlight':
                    result.append("\n\n" + code_block(element))
            case 'figure':
                result.append("\n\n" + image(element))
            case None:
                result.append(element.text)


def article(soup: BeautifulSoup) -> str:
    jsinitdata = json.loads(soup.select(
        'script[id="js-initialData"]')[0].get_text())
    articles = jsinitdata["initialState"]["entities"]["articles"]
    inner = articles[list(articles.keys())[0]]

    created = inner["created"]
    updated = inner["updated"]
    return created, updated

# 知乎专栏


def column(soup: BeautifulSoup) -> str:
    jsinitdata = json.loads(soup.select(
        'script[id="js-initialData"]')[0].get_text())
    columns = jsinitdata["initialState"]["entities"]["columns"]
    inner = columns[list(columns.keys())[0]]

    created = inner["created"]
    updated = inner["updated"]
    return created, updated


def request(url: str):
    headers = {"Content-Type": "text/html; charset=utf-8"}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.select('h1[class^="Post-Title"]')[0].text
    cover = soup.select("meta[property='og:image']")[0]['content']

    created, updated = article(soup)
    result = [f"# {title}\n\n", f"![cover]({cover})\n\n"]
    body = soup.select('div[class^="RichText"]')[0].children

    toMarkdown(result, body)

    return "".join(result), cover, title, datetime.datetime.fromtimestamp(created), datetime.datetime.fromtimestamp(updated)


def main():
    current_dir = os.path.dirname(__file__)
    json_path = os.path.join(current_dir, 'map.json')
    map_json = json.loads(open(json_path, 'r').read())
    for url, value in map_json.items():
        urls_map[url] = url.replace(
            'https://zhuanlan.zhihu.com/p', "https://16bit-ykiko.github.io/about-me")

    for url in urls_map.keys():
        name = url.split('/')[-1]
        markdown, cover, title, cr, up = request(url)

        markdown = (f"---\n"
                    f"title: '{title}'\n"
                    f"date: {cr}\n"
                    f"updated: {up}\n"
                    f"type: 'post'\n"
                    f"cover: '{cover}'\n"
                    f"---\n") + markdown

        dest = os.path.join(current_dir, f'../hexo/source/_posts/{name}.md')

        with open(dest, 'w', encoding="utf-8") as f:
            f.write(markdown)


if __name__ == '__main__':
    main()
