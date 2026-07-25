import os
import json
import random
import requests
import hashlib
from datetime import datetime, timedelta, timezone

# --- 配置区域 ---
QUOTES_FILE = 'quotes.txt'
DB_FILE = 'memory.json'
MAX_REVIEW_COUNT = 3
INTERVALS = [1, 2, 4, 7, 15, 30, 60]
# 新 API 的配置
TTS_API_URL = "https://t.leftsite.cn/api/v1/tts"
TTS_VOICE = "zh-CN-XiaoxiaoNeural"

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
            print(f"❌ Telegram Text API 报错: {res.text}")
            return False
    except Exception as e:
        print(f"❌ 网络请求异常: {e}")
        return False

def send_telegram_audio(file_path, caption="", title="今日新知朗读"):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendAudio"
    
    try:
        with open(file_path, 'rb') as audio:
            files = {'audio': audio}
            # 截取 caption 长度防止超过 Telegram 限制 (1024字符)
            safe_caption = caption[:1000] + "..." if len(caption) > 1000 else caption
            data = {'chat_id': chat_id, 'title': title, 'performer': 'Derek', 'caption': safe_caption}
            res = requests.post(url, files=files, data=data)
            
        if res.status_code == 200:
            print("✅ 语音发送成功")
            return True
        else:
            print(f"❌ Telegram Audio API 报错: {res.text}")
            return False
    except Exception as e:
        print(f"❌ 发送语音异常: {e}")
        return False

# --- [关键修改] 使用第三方 API 生成音频 ---
def generate_tts_audio(text, output_file="speech.mp3"):
    """调用 t.leftsite.cn API 生成晓晓语音"""
    try:
        if os.path.exists(output_file):
            os.remove(output_file)
            
        print("🔊 正在请求 t.leftsite.cn API (晓晓)...")
        
        # 构造请求参数
        params = {
            "text": text,
            "voice": TTS_VOICE,
            "rate": 0,
            "pitch": 0,
            "api_key": ""
        }
        
        # 发送请求，stream=True 用于下载文件
        res = requests.get(TTS_API_URL, params=params, stream=True, timeout=30)
        
        if res.status_code == 200:
            # 写入文件
            with open(output_file, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 检查文件是否生成成功
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return True
            else:
                print("⚠️ TTS 文件虽然下载了但大小为0")
                return False
        else:
            print(f"⚠️ TTS API 请求失败: {res.status_code} - {res.text}")
            return False
            
    except Exception as e:
        print(f"⚠️ TTS 生成异常: {e}")
        if os.path.exists(output_file):
            os.remove(output_file)
        return False

def get_ai_analysis(text):
    """调用 Google Gemini API"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ 未检测到 GEMINI_API_KEY，跳过 AI 分析")
        return ""

    # ⚠️ 如果运行报错 404，请检查模型名称是否准确
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
    
    prompt = f"""
    请阅读下面这段话，完成两项任务：
    1. 提取 3-5 个最核心的关键词（#Tag 风格）。
    2. 为这段话生成一个精炼简短的标题（不超过10个字）。

    请直接返回纯 JSON 字符串，不要包含 ```json 等 Markdown 标记：
    {{
        "keywords": "#关键词1 #关键词2 #关键词3",
        "title": "这里是标题"
    }}

    内容：
    “{text}”
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            raw_text = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            # 清洗可能存在的 Markdown 标记
            clean_text = raw_text.replace('```json', '').replace('```', '').strip()
            
            return json.loads(clean_text)
        else:
            print(f"⚠️ AI API 调用失败 (Status {response.status_code}): {response.text}")
            return ""
    except Exception as e:
        print(f"⚠️ AI 解析异常: {e}")
        return None

# --- [调试版] 从录入 Bot 获取新笔记 ---
def fetch_and_save_new_quotes():
    """
    检查录入 Bot 的新消息，追加到 quotes.txt (带详细调试日志)
    """
    input_token = os.environ.get("INPUT_BOT_TOKEN")
    my_chat_id = os.environ.get("TG_CHAT_ID") 

    print("🔍 [调试] 开始检查录入...")

    if not input_token:
        print("⚠️ [调试] 未找到 INPUT_BOT_TOKEN")
        return 0
    
    # 打印 Chat ID 的前几位和类型，检查是否读取正确
    print(f"🔍 [调试] 目标 Chat ID: {str(my_chat_id)}")

    url = f"https://api.telegram.org/bot{input_token}/getUpdates"
    
    try:
        res = requests.get(url, timeout=10)
        
        # 自动修复 Webhook
        if res.status_code == 409:
            print("⚠️ [调试] Webhook 冲突，执行删除...")
            requests.get(f"https://api.telegram.org/bot{input_token}/deleteWebhook")
            res = requests.get(url, timeout=10)

        if res.status_code != 200:
            print(f"⚠️ [调试] API 请求失败: {res.text}")
            return 0
        
        updates = res.json().get('result', [])
        
        # 关键调试点：打印收到了多少条消息
        print(f"🔍 [调试] API 返回了 {len(updates)} 条更新")
        
        if not updates:
            print("ℹ️ [调试] 没有新消息。请确认：1.你刚才给录入Bot发消息了吗？ 2.是不是发错Bot了？")
            return 0

        new_quotes = []
        max_update_id = 0

        for u in updates:
            update_id = u['update_id']
            max_update_id = max(max_update_id, update_id)
            
            if 'message' in u:
                msg = u['message']
                sender_id = str(msg.get('chat', {}).get('id', ''))
                target_id = str(my_chat_id)
                text = msg.get('text', '').strip()
                
                # 关键调试点：打印每条消息的匹配情况
                print(f"  👉 [消息] 发送者ID: '{sender_id}' | 目标ID: '{target_id}' | 内容: {text[:10]}...")
                
                if sender_id == target_id:
                    if text:
                        print("     ✅ 身份匹配，内容有效，加入列表")
                        new_quotes.append(text)
                    else:
                        print("     ❌ 身份匹配，但不是文本消息 (可能是图片/表情)")
                else:
                    print("     ❌ 身份不匹配！请检查 Secrets 中的 TG_CHAT_ID 是否正确")

        if new_quotes:
            print(f"📥 [调试] 最终提取到 {len(new_quotes)} 条有效笔记，正在写入...")
            with open(QUOTES_FILE, 'a', encoding='utf-8') as f:
                f.write('\n\n') 
                f.write('\n\n'.join(new_quotes))
            
            requests.get(f"{url}?offset={max_update_id + 1}")
            return len(new_quotes)
            
        if max_update_id > 0:
            print("🧹 [调试] 清理无效/不匹配的消息队列...")
            requests.get(f"{url}?offset={max_update_id + 1}")
            
        return 0

    except Exception as e:
        print(f"⚠️ [调试] 发生异常: {e}")
        return 0

def generate_weekly_report(data):
    total_cards = len(data)
    if total_cards == 0: return ""

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

    report = f"""
    📅 本周记忆周报
    ━━━━━━━━━━━━━━━━
    📚 知识库总量：{total_cards} 条
    
    📊 记忆分布热力：
    🌱 新知酝酿 (Lv.0)：{stats['new']}
    🌲 正在生根 (Lv.1-3)：{stats['learning']}
    🌳 枝繁叶茂 (Lv.4-6)：{stats['mastering']}
    🏛️ 永久收藏 (Lv.7+)：{stats['archived']}
    
    📈 内化进度：{mastery_rate:.1f}%
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
    # --- 1. 先检查有没有新录入的笔记 ---
    # 如果有新录入，先写入文件，然后再 load_data，这样今天就能复习到刚录入的
    added_count = fetch_and_save_new_quotes()
    if added_count > 0:
        print(f"📥 **自动剪藏助手**\n已成功收录 {added_count} 条新灵感！\n(将在今日或明日安排复习)")

    # --- 2. 常规复习流程 ---
    data = load_data()
    beijing_time = get_beijing_time()
    today_str = beijing_time.strftime('%Y-%m-%d')
    is_monday_morning = (beijing_time.weekday() == 0) and (beijing_time.hour < 11)

    if not data:
        print("⚠️ 数据库为空")
        return

    new_items = [item for item in data.values() if item['level'] == 0]
    review_candidates = [
        item for item in data.values() 
        if item['level'] > 0 and item['next_review'] and item['next_review'] <= today_str
    ]

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

    # --- 构造消息 ---
    msg_parts = []
    
    # A. 新知处理
    if picked_new:
        title = "🌱 今日新知" if picked_new['level'] == 0 else "🎲 随机漫步"
        msg_parts.append(f"{title}\n\n{picked_new['content']}")
        
        print("正在请求 AI 分析...")
        ai_result = get_ai_analysis(picked_new['content'])
        
        # 设置默认值
        ai_keywords = ""
        ai_title = "今日新知朗读"
        
        if ai_result and isinstance(ai_result, dict):
            ai_keywords = ai_result.get("keywords", "")
            ai_title = ai_result.get("title", "今日新知朗读")
        
        # [修改点1] 删除了将 ai_feedback 加入文本消息的逻辑
        # if ai_feedback:
        #     msg_parts.append(f"\n\n{ai_feedback}")

        # === 🎤 发送 TTS 语音 (Caption 放 AI Feedback) ===
        print("正在生成语音...")
        tts_text = picked_new['content'][:300].replace('*', '').replace('-', '')
        audio_file = "speech.mp3"
        
        # [修改点2] 将 AI 反馈作为语音的 Caption
        audio_caption = ai_keywords if ai_keywords else "🎧 今日新知伴读"
        
        try:
            if generate_tts_audio(tts_text, audio_file):
                print(f"语音生成完毕，标题: {ai_title}，正在发送...")
                send_telegram_audio(audio_file, caption=audio_caption, title=ai_title)
            else:
                print("⚠️ 跳过语音发送")
        finally:
            # 【关键修改】无论发送成功还是失败，最后都强制删除文件
            if os.path.exists(audio_file):
                os.remove(audio_file)
                print("🧹 已清理临时语音文件")
        # ===============================================
    
    # B. 复习列表
    if picked_reviews:
        msg_parts.append(f"\n🧠 今日复习 ({len(picked_reviews)}条)")
        for idx, item in enumerate(picked_reviews, 1):
            msg_parts.append(f"\n[{idx}] (Lv.{item['level']})\n{item['content']}")

    # C. 周报
    if is_monday_morning:
        print("📅 检测到周一早晨，正在生成周报...")
        report = generate_weekly_report(data)
        if report:
            msg_parts.append("\n" + report)

    final_msg = "\n".join(msg_parts)
    print(f"准备发送文本消息...")
    
    success = send_telegram_message(final_msg)

    # 5. 更新数据库
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
