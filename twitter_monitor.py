import os
import json
import requests
from apify_client import ApifyClient
from datetime import datetime, timedelta, timezone

# --- 配置 ---
# 你想监控的推特博主 ID (不带 @)
TARGET_HANDLES = ["elonmusk", "OpenAI", "SamAltman"]
# 历史记录文件 (用于去重)
HISTORY_FILE = "tweet_history.json"

def get_api_key(name):
    return os.environ.get(name)

def send_telegram(msg):
    token = get_api_key("TG_BOT_TOKEN")
    chat_id = get_api_key("TG_CHAT_ID")
    if not token or not chat_id: return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg}
    )

def ai_summarize(text):
    """使用 Gemini 进行翻译和总结 (省钱)"""
    key = get_api_key("GEMINI_API_KEY")
    if not key: return text # 没key就直接返回原文
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={key}"
    prompt = f"""
    请翻译并总结以下推文。
    要求：
    1. 翻译成中文。
    2. 如果是广告或无意义内容，直接返回 "SKIP"。
    3. 输出格式：【博主名】内容总结 (URL)

    推文内容：
    {text}
    """
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        return text

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) # 格式: {"tweet_id": timestamp}
        except: pass
    return {}

def save_history(data):
    # 只保留最近 7 天的记录，防止文件无限膨胀
    cutoff = (datetime.now() - timedelta(days=7)).timestamp()
    new_data = {k: v for k, v in data.items() if v > cutoff}
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f)

def run_apify():
    token = get_api_key("APIFY_API_TOKEN")
    if not token:
        print("❌ 缺少 Apify Token")
        return

    client = ApifyClient(token)
    history = load_history()
    
    # 使用 apidojo/tweet-scraper (需要耗费 Compute Units)
    # 这是一个通用的 Actor，参数可能随版本更新变动，请参考 Apify 文档
    run_input = {
        "twitterHandles": TARGET_HANDLES,
        "maxItems": 5, # 每次每个号只抓最新 5 条，省钱
        "sort": "Latest",
    }

    print("🕷️ 正在呼叫 Apify 爬虫...")
    # 注意：这里 Actor ID 可能会变，建议去 Apify Store 找最新的
    # 这里以 'apidojo/tweet-scraper' 为例
    run = client.actor("apidojo/tweet-scraper").call(run_input=run_input)

    if not run:
        print("⚠️ Apify 运行失败")
        return

    print("📦 获取数据中...")
    # 获取数据集
    dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
    
    new_count = 0
    for item in dataset_items:
        # 提取关键信息
        tweet_id = item.get("id")
        text = item.get("text")
        author = item.get("author", {}).get("userName")
        url = item.get("url")
        
        if not tweet_id or tweet_id in history:
            continue
            
        # --- 发现新推文 ---
        print(f"⚡️ 发现新推文: {author}")
        
        # 1. AI 处理
        summary = ai_summarize(f"Author: {author}\nContent: {text}\nURL: {url}")
        
        if "SKIP" in summary:
            print("  -> 广告/无效内容，跳过")
            history[tweet_id] = datetime.now().timestamp()
            continue
            
        # 2. 推送
        msg = f"🐦 **Twitter 监控**\n\n{summary}\n\n🔗 [原文链接]({url})"
        send_telegram(msg)
        
        # 3. 记录历史
        history[tweet_id] = datetime.now().timestamp()
        new_count += 1

    save_history(history)
    print(f"✅ 完成。推送了 {new_count} 条新内容。")

if __name__ == "__main__":
    run_apify()
