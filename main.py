import os
import random
import requests
import datetime

def send_telegram_message(message):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown" # 依然支持 Markdown
    }
    try:
        res = requests.post(url, data=payload)
        return res.status_code == 200
    except:
        return False

def get_segments_from_file(filename):
    """
    读取文件，按空行分割成段落列表
    """
    if not os.path.exists(filename):
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 核心逻辑：使用双换行符分割
    # split('\n\n') 会根据空行切分
    # 如果你的空行里包含空格，可以用正则，但简单场景下 strip() 足够
    segments = content.split('\n\n')
    
    # 清理数据：去除每个段落首尾的空白，并过滤掉纯空段落
    cleaned_segments = [seg.strip() for seg in segments if seg.strip()]
    
    return cleaned_segments

def save_segments_to_file(filename, segments):
    """
    将段落列表保存回文件，段落之间用两个换行符连接
    """
    with open(filename, 'w', encoding='utf-8') as f:
        # join 的时候加上 \n\n 恢复空行格式
        f.write('\n\n'.join(segments))

def main():
    # 文件名配置
    quotes_file = 'quotes.txt'
    used_file = 'used_quotes.txt'
    
    # 1. 读取数据
    # 注意：现在得到的 lines 其实是 blocks (段落块)
    blocks = get_segments_from_file(quotes_file)
    
    # 2. 检查库存与循环逻辑
    if not blocks:
        print("主库已空，正在从 used 库回填...")
        used_blocks = get_segments_from_file(used_file)
        
        if not used_blocks:
            print("错误：两个库都空了。")
            send_telegram_message("⚠️ 题库已空，请添加内容！")
            return
            
        # 回填
        blocks = used_blocks
        save_segments_to_file(quotes_file, blocks)
        # 清空 used 文件
        open(used_file, 'w').close()
        print("回填完毕。")

    # 3. 随机抽取
    picked_block = random.choice(blocks)
    
    # 4. 确定当前时间段 (装饰用)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    beijing_now = utc_now + datetime.timedelta(hours=8)
    hour = beijing_now.hour
    
    if hour < 10:
        icon = "☀️ 早安复习"
    elif hour < 14:
        icon = "🍱 午间充电"
    else:
        icon = "🌙 晚安回顾"

    # 5. 构造消息
    # picked_block 本身就是一大段带换行的文本，直接拼接即可
    final_msg = f"*{icon}*\n\n{picked_block}"
    
    # 6. 发送
    success = send_telegram_message(final_msg)

    if success:
        print("发送成功")
        
        # 7. 移动数据 (防重复逻辑)
        blocks.remove(picked_block) # 从主库移除
        
        # 重新写入主库
        save_segments_to_file(quotes_file, blocks)
        
        # 追加到 used 库 (注意要先读旧的，或者直接追加模式)
        # 为了保持格式整洁，建议用追加模式写入，并补上换行
        with open(used_file, 'a', encoding='utf-8') as f:
            # 如果文件不为空，先加个空行
            if os.path.getsize(used_file) > 0:
                f.write('\n\n')
            f.write(picked_block)
            
    else:
        print("发送失败，不修改文件")

if __name__ == "__main__":
    main()
