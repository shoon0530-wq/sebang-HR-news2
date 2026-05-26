import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import ssl
from datetime import datetime, timedelta
import time
import re

try:
    import feedparser
except ImportError:
    os.system('pip install feedparser')
    import feedparser

try:
    import requests
except ImportError:
    os.system('pip install requests')
    import requests

def get_hr_news():
    broad_query = '(인사관리 OR 노무 OR 근로기준법 OR 유연근무 OR "채용 트렌드" OR "조직문화" OR "인사노무" OR "노동법 판례" OR "임단협 파업" OR "고용노동부 정책")'
    encoded_keyword = urllib.parse.quote(broad_query)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    temp_pool = []
    word_frequency = {}
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    now = datetime.now()
    time_limit = now - timedelta(days=5) # 주말 공백을 지우기 위해 수집 범위 조율
    
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            source = entry.source.title if hasattr(entry, 'source') else "언론사"
            
            pub_time = now
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                if pub_time < time_limit:
                    continue
            
            clean_title = title.split(" - ")[0].strip()
            if " < " in clean_title:
                clean_title = clean_title.split(" < ")[0].strip()
            
            noise_words = ["노무현재단", "재단", "연예", "스포츠", "아이돌", "드라마", "영화", "모집", "공고"]
            if any(nw in clean_title for nw in noise_words):
                continue
                
            words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', clean_title)
            for w in words:
                if w in ["뉴스", "기자", "오늘", "내일", "인사", "노무", "그룹", "강화"]:
                    continue
                word_frequency[w] = word_frequency.get(w, 0) + 1
                
            temp_pool.append({
                "title": clean_title,
                "url": link,
                "source": source,
                "time": pub_time,
                "words": words
            })
            
    except Exception as e:
        print(f"뉴스 수집 중 오류: {e}")
        return []

    # 단어 빈도수와 최신성을 결합하여 1차 정렬
    def calculate_score(article):
        score = sum(word_frequency.get(w, 0) for w in article["words"])
        hours_ago = (now - article["time"]).total_seconds() / 3600
        return score - (hours_ago * 0.1)

    temp_pool.sort(key=calculate_score, reverse=True)
    
    final_news_list = []
    global_word_counter = {}
    
    for article in temp_pool:
        if len(final_news_list) >= 10: # 일일 적정 보고서 분량 제한
            break
            
        # 🌟 동일한 핵심 명사가 최종 리스트 내에 2번 이상 등장했는지 엄격히 감시
        is_flooded = False
        for w in article["words"]:
            # 특정 기업명(예: 한국앤컴퍼니, 삼성전자 등)이나 주요 이슈어 단어 도배 차단
            if global_word_counter.get(w, 0) >= 2:
                is_flooded = True
                break
                    
        if is_flooded:
            continue # 특정 주제/기업 뉴스 독점 방지를 위해 과감히 탈락 처리
            
        if not any(n['url'] == article['url'] for n in final_news_list):
            final_news_list.append({
                "title": article["title"],
                "url": article["url"],
                "source": article["source"]
            })
            # 사용된 모든 단어의 카운트를 증가시켜 유사 기사 차단망 구축
            for w in article["words"]:
                global_word_counter[w] = global_word_counter.get(w, 0) + 1

    return final_news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 매체: {news['source']} | 제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대기업의 수석 인사노무 전문가이자 뉴스레터 편집자입니다.
    제공되는 뉴스는 중복 분산 처리가 완료된 고품질 HR 시사 트렌드 데이터입니다.
    경영진을 위한 종합 데일리 리포트를 양식에 맞춰 완벽하게 작성해 주세요.
    
    [핵심 작성 규칙]
    1. 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 각 기사에 대해 날카롭고 명확한 핵심 요점을 정확히 2줄(불릿포인트)로 작성해 주세요.
    3. 각 기사 본문 작성이 끝나면 [구분자] 코드를 반드시 새 행에 적어주세요.
    
    [출력 양식 예시]
    언론사이름 | 기사제목
    • 첫 번째 요약 문장입니다.
    • 두 번째 요약 문장입니다.
    기사링크주소
    [구분자]
    
    [실시간 뉴스 데이터]
    {raw_news_text}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=40)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return None
    except Exception:
        return None

def build_html_template(ai_content, raw_news):
    today_str = datetime.now().strftime('%Y년 %m월 %d일')
    html_body = f"""
    <div style="background-color: #f8fafc; padding: 20px 10px 40px 10px; font-family: 'Malgun Gothic', sans-serif; color: #334155; line-height: 1.6; margin: 0;">
        <div style="max-width: 620px; margin: 0 auto;">
            <div style="background-color: #0f172a; padding: 30px 20px; text-align: center; border-radius: 12px; color: #ffffff; margin-bottom: 20px;">
                <span style="display: inline-block; background-color: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; margin-bottom: 8px; color: #ffffff;">EXECUTIVE HR BRIEFING</span>
                <h1 style="margin: 0px 0 6px 0; font-size: 26px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">세방 HR 브리핑</h1>
                <p style="margin: 0; font-size: 13px; color: #ffffff; opacity: 0.85; font-weight: 300;">{today_str} 주요 인사·노무 및 시사 트렌드 동향</p>
            </div>
            <div style="padding: 0px 0;">
    """
    try:
        if ai_content and "[구분자]" in ai_content:
            articles = ai_content.strip().split("[구분자]")
            valid_count = 0
            for article in articles:
                lines = [line.strip() for line in article.strip().split('\n') if line.strip()]
                if len(lines) >= 3:
                    header_line = lines[0]
                    link_line = lines[-1]
                    summary_lines = lines[1:-1]
                    if not link_line.startswith("http"): continue
                    
                    source_name = "실시간 주요현안"
                    title_name = header_line
                    if "|" in header_line:
                        source_name, title_name = header_line.split("|", 1)
                    
                    summary_html = ""
                    for sl in summary_lines:
                        clean_sl = sl.replace('•', '').replace('-', '').strip()
                        if clean_sl:
                            summary_html += f"<li style='margin-bottom: 6px;'>{clean_sl}</li>"
                    if not summary_html: continue
                    
                    valid_count += 1
                    border_color = "#3b82f6" if valid_count <= 2 else "#e2e8f0"
                    badge_bg = "#dbeafe" if valid_count <= 2 else "#eff6ff"
                    badge_text = "#1e40af" if valid_count <= 2 else "#2563eb"
                    badge_label = "🔥 TOP ISSUE" if valid_count <= 2 else "동향 리포트"
                    
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid {border_color}; border-top: 4px solid #2563eb; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: {badge_bg}; color: {badge_text}; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{badge_label} | {source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 18px 0; padding-left: 20px; font-size: 14px; color: #475569;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #1e40af; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                        </div>
                    </div>
                    """
            if valid_count == 0: raise Exception("Fallback")
        else: raise Exception("Fallback")
    except Exception:
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #475569; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                <div style="margin-bottom: 10px;">
                    <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{news['source']}</span>
                </div>
                <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e293b; font-weight: bold;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="display: inline-block; background-color: #64748b; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                </div>
            </div>
            """
    html_body += """
            </div>
            <div style="margin-top: 10px; padding: 25px; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #e2e8f0;">
                본 메일은 사내 인사 정보 참고 목적으로 생성형 AI 엔진을 통해 자동 발송되었습니다.<br>
                <strong style="color: #64748b;">© 2026 SEBANG HR Automation. All Rights Reserved.</strong>
            </div>
        </div>
    </div>
    """
    return html_body

def send_email(html_content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_raw = os.environ.get("RECEIVER_EMAIL")
    if not receiver_raw: return
    
    receiver_list = [email.strip() for email in receiver_raw.split(",") if email.strip()]
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            for receiver_email in receiver_list:
                msg = MIMEMultipart()
                msg['From'] = gmail_user
                msg['To'] = receiver_email
                msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 주요 시사 및 인사노무 종합 리포트"
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 평일 뉴스레터 송신 완료")
    except Exception as e:
        print(f"발송 에러: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    if raw_news:
        ai_content = generate_newsletter_with_gemini(raw_news)
        final_html = build_html_template(ai_content, raw_news)
        send_email(final_html)
