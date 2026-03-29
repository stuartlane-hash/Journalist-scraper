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

# ─── CONFIG ───────────────────────────────────────────────
NEWSDATA_API_KEY = "YOUR_API_KEY"
HUNTER_API_KEY = "YOUR_API_KEY"

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

CSV_FIELDS = ["topic", "source", "title", "url", "author", "emails", "twitter", "linkedin", "scraped_at"]

# ─── CORE FUNCTIONS ───────────────────────────────────────
def search_rss(topic, selected_sources, all_feeds, max_per_feed=20, match_any=False):
    results = []
    keywords = [kw.strip().lower() for kw in topic.split()]
    for source, feed_url in all_feeds.items():
        if source not in selected_sources:
            continue
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                matched = any(kw in text for kw in keywords) if match_any else all(kw in text for kw in keywords)
                if matched:
                    results.append({
                        "source": source,
                        "title": entry.get("title"),
                        "url": entry.get("link"),
                        "author": entry.get("author", "Unknown"),
                    })
        except Exception:
            continue
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
        emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}", r.text)))
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

def build_excel(results, topic):
    wb = Workbook()

    # ── All Results Sheet ──
    ws_all = wb.active
    ws_all.title = "All Results"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    alt_fill = PatternFill("solid", fgColor="D6E4F0")

    headers = ["Topic", "Source", "Title", "URL", "Author", "Emails", "Twitter", "LinkedIn", "Scraped At"]
    for col_num, header in enumerate(headers, 1):
        cell = ws_all.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row_num, row in enumerate(results, 2):
        fill = alt_fill if row_num % 2 == 0 else PatternFill()
        values = [
            row.get("topic"), row.get("source"), row.get("title"),
            row.get("url"), row.get("author"), row.get("emails"),
            row.get("twitter"), row.get("linkedin"), row.get("scraped_at")
        ]
        for col_num, value in enumerate(values, 1):
            cell = ws_all.cell(row=row_num, column=col_num, value=value)
            cell.fill = fill
            cell.alignment = Alignment(wrap_text=True)

    # Auto-size columns
    col_widths = [15, 20, 50, 50, 25, 35, 35, 35, 20]
    for i, width in enumerate(col_widths, 1):
        ws_all.column_dimensions[get_column_letter(i)].width = width

    # ── Per-Source Sheets ──
    sources_in_results = sorted(set(r["source"] for r in results))
    for source in sources_in_results:
        safe_name = re.sub(r"[\\/*?:[]]", "", source)[:31]
        ws = wb.create_sheet(title=safe_name)

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        source_rows = [r for r in results if r["source"] == source]
        for row_num, row in enumerate(source_rows, 2):
            fill = alt_fill if row_num % 2 == 0 else PatternFill()
            values = [
                row.get("topic"), row.get("source"), row.get("title"),
                row.get("url"), row.get("author"), row.get("emails"),
                row.get("twitter"), row.get("linkedin"), row.get("scraped_at")
            ]
            for col_num, value in enumerate(values, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.fill = fill
                cell.alignment = Alignment(wrap_text=True)

        for i, width in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

def validate_rss(url):
    try:
        feed = feedparser.parse(url)
        return len(feed.entries) > 0
    except Exception:
        return False

# ─── PAGE CONFIG ──────────────────────────────────────────
st.set_page_config(page_title="Journalist Finder", page_icon="📰", layout="wide")

st.title("📰 Journalist Finder")
st.markdown("Search national and regional UK news sources for journalists covering a topic — extract emails & social media contacts.")

# ─── SESSION STATE ─────────────────────────────────────────
if "custom_feeds" not in st.session_state:
    st.session_state.custom_feeds = {}
if "enriched_results" not in st.session_state:
    st.session_state.enriched_results = []
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""

# ─── SIDEBAR ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    topic = st.text_input("Search Topic", placeholder="e.g. knife crime, climate change")

    st.subheader("📡 National Sources")
    select_all_national = st.checkbox("Select all national", value=True)
    national_sources = st.multiselect(
        "National Sources",
        options=list(NATIONAL_FEEDS.keys()),
        default=list(NATIONAL_FEEDS.keys()) if select_all_national else [],
        label_visibility="collapsed"
    )

    st.subheader("🗺️ Regional Sources")
    select_all_regional = st.checkbox("Select all regional", value=False)
    regional_sources = st.multiselect(
        "Regional Sources",
        options=list(REGIONAL_FEEDS.keys()),
        default=list(REGIONAL_FEEDS.keys()) if select_all_regional else [],
        label_visibility="collapsed"
    )

    st.subheader("➕ Add Custom Source")
    custom_name = st.text_input("Publication name", placeholder="e.g. Swindon Advertiser")
    custom_url = st.text_input("RSS feed URL", placeholder="e.g. https://example.com/rss.xml")

    if st.button("Add Source", use_container_width=True):
        if not custom_name:
            st.warning("Please enter a publication name.")
        elif not custom_url.startswith("http"):
            st.warning("Please enter a valid URL starting with http.")
        elif custom_name in st.session_state.custom_feeds:
            st.warning(f"'{custom_name}' is already added.")
        else:
            with st.spinner("Validating RSS feed..."):
                if validate_rss(custom_url):
                    st.session_state.custom_feeds[custom_name] = custom_url
                    st.success(f"✅ '{custom_name}' added!")
                else:
                    st.error("Could not find any articles at that URL. Please check it's a valid RSS feed.")

    if st.session_state.custom_feeds:
        st.subheader("📌 Custom Sources")
        custom_to_remove = []
        custom_sources = []
        for name, url in st.session_state.custom_feeds.items():
            col1, col2 = st.columns([3, 1])
            col1.markdown(f"✅ {name}")
            if col2.button("✕", key=f"remove_{name}"):
                custom_to_remove.append(name)
            else:
                custom_sources.append(name)
        for name in custom_to_remove:
            del st.session_state.custom_feeds[name]
            st.rerun()
    else:
        custom_sources = []

    st.markdown("---")
    max_results = st.slider("Max articles per source", min_value=5, max_value=50, value=20)
    match_any = st.toggle("Match ANY keyword (broader search)", value=False)
    search_btn = st.button("🔍 Search", use_container_width=True)

# ─── COMBINE ALL FEEDS ────────────────────────────────────
all_feeds = {**NATIONAL_FEEDS, **REGIONAL_FEEDS, **st.session_state.custom_feeds}
sources = national_sources + regional_sources + custom_sources

# ─── MAIN PANEL ───────────────────────────────────────────
if search_btn:
    if not topic:
        st.warning("Please enter a topic to search.")
    elif not sources:
        st.warning("Please select at least one news source.")
    else:
        with st.spinner(f"Searching for journalists covering **{topic}**..."):
            raw = search_rss(topic, sources, all_feeds, max_per_feed=max_results, match_any=match_any)

        if not raw:
            st.error("No articles found. Try enabling **'Match ANY keyword'** in the sidebar, or add more sources.")
        else:
            st.success(f"Found **{len(raw)}** matching articles. Enriching contact data...")
            enriched = []
            progress = st.progress(0)
            status = st.empty()

            for i, item in enumerate(raw):
                status.text(f"Scraping: {item['title'][:60]}...")
                details = scrape_article(item["url"])
                enriched.append({
                    "topic": topic,
                    "source": item["source"],
                    "title": item["title"],
                    "url": item["url"],
                    "author": details.get("author") or item["author"],
                    "emails": "; ".join(details.get("emails", [])),
                    "twitter": "; ".join(details.get("twitter", [])),
                    "linkedin": "; ".join(details.get("linkedin", [])),
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                progress.progress((i + 1) / len(raw))

            status.empty()
            progress.empty()
            st.session_state.enriched_results = enriched
            st.session_state.last_topic = topic

if st.session_state.enriched_results:
    enriched = st.session_state.enriched_results
    topic = st.session_state.last_topic

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Articles", len(enriched))
    col2.metric("📧 With Email", sum(1 for r in enriched if r["emails"]))
    col3.metric("🐦 With Twitter", sum(1 for r in enriched if r["twitter"]))
    col4.metric("💼 With LinkedIn", sum(1 for r in enriched if r["linkedin"]))

    st.markdown("---")

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

    st.markdown("---")
    safe_topic = re.sub(r"[^w-]", "_", topic.lower())
    timestamp = datetime.now().strftim