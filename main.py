import os
import random
import requests

def send_telegram_message(message):
    # 1. 从 GitHub Secrets 获取 Token 和 Chat ID
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    if not token or not chat_id:
        print("Error: 未找到 Token 或 Chat ID，请检查 Secrets 设置")
        return

    # 2. Telegram API URL
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # 3. 构造发送的数据
    # parse_mode='Markdown' 可以让你的文本支持粗体等格式
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown" 
    }

    # 4. 发送请求
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Telegram 推送成功")
        else:
            print(f"推送失败: {response.text}")
    except Exception as e:
        print(f"网络请求错误: {e}")

def main():
    try:
        # 读取 quotes.txt
        with open('quotes.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        lines = [line.strip() for line in lines if line.strip()]
        
        if not lines:
            print("没有内容可发送")
            return

        # 随机抽取
        content = random.choice(lines)
        
        # 可以在内容前加个 emoji 或者标题，更有仪式感
        formatted_content = f"🔔 *每日复习时刻*\n\n{content}"
        
        print(f"准备发送: {content}")
        send_telegram_message(formatted_content)
        
    except FileNotFoundError:
        print("错误: 找不到 quotes.txt 文件")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
