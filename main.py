import os
import random
import requests
import datetime

def send_telegram_message(message):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ 错误: 环境变量中未找到 Token 或 Chat ID")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # --- 修改点在这里 ---
    # 去掉了 "parse_mode": "Markdown"
    # 这样 Telegram 就会把你的内容当成普通纯文本，包含任何符号都不会报错！
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        res = requests.post(url, json=payload) # 这里改用 json 发送更规范
        
        if res.status_code == 200:
            return True
        else:
            # --- 调试关键 ---
            # 如果失败，打印 Telegram 返回的具体错误信息
            print(f"❌ Telegram API 报错: {res.text}")
            return False
    except Exception as e:
        print(f"❌ 网络请求异常: {e}")
        return False

def get_segments_from_file(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    # 按空行分割
    segments = content.split('\n\n')
    return [seg.strip() for seg in segments if seg.strip()]

def save_segments_to_file(filename, segments):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(segments))

def main():
    quotes_file = 'quotes.txt'
    used_file = 'used_quotes.txt'
    
    # 1. 读取
    blocks = get_segments_from_file(quotes_file)
    
    # 2. 检查库存与回填
    if not blocks:
        print("ℹ️ 主库已空，尝试从 used 库回填...")
        blocks = get_segments_from_file(used_file)
        if not blocks:
            print("⚠️ 两个库都空了，无法发送。")
            return
        save_segments_to_file(quotes_file, blocks)
        open(used_file, 'w').close()
        print("✅ 回填完毕。")

    # 3. 随机抽取
    picked_block = random.choice(blocks)
    
    # 4. 时间图标
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    beijing_hour = (utc_now + datetime.timedelta(hours=8)).hour
    if beijing_hour < 10: icon = "☀️ 早安复习"
    elif beijing_hour < 14: icon = "🍱 午间充电"
    else: icon = "🌙 晚安回顾"

    # 5. 拼接消息 (纯文本模式下，*不会变粗体，但能保证发出)
    final_msg = f"【{icon}】\n\n{picked_block}"
    
    print(f"正在发送内容片段 (前20字): {picked_block[:20]}...")

    # 6. 发送
    success = send_telegram_message(final_msg)

    if success:
        print("✅ 发送成功！")
        # 7. 移动数据
        blocks.remove(picked_block)
        save_segments_to_file(quotes_file, blocks)
        with open(used_file, 'a', encoding='utf-8') as f:
            if os.path.getsize(used_file) > 0:
                f.write('\n\n')
            f.write(picked_block)
    else:
        print("❌ 发送流程失败，不修改文件。")

if __name__ == "__main__":
    main()
