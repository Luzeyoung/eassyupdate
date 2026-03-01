import feedparser
import requests
import os
import json
import datetime
import time
import re
import html
import cloudscraper
import arxiv

import sys
# Reconfigure stdout to utf-8 to avoid encoding errors with emojis on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ============================
#       用户配置区 (必填!)
# ============================

# 1. Telegram 机器人配置
TG_TOKEN = "YOUR_TG_TOKEN"
TG_CHAT_ID = "8384265672"

# 2. AI 服务配置
AI_API_KEY = "YOUR_AI_API_KEY"
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"

# OpenAlex API Key (Optional but recommended for higher limits)
OPENALEX_API_KEY = "YOUR_OPENALEX_API_KEY"

# Elsevier/Scopus API Key (Optional - for ScienceDirect/Acta Materialia)
# Apply at: https://dev.elsevier.com/
ELSEVIER_API_KEY = "YOUR_ELSEVIER_API_KEY" 

# SiYuan Note Config
SIYUAN_API_URL = "http://10.42.0.58:6806"
SIYUAN_API_TOKEN = "YOUR_SIYUAN_API_TOKEN"
SIYUAN_NOTEBOOK_ID = "20260301131510-yehu9uc" # Provided by user
SIYUAN_THRESHOLD = 3

# 3. RSSHub 服务地址
RSSHUB_BASE = "https://rsshub.app"

# 4. 网络代理设置
# 如果不需要代理，请将其设置为 None。如果需要，请替换为您的代理地址。
# 例如: "http://127.0.0.1:7890"
PROXIES = {

} 

# 5. User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Referer": "https://www.google.com/"
}
CROSSREF_HEADERS = {
    "User-Agent": "EssayUpdateBot/1.0 (mailto:user@example.com)"
}

# 6. 历史记录文件
DATA_FILE = "journal_history.json"

# 7. 检索配置
KEYWORDS = ["NiTi", "shape memory", "martensite", "superelasticity", "DFT", "molecular dynamics", "materials", "LAMMPS", "high entropy alloy","dislocation", "precipitate", "phase transformation", "microstructure"] # 可选，留空表示不过滤关键词
DAYS_LOOKBACK = 7  # 追溯最近多少天的文章
MAX_PAPERS_PER_SOURCE = 100 # 避免一次推送过多，设置一个较大的上限

# ============================
#   期刊配置 (Official RSS + CrossRef ISSN)
# ============================

# RSS 类期刊 (Nature/Science/Wiley/ACS)
RSS_JOURNALS = {
    # --- Nature Family ---
    "Nature (正刊)": "https://www.nature.com/nature.rss",
    "Nature Materials": "https://www.nature.com/nmat.rss",
    "Nature Reviews Materials": "https://www.nature.com/natrevmats.rss",
    "npj 2D Materials": "https://www.nature.com/npj2dmaterials.rss",
    "Nature Nanotechnology": "https://www.nature.com/nnano.rss",       
    "Nature Communications": "https://www.nature.com/ncomms.rss",
    "Nature Synthesis": "https://www.nature.com/nsynthesis.rss",

    # --- Science Family ---
    "Science": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "Science Advances": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv",
    "Science Robotics": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=scirobotics",

    # --- Wiley ---
    "Advanced Materials": "https://onlinelibrary.wiley.com/feed/15214095/most-recent",
    "Advanced Functional Materials": "https://onlinelibrary.wiley.com/feed/16163028/most-recent",
    "Small": "https://onlinelibrary.wiley.com/feed/16136829/most-recent",
    "Advanced Energy Materials": "https://onlinelibrary.wiley.com/feed/16146840/most-recent",
    "Advanced Science": "https://onlinelibrary.wiley.com/feed/21983844/most-recent",
    "Advanced Optical Materials": "https://onlinelibrary.wiley.com/feed/21951071/most-recent",
    "Small Methods": "https://onlinelibrary.wiley.com/feed/23669608/most-recent",

    # --- ACS ---
    "ACS Nano": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=ancac3",             
    "Nano Letters": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=nalefd",         
    "Chemistry of Materials": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=cmatex",
    "ACS Energy Letters": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=aelccp",
    "ACS Materials Letters": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=amlced",

    # --- RSC ---
    "Energy & Environmental Science": "http://feeds.rsc.org/rss/ee",
    "J. Mater. Chem. A": "http://feeds.rsc.org/rss/ta",
    "Materials Horizons": "https://pubs.rsc.org/en/journals/journalissues/mh?rss=true",

    # --- Springer ---
    "Nano-Micro Letters": "https://link.springer.com/search.rss?facet-content-type=Article&facet-journal-id=40820",
}

# CrossRef 类期刊 (Elsevier/ScienceDirect - RSS blocked)
# 使用 ISSN 查询 CrossRef API 替代
CROSSREF_JOURNALS = {
    "Acta Materialia": "1359-6454",
    "Additive Manufacturing": "2214-8604",
    "Intl. J. of Plasticity": "0749-6419",
    "J. Mater. Res. & Tech": "2238-7854",
    "J. Mater. Sci. & Tech": "1005-0302",
    "Materials & Design": "0264-1275",
    "Materials Today": "1369-7021",
    "Scripta Materialia": "1359-6462",
    "Corrosion Science": "0010-938X",
    "Applied Material Today": "2352-9407", # Fixed name
    "Bioactive Materials": "2452-199X",
}

# ============================
#          功能函数
# ============================

def load_history():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history[-3000:], f, ensure_ascii=False)

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_html)
    return html.unescape(text.replace('\n', ' ').strip())
def reconstruct_openalex_abstract(inverted_index):
    if not inverted_index: return None
    word_index = []
    for k, v in inverted_index.items():
        for index in v:
            word_index.append([k, index])
    word_index = sorted(word_index, key = lambda x : x[1])
    return " ".join([x[0] for x in word_index])

def fetch_metadata_from_openalex(doi):
    """通过 OpenAlex 获取更准确的摘要和作者信息"""
    if not doi: return None, None
    clean_doi = doi.replace("https://doi.org/", "")
    url = f"https://api.openalex.org/works/doi:{clean_doi}"
    
    try:
        # 建议在 headers 中带上你的邮箱，OpenAlex 会给更高配额
        headers = {
            "User-Agent": "mailto:2410017@tongji.edu.cn", 
            "x-api-key": OPENALEX_API_KEY
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Abstract
            abstract = None
            abstract_inverted_index = data.get('abstract_inverted_index')
            if abstract_inverted_index:
                 abstract = reconstruct_openalex_abstract(abstract_inverted_index)
            
            # Authors
            # authorships list contains: author { display_name }, is_corresponding, etc.
            authorships = data.get('authorships', [])
            authors_data = []
            for auth in authorships:
                a_info = auth.get('author', {})
                name = a_info.get('display_name', 'Unknown')
                is_corr = auth.get('is_corresponding', False)
                authors_data.append({'name': name, 'is_corresponding': is_corr})
            
            return abstract, authors_data

        else:
            print(f"    ❌  Status: {resp.status_code}")
    except Exception as e:
        print(f"    ❌ OpenAlex Exception: {e}")
    return None, None
def fetch_abstract_from_crossref_xml(doi):
    """尝试从 CrossRef Unixref XML 获取 API """
    if not doi: return None
    # print(f"    Trying CrossRef XML for DOI: {doi} ...")
    url = f"https://api.crossref.org/works/{doi}"
    headers = {
        "Accept": "application/vnd.crossref.unixref+xml",
        "User-Agent": "EssayUpdateBot/1.0 (mailto:user@example.com)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15, proxies=PROXIES)
        if resp.status_code == 200:
            xml = resp.text
            # Look for <jats:abstract> or <abstract>
            match = re.search(r'<(?:jats:)?abstract[^>]*>(.*?)</(?:jats:)?abstract>', xml, re.IGNORECASE | re.DOTALL)
            if match:
                return clean_html(match.group(1))
            # Fallback for plain XML return
            match = re.search(r'<abstract[^>]*>(.*?)</abstract>', xml, re.IGNORECASE | re.DOTALL)
            if match:
                return clean_html(match.group(1))
    except Exception as e:
        # print(f"    ❌ CrossRef XML Error: {e}")
        pass
    return None

def fetch_abstract_from_elsevier(doi):
    """
    通过 Elsevier API 获取摘要 (需要 API Key)
    """
    if not ELSEVIER_API_KEY or not doi: return None
    
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    headers = {
        "X-ELS-APIKey": ELSEVIER_API_KEY,
        "Accept": "application/json"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies=PROXIES)
        if resp.status_code == 200:
            data = resp.json()
            # Navigate JSON: full-text-retrieval-response -> coredata -> dc:description
            coredata = data.get('full-text-retrieval-response', {}).get('coredata', {})
            abstract = coredata.get('dc:description')
            if abstract:
                 return clean_html(abstract)
    except Exception as e:
        # print(f"    ❌ Elsevier API Error: {e}")
        pass
    return None

def fetch_abstract_from_model_context_protocol(doi):
    pass

def fetch_abstract_from_semantic_scholar(doi):
    """尝试从 Semantic Scholar API 获取摘要"""
    if not doi: return None
    # print(f"    Trying Semantic Scholar for DOI: {doi} ...")
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
    try:
        resp = requests.get(url, timeout=10, proxies=PROXIES)
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get('abstract')
            if abstract:
                return abstract.strip()
            else:
                print(f"    ⚠️ Semantic Scholar: Abstract is None for {doi}")
        else:
            print(f"    ❌ Semantic Scholar Status: {resp.status_code} | {resp.text[:100]}")
    except Exception as e:
        print(f"    ❌ Semantic Scholar Exception: {e}")
        pass
    return None

def fetch_abstract_from_url(url, retries=2):
    """
    尝试从网页中提取完整摘要和预览图 (针对 RSS 摘要不全的情况)
    Returns: (abstract_text, image_url)
    """
    # print(f"    Fetching from: {url} ...") 
    
    # Use Cloudscraper to bypass Cloudflare
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    
    current_url = url
    abstract = None
    image_url = None

    try:
        for attempt in range(retries):
            # Try to fetch
            try:
                # Add headers manually to the request, combining with scraper's default
                req_headers = HEADERS.copy()
                resp = scraper.get(current_url, headers=req_headers, proxies=PROXIES, timeout=20, allow_redirects=True)
            except:
                return None, None, []
                
            html_text = resp.text
            
            # Special Handling for ScienceDirect / Elsevier Redirects
            # They often use a meta refresh or a JS redirect that we can't easily execute.
            # But sometimes the "Redirect=..." parameter in the URL tells us where it's going.
            if "sciencedirect.com" in resp.url and (resp.status_code == 403 or resp.status_code == 401):    
                 # If blocked by ScienceDirect, we can't do much with simple requests.
                 # But sometimes the initial linkinghub URL works if we don't follow all redirects or manage cookies differently.
                 # For now, just mark failed.
                 pass

            # Check for generic Meta Refresh
            refresh_match = re.search(r'<meta\s+http-equiv=["\']?REFRESH["\']?\s+content=["\']\d+;\s*url=[\'"]?(.*?)[\'"]?["\']', html_text, re.IGNORECASE)
            if refresh_match:
                next_url = refresh_match.group(1)
                next_url = html.unescape(next_url)
                if next_url.startswith('/'):
                    from urllib.parse import urljoin
                    next_url = urljoin(resp.url, next_url)
                
                current_url = next_url
                time.sleep(1)
                continue 
            
            # --- Extract Image (og:image) ---
            if not image_url:
                img_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE)
                if img_match:
                    image_url = img_match.group(1)
                else:
                    # Try twitter:image
                    img_match = re.search(r'<meta\s+name=["\']twitter:image["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE)
                    if img_match:
                        image_url = img_match.group(1)

            # --- Extract Authors ---
            found_authors = []
            author_matches = re.findall(r'<meta\s+name=["\']citation_author["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE)
            for m in author_matches:
                found_authors.append(clean_html(m))
            
            if not found_authors:
                creator_matches = re.findall(r'<meta\s+name=["\']DC.Creator["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE)
                for m in creator_matches:
                    found_authors.append(clean_html(m))

            # --- Extract Abstract ---
            found_abstract = None
            
            # 1. Try citation_abstract (Standard for academic papers)
            match = re.search(r'<meta\s+name=["\']citation_abstract["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE | re.DOTALL)
            if match:
                found_abstract = clean_html(match.group(1))
            
            # 2. Try DC.Description
            if not found_abstract:
                match = re.search(r'<meta\s+name=["\']DC.Description["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE | re.DOTALL)
                if match:
                    found_abstract = clean_html(match.group(1))

            # 3. Try description
            if not found_abstract:
                match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_text, re.IGNORECASE | re.DOTALL)
                if match:
                    desc = clean_html(match.group(1))
                    # Elsevier's login page description is generic, filter it.
                    if "ScienceDirect" not in desc and len(desc) > 150:
                        found_abstract = desc
            
            # If status is 200 but no abstract, maybe it's just not in meta tags.
            if resp.status_code == 200 and not found_abstract:
                # Try JSON-LD (ScienceDirect sometimes has it)
                json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.DOTALL)
                if json_ld_match:
                     try:
                         data = json.loads(json_ld_match.group(1))
                         if 'description' in data:
                             found_abstract = clean_html(data['description'])
                     except:
                         pass

            if found_abstract:
                return found_abstract, image_url, found_authors
            
            # If we got image but not abstract
            return None, image_url, found_authors 
            
    except Exception as e:
        pass
    return None, None, []

def check_keywords(text):
    """检查文本是否包含特定关键词"""
    if not KEYWORDS: return False
    text_lower = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False

def is_noise(title):
    """过滤非学术文章（针对 Nature/Science 等混杂 RSS）"""
    noise_keywords = [
        "Daily Briefing", "Podcast:", "Audio:", "Author Correction", 
        "Publisher Correction", "Books & Arts", "Editorial", "News & Views",
        "World View", "Career Feature", "Outlook", "Where I Work"
    ]
    for k in noise_keywords:
        if k in title:
            return True
    return False

def is_within_days(date_struct, days):
    """检查日期是否在指定天数内"""
    if not date_struct: return False # 无法获取日期的默认不通过，或者通过？稳妥起见，如果没日期，可能太老或太新。
    # 这里我们假设 date_struct 是 time.struct_time
    try:
        dt_entry = datetime.datetime(*date_struct[:6])
        dt_now = datetime.datetime.now()
        delta = dt_now - dt_entry
        return delta.days <= days
    except:
        return False

def check_arxiv_updates(history, days_lookback):
    """Check ArXiv for new papers"""
    print(f"🔎 检查 (ArXiv): ...")
    
    # 针对你的研究方向定制查询
    # TiNi, Shape Memory, DFT, Molecular Dynamics
    query = 'cat:cond-mat.mtrl-sci AND ("shape memory" OR "NiTi" OR "DFT" OR "molecular dynamics")'
    
    try:
        search = arxiv.Search(
            query=query,
            max_results=50,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        new_papers = []
        for result in search.results():
            paper_id = result.entry_id.split('/')[-1]
            if paper_id in history: continue
            
            # Check date
            if (datetime.datetime.now(datetime.timezone.utc) - result.published).days > days_lookback:
                continue

            # Check keywords again locally if needed, or trust query
            if not check_keywords(result.title + " " + result.summary):
                continue
            
            # ArXiv 自带高质量摘要，不需要爬网页
            paper = {
                "title": result.title,
                "link": result.entry_id,
                "summary": result.summary.replace("\n", " "),
                "source": "ArXiv",
                "date": result.published,
                "id": paper_id
            }
            new_papers.append(paper)
        return new_papers
    except Exception as e:
        print(f"  ❌ ArXiv Search Error: {e}")
        return []

def get_ai_summary(title, abstract, include_translation=False):
    """
    Returns: (summary_text, relevance_score)
    """
    if not abstract or len(abstract) < 50:
        return "⚠️ 摘要过短，跳过总结。", 0
    
    user_interest = "NiTi based shape memory alloys, martensitic transformation, DFT/MD/KMC computational modeling, TEM/EBSD characterization."

    # 针对材料学的 Prompt (详细版)
    prompt = f"""
    Role: Research Assistant in Materials Science.
    Task: Analyze the abstract for a Ph.D. candidate focusing on: {user_interest}.
    
    Output Format (JSON):
    {{
        "relevance_score": <0-10>,  // 0: Irrelevant, 10: Highly Relevant (Directly related to NiTi or methods used)
        "one_sentence_takeaway": "Chinese summary of the core finding.",
        "methodology": "List specific methods used (e.g., VASP, LAMMPS, HRTEM)",
        "why_read": "One specific reason why the user should read this (or 'Skip' if score < 5)",
        "full_translation": "Full Chinese translation of the abstract (only if requested)"
    }}
    """

    if include_translation:
        prompt += """
    (Please include the 'full_translation' field in the JSON)
    """

    prompt += f"""
    **Paper Title:** {title}
    **Abstract:** {abstract[:3000]}
    """
    
    try:
        # 即使 PROXIES 为 None，requests 也会尝试读取系统环境变量
        resp = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"} 
            },
            timeout=30,
            proxies=PROXIES 
        )
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content'].strip()
            try:
                data = json.loads(content)
                score = data.get('relevance_score', 0)
                icon = "🔴" if score >= 8 else ("⚪️" if score < 5 else "🟡")
                
                summary = (
                    f"{icon} **Relevance**: {score}/10\n"
                    f"💡 **Takeaway**: {data.get('one_sentence_takeaway')}\n"
                    f"🛠 **Method**: {data.get('methodology')}\n"
                    f"🧐 **Why Read**: {data.get('why_read')}\n"
                )
                if include_translation and 'full_translation' in data:
                    summary += f"\n📝 **Translation**:\n{data['full_translation']}"
                
                return summary, score
            except json.JSONDecodeError:
                return content, 0 # Fallback to raw content if not JSON
        else:
            return f"AI 错误: {resp.status_code}", 0
    except Exception as e:
        print(f"AI 连接失败: {e}")
        return "AI 服务连接超时", 0

def send_telegram_msg(message):
    if not message: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    max_len = 3000
    for i in range(0, len(message), max_len):
        chunk = message[i:i+max_len]
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown", 
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload, timeout=10, proxies=PROXIES)
            time.sleep(1)
        except Exception as e:
            print(f"Telegram 发送失败: {e}")

def send_telegram_photo(photo_url, caption=None):
    if not photo_url: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TG_CHAT_ID,
        "photo": photo_url,
        "caption": caption[:1024] if caption else "",
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10, proxies=PROXIES)
        time.sleep(1)
    except Exception as e:
        print(f"Telegram 发送图片失败: {e}")

def extract_first_image(html_content):
    if not html_content: return None
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

# ============================
#          主程序
# ============================

def get_crossref_papers(issn, limit=20):
    """
    Fetch latest papers from CrossRef API by ISSN (free, no-key).
    Returns list of entries compatible with feedparser structure.
    """
    base_url = "https://api.crossref.org/works"
    params = {
        "filter": f"issn:{issn}",
        "sort": "published",
        "order": "desc",
        "rows": limit
    }
    entries = []
    try:
        resp = requests.get(base_url, params=params, headers=CROSSREF_HEADERS, timeout=15)
        if resp.status_code == 200:
            items = resp.json().get('message', {}).get('items', [])
            for item in items:
                title_list = item.get('title', [])
                title = title_list[0] if title_list else "No Title"
                
                # DOI
                doi = item.get('DOI', "")
                link = f"https://doi.org/{doi}" if doi else ""
                
                # Date
                pub_parts = item.get('published', {}).get('date-parts', [[0,0,0]])[0]
                # Format: YYYY-M-D
                try:
                    # 将 CrossRef 的日期部分转换为 struct_time 格式以便统一处理
                    # pub_parts 可能只有年 [2023]，或者年月 [2023, 1]，或者年月日 [2023, 1, 1]
                    year = pub_parts[0]
                    month = pub_parts[1] if len(pub_parts) > 1 else 1
                    day = pub_parts[2] if len(pub_parts) > 2 else 1
                    published_parsed = time.struct_time((year, month, day, 0, 0, 0, 0, 0, 0))
                except:
                    published_parsed = None
                
                # Authors
                authors_list = item.get('author', [])
                auth_arr = []
                for a in authors_list:
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if not name: name = a.get('family', '') or a.get('name', 'Unknown')
                    auth_arr.append(name)
                
                # Mock Entry Object
                class Entry:
                    pass
                e = Entry()
                e.title = title
                e.link = link
                e.doi = doi
                e.id = link
                e.summary = f"DOI: {doi} (Abstract not available via CrossRef)"
                e.published_parsed = published_parsed
                e.authors = auth_arr
                
                entries.append(e)
    except Exception as e:
        print(f"  ❌ CrossRef Error: {e}")
        
    return entries

def format_authors(authors_data):
    """Simple helper to format authors list.
    authors_data can be:
    - String: "Name"
    - List of str: ["A", "B"]
    - List of dict: [{'name': 'A', 'is_corresponding': True}, ...]
    """
    if not authors_data: return "Unknown"
    
    if isinstance(authors_data, str):
        return authors_data
    
    parts = []
    if isinstance(authors_data, list):
        for a in authors_data:
            if isinstance(a, str):
                parts.append(a)
            elif isinstance(a, dict):
                name = a.get('name', 'Unknown')
                if a.get('is_corresponding'):
                    # Bold corresponding author
                    parts.append(f"**{name}**")
                else:
                    parts.append(name)
    
    return ", ".join(parts) if parts else "Unknown"

def export_to_siyuan(title, content, score, notebook_id=None):
    if not (SIYUAN_API_URL and SIYUAN_API_TOKEN): return
    try:
        score_val = float(score)
    except:
        score_val = 0
    if score_val < SIYUAN_THRESHOLD: return

    print(f"    📤 Exporting to SiYuan Note (Score {score})...")
    
    nb_id = notebook_id or SIYUAN_NOTEBOOK_ID
    if not nb_id: return

    # Sanitize title
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    path = f"/EssayUpdate/{datetime.date.today()}/{safe_title}"

    payload = {
        "notebook": nb_id,
        "path": path,
        "markdown": content
    }
    
    headers = {"Authorization": f"Token {SIYUAN_API_TOKEN}"}
    
    try:
        resp = requests.post(
            f"{SIYUAN_API_URL}/api/filetree/createDocWithMd", 
            json=payload, 
            headers=headers, 
            timeout=10
        )
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print(f"    ✅ SiYuan Note Created: {path}")
        else:
            print(f"    ❌ SiYuan Error: {resp.text}")
    except Exception as e:
        print(f"    ❌ SiYuan Exception: {e}")

def main():
    print(f"🚀 启动任务: {datetime.datetime.now().strftime('%H:%M:%S')}")
    print("💡 提示: 如果报错 'ConnectionError'，请检查你的代理软件是否开启了 'System Proxy (系统代理)' 模式。")
    
    history = load_history()
    new_history_ids = []
    messages = []
    key_papers_markdown = [] # 用于存储关键词文章的笔记
    total_new = 0
    
    # 1. Process Standard RSS Feeds
    for journal_name, rss_url in RSS_JOURNALS.items():
        print(f"🔎 检查 (RSS): {journal_name} ...")
        
        try:
            # Use cloudscraper for RSS too, just in case
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(rss_url, proxies=PROXIES, timeout=15)
            
            if resp.status_code == 404:
                print(f"  ❌ 状态码 404 - Feed Not Found")
                continue
            elif resp.status_code != 200:
                print(f"  ❌ 状态码 {resp.status_code}")
                continue

            feed = feedparser.parse(resp.content)
            
            count = 0
            # 移除切片限制，改为时间判断
            for entry in feed.entries:
                guid = entry.id if 'id' in entry else entry.link
                if guid in history or guid in new_history_ids:
                    continue
                
                title = entry.title
                link = entry.link

                # 特殊过滤: Nature 正刊仅保留学术论文 (链接包含 s41586)
                # News/Editorials 通常包含 d41586
                if journal_name == "Nature (正刊)" and "s41586" not in link:
                    continue

                # 特殊过滤: Science 仅保留 Research Article
                if journal_name == "Science" and entry.get('dc_type') != "Research Article":
                    continue

                # 通用噪声过滤
                if is_noise(title):
                    continue

                # 时间过滤
                if hasattr(entry, 'published_parsed'):
                    if not is_within_days(entry.published_parsed, DAYS_LOOKBACK):
                        continue
                
                # Try to get full content from entry.content (preferred) or summary
                raw_summary = ''
                if 'content' in entry:
                    # entry.content is a list of dicts
                    content_list = [c.get('value', '') for c in entry.content]
                    raw_summary = " ".join(content_list)
                
                if not raw_summary:
                    raw_summary = entry.get('summary', '') or entry.get('description', '')

                clean_summary = clean_html(raw_summary)
                
                print(f"  ✨ 新发现: {title[:30]}...")
                
                # --- Quick Filter (Title based) ---
                # Check if it's VIP Journal or Title matches keywords
                is_vip_journal = journal_name in ["Nature Materials", "Nature (正刊)"]
                title_match = check_keywords(title)
                
                # If NOT VIP and Title doesn't match, we can skip fetching abstract/image from web.
                # UNLESS: You really want to check abstract for keywords heavily.
                # Request was: "If title mismatch, pass directly, don't fetch abstract"
                if not is_vip_journal and not title_match:
                     # Skip heavy lifting
                     print("    ➡️ Title mismatch & Not VIP, Skipping...")
                     new_history_ids.append(guid) # Mark as seen so we don't check again
                     continue

                # 强制对所有新文章尝试抓取 (因为RSS摘要通常不完整)
                fetched_abstract, fetched_image, fetched_authors = fetch_abstract_from_url(link)
                if fetched_abstract and len(fetched_abstract) > len(clean_summary):
                    clean_summary = fetched_abstract
                    print(f"    ✅ 成功抓取完整摘要 ({len(clean_summary)} chars)")
                
                # --- Authors Handling ---
                current_authors = fetched_authors
                if not current_authors:
                     # Try from RSS feed
                     if 'authors' in entry and entry.authors:
                         current_authors = [a.get('name', '') for a in entry.authors]
                     elif 'author' in entry:
                         current_authors = entry.author
                
                authors_str = format_authors(current_authors)

                # 关键词匹配 (使用完整摘要再次确认，以防 Title 漏掉但 Abstract 命中？ 
                # User request says: "If title not valid, pass directly". 
                # So if we are here, either it is VIP or Title Matched. 
                # We update match status with abstract just in case it helps AI score context.
                is_keyword_match = check_keywords(title + " " + clean_summary)

                # Filter Logic:
                # 1. If VIP Journal -> Process
                # 2. If Keyword Match -> Process
                # 3. Else -> Skip
                if not (is_vip_journal or is_keyword_match):
                    continue

                # AI Summary
                # 如果是关键词文章或VIP，需保留完整摘要并进行翻译
                ai_result, ai_score = get_ai_summary(title, clean_summary, include_translation=(is_keyword_match or is_vip_journal))
                
                # Push Logic:
                # 1. VIP -> Always Push
                # 2. Key Paper -> Always Push (Ignore AI Score threshold)
                should_push = False
                if is_vip_journal:
                    should_push = True
                elif is_keyword_match:
                    should_push = True
                
                if not should_push:
                    continue

                # Extract image if it's a key paper
                img_url = None
                # Always try to fetch image if we are pushing
                if fetched_image:
                    img_url = fetched_image
                else:
                    img_url = extract_first_image(raw_summary)
                
                limit = 50000 
                orig_abstract = clean_summary[:limit]
                title_prefix = "🌟 (Key) " if is_keyword_match else ""
                if is_vip_journal and not is_keyword_match:
                    title_prefix = "🔥 (VIP) "
                
                msg_text = (
                    f"📄 *{journal_name}*\n"
                    f"**{title_prefix}{title}**\n"
                    f"👥 Authors: {authors_str}\n"
                    f"[Link]({link})\n\n"
                    f"{ai_result}\n\n"
                    f"📝 *Original Abstract:*\n"
                    f"_{orig_abstract}_\n"
                    f"━━━━━━━━━━━━━━━━━━"
                )
                messages.append({'text': msg_text, 'image': img_url})

                # 保存关键词文章内容到列表
                if is_keyword_match or is_vip_journal:
                    # 重新整理一下 Markdown 内容
                    img_md = f"![Image]({img_url})\n\n" if img_url else ""
                    md_note = (
                        f"## {title}\n"
                        f"- **Journal**: {journal_name}\n"
                        f"- **Authors**: {authors_str}\n"
                        f"- **Link**: <{link}>\n\n"
                        f"{img_md}"
                        f"### AI Summary\n{ai_result}\n\n"
                        f"### Original Abstract\n{clean_summary}\n"
                        f"\n---\n"
                    )
                    key_papers_markdown.append(md_note)
                    # SiYuan Export
                    export_to_siyuan(title, md_note, ai_score)

                new_history_ids.append(guid)
                count += 1
            
            if count > 0:
                print(f"  ✅ 待推送 {count} 篇")
                save_history(history + new_history_ids)
            total_new += count
            
        except Exception as e:
            print(f"  ❌ 异常: {e}")

    # 2. Process CrossRef Journals (Elsevier)
    for journal_name, issn in CROSSREF_JOURNALS.items():
        print(f"🔎 检查 (CrossRef): {journal_name} ...")
        entries = get_crossref_papers(issn, limit=MAX_PAPERS_PER_SOURCE)
        
        count = 0
        for entry in entries:
            if entry.id in history or entry.id in new_history_ids:
                continue
            
            # 时间过滤
            if hasattr(entry, 'published_parsed'):
                if not is_within_days(entry.published_parsed, DAYS_LOOKBACK):
                    continue
            
            # --- Quick Filter (Title based) ---
            print(f"  ✨ 新发现: {entry.title[:30]}...")
            is_vip_journal = journal_name in ["Acta Materialia", "Scripta Materialia", "Intl. J. of Plasticity", "J. Mater. Sci. & Tech"]
            title_match = check_keywords(entry.title)
            
            if not is_vip_journal and not title_match:
                 print("    ➡️ Title mismatch & Not VIP, Skipping...")
                 new_history_ids.append(entry.id)
                 continue

            # 尝试获取完整摘要
            full_abstract = None
            fetched_image = None
            fetched_authors = None
            openalex_authors = None
            
            # 1. Web Fetch (ScienceDirect 等可能需要多次跳转)
            full_abstract, fetched_image, fetched_authors = fetch_abstract_from_url(entry.link)
            
            # 2. OpenAlex (Preferred Metdata Source)
            if not full_abstract and hasattr(entry, 'doi') and entry.doi:
                 full_abstract, openalex_authors = fetch_metadata_from_openalex(entry.doi)

            # 3. Elsevier API (If key configured)
            if not full_abstract and hasattr(entry, 'doi') and entry.doi:
                 full_abstract = fetch_abstract_from_elsevier(entry.doi)

            # 4. Semantic Scholar Fallback
            if not full_abstract and hasattr(entry, 'doi') and entry.doi:
                 full_abstract = fetch_abstract_from_semantic_scholar(entry.doi)

            # 4. CrossRef XML Fallback
            if not full_abstract and hasattr(entry, 'doi') and entry.doi:
                 full_abstract = fetch_abstract_from_crossref_xml(entry.doi)


            if full_abstract:
                clean_summary = full_abstract
                print(f"    ✅ 成功获取摘要 ({len(clean_summary)} chars)")
            else:
                clean_summary = ""
                print("    ❌ 无法获取摘要 (Web/Semantic Scholar failed)")

            # 关键词匹配 (标题 + 摘要)
            is_keyword_match = check_keywords(entry.title + " " + clean_summary)
            is_vip_journal = journal_name in ["Acta Materialia", "Scripta Materialia", "Intl. J. of Plasticity", "J. Mater. Sci. & Tech"]

            # Filter Logic
            if not (is_vip_journal or is_keyword_match):
                continue

            print(f"  ✨ 新发现: {entry.title[:30]}...")
            
            # AI Summary
            ai_result = ""
            ai_score = 0
            if clean_summary:
                ai_result, ai_score = get_ai_summary(entry.title, clean_summary, include_translation=(is_keyword_match or is_vip_journal))
            else:
                ai_result = "⚠️ Abstract not available via CrossRef/Web/SemanticScholar. Please click link to view."
            
            # Push Logic
            should_push = False
            if is_vip_journal:
                should_push = True
            elif is_keyword_match:
                should_push = True
            
            if not should_push:
                continue

            title_prefix = "🌟 (Key) " if is_keyword_match else ""
            if is_vip_journal and not is_keyword_match:
                title_prefix = "🔥 (VIP) "

            # --- Authors Handling ---
            final_authors = []
            if openalex_authors:
                final_authors = openalex_authors
            elif fetched_authors:
                final_authors = fetched_authors
            elif hasattr(entry, 'authors'):
                final_authors = entry.authors
                
            authors_str = format_authors(final_authors)

            msg_text = (
                f"📄 *{journal_name}*\n"
                f"**{title_prefix}{entry.title}**\n"
                f"👥 Authors: {authors_str}\n"
                f"[Link]({entry.link})\n\n"
                f"{ai_result}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            
            # Note: CrossRef usually no image unless we fetch full HTML.
            img_url = fetched_image if fetched_image else None
            messages.append({'text': msg_text, 'image': img_url})

            # Save Key Paper Note
            if is_keyword_match or is_vip_journal:
                img_md = f"![Image]({img_url})\n\n" if img_url else ""
                md_note = (
                    f"## {entry.title}\n"
                    f"- **Journal**: {journal_name}\n"
                    f"- **Link**: <{entry.link}>\n\n"
                    f"{img_md}"
                    f"### AI Summary\n{ai_result}\n\n"
                    f"### Original Abstract\n{clean_summary}\n"
                    f"\n---\n"
                )
                key_papers_markdown.append(md_note)
                export_to_siyuan(entry.title, md_note, ai_score)
            
            new_history_ids.append(entry.id)
            count += 1
            
        if count > 0:
            print(f"  ✅ 待推送 {count} 篇")
            save_history(history + new_history_ids)
        total_new += count

    # 3. Process ArXiv Updates
    arxiv_papers = check_arxiv_updates(history + new_history_ids, DAYS_LOOKBACK)
    if arxiv_papers:
        print(f"  ✅ ArXiv 新发现 {len(arxiv_papers)} 篇")
        for paper in arxiv_papers:
            # AI Summary
            # ArXiv papers are all "Key Papers" by definition of query/keyword check
            ai_result, ai_score = get_ai_summary(paper['title'], paper['summary'], include_translation=True)
            
            # Filter: Check Relevance Score >= 7
            if ai_score < 7:
                 print(f"    ⚠️ ArXiv Paper Skipped (Low Relevance: {ai_score}): {paper['title'][:30]}")
                 continue

            msg_text = (
                f"📄 *ArXiv Preprints*\n"
                f"**🌟 (Key) {paper['title']}**\n"
                f"[Link]({paper['link']})\n\n"
                f"{ai_result}\n\n"
                f"📝 *Abstract:*\n_{paper['summary'][:500]}..._\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            messages.append({'text': msg_text, 'image': None})
            
            # Save to MarkDown
            md_note = (
                f"## {paper['title']}\n"
                f"- **Journal**: ArXiv\n"
                f"- **Link**: <{paper['link']}>\n\n"
                f"### AI Summary\n{ai_result}\n\n"
                f"### Abstract\n{paper['summary']}\n"
                f"\n---\n"
            )
            key_papers_markdown.append(md_note)
            export_to_siyuan(paper['title'], md_note, ai_score)
            
            new_history_ids.append(paper['id'])
            total_new += 1

    # 发送消息
    if messages:
        # 保存 Markdown 文件
        if key_papers_markdown:
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            md_filename = f"Key_Papers_{today_str}.md"
            mode = 'a' if os.path.exists(md_filename) else 'w'
            try:
                with open(md_filename, mode, encoding='utf-8') as f:
                    if mode == 'w':
                        f.write(f"# 🌟 Key Papers ({today_str})\n\n")
                    for note in key_papers_markdown:
                        f.write(note)
                print(f"💾 重点文章笔记已保存: {md_filename}")
            except Exception as e:
                print(f"❌ 保存笔记失败: {e}")

        print(f"📤 正在推送到 Telegram...")
        # Split into chunks if too many messages
        full_text = f"📅 *期刊更新日报* ({datetime.date.today()})\n共发现 {total_new} 篇新论文\n━━━━━━━━━━━━━━━━━━\n\n"
        
        # Send one by one to avoid huge payload
        send_telegram_msg(full_text)
        for m in messages:
            if isinstance(m, dict):
                send_telegram_msg(m['text'])
                if m.get('image'):
                    send_telegram_photo(m['image'])
            else:
                send_telegram_msg(m)
                send_telegram_msg(m)
        
        history.extend(new_history_ids)
        save_history(history)
        print("🎉 完成！")
    else:
        print("😴 暂无新文章。")

if __name__ == "__main__":
    main()