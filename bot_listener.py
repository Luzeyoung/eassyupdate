import requests
import time
import datetime
import subprocess
import os
import json
import threading

# --- Configuration ---
# Must match your existing config
TG_TOKEN = "YOUR_TG_TOKEN"
ALLOWED_CHAT_ID = "8384265672" # String for comparison
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "essayupdate.py")
RESEARCH_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "essay_research.py")
AUTHOR_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "essay_author.py")
BRIEFING_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "daily_briefing.py")
PYTHON_EXEC = "python3" # Or full path if needed

# --- Telegram API Helpers ---
BASE_URL = f"https://api.telegram.org/bot{TG_TOKEN}"

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Send Error: {e}")

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(url, params=params, timeout=40)
        return resp.json()
    except Exception as e:
        print(f"⚠️ Polling Error: {e}")
        time.sleep(5)
        return None

def run_briefing_task(chat_id=None):
    """Runs the daily briefing script"""
    # If chat_id not provided, use default
    target_chat_id = chat_id if chat_id else ALLOWED_CHAT_ID
    
    send_message(target_chat_id, "🚀 Generating Daily Strategic Briefing...") # Optional feedback
    print("--- Starting Briefing Script ---")
    
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # We pass "now" argument to trigger immediate execution
        process = subprocess.Popen(
            [PYTHON_EXEC, BRIEFING_SCRIPT_PATH, "now"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8', 
            cwd=os.path.dirname(BRIEFING_SCRIPT_PATH),
            env=env
        )
        
        stdout, stderr = process.communicate()
        print(stdout)
        if stderr:
             print(f"Briefing Error: {stderr}")

        # The script sends the actual content, so we just acknowledge completion or silence
        # send_message(target_chat_id, "✅ Briefing Task Complete.")
        
    except Exception as e:
        err_msg = f"❌ Failed to run briefing script: {e}"
        print(err_msg)
        send_message(target_chat_id, err_msg)

def scheduler_loop():
    """Background thread to check time and run scheduled tasks"""
    print("⏰ Scheduler Thread Started.")
    print("   - 06:30: Essay Update")
    print("   - 12:00: Market Briefing")
    print("   - 20:00: Market Briefing")
    
    last_run_minute = ""
    
    while True:
        now = datetime.datetime.now()
        current_hm = now.strftime("%H:%M")
        current_minute_str = now.strftime("%Y-%m-%d %H:%M")
        
        # Avoid running multiple times in the same minute
        if last_run_minute == current_minute_str:
             time.sleep(10)
             continue

        # 1. Essay Update (06:30)
        if current_hm == "06:30":
            print(f"[{current_minute_str}] ⏰ Triggering Morning Essay Update...")
            try:
                 subprocess.run([PYTHON_EXEC, SCRIPT_PATH], cwd=os.path.dirname(SCRIPT_PATH), check=False)
            except Exception as e:
                 print(f"Error running essay update: {e}")
            last_run_minute = current_minute_str
            
        # 2. Daily Briefing (12:00, 20:00)
        elif current_hm in ["12:00", "20:00"]:
            print(f"[{current_minute_str}] ⏰ Triggering Daily Briefing...")
            # Run briefing in a thread so it doesn't block the scheduler loop if it takes long
            threading.Thread(target=run_briefing_task, args=(ALLOWED_CHAT_ID,)).start()
            last_run_minute = current_minute_str
            
        time.sleep(30) # Check every 30 seconds

def run_update_task(chat_id):
    """Runs the update script in a separate thread so it doesn't block polling"""
    send_message(chat_id, "🚀 Received command. Starting essay update...")
    
    print("--- Starting Update Script ---")
    try:
        # Use full path to python if needed, or just 'python' if in PATH
        # We run the script and capture output
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            [PYTHON_EXEC, SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8', 
            cwd=os.path.dirname(SCRIPT_PATH), # Set CWD to script dir
            env=env
        )
        
        # We can wait for it or just let it run. 
        # Waiting allows us to report completion.
        stdout, stderr = process.communicate()
        
        print(stdout)
        if stderr:
             print(f"Error: {stderr}")

        send_message(chat_id, "✅ Update task finished check logs/channel for new papers.")
        
    except Exception as e:
        err_msg = f"❌ Failed to run script: {e}"
        print(err_msg)
        send_message(chat_id, err_msg)

def run_author_task(chat_id, args_str):
    """Runs the author profiling script"""
    # args_str: "Name" or "Name, Institution" or "Name Institution"
    # Logic: if contains comma, split by comma. 
    # If not, assume first word is name? No, names can be multi-word.
    # Let's simple assumption: Everything is name unless user uses specific separator like | or ,
    # Or, we just pass the raw name to the script and let user provide hint optionally via logic below:
    # Command: /author Name | Institution
    
    parts = args_str.split('|')
    name = parts[0].strip()
    inst = parts[1].strip() if len(parts) > 1 else None
    
    print(f"--- Starting Author Profile: {name} (Inst: {inst}) ---")
    
    cmd_args = [PYTHON_EXEC, AUTHOR_SCRIPT_PATH, name, "--chat_id", str(chat_id)]
    if inst:
        cmd_args.extend(["--inst", inst])
        
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            cwd=os.path.dirname(AUTHOR_SCRIPT_PATH),
            env=env
        )
        stdout, stderr = process.communicate()
        
        print(stdout)
        if stderr: print(f"Author Script Error: {stderr}")
        
    except Exception as e:
        send_message(chat_id, f"❌ Failed: {e}")

def run_research_task(chat_id, keywords_str):
    """Runs the research script"""
    print(f"--- Starting Research Task: {keywords_str} ---")
    try:
        # keywords_str is "term1 term2", split or pass as is? 
        # Argparse in script expects list of strings
        # We pass it as a single string argument if we want argparse to join, or split here.
        # But subprocess needs list of args.
        cmd_args = [PYTHON_EXEC, RESEARCH_SCRIPT_PATH] + keywords_str.split() + ["--chat_id", str(chat_id)]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8', 
            cwd=os.path.dirname(RESEARCH_SCRIPT_PATH),
            env=env
        )
        
        stdout, stderr = process.communicate()
        print(stdout)
        if stderr:
             print(f"Research Error: {stderr}")
             
        # The script itself sends the file and messages, so we don't need to do much here
        # except maybe confirm if it crashed silently.
        if process.returncode != 0:
             send_message(chat_id, f"❌ Research task failed with code {process.returncode}")

    except Exception as e:
        err_msg = f"❌ Failed to run research: {e}"
        print(err_msg)
        send_message(chat_id, err_msg)

# --- Main Loop ---
def main():
    print(f"🤖 Bot Listener v1.2 Started.")
    print(f"   - Monitor Chat: {ALLOWED_CHAT_ID}")
    print("   - Commands: /update, /briefing, /research <kw>, /author <name>")
    
    # Start Scheduler Thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    last_update_id = None
    
    # Initial cleanup: Get latest update ID to avoid processing old messages
    updates = get_updates()
    if updates and updates.get("ok"):
        results = updates.get("result", [])
        if results:
            last_update_id = results[-1]["update_id"] + 1

    while True:
        updates = get_updates(last_update_id)
        
        if updates and updates.get("ok"):
            results = updates.get("result", [])
            for res in results:
                last_update_id = res["update_id"] + 1
                
                message = res.get("message", {})
                chat_id_raw = message.get("chat", {}).get("id")
                chat_id = str(chat_id_raw)
                text = message.get("text", "").strip()
                
                if chat_id != ALLOWED_CHAT_ID:
                    print(f"⚠️ Ignored message from unauthorized chat: {chat_id}")
                    continue
                
                print(f"📩 Received: {text}")
                text_lower = text.lower()
                
                # --- Command Handling ---
                
                if text_lower.startswith("/research") or text_lower.startswith("research"):
                    # Extract keywords
                    parts = text.split(" ", 1)
                    if len(parts) > 1:
                        keywords = parts[1]
                        formatted_time = time.strftime("%H:%M:%S")
                        print(f"[{formatted_time}] Triggering research for: {keywords}")
                        t = threading.Thread(target=run_research_task, args=(chat_id, keywords))
                        t.start()
                    else:
                        send_message(chat_id, "ℹ️ Please provide keywords. Example: /research NiTi shape memory")

                elif text_lower.startswith("/author") or text_lower.startswith("author"):
                    parts = text.split(" ", 1)
                    if len(parts) > 1:
                        args_str = parts[1]
                        print(f"Triggering author search: {args_str}")
                        t = threading.Thread(target=run_author_task, args=(chat_id, args_str))
                        t.start()
                    else:
                        send_message(chat_id, "ℹ️ Format: /author Name | Institution (Optional)\nExample: /author Wei Gong | Tongji University")

                elif text_lower in ["/update", "/run", "/start", "update", "run"]:
                    formatted_time = time.strftime("%H:%M:%S")
                    print(f"[{formatted_time}] Triggering update...")
                    t = threading.Thread(target=run_update_task, args=(chat_id,))
                    t.start()
                    
                elif text_lower in ["/briefing", "/news", "briefing", "news"]:
                    formatted_time = time.strftime("%H:%M:%S")
                    print(f"[{formatted_time}] Triggering briefing manually...")
                    t = threading.Thread(target=run_briefing_task, args=(chat_id,))
                    t.start()

                elif text_lower in ["/help", "help", "/menu", "menu"]:
                    help_text = (
                        "🤖 **Bot Helpers & Commands**\n\n"
                        "1. **/update** (or /run)\n"
                        "   🚀 Returns latest essays & papers immediately.\n"
                        "   _(Scheduled daily at 06:30)_\n\n"
                        "2. **/briefing** (or /news)\n"
                        "   💰 Returns Real-Time Market & News Briefing.\n"
                        "   _(Scheduled daily at 12:00 & 20:00)_\n\n"
                        "3. **/research <keywords>**\n"
                        "   🔎 Search for papers on a specific topic.\n"
                        "   _Example: /research NiTi shape memory_\n\n"
                        "4. **/author <name> | <institution>**\n"
                        "   👤 Search for an author's recent work.\n"
                        "   _Example: /author Wei Gong | Tongji University_"
                    )
                    send_message(chat_id, help_text)

                else:
                    send_message(chat_id, "Unknown command. Try **/help** to see all options.")
                    
        time.sleep(1)

if __name__ == "__main__":
    main()
