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
    # 🌟 인사쟁이 수준의 무거운 전문 주제들로 쿼리 전면 재편
    expert_query = (
        '("노동법 판례" OR "대법원 판결" OR "고용노동부 지침" OR "근로기준법 개정" OR '
        '"임금체계 개편" OR "퇴직률" OR "이직률" OR "구조조정 동향" OR "통상임금" OR '
        '"산재 판결" OR "부당해고" OR "주52시간제" OR "최저임금위원회" OR "직장내괴롭힘 판례")'
    )
    encoded_keyword = urllib.parse.quote(expert_query)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    temp_pool = []
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    now = datetime.now()
    time_limit = now - timedelta(days=4) # 최신 트렌드 유지를 위해 수집 기간 압축
    
    # 🌟 가십성 뉴스나 단순 홍보 기사가 주로 채널링되는 매체 감점/차단 리스트
    low_priority_sources = ["네이트", "이투데이", "뉴스웍스", "퍼블릭뉴스", "스타뉴스", "연예", "스포츠"]
    
    # 🌟 인사쟁이 뉴스레터 스타일의 고품질 핵심 단어 가중치 시스템
    high_priority_keywords = ["판결", "판례", "개정", "지침", "선고", "해고", "퇴직", "이직", "조사 결과", "통계", "실태"]

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
            
            # 🌟 무가치한 홍보성/행사성 단어 필터링 (런던베이글, 단순 공고 등 원천 차단)
            noise_words = [
                "모집", "공고", "개최", "세미나", "설명회", "MOU", "체결", "출시", "이벤트", 
                "기념", "데이", "간담회", "캠페인", "특강", "방문", "재단", "포토", "인사말"
            ]
            if any(nw in clean_title for nw in noise_words):
                continue
                
            # 매체 필터링
            if any(lps in source for lps in low_priority_sources):
                continue

            # 가중치 계산 (기본 점수 100점)
            score = 100
            
            # 고품질 키워드 포함 시 보너스 점수 부여
            for hpk in high_priority_keywords:
                if hpk in clean_title:
                    score += 50
            
            # 최신 뉴스일수록 우대
            hours_ago = (now - pub_time).total_seconds() / 3600
            score -= (hours_ago * 2)
            
            words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', clean_title)
            
            temp_pool.append({
                "title": clean_title,
                "url": link,
                "source": source,
                "time": pub_time,
                "score": score,
                "words": words
            })
            
    except Exception as e:
        print(f"뉴스 수집 중 오류: {e}")
        return []

    # 점수 기준 내림차순 정렬
    temp_pool.sort(key=lambda x: x["score"], reverse=True)
    
    final_news_list = []
    global_word_counter = {}
    
    for article in temp_pool:
        if len(final_news_list) >= 8: # 밀도 높은 핵심 8개 기사만 선별
            break
            
        # 특정 단어/기업명 도배 방지 (전날 기사 연속 노출 차단)
        is_flooded = False
        for w in article["words"]:
            if w in ["뉴스", "기자", "정부", "근로자", "노동"]: 
                continue
            if global_word_counter.get(w, 0) >= 1: # 단어 중복 임계치를 1회로 극단적 하향 (완벽한 다채로움 보장)
                is_flooded = True
                break
                    
        if is_flooded:
            continue
            
        if not any(n['url'] == article['url'] for n in final_news_list):
            final_news_list.append({
                "title": article["title"],
                "url": article["url"],
                "source": article["source"]
            })
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
    당신은 최고경영진(C-Level) 및 최고인사책임자(CHRO)를 보좌하는 수석 노무전략가입니다.
    선별된 뉴스는 기업 경영과 조직 리스크 관리에 직결되는 핵심 법률/시장 정보입니다.
    
    [핵심 요약 규칙]
    1. 마크다운 기호(#, **, ` 등)는 절대 쓰지 마세요.
    2. 이 기사가 '우리 기업 운영에 미치는 실무적 영향이나 시사점'을 포함하여 날카롭게 2줄(불릿포인트)로 요약해 주세요. 단순 사실 나열은 금지합니다.
    3. 각 기사 분리가 끝나면 [구분자] 코드를 새 행에 입력하세요.
    
    [출력 양식]
    언론사이름 | 기사제목
    • 실무 시사점 요약 1문장
    • 경영진 대응 가이드 1문장
    기사링크주소
    [구분자]
    
    [입력 데이터]
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
            <div style="background-color: #1e3a8a; padding: 30px 20px; text-align: center; border-radius: 12px; color: #ffffff; margin-bottom: 20px;">
                <span style="display: inline-block; background-color: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; margin-bottom: 8px; color: #ffffff;">CHRO STRATEGIC REPORT</span>
                <h1 style="margin: 0px 0 6px 0; font-size: 25px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">세방 HR 브리핑</h1>
                <p style="margin: 0; font-size: 13px; color: #ffffff; opacity: 0.9; font-weight: 300;">{today_str} 고품질 인사노무·법률 실무 트렌드</p>
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
                    
                    source_name = "전문 동향"
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
                    border_color = "#1d4ed8" if valid_count <= 2 else "#e2e8f0"
                    badge_bg = "#eff6ff" if valid_count <= 2 else "#f8fafc"
                    badge_text = "#1e40af" if valid_count <= 2 else "#64748b"
                    badge_label = "⭐ 핵심 현안" if valid_count <= 2 else "실무 리포트"
                    
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid {border_color}; border-top: 4px solid #1e3a8a; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: {badge_bg}; color: {badge_text}; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{badge_label} | {source_name.strip()}</span>
                        </div>
                        <h3 style="margin: 0 0 12px 0; font-size: 15px; color: #0f172a; font-weight: bold; line-height: 1.4;">{title_name.strip()}</h3>
                        <ul style="margin: 0 0 18px 0; padding-left: 20px; font-size: 13.5px; color: #334155;">
                            {summary_html}
                        </ul>
                        <div style="text-align: right;">
                            <a href="{link_line.strip()}" target="_blank" style="display: inline-block; background-color: #1e3a8a; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                        </div>
                    </div>
                    """
            if valid_count == 0: raise Exception("Fallback")
        else: raise Exception("Fallback")
    except Exception:
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #64748b; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                <div style="margin-bottom: 10px;">
                    <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{news['source']}</span>
                </div>
                <h3 style="margin: 0 0 12px 0; font-size: 15px; color: #0f172a; font-weight: bold;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="display: inline-block; background-color: #475569; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 16px; border-radius: 6px;">기사 원문 보기 →</a>
                </div>
            </div>
            """
    html_body += """
            </div>
            <div style="margin-top: 10px; padding: 25px; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #e2e8f0;">
                본 메일은 사내 인사 전략 참고 목적으로 핵심 필터링 정제 후 자동 발송되었습니다.<br>
                <strong style="color: #475569;">© 2026 SEBANG HR Automation. All Rights Reserved.</strong>
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
                msg['Subject'] = f"[세방 HR 브리핑] {datetime.now().strftime('%m/%d')} 경영진을 위한 인사노무 핵심 동향 리포트"
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("🚀 고품질 전략 리포트 발송 완료")
    except Exception as e:
        print(f"발송 에러: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    if raw_news:
        ai_content = generate_newsletter_with_gemini(raw_news)
        final_html = build_html_template(ai_content, raw_news)
        send_email(final_html)
