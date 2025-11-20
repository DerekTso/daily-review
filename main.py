import os
import json
import random
import requests
import hashlib
from datetime import datetime, timedelta, timezone

# --- 配置区域 ---
QUOTES_FILE = 'quotes.txt'
DB_FILE = 'memory.json' # 用来存储记忆状态的数据库文件

# 记忆曲线间隔 (天数): 第1次1天后，第2次2天后，第3次4天后...
INTERVALS = [1, 2, 4, 7, 15, 30, 60]

def get_beijing_today():
    """获取北京时间今天的日期字符串 (YYYY-MM-DD)"""
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime('%Y-%m-%d')

def send_telegram_message(message):
    """发送消息到 Telegram"""
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ 错误: 环境变量中未找到 Token 或 Chat ID")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # 使用纯文本发送，避免格式报错，体验最稳
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
    """
    加载数据：
    1. 读取 quotes.txt (作为数据源输入)
    2. 读取 memory.json (作为状态记录)
    3. 将 txt 里的新内容合并进 json 库
    """
    # 1. 读取 txt 原文
    txt_segments = []
    if os.path.exists(QUOTES_FILE):
        with open(QUOTES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        # 按空行分割
        txt_segments = [seg.strip() for seg in content.split('\n\n') if seg.strip()]

    # 2. 读取 json 数据库
    db_data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
        except:
            db_data = {}

    # 3. 同步：如果 txt 有新内容，加入 db；如果 txt 删了内容，保留 db (防止学习进度丢失)
    # 使用内容的哈希值作为 ID，防止重复添加
    current_ids = set()
    
    for segment in txt_segments:
        # 生成唯一ID (MD5)
        seg_id = hashlib.md5(segment.encode('utf-8')).hexdigest()
        current_ids.add(seg_id)
        
        if seg_id not in db_data:
            # 这是一个新段落
            db_data[seg_id] = {
                "content": segment,
                "level": 0,          # 0表示没学过
                "next_review": None, # 下次复习时间
                "id": seg_id
            }
    
    return db_data

def save_data(data):
    """保存数据库"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    data = load_data()
    today = get_beijing_today()
    
    if not data:
        print("⚠️ 数据库为空，请先在 quotes.txt 添加内容")
        return

    # --- 筛选候选池 ---
    # 1. 待学习的新卡片 (Level 0)
    new_items = [item for item in data.values() if item['level'] == 0]
    
    # 2. 待复习的旧卡片 (Level > 0 且 日期 <= 今天)
    review_items = [
        item for item in data.values() 
        if item['level'] > 0 and item['next_review'] and item['next_review'] <= today
    ]

    # --- 抽取策略 ---
    picked_new = None
    picked_review = None

    # 必选一条新的 (如果没有新的，就不选)
    if new_items:
        picked_new = random.choice(new_items)
    
    # 选一条复习的 (如果有很多到期的，随机抽一条)
    if review_items:
        picked_review = random.choice(review_items)

    if not picked_new and not picked_review:
        print("🎉 所有内容都已学完且今日无需复习！")
        # 这种情况下，为了不让推送空着，可以随机来一条随便看看，或者直接不发
        # 这里选择：随机随机来一条作为回顾
        all_items = list(data.values())
        if all_items:
             picked_new = random.choice(all_items) # 假装它是新的，发出去看看
        else:
            return

    # --- 构造消息 ---
    msg_parts = []
    
    # 1. 顶部：今日新知 (或者今日精选)
    if picked_new:
        icon = "🌱 今日新知" if picked_new['level'] == 0 else "🎲 随机漫步"
        msg_parts.append(f"【{icon}】\n\n{picked_new['content']}")
    
    # 2. 底部：复习回顾
    if picked_review:
        msg_parts.append("----------------------")
        msg_parts.append(f"【🧠 记忆唤醒 · Level {picked_review['level']}】\n\n{picked_review['content']}")
        msg_parts.append("\n(根据遗忘曲线自动推荐)")

    final_msg = "\n".join(msg_parts)
    
    print("正在发送...")
    success = send_telegram_message(final_msg)

    # --- 更新数据库状态 ---
    if success:
        print("✅ 发送成功，更新记忆进度...")
        
        # 更新新卡片状态
        if picked_new and picked_new['level'] == 0:
            # 从 0 级升到 1 级，下次复习是 1 天后
            picked_new['level'] = 1
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=INTERVALS[0])
            picked_new['next_review'] = next_date.strftime('%Y-%m-%d')
            
        # 更新复习卡片状态
        if picked_review:
            current_level = picked_review['level']
            # 升级 (如果还没满级)
            if current_level < len(INTERVALS):
                days_add = INTERVALS[current_level] # 获取下一级间隔
                picked_review['level'] += 1
            else:
                days_add = 60 # 满级后每60天复习一次
            
            next_date = datetime.strptime(today, '%Y-%m-%d') + timedelta(days=days_add)
            picked_review['next_review'] = next_date.strftime('%Y-%m-%d')

        save_data(data)
    else:
        print("❌ 发送失败，不更新进度")

if __name__ == "__main__":
    main()
