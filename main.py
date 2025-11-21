import os
import json
import random
import requests
import hashlib
from datetime import datetime, timedelta, timezone

# --- 配置区域 ---
QUOTES_FILE = 'quotes.txt'
DB_FILE = 'memory.json'
MAX_REVIEW_COUNT = 5  # 每天每次推送最多包含几条复习内容（防止消息太长）
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
    # 坚持使用纯文本发送，最稳妥
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

    # 同步新内容
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

    # 1. 筛选候选池
    new_items = [item for item in data.values() if item['level'] == 0]
    
    # 筛选所有“今天或之前”到期的复习卡片
    review_candidates = [
        item for item in data.values() 
        if item['level'] > 0 and item['next_review'] and item['next_review'] <= today
    ]

    # 2. 抽取策略
    picked_new = None
    picked_reviews = []

    # A. 必选一条新的 (如果有)
    if new_items:
        picked_new = random.choice(new_items)
    
    # B. 选出待复习的 (最多 MAX_REVIEW_COUNT 条)
    if review_candidates:
        # 先打乱顺序，避免每次都复习同一批积压的
        random.shuffle(review_candidates)
        picked_reviews = review_candidates[:MAX_REVIEW_COUNT]

    # 如果啥都没有
    if not picked_new and not picked_reviews:
        print("🎉 今日任务全部完成！随机抽取一条回顾...")
        all_items = list(data.values())
        if all_items:
             picked_new = random.choice(all_items) # 假装它是新的发出去
        else:
            return

    # 3. 构造消息
    msg_parts = []
    
    # --- 顶部：新知 ---
    if picked_new:
        title = "🌱 今日新知" if picked_new['level'] == 0 else "🎲 随机漫步"
        msg_parts.append(f"【{title}】\n\n{picked_new['content']}")
    
    # --- 底部：复习列表 ---
    if picked_reviews:
        msg_parts.append("\n----------------------")
        msg_parts.append(f"🧠 今日复习 ({len(picked_reviews)}条)")
        
        for idx, item in enumerate(picked_reviews, 1):
            # 为了阅读体验，如果内容太长，可以考虑截断，或者就直接发全本
            # 这里选择发全本，但在每条前面加序号和等级
            msg_parts.append(f"\n[{idx}] (Lv.{item['level']})\n{item['content']}")
            
        msg_parts.append("\n(根据艾宾浩斯曲线推荐)")

    final_msg = "\n".join(msg_parts)
    
    print(f"准备发送: 1条新知 + {len(picked_reviews)}条复习")
    
    # 4. 发送
    success = send_telegram_message(final_msg)

    # 5. 更新数据库
    if success:
        print("✅ 发送成功，更新进度...")
        
        # 更新新卡片
        if picked_new and picked_new['level'] == 0:
            picked_new['level'] = 1
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=INTERVALS[0])
            picked_new['next_review'] = next_date.strftime('%Y-%m-%d')
            
        # 批量更新复习卡片
        for item in picked_reviews:
            current_level = item['level']
            # 升级逻辑
            if current_level < len(INTERVALS):
                days_add = INTERVALS[current_level]
                item['level'] += 1
            else:
                # 满级后固定间隔(比如60天)复习一次，或者你可以设置 items['level'] 不再增加
                days_add = 60 
                # item['level'] += 1 # 可选：是否继续增加等级数字
            
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=days_add)
            item['next_review'] = next_date.strftime('%Y-%m-%d')

        save_data(data)
    else:
        print("❌ 发送失败，不更新进度")

if __name__ == "__main__":
    main()
