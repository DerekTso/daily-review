import os
import random
import requests

def send_telegram_message(message):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, data=payload)
        return res.status_code == 200
    except:
        return False

def main():
    # 1. 读取待复习列表
    quotes_file = 'quotes.txt'
    used_file = 'used_quotes.txt' # 用来存已发过的
    
    # 如果文件不存在，创建空文件防止报错
    if not os.path.exists(quotes_file):
        open(quotes_file, 'w').close()
    if not os.path.exists(used_file):
        open(used_file, 'w').close()

    with open(quotes_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    # 2. 检查是否还有库存
    if not lines:
        print("待复习列表已空，正在从已复习列表(used_quotes.txt)回填...")
        # 从 used 回填到 quotes
        with open(used_file, 'r', encoding='utf-8') as f:
            used_lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if not used_lines:
            print("错误：两个列表都空了，请手动添加内容。")
            send_telegram_message("⚠️ 题库已空，请去 GitHub 添加新内容！")
            return

        # 重置文件
        lines = used_lines
        with open(quotes_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        # 清空 used 文件
        open(used_file, 'w').close()
        
        print("回填完毕，重新开始循环。")

    # 3. 随机抽取一条
    picked_quote = random.choice(lines)
    
    # 4. 发送
    # 根据时间判断是早/中/晚 (仅用于显示文案，可选)
    import datetime
    hour = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).hour
    if hour < 10:
        period = "☀️ 早晨"
    elif hour < 14:
        period = "🍱 中午"
    else:
        period = "🌙 晚上"

    msg = f"{period}复习：\n\n{picked_quote}"
    success = send_telegram_message(msg)

    if success:
        print(f"发送成功: {picked_quote}")
        
        # 5. 数据迁移（关键步骤：不重复的核心）
        # 从 lines 中移除这一条
        lines.remove(picked_quote)
        
        # 重写 quotes.txt (剩下的)
        with open(quotes_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            
        # 追加到 used_quotes.txt (已用的)
        with open(used_file, 'a', encoding='utf-8') as f:
            f.write(picked_quote + '\n')
            
    else:
        print("发送失败，不修改文件，下次重试")

if __name__ == "__main__":
    main()
