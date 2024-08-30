#!/usr/bin/env python3

import os
import re
import requests
import shutil
import sys
import time
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime, timedelta


# throttle HTTP requests so we don't get blacklisted
HTTP_REQUEST_DELAY_SECS= 2

@dataclass
class Event:
    url: str
    date: str
    name: str

@dataclass
class Deck:
    url: str
    player: str
    finish: str


def convertDateStr(date):
    return datetime.strptime(date, "%d/%m/%y").strftime("%Y%m%d")


def dateInRange(date, startDate, endDate):
    # a "YYYYMMDD" string converted to int should preserve ordering
    return (int(date) >= int(startDate) and int(date) <= int(endDate))


def getHtml(url):

    print(f"Retrieving {url} ...")
    time.sleep(HTTP_REQUEST_DELAY_SECS)

    response = requests.get(url)
    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code} attempting to GET {url}", file=sys.stderr)
        return None

    html = BeautifulSoup(response.content, "html.parser")
    # print(html.prettify())
    return html


def getEventsFromHtml(html, startDate, endDate):

    earliestDate = None
    events = []

    try:
        eventTable = html.find_all("table", class_="Stable")[1]
    except:
        print("ERROR: Event table not found!", file=sys.stderr)
        return ([], None)

    for eventTr in eventTable.find_all("tr"):

        # example dateTd
        # <td align="right" class="S12" width="12%">17/08/24</td>
        dateTd = eventTr.find("td", class_="S12")
        if not dateTd or not dateTd.text:
            print("ERROR: Date not found in event row!", file=sys.stderr)
            continue

        try:
            eventDate = convertDateStr(dateTd.text)
        except:
            print(f"ERROR: Date '{dateTd.text}' not in expected DD/MM/YY format!", file=sys.stderr)
            continue

        # track the earliest date seen so the caller can short circuit
        # scanning additional pages if necessary
        if earliestDate is None or int(eventDate) < int(earliestDate):
            earliestDate = eventDate

        if not dateInRange(eventDate, startDate, endDate):
            continue

        # example eventUrlTd
        # <td class="S14" width="70%"><a href="event?e=58498&amp;f=PAU">MTGO League</a> <span class="new">NEW</span></td>
        try:
            eventUrlA = eventTr.find("td", class_="S14").find("a")
            eventUrlHref = eventUrlA.get("href")
            if not eventUrlHref:
                raise Exception()
        except:
            print("ERROR: Event URL not found in event row!", file=sys.stderr)
            continue

        eventName = eventUrlA.text
        eventUrl = f"https://www.mtgtop8.com/{eventUrlHref}"

        event = Event(eventUrl, eventDate, eventName)
        events.append(event)
        print(f"Found event: {event}")

    return (events, earliestDate)


def getEvents(startDate, endDate):

    events = []

    # TODO break up the search into 'top' pages by year

    page = 1
    while True:
        pageUrl = f"https://www.mtgtop8.com/format?f=PAU&meta=127&cp={page}"
        html = getHtml(pageUrl)
        if html is not None:
            (results, earliestDate) = getEventsFromHtml(html, startDate, endDate)
            events.extend(results)
        if html is None or int(earliestDate) < int(startDate):
            # subsequent pages go back in time, so if the earliest found event
            # was before our start boundary, there will be no more hits
            break
        else:
            page = page + 1

    return events


def getDeckFromDeckDiv(deckDiv, numPlayers):

    try:
        deckHref = deckDiv.find("div", attrs={"style":"width:100%;padding-left:4px;margin-bottom:4px;"}).find("a").get("href")
        deckUrl = f"https://www.mtgtop8.com/event{deckHref}"
    except:
        print("ERROR: Deck list URL not found in event deck row!", file=sys.stderr)
        return None

    try:
        deckPlayer = deckDiv.find("div", "G11").text
    except:
        print("ERROR: Player name not found in event deck row!", file=sys.stderr)
        return None

    try:
        deckRank = deckDiv.find("div", "S14").text
    except:
        print("ERROR: Deck rank not found in event deck row!", file=sys.stderr)
        return None

    deckFinish = "-" if numPlayers == None else f"{deckRank}/{numPlayers}"

    deck = Deck(deckUrl, deckPlayer, deckFinish)
    print(f"Found deck: {deck}")
    return deck


def getDecksFromHtml(html):

    decks = []

    # example eventDataDiv:
    # <div style="margin-bottom:5px;">40 players - 06/08/24</div>
    eventDataDiv = html.find("div", attrs={"style":"margin-bottom:5px;"})
    if not eventDataDiv:
        print(f"ERROR: Event metadata div not found!", file=sys.stderr)
        return []

    # use None as a flag for events without positional rankings (e.g. mtgo leagues)
    playersRegex = re.search(r"(\d+) players", eventDataDiv.text)
    numPlayers = None if playersRegex is None else playersRegex.group(1)

    leftNavDiv = html.find("div", attrs={"style":"margin:0px 4px 0px 4px;"})
    if not leftNavDiv:
        print(f"ERROR: Left div not found!", file=sys.stderr)
        return []

    firstDeckDiv = leftNavDiv.find("div", class_="chosen_tr")
    if not firstDeckDiv:
        print(f"ERROR: First deck div not found!", file=sys.stderr)
        return []

    deck = getDeckFromDeckDiv(firstDeckDiv, numPlayers)
    if deck:
        decks.append(deck)

    for deckDiv in leftNavDiv.find_all("div", class_="hover_tr"):
        deck = getDeckFromDeckDiv(deckDiv, numPlayers)
        if deck:
            decks.append(deck)

    return decks


def getDecksFromEvent(event):

    html = getHtml(event.url)
    if html is None:
        print(f"ERROR: Failed to retrieve event {event.url}", file=sys.stderr)
        return []

    decks = getDecksFromHtml(html)
    return decks


def getDeckTextFromHtml(html):

    deckListDiv = html.find("div", attrs={"style":"display:flex;align-content:stretch;"})
    if not deckListDiv:
        print("ERROR: Deck list div not found!", file=sys.stderr)
        return None

    mb = []
    sb = []
    for cardGroupDiv in deckListDiv.find_all("div", attrs={"style":"margin:3px;flex:1;"}):
        labelDiv = cardGroupDiv.find("div", class_="O14")
        for cardDiv in cardGroupDiv.find_all("div", class_="deck_line"):
            line = cardDiv.text.strip()
            if labelDiv and labelDiv.text == "SIDEBOARD":
                sb.append(line)
            else:
                mb.append(line)

    deckText = "\n".join( [ "\n".join(mb), "SIDEBOARD", "\n".join(sb) ] )
    return deckText


def getDeckText(deck):

    html = getHtml(deck.url)
    if html is None:
        print(f"ERROR: Failed to retrieve deck {event.url}", file=sys.stderr)
        return None

    deckText = getDeckTextFromHtml(html)
    return deckText


def eventToDirPath(event):
    name = event.name.strip().replace(' ', '_').replace('/', '_').replace("'", '').replace('"', '')
    year = event.date[0:4]
    month = event.date[4:6]
    day = event.date[6:8]
    return os.path.join("data", year, month, day, name)


def eventToTmpPath(event):
    name = event.name.strip().replace(' ', '_').replace('/', '_').replace("'", '').replace('"', '')
    return os.path.join("/", "tmp", name)


def deckToFileName(deckIndex, deck):
    finish = deck.finish.replace('/', ':')
    player = deck.player.replace(' ', '-').replace('/', '-').replace("'", '').replace('"', '')
    return f"{deckIndex}_{finish}_{player}"


def downloadResults(startDate, endDate):

    events = getEvents(startDate, endDate)
    for event in events:

        eventDirPath = eventToDirPath(event)
        if os.path.exists(eventDirPath):
            print(f"Already downloaded {eventtDirPath}, skipping...")
            continue

        tmpDirPath = eventToTmpPath(event)
        if os.path.exists(tmpDirPath):
            shutil.rmtree(tmpDirPath)
        os.makedirs(tmpDirPath)

        decks = getDecksFromEvent(event)
        for deckIndex, deck in enumerate(decks):

            deckText = getDeckText(deck)
            if deckText:

                deckPath = os.path.join(tmpDirPath, deckToFileName(deckIndex, deck))
                with open(deckPath, 'w') as f:
                    f.write(f"// URL: {deck.url}\n")
                    f.write(f"// PLAYER: {deck.player}\n")
                    f.write(f"// FINISH: {deck.finish}\n")
                    f.write(deckText)
                    print(f"Saved {deckPath}")

        # create the entire event's deck dir in /tmp and move it to its final
        # canonical path as the last step, so we can be confident that if it
        # ever exists at the latter path, its contents are complete
        if len(os.listdir(tmpDirPath)) > 0:
            shutil.move(tmpDirPath, eventDirPath)
            print(f"Saved {eventDirPath}")


def main():

    # TODO argparse stuff to get optional start/end dates

    startDate = (datetime.today() - timedelta(days=3)).strftime("%Y%m%d")
    endDate = datetime.today().strftime("%Y%m%d")

    downloadResults(startDate, endDate)


if __name__ == "__main__":
    main()

