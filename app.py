import streamlit as st
import requests
from bs4 import BeautifulSoup
import feedparser
import re
import csv
import io
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────
NEWSDATA_API_KEY = "YOUR_API_KEY"  # Free tier: newsdata.io
HUNTER_API_KEY   = "YOUR_API_KEY"  # Free tier: hunter.io

RSS_FEEDS = {
    "BBC":      "http://feeds.bbci.co.uk/news/rss.xml",
    "Guardian": "https://www.theguardian.com/uk/rss",
    "Reuters":  "https://feeds.reuters.com/reuters/topNews",
    "Sky News": "https://feeds.skynews.com/feeds/rss/home.xml",
}

CSV_FIELDS = ["topic","source","title","url","author","emails","twitter","linkedin","scraped_at"]

# ─── CORE FUNCTIONS ───────────────────────────────────────
def search_rss(topic, sources, max_per_feed=10):
    results = []
    for source, feed_url in RSS_FEEDS.items():
        if source not in sources:
            continue
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:max_per_feed]:
            if topic.lower() in (entry.get("title","") + entry.get("summary","")).lower():
                results.append({
                    "source": source,
                    "title":  entry.get("title"),
                    "url":    entry.get("link"),
                    "author": entry.get("author", "Unknown"),
                })
    return results

def scrape_article(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        author = None
        for tag in ["[rel='author']", ".author", ".byline", "[itemprop='author']"]:
            el = soup.select_one(tag)
            if el:
                author = el.get_text(strip=True)
                break
        emails  = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}", r.text)))
        twitter, linkedin = [], []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "twitter.com" in href or "x.com" in href:
                twitter.append(href)
            elif "linkedin.com/in" in href:
                linkedin.append(href)
        return {"author": author, "emails": emails, "twitter": twitter, "linkedin": linkedin}
    except Exception as e:
        return {"author": None, "emails": [], "twitter": [], "linkedin": [], "error": str(e)}

def build_csv(results):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)
    return output.getvalue().encode("utf-8")

# ─── PAGE CONFIG ──────────────────────────────────────────
st.set_page_config(page_title="Journalist Finder", page_icon="📰", layout="wide")

st.title("📰 Journalist Finder")
st.markdown("Search news sources for journalists covering a topic — extract emails & social media contacts.")

# ─── SIDEBAR ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    topic = st.text_input("Search Topic", placeholder="e.g. AI regulation, climate change")
    sources = st.multiselect(
        "News Sources",
        options=list(RSS_FEEDS.keys()),
        default=list(RSS_FEEDS.keys())
    )
    max_results = st.slider("Max articles per source", min_value=1, max_value=20, value=5)
    search_btn  = st.button("🔍 Search", use_container_width=True)

# ─── MAIN PANEL ───────────────────────────────────────────
if search_btn:
    if not topic:
        st.warning("Please enter a topic to search.")
    elif not sources:
        st.warning("Please select at least one news source.")
    else:
        with st.spinner(f"Searching for journalists covering **{topic}**..."):
            raw = search_rss(topic, sources, max_per_feed=max_results)

        if not raw:
            st.error("No articles found. Try a broader topic or different sources.")
        else:
            st.success(f"Found **{len(raw)}** matching articles. Enriching contact data...")
            enriched = []
            progress = st.progress(0)
            status   = st.empty()

            for i, item in enumerate(raw):
                status.text(f"Scraping: {item['title'][:60]}...")
                details = scrape_article(item["url"])
                enriched.append({
                    "topic":      topic,
                    "source":     item["source"],
                    "title":      item["title"],
                    "url":        item["url"],
                    "author":     details.get("author") or item["author"],
                    "emails":     "; ".join(details.get("emails", [])),
                    "twitter":    "; ".join(details.get("twitter", [])),
                    "linkedin":   "; ".join(details.get("linkedin", [])),
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                progress.progress((i + 1) / len(raw))

            status.empty()
            progress.empty()

            # ── Summary metrics ──
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📄 Articles", len(enriched))
            col2.metric("📧 With Email",    sum(1 for r in enriched if r["emails"]))
            col3.metric("🐦 With Twitter",  sum(1 for r in enriched if r["twitter"]))
            col4.metric("💼 With LinkedIn", sum(1 for r in enriched if r["linkedin"]))

            st.markdown("---")

            # ── Results cards ──
            for row in enriched:
                with st.expander(f"📰 {row['title']} — *{row['source']}*"):
                    cols = st.columns([2, 2, 3])
                    cols[0].markdown(f"**Author:** {row['author'] or 'Unknown'}")
                    cols[1].markdown(f"**Scraped:** {row['scraped_at']}")
                    cols[2].markdown(f"[🔗 View Article]({row['url']})")
                    if row["emails"]:
                        st.markdown(f"📧 **Email:** `{row['emails']}`")
                    if row["twitter"]:
                        st.markdown(f"🐦 **Twitter/X:** {row['twitter']}")
                    if row["linkedin"]:
                        st.markdown(f"💼 **LinkedIn:** {row['linkedin']}")
                    if not any([row["emails"], row["twitter"], row["linkedin"]]):
                        st.caption("No contact info found for this article.")

            # ── CSV Download ──
            st.markdown("---")
            safe_topic = re.sub(r"[^w-]", "_", topic.lower())
            filename   = f"journalists_{safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            st.download_button(
                label="⬇️ Download CSV",
                data=build_csv(enriched),
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
            )

elif not search_btn:
    st.info("👈 Enter a topic and click **Search** to get started.")