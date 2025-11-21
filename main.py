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

def get_beijing_time():
    """获取北京时间对象"""
    utc_now = datetime.now(timezone.utc)
    return utc_now + timedelta(hours=8)

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

def get_ai_analysis(text):
    """调用 Google Gemini API"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 GEMINI_API_KEY，跳过 AI 分析")
        return ""

    # ⚠️ 如果运行报错 404，请检查模型名称是否准确
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    # 使用【深度解码风】Prompt
    prompt = f"""
    请阅读下面这段话，提取出 3 个最核心的关键词或概念。
    并为每个关键词写一句极简短的“解码”（解释它在这段话里的深层含义，不超过15个字）。

    内容：
    “{text}”

    要求：
    1. 格式严格如下，不要Markdown标题，不要废话：
    【🔑 核心解码】
    
    - 关键词1：解码内容
    - 关键词2：解码内容
    - 关键词3：解码内容

    2. 解码内容要深刻且精炼，直击本质。
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            # 打印错误信息方便调试模型名称是否正确
            print(f"⚠️ AI API 调用失败 (Status {response.status_code}): {response.text}")
            return ""
    except:
        return ""

# --- 生成周报 ---
def generate_weekly_report(data):
    """生成文本形式的周报仪表盘"""
    total_cards = len(data)
    if total_cards == 0:
        return ""

    stats = {"new": 0, "learning": 0, "mastering": 0, "archived": 0}
    
    for item in data.values():
        lv = item['level']
        if lv == 0: stats["new"] += 1
        elif lv <= 3: stats["learning"] += 1
        elif lv <= 6: stats["mastering"] += 1
        else: stats["archived"] += 1

    mastery_rate = ((stats["mastering"] + stats["archived"]) / total_cards) * 100
    
    filled_blocks = int(mastery_rate / 10)
    progress_bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)

    # [修改点2] 删除了“本周寄语”
    report = f"""
📅 **本周记忆周报**
━━━━━━━━━━━━━━━━
📚 **知识库总量**：{total_cards} 条

📊 **记忆分布热力**：
🌱 新知酝酿 (Lv.0)：{stats['new']}
🌲 正在生根 (Lv.1-3)：{stats['learning']}
🌳 枝繁叶茂 (Lv.4-6)：{stats['mastering']}
🏛️ 永久收藏 (Lv.7+)：{stats['archived']}

📈 **内化进度**：{mastery_rate:.1f}%
{progress_bar}
"""
    return report

def load_data():
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
    beijing_time = get_beijing_time()
    today_str = beijing_time.strftime('%Y-%m-%d')
    
    # [修改点3] 周一早上 00:00 - 11:00 之间触发 (hour < 11)
    is_monday_morning = (beijing_time.weekday() == 0) and (beijing_time.hour < 11)

    if not data:
        print("⚠️ 数据库为空")
        return

    # 1. 筛选
    new_items = [item for item in data.values() if item['level'] == 0]
    
    review_candidates = [
        item for item in data.values() 
        if item['level'] > 0 and item['next_review'] and item['next_review'] <= today_str
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
        print("🎉 任务完成，随机抽取...")
        all_items = list(data.values())
        if all_items: picked_new = random.choice(all_items)
        else: return

    # 3. 构造消息
    msg_parts = []
    
    # --- A. 顶部：新知 + AI ---
    if picked_new:
        title = "🌱 今日新知" if picked_new['level'] == 0 else "🎲 随机漫步"
        msg_parts.append(f"【{title}】\n\n{picked_new['content']}")
        
        print("正在请求 AI 分析...")
        ai_feedback = get_ai_analysis(picked_new['content'])
        if ai_feedback:
            msg_parts.append(f"\n{ai_feedback}")
    
    # --- B. 中部：复习列表 ---
    if picked_reviews:
        msg_parts.append(f"\n\n🧠 今日复习 ({len(picked_reviews)}条)")
        for idx, item in enumerate(picked_reviews, 1):
            msg_parts.append(f"\n[{idx}] (Lv.{item['level']})\n{item['content']}")

    # --- C. 底部：周一专属周报 ---
    if is_monday_morning:
        print("📅 检测到周一早晨，正在生成周报...")
        report = generate_weekly_report(data)
        if report:
            msg_parts.append("\n\n" + report)

    final_msg = "\n".join(msg_parts)
    print(f"准备发送消息...")
    
    # 4. 发送
    success = send_telegram_message(final_msg)

    # 5. 更新
    if success:
        print("✅ 发送成功，更新进度...")
        if picked_new and picked_new['level'] == 0:
            picked_new['level'] = 1
            next_date = datetime.strptime(today_str, '%Y-%m-%d') + timedelta(days=INTERVALS[0])
            picked_new['next_review'] = next_date.strftime('%Y-%m-%d')
            
        for item in picked_reviews:
            current_level = item['level']
            if current_level < len(INTERVALS):
                days_add = INTERVALS[current_level]
                item['level'] += 1
            else:
                days_add = 60 
            next_date = datetime.strptime(today_str, '%Y-%m-%d') + timedelta(days=days_add)
            item['next_review'] = next_date.strftime('%Y-%m-%d')
        save_data(data)
    else:
        print("❌ 发送失败")

if __name__ == "__main__":
    main()
