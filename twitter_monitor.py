import os
import json
import requests
from apify_client import ApifyClient
from datetime import datetime, timedelta

# --- 配置 ---
# 你想监控的推特博主 ID (不带 @)
TARGET_HANDLES = ["elonmusk", "OpenAI", "SamAltman"]
HISTORY_FILE = "tweet_history.json"

def get_env(name):
    return os.environ.get(name)

def send_telegram(msg):
    token = get_env("TG_BOT_TOKEN")
    chat_id = get_env("TG_CHAT_ID")
    if not token or not chat_id: return
    # 截断防止超长
    if len(msg) > 4000: msg = msg[:4000] + "..."
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg}
    )

def ai_summarize(text):
    """Gemini 总结"""
    key = get_env("GEMINI_API_KEY")
    if not key: return text
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={key}"
    prompt = f"""
    请翻译并总结以下推文。
    1. 翻译成中文。
    2. 如果是广告/垃圾信息/只有表情包，返回 "SKIP"。
    3. 格式：内容总结 (URL)

    推文内容：
    {text}
    """
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        pass
    return text

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def save_history(data):
    cutoff = (datetime.now() - timedelta(days=7)).timestamp()
    new_data = {k: v for k, v in data.items() if v > cutoff}
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f)

def run_apify():
    token = get_env("APIFY_API_TOKEN")
    if not token:
        print("❌ 缺少 Apify Token")
        return

    client = ApifyClient(token)
    history = load_history()
    
    # 构造查询语句: ["from:elonmusk", "from:OpenAI", ...]
    queries = [f"from:{handle}" for handle in TARGET_HANDLES]
    
    # danek/twitter-scraper-ppr 的参数配置
    run_input = {
        "queries": queries,
        "maxPosts": 5,    # 每次每个 query 抓多少条
        "sort": "Latest",  # 按时间倒序
        "lang": "en"       # 可选
    }

    print(f"🕷️ 正在呼叫 Actor: danek/twitter-scraper-ppr ...")
    
    # 运行 Actor
    run = client.actor("danek/twitter-scraper-ppr").call(run_input=run_input)

    if not run:
        print("⚠️ Apify 运行失败 (Run对象为空)")
        return

    print(f"📦 运行结束，正在获取数据集 (Dataset ID: {run['defaultDatasetId']})...")
    
    # 获取数据
    dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
    
    new_count = 0
    print(f"🔍 抓取到 {len(dataset_items)} 条原始数据")

    for item in dataset_items:
        # --- 适配不同的数据字段 ---
        # Apify 的 actor 返回字段经常变，这里做多重尝试
        tweet_id = item.get("id") or item.get("id_str")
        
        # 获取正文
        text = item.get("text") or item.get("full_text") or item.get("description")
        
        # 获取作者名
        user_info = item.get("user") or item.get("author") or {}
        author = user_info.get("screen_name") or user_info.get("username") or user_info.get("name") or "Unknown"
        
        # 获取链接
        url = item.get("url") or item.get("tweet_url")
        if not url and tweet_id and author:
            url = f"https://twitter.com/{author}/status/{tweet_id}"
        
        # 必要的去重检查
        if not tweet_id or not text:
            continue
            
        if tweet_id in history:
            continue
            
        # --- 发现新推文 ---
        print(f"⚡️ 新推文 from {author}: {text[:30]}...")
        
        # AI 处理
        summary = ai_summarize(f"Author: {author}\nContent: {text}")
        
        if "SKIP" in summary:
            print("  -> AI 判断为无效内容，跳过")
            history[tweet_id] = datetime.now().timestamp()
            continue
            
        # 推送
        msg = f"🐦 **{author}**\n\n{summary}\n\n🔗 {url}"
        send_telegram(msg)
        
        # 记录
        history[tweet_id] = datetime.now().timestamp()
        new_count += 1

    save_history(history)
    print(f"✅ 完成。推送了 {new_count} 条新内容。")

if __name__ == "__main__":
    run_apify()
