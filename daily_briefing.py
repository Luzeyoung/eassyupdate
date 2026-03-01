import time
import datetime
import requests
import feedparser
import json
import cloudscraper
import re
import sys
from bs4 import BeautifulSoup

# ============================
#       Configuration
# ============================

# 1. Telegram Bot
TG_TOKEN = "YOUR_TG_TOKEN"
TG_CHAT_ID = "8384265672"

# 2. AI Service
AI_API_KEY = "YOUR_AI_API_KEY"
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"

# 3. Market Data Sources (Real-time Scraping)
MARKET_URLS = {
    "🟡 黄金 (Gold Spot)": "https://www.investing.com/commodities/gold",
    "🇺🇸 标普500 (S&P 500)": "https://www.investing.com/indices/us-spx-500",
    "🇺🇸 纳斯达克 (Nasdaq)": "https://www.investing.com/indices/nasdaq-composite",
    "🇨🇳 A股 (上证指数)": "https://www.investing.com/indices/shanghai-composite",
    "🇨🇳 A股 (沪深300)": "https://www.investing.com/indices/csi300"
}

# 4. RSS Feeds (News Only) - Enhanced with Tier 1 Sources from World Monitor
NEWS_FEEDS = {
    # --- 1. Top-Tier Geopolitics & Strategy (Strategic Level) ---
    "Geopolitics & Defense": [
        "https://www.foreignaffairs.com/rss.xml",           # Foreign Affairs (Deep Policy)
        "https://www.defenseone.com/rss/all/",               # Defense One (Military Strategy)
        "https://www.csis.org/rss/all",                      # CSIS (Think Tank)
        "https://breakingdefense.com/feed/",                 # Breaking Defense
        "https://www.atlanticcouncil.org/feed/",             # Atlantic Council
    ],
    
    # --- 2. Regional News (Operational Level) ---
    "Asia-Pacific": [
        "https://www.scmp.com/rss/91/feed",                  # South China Morning Post
        "https://asia.nikkei.com/rss/feed/nar",             # Nikkei Asia
        "https://thediplomat.com/feed/",                     # The Diplomat (Asia Focus)
        "https://www.channelnewsasia.com/api/v1/rss-feeds/8395986", # CNA (Singapore/Asia)
    ],
    "Europe": [
        "https://www.politico.eu/feed/",                     # Politico Europe
        "https://www.euronews.com/rss",                      # EuroNews
        "https://www.theguardian.com/world/europe/rss",      # Guardian Europe
    ],
    "Middle East": [
        "https://www.aljazeera.com/xml/rss/all.xml",         # Al Jazeera
        "https://www.jpost.com/rss/rssfeedsheadlines.aspx",  # Jerusalem Post
    ],
    "Americas": [
        "https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en", # AP News
        "https://www.politico.com/rss/politics08.xml",       # Politico US
    ],

    # --- 3. Economics & Tech ---
    "Financial Markets": [
        "https://feeds.content.dowjones.com/public/rss/mw_topstories", # MarketWatch
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # CNBC
        "https://www.ft.com/?format=rss", # Financial Times
    ],
    "Tech & Innovation": [
        "https://feeds.feedburner.com/TechCrunch/",            # TechCrunch
        "https://www.theverge.com/rss/index.xml",              # The Verge
        "https://www.wired.com/feed/rss",                      # Wired
    ]
}

# 5. Schedule Times (24h format)
SCHEDULE_TIMES = ["12:00", "20:00"] 

# ============================
#       Core Functions
# ============================

def send_telegram_message(text):
    """Sends a message to the defined Telegram chat."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "text": text, 
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code != 200:
            print(f"[{datetime.datetime.now()}] Setup failed to send. Status: {response.status_code}, Response: {response.text}")
            # Fallback: Try sending without Markdown
            payload["parse_mode"] = ""
            print("Retrying without Markdown...")
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                 print(f"[{datetime.datetime.now()}] Message sent (plaintext fallback).")
            else:
                 print(f"[{datetime.datetime.now()}] Failed again. {response.text}")
        else:
            print(f"[{datetime.datetime.now()}] Message sent to Telegram.")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Failed to send Telegram message: {e}")

def get_realtime_price(name, url):
    """Scrapes Investing.com for real-time price and change."""
    try:
        scraper = cloudscraper.create_scraper()
        # Add headers to mimic a real browser to avoid 403 blocks
        scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response = scraper.get(url, timeout=15)
        if response.status_code != 200:
            return {"name": name, "price": "Error", "change": "N/A", "percent": "N/A"}
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Investing.com uses data-test attributes which are stable
        price = soup.find(attrs={"data-test": "instrument-price-last"})
        change = soup.find(attrs={"data-test": "instrument-price-change"})
        percent = soup.find(attrs={"data-test": "instrument-price-change-percent"})
        
        return {
            "name": name,
            "price": price.text if price else "N/A",
            "change": change.text if change else "0.00",
            "percent": percent.text if percent else "(0.00%)"
        }
    except Exception as e:
        print(f"Error scraping {name}: {e}")
        return {"name": name, "price": "Error", "change": "N/A", "percent": "N/A"}

def fetch_rss_feed(urls, limit=5):
    """Fetches and aggregates RSS feeds from multiple sources."""
    if isinstance(urls, str):
        urls = [urls]
        
    all_entries = []
    seen_titles = set()
    scraper = cloudscraper.create_scraper()
    
    for url in urls:
        try:
            response = scraper.get(url, timeout=10)
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                continue
                
            for entry in feed.entries:
                title = entry.title
                link = getattr(entry, 'link', '')
                
                # Deduplication check
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                
                # Cleanup HTML in title
                title = re.sub(r'<[^>]+>', '', title)
                
                all_entries.append(f"- [{title}]({link})")
                
                if len(all_entries) >= limit:
                    break
            
            if len(all_entries) >= limit:
                break
                
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            continue

    return "\n".join(all_entries) if all_entries else "No news found."

def generate_briefing():
    """Compiles the briefing content using AI + Real-time Data."""
    print(f"[{datetime.datetime.now()}] Generating Briefing...")
    
    # 1. Fetch Real-time Market Data
    market_data = []
    market_text = ""
    for name, url in MARKET_URLS.items():
        data = get_realtime_price(name, url)
        market_data.append(data)
        # Format: Gold: $2000 (+10 / +0.5%)
        # Add emoji for up/down
        icon = "🟢" if "+" in data['change'] else "🔴" if "-" in data['change'] else "⚪"
        market_text += f"{icon} **{name}**: `{data['price']}` ({data['change']} / {data['percent']})\n"
    
    # 2. Fetch News Data - Regional & Strategic Split
    print("Fetching Geopolitics News...")
    geo_news = fetch_rss_feed(NEWS_FEEDS["Geopolitics & Defense"], limit=5)
    
    print("Fetching Regional News (Asia/Europe/ME/US)...")
    asia_news = fetch_rss_feed(NEWS_FEEDS["Asia-Pacific"], limit=4)
    europe_news = fetch_rss_feed(NEWS_FEEDS["Europe"], limit=3)
    me_news = fetch_rss_feed(NEWS_FEEDS["Middle East"], limit=3)
    us_news = fetch_rss_feed(NEWS_FEEDS["Americas"], limit=3)
    
    # Combine regional news into one block for the prompt
    regional_news_block = f"""
    [Asia-Pacific]
    {asia_news}
    [Europe]
    {europe_news}
    [Middle East]
    {me_news}
    [Americas]
    """

    print("Fetching Financial & Tech News...")
    finance_news = fetch_rss_feed(NEWS_FEEDS["Financial Markets"], limit=5)
    tech_news = fetch_rss_feed(NEWS_FEEDS["Tech & Innovation"], limit=4)
    
    # 3. Construct AI Prompt
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    prompt = f"""
    You are a strategic intelligence assistant. 
    Current Time: {current_time}
    
    Here is the REAL-TIME Market Data:
    {market_text}
    
    Here are the Latest Intelligence Reports:
    
    [🛡️ Global Strategy & Defense]
    {geo_news}
    
    [🌍 Regional Flashpoints]
    {regional_news_block}
    
    [💰 Macro-Finance & Tech]
    {finance_news}
    {tech_news}
    
    Task: Write a "Daily Strategic Briefing" (每日战略简报) in Chinese.
    
    Structure:
    1. **📊 Market Snapshot**: Quick real-time numbers summary.
    2. **🛡️ Global Geopolitics (重点深度及地缘分析)**:
       - Summarize 3-4 major strategic shifts or defense/policy news.
       - Analyze implications briefly if possible.
    3. **🌍 Regional Watch**:
       - **Asia-Pacific**: Key updates (China/US relations, regional tensions).
       - **Europe/War in Ukraine**: Critical updates.
       - **Middle East**: Conflict updates.
    4. **💰 Econ & Tech**: Only the most significant movement.
    
    Tone: Intelligence briefing style - objective, analytical, concise. No fluff.
    """
    
    # 4. Call AI
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}"
    }
    
    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(f"{AI_BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        ai_content = result['choices'][0]['message']['content']
        
        final_message = f"📅 **Daily Briefing** ({current_time})\n\n" + ai_content
        return final_message
        
    except Exception as e:
        error_msg = f"⚠️ AI Generation Failed: {e}"
        print(error_msg)
        # Fallback to just sending the raw data and news
        return f"📅 **Daily Briefing (Fallback)**\n\n**Market Data**:\n{market_text}\n\n**News**:\n{geo_news}"

def job():
    """The main task execution."""
    content = generate_briefing()
    send_telegram_message(content)

# ============================
#       Scheduler Loop
# ============================

def run_scheduler():
    print(f"[{datetime.datetime.now()}] 🚀 Daily Briefing Bot Started.")
    print(f"📅 Schedule: {', '.join(SCHEDULE_TIMES)}")
    
    # Initial notification
    send_telegram_message(f"🤖 **Bot Online**\nWill send updates at: {', '.join(SCHEDULE_TIMES)}")
    
    last_run_minute = ""
    
    while True:
        now = datetime.datetime.now()
        current_hm = now.strftime("%H:%M")
        # Unique identifier for this minute (to prevent double execution)
        current_minute_unique = now.strftime("%Y-%m-%d %H:%M") 
        
        if current_hm in SCHEDULE_TIMES:
            # Check if we haven't run for this specific minute yet
            if last_run_minute != current_minute_unique:
                print(f"⏰ Triggering scheduled job at {current_hm}...")
                job()
                last_run_minute = current_minute_unique
                print(f"✅ Job finished. Waiting for next schedule...")
            else:
                # Already ran this minute
                pass
        
        # Check every 10 seconds
        time.sleep(10)

if __name__ == "__main__":
    # Support manual run: python daily_briefing.py now
    if len(sys.argv) > 1 and sys.argv[1] == "now":
        print("Running immediate manual update...")
        job()
    else:
        try:
            run_scheduler()
        except KeyboardInterrupt:
            print("\nBot Stopped.")
