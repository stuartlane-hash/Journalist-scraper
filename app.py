import streamlit as st
import requests
from bs4 import BeautifulSoup
import feedparser
import re
import csv
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# ---------------- CONFIG ----------------
NEWSDATA_API_KEY = "YOUR_API_KEY"
HUNTER_API_KEY = "YOUR_API_KEY"

NEWSDATA_API_URL = "https://newsdata.io/api/1/news"

NATIONAL_FEEDS = {
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "BBC UK": "http://feeds.bbci.co.uk/news/uk/rss.xml",
    "Guardian": "https://www.theguardian.com/uk/rss",
    "Guardian UK Crime": "https://www.theguardian.com/uk/ukcrime/rss",
    "Reuters": "https://feeds.reuters.com/reuters/topNews",
    "Sky News": "https://feeds.skynews.com/feeds/rss/home.xml",
    "Sky News UK": "https://feeds.skynews.com/feeds/rss/uk.xml",
    "Independent": "https://www.independent.co.uk/news/uk/rss",
    "Mirror": "https://www.mirror.co.uk/news/rss.xml",
    "Evening Standard": "https://www.standard.co.uk/rss",
}

REGIONAL_FEEDS = {
    "Birmingham Live": "https://www.birminghammail.co.uk/news/rss.xml",
    "Coventry Telegraph": "https://www.coventrytelegraph.net/news/rss.xml",
    "Nottingham Post": "https://www.nottinghampost.com/news/rss.xml",
    "Leicester Mercury": "https://www.leicestermercury.co.uk/news/rss.xml",
    "Manchester Evening News": "https://www.manchestereveningnews.co.uk/news/rss.xml",
    "Liverpool Echo": "https://www.liverpoolecho.co.uk/news/rss.xml",
    "Lancashire Telegraph": "https://www.lancashiretelegraph.co.uk/news/rss.xml",
    "Yorkshire Post": "https://www.yorkshirepost.co.uk/news/rss.xml",
    "Chronicle Live (Newcastle)": "https://www.chroniclelive.co.uk/news/rss.xml",
    "Leeds Live": "https://www.leeds-live.co.uk/news/rss.xml",
    "Sheffield Star": "https://www.thestar.co.uk/news/rss.xml",
    "My London": "https://www.mylondon.news/news/rss.xml",
    "Brighton Argus": "https://www.theargus.co.uk/news/rss.xml",
    "Hampshire Chronicle": "https://www.hampshirechronicle.co.uk/news/rss.xml",
    "Kent Online": "https://www.kentonline.co.uk/rss/",
    "Bristol Post": "https://www.bristolpost.co.uk/news/rss.xml",
    "Plymouth Herald": "https://www.plymouthherald.co.uk/news/rss.xml",
    "Cornwall Live": "https://www.cornwalllive.com/news/rss.xml",
    "Wales Online": "https://www.walesonline.co.uk/news/rss.xml",
    "The Scotsman": "https://www.scotsman.com/news/rss.xml",
    "Herald Scotland": "https://www.heraldscotland.com/news/rss.xml",
    "Glasgow Live": "https://www.glasgowlive.co.uk/news/rss.xml",
    "Belfast Telegraph": "https://www.belfasttelegraph.co.uk/news/rss.xml",
    "Irish News": "https://www.irishnews.com/rss.xml",
}

CSV_FIELDS = [
    "topic", "source", "title", "url", "author",
    "emails", "twitter", "linkedin", "scraped_at"
]

TOPIC_SYNONYMS = {
    "anti-social": ["antisocial", "anti social", "asb", "nuisance", "disorder", "harassment", "vandalism"],
    "antisocial": ["anti-social", "anti social", "asb", "nuisance", "disorder", "harassment", "vandalism"],
    "asb": ["anti-social", "antisocial", "anti social", "nuisance", "disorder", "harassment", "vandalism"],
    "knife": ["stabbing", "blade", "machete"],
    "crime": ["police", "arrest", "charged", "offence", "investigation"],
    "housing": ["homes", "tenants", "landlord", "council housing"],
    "homeless": ["rough sleeping", "rough sleeper", "street homeless"],
    "climate": ["environment", "emissions", "carbon", "net zero"],
    "flood": ["flooding", "storms", "weather warning"],
}

# ---------------- HELPERS ----------------
def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = text.replace("anti-social", "antisocial")
    text = text.replace("anti social", "antisocial")
    text = re.sub(r"[^a-z0-9\s:/._-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def build_keyword_set(topic):
    base = [normalize_text(k) for k in topic.split() if k.strip()]
    expanded = set(base)
    full_topic = normalize_text(topic)
    if full_topic:
        expanded.add(full_topic)

    for kw in list(base):
        if kw in TOPIC_SYNONYMS:
            expanded.update(normalize_text(x) for x in TOPIC_SYNONYMS[kw])

    return {x for x in expanded if x}

def topic_match_score(topic, text):
    text = normalize_text(text)
    topic_norm = normalize_text(topic)
    keywords = build_keyword_set(topic)

    score = 0
    if topic_norm and topic_norm in text:
        score += 4

    for kw in keywords:
        if kw in text:
            score += 2 if " " in kw else 1

    return score

def topic_matches(topic, text, match_any=False, min_score=1):
    text_norm = normalize_text(text)
    base_keywords = [normalize_text(k) for k in topic.split() if k.strip()]
    if not base_keywords:
        return False, 0

    score = topic_match_score(topic, text_norm)

    if match_any:
        return score >= min_score, score

    all_present = all(k in text_norm for k in base_keywords)
    return all_present or score >= max(2, min_score), score

def dedupe_results(results):
    seen = set()
    output 