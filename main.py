import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import ssl
from datetime import datetime, timedelta
import time

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
    # 🔍 10가지 인사노무 핵심 테마
    categories = [
        {"name": "노동법 개정", "query": "근로기준법 개정 시간단위 연차 4시간 근무 선택 퇴근"},
        {"name": "노란봉투법", "query": "노란봉투법 국회 본회의"},
        {"name": "정년연장", "query": "고령자 정년연장 계속고용 정년 법제화"},
        {"name": "인사 현안", "query": "주4.5일제 유연근무제 주4일제 도입 기업"},
        {"name": "AI 인사 노무", "query": "HR 테크 AI 인사관리 노무 자동화 트렌드"},
        {"name": "노무 파업 임단협", "query": "삼성전자 파업 대기업 임단협 성과급 협상"},
        {"name": "정부 제도 변경", "query": "고용노동부 제도 변경 취업자 증가 고용 동향"},
        {"name": "세무 및 사건사고", "query": "직장인 연말정산 종합소득세 횡령 사건사고"},
        {"name": "인사노무 판례", "query": "대법원 인사노무 판례 통상임금 근로자성 선고"},
        {"name": "인사 트렌드", "query": "인사담당자 채용 트렌드 조직문화 가치관"}
    ]
    
    news_list = []
    global_issue_counts = {"파업/노사": 0, "노란봉투": 0}
    
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
        
    now = datetime.now()
    
    # 📆 [날짜 보정 패치] 월요일이거나 연휴 직후(주말 공백)일 때는 수집 범위를 7일 전까지 확대하여 기사 고갈을 막습니다.
    if now.weekday() in [0, 1]:  # 월요일(0) 또는 화요일(1)인 경우
        days_ago = 7
        print(f"📅 주말/연휴 공백을 감안하여 최근 {days_ago}일간의 뉴스를 검색합니다.")
    else:
        days_ago = 4  # 평일에는 4일 이내 신선한 뉴스 수집
        print(f"📅 평일 주기: 최근 {days_ago}일간의 뉴스를 검색합니다.")
        
    time_limit = now - timedelta(days=days_ago)
        
    for cat in categories:
        cat_name = cat["name"]
        query_str = cat["query"]
        
        encoded_keyword = urllib.parse.quote(query_str)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        cat_collected_count = 0
        max_quota = 2  # 이슈 성격별 최대 2개 강제 제한 유지
        
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if cat_collected_count >= max_quota:
                    break
                    
                title = entry.title
                link = entry.link
                source = entry.source.title if hasattr(entry, 'source') else "언론사"
                
                # 발행 날짜 체크
                is_recent = True
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_dt < time_limit:
                        is_recent = False
                
                if not is_recent or not link:
                    continue
                    
                # 제목 끝에 붙는 언론사 꼬리표 깨끗하게 제거
                clean_title = title.split(" - ")[0].strip()
                if " < " in clean_title:
                    clean_title = clean_title.split(" < ")[0].strip()
                
                # 특정 이슈 과밀집 방지 2중 안전 잠금 장치
                strike_words = ["파업", "쟁의", "노사 갈등", "임단협", "성과급", "삼성전자"]
                yellow_words = ["노란봉투", "노란 봉투"]
                
                if any(w in clean_title for w in strike_words):
                    if global_issue_counts["파업/노사"] >= 2 and cat_name != "노무 파업 임단협":
                        continue
                        
                if any(w in clean_title for w in yellow_words):
                    if global_issue_counts["노란봉투"] >= 2 and cat_name != "노란봉투법":
                        continue
                
                if not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": cat_name,
                        "title": clean_title,
                        "url": link,
                        "source": source
                    })
                    
                    cat_collected_count += 1
                    if any(w in clean_title for w in strike_words):
                        global_issue_counts["파업/노사"] += 1
                    if any(w in clean_title for w in yellow_words):
                        global_issue_counts["노란봉투"] += 1
                        
                    print(f"   ✅ [{cat_name}] 수집 ({cat_collected_count}/{max_quota}): {clean_title[:25]}...")
                    
        except Exception as e:
            print(f"[{cat_name}] 검색 오류 스킵: {e}")
            
    print(f"📊 최종 균등 조율 완료 뉴스 총합: {len(news_list)}개")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 분야: {news['keyword']} | 매체: {news['source']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 대기업의 수석 인사노무 전문가이자 뉴스레터 편집자입니다.
    아래 제공되는 최신 뉴스 데이터를 바탕으로 경영진을 위한 종합 데일리 리포트를 작성해 주세요.
    다양한 테마들이 균형 있게 섞여 있으니 이 결을 그대로 유지해야 합니다.
    
    [핵심 작성 규칙]
    1. 답변은 반드시 아래의 포맷 양식으로만 구성해야 하며, 마크다운 기호(#, **, ` 등)는 절대로 쓰지 마세요.
    2. 각 기사에 대해 날카롭고 명확한 핵심 요점을 정확히 2줄(불릿포인트)로 작성해 주세요.
    3. 각 기사 본문 작성이 끝나면 다음 기사로 넘어가기 전에 [구분자] 코드를 반드시 새 행에 적어주세요.
    
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
        else:
            return None
    except Exception as e:
        print(f"AI 호출 오류: {e}")
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
        # AI 결과가 유효하고 구분자가 존재하는지 검증 후 파싱
        if ai_content and "[구분자]" in ai_content:
            articles = ai_content.strip().split("[구분자]")
            valid_count = 0
            
            for article in articles:
                lines = [line.strip() for line in article.strip().split('\n') if line.strip()]
                if len(lines) >= 3:
                    header_line = lines[0]
                    link_line = lines[-1]
                    summary_lines = lines[1:-1]
                    
                    if not link_line.startswith("http"):
                        continue
                        
                    source_name = "주요이슈"
                    title_name = header_line
                    if "|" in header_line:
                        source_name, title_name = header_line.split("|", 1)
                    
                    summary_html = ""
                    for sl in summary_lines:
                        clean_sl = sl.replace('•', '').replace('-', '').strip()
                        if clean_sl:
                            summary_html += f"<li style='margin-bottom: 6px;'>{clean_sl}</li>"
                    
                    if not summary_html:
                        continue
                        
                    valid_count += 1
                    html_body += f"""
                    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #2563eb; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: #eff6ff; color: #2563eb; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{source_name.strip()}</span>
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
            
            if valid_count == 0:
                raise Exception("No valid parsed articles")
        else:
            raise Exception("Fallback Trigger")
            
    except Exception:
        # 파싱 중 예외 발생 시 원본 데이터를 안전하게 매핑하여 빈 메일 발송 방지
        for news in raw_news:
            html_body += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #64748b; padding: 22px; margin-bottom: 20px; border-radius: 8px;">
                <span style="background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 6px;">{news['source']} ({news['keyword']})</span>
                <h3 style="margin: 8px 0 14px 0; font-size: 15px; color: #1e293b; font-weight: bold;">{news['title']}</h3>
                <div style="text-align: right;">
                    <a href="{news['url']}" target="_blank" style="color: #2563eb; font-size: 13px; font-weight: bold; text-decoration: none;">기사 원문 보기 →</a>
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
    
    if not receiver_raw:
        print("❌ RECEIVER_EMAIL 설정이 비어있습니다.")
        return
        
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
                print(f"📩 {receiver_email} 발송 완료!")
                
        print("🚀 모든 수신자에게 뉴스레터 발송 완료!")
    except Exception as e:
        print(f"메일 발송 오류: {e}")

if __name__ == "__main__":
    try:
        raw_news = get_hr_news()
        
        if not raw_news:
            print("⚠️ 새로운 뉴스 기사가 없습니다.")
            today_str = datetime.now().strftime('%Y년 %m월 %d일')
            no_news_html = f"""
            <div style="background-color: #f8fafc; padding: 40px 20px; font-family: 'Malgun Gothic', sans-serif; text-align: center;">
                <div style="max-width: 620px; margin: 0 auto; background: #ffffff; padding: 35px 30px; border-radius: 12px; border-top: 5px solid #64748b; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                    <h2 style="color: #1e293b; margin-top: 0; font-size: 20px;">세방 HR 브리핑 시스템 알림</h2>
                    <p style="font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 20px;">
                        안녕하세요. 오늘({today_str}) 지정된 핵심 시사 키워드에 대해<br>
                        <strong>최근 발행된 주요 기사가 발견되지 않았습니다.</strong>
                    </p>
                </div>
            </div>
            """
            send_email(no_news_html)
        else:
            ai_content = generate_newsletter_with_gemini(raw_news)
            final_html = build_html_template(ai_content, raw_news)
            send_email(final_html)
            
    except Exception as main_error:
        print(f"❌ 시스템 치명적 오류 발생: {main_error}")
