import os
import json
import random
import requests
import hashlib
from datetime import datetime, timedelta, timezone

# --- 配置区域 ---
QUOTES_FILE = 'quotes.txt'
DB_FILE = 'memory.json'
MAX_REVIEW_COUNT = 3  # 每次推送最多包含几条复习内容
INTERVALS = [1, 2, 4, 7, 15, 30, 60] # 记忆曲线间隔(天)

def get_beijing_today():
    """获取北京时间今天的日期字符串"""
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime('%Y-%m-%d')

def send_telegram_message(message):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ 错误: 环境变量中未找到 Token 或 Chat ID")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            return True
        else:
            print(f"❌ Telegram API 报错: {res.text}")
            return False
    except Exception as e:
        print(f"❌ 网络请求异常: {e}")
        return False

# --- 新增：AI 分析函数 ---
def get_ai_analysis(text):
    """
    调用 Google Gemini API 对内容进行深度分析
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 GEMINI_API_KEY，跳过 AI 分析")
        return ""

    # 使用 Gemini 1.5 Flash 模型
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
    请阅读下面这段话，提取出 3 个最核心的关键词或概念。
    并为每个关键词写一句极简短的“解码”（解释它在这段话里的深层含义，不超过15个字）。

    内容：
    “{text}”

    要求：
    1. 格式严格如下，不要Markdown标题，不要废话：
    🔑 核心解码：
    • 关键词1 —— 解码内容
    • 关键词2 —— 解码内容
    • 关键词3 —— 解码内容

    2. 解码内容要深刻且精炼，直击本质。
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            # 提取 AI 回复的文本
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            return ai_text.strip()
        else:
            print(f"⚠️ AI API 调用失败: {response.text}")
            return ""
    except Exception as e:
        print(f"⚠️ AI 请求异常: {e}")
        return ""

def load_data():
    """加载数据并同步 quotes.txt 的新内容"""
    txt_segments = []
    if os.path.exists(QUOTES_FILE):
        with open(QUOTES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        txt_segments = [seg.strip() for seg in content.split('\n\n') if seg.strip()]

    db_data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
        except:
            db_data = {}

    for segment in txt_segments:
        seg_id = hashlib.md5(segment.encode('utf-8')).hexdigest()
        if seg_id not in db_data:
            db_data[seg_id] = {
                "content": segment,
                "level": 0,
                "next_review": None,
                "id": seg_id
            }
    return db_data

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    data = load_data()
    today = get_beijing_today()
    
    if not data:
        print("⚠️ 数据库为空，请先在 quotes.txt 添加内容")
        return

    # 1. 筛选
    new_items = [item for item in data.values() if item['level'] == 0]
    
    review_candidates = [
        item for item in data.values() 
        if item['level'] > 0 and item['next_review'] and item['next_review'] <= today
    ]

    # 2. 抽取
    picked_new = None
    picked_reviews = []

    if new_items:
        picked_new = random.choice(new_items)
    
    if review_candidates:
        random.shuffle(review_candidates)
        picked_reviews = review_candidates[:MAX_REVIEW_COUNT]
        picked_reviews.sort(key=lambda x: x['level'], reverse=True)

    if not picked_new and not picked_reviews:
        print("🎉 今日任务全部完成！随机抽取一条回顾...")
        all_items = list(data.values())
        if all_items:
             picked_new = random.choice(all_items)
        else:
            return

    # 3. 构造消息
    msg_parts = []
    
    # --- 顶部：新知 + AI 分析 ---
    if picked_new:
        title = "🌱 今日新知" if picked_new['level'] == 0 else "🎲 随机漫步"
        msg_parts.append(f"【{title}】\n\n{picked_new['content']}")
        
        # === 💡 这里调用 AI 进行分析 ===
        print("正在请求 AI 分析...")
        ai_feedback = get_ai_analysis(picked_new['content'])
        
        if ai_feedback:
            # 加一条分割线让排版更好看
            msg_parts.append(f"\n----------------------\n{ai_feedback}")
    
    # --- 底部：复习列表 ---
    if picked_reviews:
        msg_parts.append("\n----------------------")
        msg_parts.append(f"🧠 今日复习 ({len(picked_reviews)}条)")
        
        for idx, item in enumerate(picked_reviews, 1):
            msg_parts.append(f"\n[{idx}] (Lv.{item['level']})\n{item['content']}")

    final_msg = "\n".join(msg_parts)
    
    print(f"准备发送: 1条新知 + {len(picked_reviews)}条复习")
    
    # 4. 发送
    success = send_telegram_message(final_msg)

    # 5. 更新数据库
    if success:
        print("✅ 发送成功，更新进度...")
        
        if picked_new and picked_new['level'] == 0:
            picked_new['level'] = 1
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=INTERVALS[0])
            picked_new['next_review'] = next_date.strftime('%Y-%m-%d')
            
        for item in picked_reviews:
            current_level = item['level']
            if current_level < len(INTERVALS):
                days_add = INTERVALS[current_level]
                item['level'] += 1
            else:
                days_add = 60 
            
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=days_add)
            item['next_review'] = next_date.strftime('%Y-%m-%d')

        save_data(data)
    else:
        print("❌ 发送失败，不更新进度")

if __name__ == "__main__":
    main()
