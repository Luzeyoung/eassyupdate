import requests
import json
import datetime
import argparse
import os
import sys
import re
import html

# Reconfigure stdout to utf-8 to avoid encoding errors with emojis on Windows
sys.stdout.reconfigure(encoding='utf-8')

# --- Config ---
TG_TOKEN = "YOUR_TG_TOKEN"
TG_CHAT_ID = "8384265672"
AI_API_KEY = "YOUR_AI_API_KEY"
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"
OPENALEX_API_KEY = "YOUR_OPENALEX_API_KEY"
# Optional: Reuse Elsevier Key if needed for abstracts, though OpenAlex is usually okay for metadata
ELSEVIER_API_KEY = "YOUR_ELSEVIER_API_KEY"

# --- SiYuan Config ---
SIYUAN_API_URL = "http://10.42.0.58:6806"
SIYUAN_API_TOKEN = "YOUR_SIYUAN_API_TOKEN"
SIYUAN_NOTEBOOK_ID = "20260301131510-yehu9uc"

# --- Helpers ---
def export_to_siyuan(title, content, notebook_id=None):
    if not (SIYUAN_API_URL and SIYUAN_API_TOKEN): return
    print(f"📤 Exporting author analysis to SiYuan Note: {title}...")
    
    nb_id = notebook_id or SIYUAN_NOTEBOOK_ID
    if not nb_id: return

    # Sanitize title
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    curr_date = datetime.date.today().strftime('%Y-%m-%d')
    path = f"/EssayUpdate/Author/{curr_date}/{safe_title}"

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

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

def send_telegram_file(chat_id, file_path):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            requests.post(url, data=data, files=files, timeout=60)
    except Exception:
        pass

# --- Core Logic ---

def find_author(name, institution_hint=None):
    """
    Search for author. If hint is provided, filter or rank by institution match.
    Returns: (author_id, display_name, institution_name, stats)
    """
    print(f"🔍 Searching profile for author: {name} (Hint: {institution_hint})...")
    url = "https://api.openalex.org/authors"
    params = {"search": name}
    headers = {"x-api-key": OPENALEX_API_KEY}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200: return None
        
        results = resp.json().get('results', [])
        if not results: return None
        
        candidates = []
        for res in results:
            aid = res['id']
            dname = res['display_name']
            
            # Collect all institutions
            inst_names = []
            
            # 1. Last Known
            last_inst = res.get('last_known_institution')
            if last_inst:
                inst_names.append(last_inst.get('display_name', ''))
            
            # 2. Affiliations History
            affs = res.get('affiliations', [])
            for aff in affs:
                if aff.get('institution'):
                    inst_names.append(aff['institution'].get('display_name', ''))
            
            # Unique & Clean
            inst_names = list(set([n for n in inst_names if n]))
            primary_inst = inst_names[0] if inst_names else "Unknown"
            
            works_count = res.get('works_count', 0)
            cited_by = res.get('cited_by_count', 0)
            
            candidates.append({
                'id': aid,
                'name': dname,
                'inst': primary_inst,
                'all_insts': inst_names,
                'works': works_count,
                'cited': cited_by
            })

        # Logic to pick best
        chosen = None
        
        if institution_hint:
            # Filter by matching institution in ANY affiliation
            filtered = []
            for c in candidates:
                # Check if hint matches any of the institutions
                match = any(institution_hint.lower() in inst.lower() for inst in c['all_insts'])
                if match:
                    filtered.append(c)
            
            if filtered:
                # Prioritize exact name match
                exact_matches = [c for c in filtered if c['name'].lower() == name.lower()]
                if exact_matches:
                    exact_matches.sort(key=lambda x: x['cited'], reverse=True)
                    chosen = exact_matches[0]
                else:
                    # Pick most cited among matches
                    filtered.sort(key=lambda x: x['cited'], reverse=True)
                    chosen = filtered[0]
                
                # Update display inst to match the hint if found (to avoid user confusion)
                for inst_name in chosen['all_insts']:
                    if institution_hint.lower() in inst_name.lower():
                        chosen['inst'] = inst_name
                        break
            else:
                # Hint failed
                print(f"⚠️ Institution hint '{institution_hint}' not found in top results.")
                # Print debug of top 5
                debug_info = []
                for c in candidates[:5]:
                    debug_info.append(f"{c['name']} ({', '.join(c['all_insts'][:2])}...)") 
                print(f"   Available candidates: {debug_info}")
                
                # Try to pick exact name match from non-filtered if hint failed? 
                # Or just stick to relevance/citation
                exact_matches = [c for c in candidates if c['name'].lower() == name.lower()]
                if exact_matches:
                    exact_matches.sort(key=lambda x: x['cited'], reverse=True)
                    chosen = exact_matches[0]
                else:
                    chosen = candidates[0]
        else:
            # No hint, prioritize exact name match, then citations
            exact_matches = [c for c in candidates if c['name'].lower() == name.lower()]
            if exact_matches:
                exact_matches.sort(key=lambda x: x['cited'], reverse=True)
                chosen = exact_matches[0]
            else:
                chosen = candidates[0]
            
        return chosen
        
    except Exception as e:
        print(f"❌ Error finding author: {e}")
        return None

def fetch_author_papers(author_id, limit=60, required_institution=None):
    """
    Fetch papers for the author.
    Strategy: Mix of Most Cited (Representative) and Newest (Current Focus).
    If required_institution is provided, strictly filter papers that contain this institution.
    """
    print(f"📚 Fetching papers for Author ID: {author_id}...")
    if required_institution:
        print(f"   (Strict Filter: Must contain '{required_institution}' in affiliations)")

    headers = {"x-api-key": OPENALEX_API_KEY}
    
    # 1. Get Most Cited (Top 100)
    url = "https://api.openalex.org/works"
    params_cited = {
        "filter": f"author.id:{author_id}",
        "sort": "cited_by_count:desc",
        "per_page": 100
    }
    
    # 2. Get Newest (Top 100)
    params_new = {
        "filter": f"author.id:{author_id}",
        "sort": "publication_date:desc",
        "per_page": 100
    }
    
    papers_map = {} # deduplicate by id
    
    def process_resp(resp):
        if resp.status_code == 200:
            for item in resp.json().get('results', []):
                pid = item['id']
                
                # --- Strict Institution Filter ---
                if required_institution:
                    match_found = False
                    for authorship in item.get('authorships', []):
                        for inst in authorship.get('institutions', []):
                            if required_institution.lower() in inst.get('display_name', '').lower():
                                match_found = True
                                break
                        if match_found: break
                    
                    if not match_found:
                        continue
                # ---------------------------------

                if pid not in papers_map:
                    title = item.get('title', 'No Title')
                    year = item.get('publication_year')
                    cited = item.get('cited_by_count', 0)
                    abstract = reconstruct_openalex_abstract(item.get('abstract_inverted_index'))
                    
                    venue = "Unknown"
                    if item.get('primary_location'):
                        source = item.get('primary_location').get('source', {})
                        if source:
                            venue = source.get('display_name', 'Unknown')

                    authors_list = []
                    for authorship in item.get('authorships', []):
                         if 'author' in authorship:
                             authors_list.append(authorship['author'].get('display_name', 'Unknown'))

                    papers_map[pid] = {
                        'title': title,
                        'year': year,
                        'cited': cited,
                        'abstract': abstract,
                        'venue': venue,
                        'authors': authors_list
                    }

    try:
        r1 = requests.get(url, params=params_cited, headers=headers, timeout=20)
        process_resp(r1)
        
        r2 = requests.get(url, params=params_new, headers=headers, timeout=20)
        process_resp(r2)
        
    except Exception as e:
        print(f"Error fetching works: {e}")
        
    return list(papers_map.values())

def ai_analyze_author(author_name, author_inst, papers):
    if not papers: return "No papers found."
    
    # Sort papers by year for timeline context
    papers.sort(key=lambda x: x['year'] if x['year'] else 0, reverse=True)
    
    # Prepare context
    # Focus on Abstract content for methods/objects
    valid_papers = [p for p in papers if p['abstract'] and len(p['abstract']) > 50]
    # Limit to fits context
    valid_papers = valid_papers[:60]
    
    content_block = ""
    for idx, p in enumerate(valid_papers):
        content_block += f"[{p['year']}] {p['title']} (Cited: {p['cited']})\nAbstract: {p['abstract'][:800]}\n\n"
        
    prompt = (
        f"You are analyzing the academic profile of researcher: {author_name} ({author_inst}).\n"
        f"You must strictly adhere to the following rules:\n"
        f"1. **ONLY** rely on the provided paper abstracts below. Do not use external knowledge or hallucinate.\n"
        f"2. If the provided text does not contain information about a specific aspect, state that it is not available in the provided papers.\n"
        f"3. When making claims, try to reference the specific paper year or title if possible.\n\n"
        f"Based on the provided {len(valid_papers)} papers (Representative & Recent), please analyze:\n\n"
        f"1. **Research Objects**: What specific materials, systems, or phenomena do they confirm studying? (e.g., NiTi alloys, Metallic Glasses, Neural Networks)\n"
        f"2. **Research Methods**: What are their primary tools? (e.g., TEM, DFT, Molecular Dynamics, EBSD, Machine Learning). List specific techniques mentioned in the abstracts.\n"
        f"3. **Research Evolution**: How has their focus changed from earlier highly-cited works to their most recent publications?\n"
        f"4. **Key Contributions**: Summarize their most impactful findings based ONLY on these abstracts.\n\n"
        f"Format as a Markdown report.\n\n"
        f"Papers Data:\n{content_block}"
    )
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_API_KEY}"}
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a scientific biographer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3, 
        "stream": False
    }
    
    try:
        resp = requests.post(f"{AI_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        else:
            return f"AI Error: {resp.text}"
    except Exception as e:
        return f"AI Exception: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Author Name")
    parser.add_argument("--inst", help="Institution Hint", default=None)
    parser.add_argument("--chat_id", help="Telegram Chat ID", default=TG_CHAT_ID)
    args = parser.parse_args()
    
    name = args.name
    inst = args.inst
    chat_id = args.chat_id
    
    send_telegram_msg(chat_id, f"🕵️ Searching Profile: *{name}* " + (f"at *{inst}*" if inst else "") + "...")
    
    # 1. Find Author
    author = find_author(name, inst)
    
    if not author:
        send_telegram_msg(chat_id, f"❌ Could not find author '{name}'. Try adding an institution hint.")
        return
        
    choice_msg = (
        f"✅ Found: **{author['name']}**\n"
        f"🏛️ {author['inst']}\n"
        f"📚 Works: {author['works']} | 🔗 Cited: {author['cited']}\n"
        f"Analyzing research profile..."
    )
    send_telegram_msg(chat_id, choice_msg)
    
    # 2. Fetch Papers
    papers = fetch_author_papers(author['id'], required_institution=inst)
    
    if not papers:
        send_telegram_msg(chat_id, "❌ Author has no accessible papers/abstracts matching criteria.")
        return
        
    # 3. AI Analyze
    send_telegram_msg(chat_id, f"🧠 Analyzing {len(papers)} papers (Methods & Objects)...")
    report = ai_analyze_author(author['name'], author['inst'], papers)
    
    # 4. Save & Send
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join([c if c.isalnum() else "_" for c in name])
    filename = f"Author_Profile_{safe_name}_{timestamp}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
        f.write("\n\n---\n# Analyzed Papers\n")
        f.write("\n*(Note: Queried author is **bolded**)*\n\n")
        for p in papers:
            # Format authors
            fmt_authors = []
            authors_list = p.get('authors', [])
            if not authors_list: authors_list = ["Unknown Authors"]
            
            for a in authors_list:
                # Check for match with found author name or query name
                # Split names to handle variations like "Xiao, Yao" vs "Yao Xiao" slightly better if needed, 
                # but simple substring usually works for "Yao Xiao" in "Yao Xiao"
                if (author['name'].lower() in a.lower()) or (name.lower() in a.lower()):
                    fmt_authors.append(f"**{a}**")
                else:
                    fmt_authors.append(a)
            
            author_str = ", ".join(fmt_authors)
            f.write(f"- {author_str} ({p['year']}). **{p['title']}**. *{p['venue']}*. (Cited: {p['cited']})\n")

    send_telegram_msg(chat_id, report[:1000] + "...\n(Full report attached)")
    send_telegram_file(chat_id, filename)
    print("Done.")

    # 5. Export to SiYuan Note
    export_to_siyuan(f"Author Profile - {author['name']} ({datetime.date.today()})", report)

if __name__ == "__main__":
    main()
