#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup


def getHtml(url):

    r = requests.get(url)
    if r.status_code != 200:
        return None

    html = BeautifulSoup(r.content, 'html.parser')
    # print(soup.prettify())
    return html


def getEventList(startDate, endDate):

    TOP_URL="https://www.mtgtop8.com/format?f=PAU&meta=127&a="
    html = getHtml(TOP_URL)


def main():
    getEventList("20240101", "20240801")



if __name__ == '__main__':
    main()

