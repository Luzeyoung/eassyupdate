import requests
import json
import datetime
import argparse
import os
import sys
import re
import html
import cloudscraper

# Reconfigure stdout to utf-8 to avoid encoding errors with emojis on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass # Python < 3.7 or not a TTY

# --- Config ---
TG_TOKEN = "YOUR_TG_TOKEN"
TG_CHAT_ID = "8384265672"
AI_API_KEY = "YOUR_AI_API_KEY"
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"
OPENALEX_API_KEY = "YOUR_OPENALEX_API_KEY"
ELSEVIER_API_KEY = "YOUR_ELSEVIER_API_KEY" 

PROXIES = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

# --- VIP Journals List (Lower case for matching) ---
VIP_JOURNALS = [
    "acta materialia",
    "scripta materialia",
    "international journal of plasticity",
    "journal of materials science & technology",
    "journal of materials science and technology",
    "nature",
    "nature materials",
    "nature communications",
    "science",
    "advanced materials",
    "materials today",
    "nano letters",
    "acs nano"
]

# --- SiYuan Config ---
SIYUAN_API_URL = "http://10.42.0.58:6806"
SIYUAN_API_TOKEN = "YOUR_SIYUAN_API_TOKEN"
SIYUAN_NOTEBOOK_ID = "20260301131510-yehu9uc"

# --- Helpers ---

def export_to_siyuan(title, content, notebook_id=None):
    if not (SIYUAN_API_URL and SIYUAN_API_TOKEN): return
    print(f"📤 Exporting review to SiYuan Note: {title}...")
    
    nb_id = notebook_id or SIYUAN_NOTEBOOK_ID
    if not nb_id: return

    # Sanitize title
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    curr_date = datetime.date.today().strftime('%Y-%m-%d')
    path = f"/EssayUpdate/Research/{curr_date}/{safe_title}"

    payload = {
        "notebook": nb_id,
        "path": path,
        "markdown": content
    }
    
    headers = {
        "Authorization": f"Token {SIYUAN_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(f"{SIYUAN_API_URL}/api/filetree/createDocWithMd", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print(f"✅ SiYuan Note Created: {path}")
        else:
            print(f"❌ SiYuan Error: {resp.text}")
    except Exception as e:
        print(f"❌ SiYuan Exception: {e}")

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

def fetch_abstract_from_elsevier(doi):
    if not ELSEVIER_API_KEY or not doi: return None
    # print(f"      Trying Elsevier API for {doi}...")
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    headers = {
        "X-ELS-APIKey": ELSEVIER_API_KEY,
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies=PROXIES)
        if resp.status_code == 200:
            data = resp.json()
            coredata = data.get('full-text-retrieval-response', {}).get('coredata', {})
            abstract = coredata.get('dc:description')
            if abstract:
                 return clean_html(abstract)
    except Exception:
        pass
    return None

def fetch_abstract_from_semantic_scholar(doi):
    if not doi: return None
    # print(f"      Trying Semantic Scholar for {doi}...")
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
    try:
        resp = requests.get(url, timeout=10, proxies=PROXIES)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('abstract')
    except Exception:
        pass
    return None

def fetch_abstract_from_crossref_xml(doi):
    if not doi: return None
    # print(f"      Trying CrossRef XML for {doi}...")
    url = f"https://api.crossref.org/works/{doi}"
    headers = {
        "Accept": "application/vnd.crossref.unixref+xml",
        "User-Agent": "EssayUpdateBot/1.0 (mailto:2410017@tongji.edu.cn)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies=PROXIES)
        if resp.status_code == 200:
            xml = resp.text
            match = re.search(r'<(?:jats:)?abstract[^>]*>(.*?)</(?:jats:)?abstract>', xml, re.IGNORECASE | re.DOTALL)
            if match: return clean_html(match.group(1))
            match = re.search(r'<abstract[^>]*>(.*?)</abstract>', xml, re.IGNORECASE | re.DOTALL)
            if match: return clean_html(match.group(1))
    except Exception:
        pass
    return None

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def send_telegram_file(chat_id, file_path):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            requests.post(url, data=data, files=files, timeout=60)
    except Exception as e:
        print(f"❌ Telegram File Error: {e}")

def get_ai_review(keywords, papers):
    if not papers: return "No papers found."
    
    # Filter only papers with valid abstracts
    valid_papers = [p for p in papers if p['abstract'] and len(p['abstract']) > 50]
    
    print(f"🧠 Asking AI to review {len(valid_papers)} papers...")

    content_block = ""
    # We take top 80 mostly due to context window limits, even though DeepSeek is large.
    # 80 papers * 250 words = 20k tokens approx.
    for idx, p in enumerate(valid_papers[:80]): 
        abstract_snippet = p['abstract'][:1200]
        authors = p.get('authors', 'Unknown')
        content_block += f"Paper {idx+1}: [{p['year']}] {p['title']} (Authors: {authors}, Venue: {p['venue']}, Cited: {p['cited_by']})\nAbstract: {abstract_snippet}\n\n"

    prompt = (
        f"You are an expert academic researcher. "
        f"Review these {len(valid_papers)} papers on '{keywords}' (2023-2026).\n"
        f"Focus heavily on high-impact papers (VIP Journals and highly cited ones).\n\n"
        f"Produce a Markdown report:\n"
        f"# In-Depth Review: {keywords}\n"
        f"## 1. Executive Summary\n"
        f"## 2. Research Trends & Statistics\n"
        f"## 3. Key Methodologies\n"
        f"## 4. Critical Findings (Cite papers e.g. [Paper 1])\n"
        f"## 5. Controversies & Gaps\n"
        f"## 6. Conclusion\n\n"
        f"Papers provided below:\n{content_block}"
    )

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_API_KEY}"}
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a senior material scientist."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3, 
        "stream": False
    }
    
    try:
        # Increase timeout for long thinking
        resp = requests.post(f"{AI_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=240)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        else:
            return f"AI Error: {resp.text}"
    except Exception as e:
        return f"AI Exception: {e}"

def search_openalex_robust(keywords, target_count=100):
    print(f"🔍 Searching OpenAlex for '{keywords}' (fetching pool of 400)...")
    
    url = "https://api.openalex.org/works"
    params = {
        "search": keywords,
        # Expanded pool to find enough VIPs
        "filter": "from_publication_date:2023-01-01,type:article",
        "sort": "relevance_score:desc", 
        "per_page": 200, 
    }
    headers = {"User-Agent": "mailto:2410017@tongji.edu.cn", "x-api-key": OPENALEX_API_KEY}
    
    extracted_papers = []

    # Fetch 2 pages (400 results) to have a good pool
    try:
        for page in [1, 2]:
            params['page'] = page
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code != 200: break
            
            data = resp.json()
            results = data.get('results', [])
            if not results: break
            
            for item in results:
                title = item.get('title', 'No Title')
                doi = item.get('doi', '').replace("https://doi.org/", "")
                pub_year = item.get('publication_year', '')
                cited_by = item.get('cited_by_count', 0)
                
                venue = "Unknown"
                if item.get('primary_location'):
                    source = item.get('primary_location').get('source', {})
                    if source:
                        venue = source.get('display_name', 'Unknown')
                if not venue: venue = "Unknown"
                
                is_vip = any(vip in venue.lower() for vip in VIP_JOURNALS)
                abstract = reconstruct_openalex_abstract(item.get('abstract_inverted_index'))
                
                # Authors Extraction
                authorships = item.get('authorships', [])
                auth_list = []
                for auth in authorships:
                    a_name = auth.get('author', {}).get('display_name', 'Unknown')
                    is_corr = auth.get('is_corresponding', False)
                    # Helper for formatting
                    if is_corr:
                        auth_list.append(f"**{a_name}**")
                    else:
                        auth_list.append(a_name)
                authors_str = ", ".join(auth_list)

                extracted_papers.append({
                    'title': title,
                    'abstract': abstract,
                    'year': pub_year,
                    'doi': doi,
                    'cited_by': cited_by,
                    'venue': venue,
                    'is_vip': is_vip,
                    'authors': authors_str
                })
        
        # Sorting Logic
        # 1. VIPs (Sorted by Cited By)
        # 2. Others (Sorted by Cited By)
        vip_group = [p for p in extracted_papers if p['is_vip']]
        other_group = [p for p in extracted_papers if not p['is_vip']]
        
        vip_group.sort(key=lambda x: x['cited_by'], reverse=True)
        other_group.sort(key=lambda x: x['cited_by'], reverse=True)
        
        final_selection = (vip_group + other_group)[:target_count]
        
        print(f"📊 Selected {len(final_selection)} papers (VIPs: {len(vip_group)} available).")
        
        # Enrich Abstracts
        count_enriched = 0
        for i, paper in enumerate(final_selection):
            if not paper['abstract'] or len(paper['abstract']) < 50:
                print(f"   [{i+1}/{len(final_selection)}] Fetching abstract for: {paper['title'][:30]}...")
                ab = fetch_abstract_from_elsevier(paper['doi'])
                if not ab: ab = fetch_abstract_from_semantic_scholar(paper['doi'])
                if not ab: ab = fetch_abstract_from_crossref_xml(paper['doi'])
                
                if ab:
                    paper['abstract'] = ab
                    count_enriched += 1
                else:
                    paper['abstract'] = "(Abstract unavailable)"
        
        print(f"✅ Enriched {count_enriched} missing abstracts.")
        return final_selection

    except Exception as e:
        print(f"❌ Exception in search: {e}")
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("keywords", help="Keywords to search", nargs='+')
    parser.add_argument("--chat_id", help="Telegram Chat ID", default=TG_CHAT_ID)
    args = parser.parse_args()
    
    target_keywords = " ".join(args.keywords)
    chat_id = args.chat_id
    
    send_telegram_msg(chat_id, f"🔍 Deep Research: *{target_keywords}*\nFetching Top 100 Papers (VIP Priority)...")

    # 1. Search
    papers = search_openalex_robust(target_keywords, target_count=100)
    
    if not papers:
        send_telegram_msg(chat_id, "❌ No relevant papers found.")
        return

    # 2. Analyze
    send_telegram_msg(chat_id, f"🧠 Writing review based on {len(papers)} papers...")
    review_text = get_ai_review(target_keywords, papers)
    
    # 3. Save
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = "".join([c if c.isalnum() else "_" for c in target_keywords])[:20]
    filename = f"Review_{safe_kw}_{timestamp}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(review_text)
        f.write("\n\n---\n# Selected Papers\n")
        f.write("Note: ★ indicates VIP Journal\n\n")
        for idx, p in enumerate(papers):
            vip_mark = "★ " if p['is_vip'] else ""
            f.write(f"### {idx+1}. {vip_mark}{p['title']}\n")
            f.write(f"- **Authors**: {p.get('authors', 'Unknown')}\n")
            f.write(f"- **Journal**: {p['venue']}\n")
            f.write(f"- **Year**: {p['year']} | **Cited By**: {p['cited_by']}\n")
            f.write(f"- **DOI**: https://doi.org/{p['doi']}\n")
            f.write("\n")

    # 4. Send
    summary_preview = f"DONE. Analyzed {len(papers)} papers.\n\n" + review_text[:800] + "..."
    send_telegram_msg(chat_id, summary_preview)
    send_telegram_file(chat_id, filename)
    print("✅ Research Task Complete.")
    
    # 5. Export to SiYuan Note
    export_to_siyuan(f"Review - {target_keywords} ({datetime.date.today()})", review_text)

if __name__ == "__main__":
    main()
