import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse

def get_hr_news():
    # 인사담당자가 반드시 봐야 할 핵심 키워드 리스트
    keywords = ["인사노무", "임단협 노사", "고용노동부 지침", "노동법 개정", "주52시간 최저임금"]
    news_list = []
    
    # 구글의 차단을 우회하기 위한 특수 헤더 세팅
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"
    }
    
    print("📰 대량의 실시간 인사/노무 뉴스 데이터 수집 시작...")
    
    for keyword in keywords:
        # 구글 뉴스 RSS 피드를 활용하여 차단을 원천 봉쇄하고 고품질 뉴스를 대량 수집합니다.
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.content, features="xml")
            items = soup.find_all("item")
            
            # 각 키워드별로 상위 4개씩 추출하여 총 15~20개의 뉴스를 확보합니다.
            for item in items[:4]:
                title = item.title.text.strip() if item.title else ""
                link = item.link.text.strip() if item.link else ""
                pub_date = item.pubDate.text.strip() if item.pubDate else ""
                source = item.source.text.strip() if item.source else "언론사"
                
                # 중복 뉴스 제거 및 유효 링크 검증
                if link and not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": title,
                        "url": link,
                        "source": source,
                        "date": pub_date
                    })
        except Exception as e:
            print(f"[{keyword}] 뉴스 수집 중 일시적 패스: {e}")
            
    print(f"총 {len(news_list)}개의 실시간 노동 뉴스 수집 완료.")
    return news_list

def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY 환경 변수를 찾을 수 없습니다.")
        return None
        
    # AI에게 넘겨줄 텍스트 데이터 정렬
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 언론사: {news['source']} / 키워드: {news['keyword']}\n제목: {news['title']}\n링크: {news['url']}\n\n"
    
    # 뉴스레터 전문가의 페르소나 주입
    prompt = f"""
    당신은 대한민국 최고의 인사노무 전문가이자 매력적인 뉴스레터 에디터입니다.
    아래 제공되는 {len(news_list)}개의 실시간 뉴스 데이터를 바탕으로, 인사담당자들이 아침에 출근해서 필수적으로 읽어야 할 '일일 HR 뉴스레터'를 작성해 주세요.
    
    [작성 규칙]
    1. 마크다운 기호(#, **, ` 등)는 이메일 화면에서 깨질 수 있으니 절대 사용하지 마세요.
    2. 오직 줄바꿈(엔터)과 직관적인 이모지(📍, 🚀, ⚖️ 등)만 사용하여 가독성을 극대화하세요.
    3. 수집된 모든 뉴스(10개~20개 전체)를 누락 없이 리스트 형태로 나열하고, 각 뉴스마다 핵심 요약을 2줄로 요약해 주세요.
    4. 각 뉴스 제목 바로 아래나 옆에 제공된 해당 기사의 원본 링크(URL)를 반드시 그대로 노출하여 클릭할 수 있게 하세요.
    
    [실시간 뉴스 데이터]
    {raw_news_text}
    """
    
    # [★구글 최신 공식 규격★] 404 에러를 완벽히 해결하는 올바른 API 엔드포인트 주소
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=40)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"구글 AI 요약 실패 (에러코드: {response.status_code}). 백업 모드로 전환합니다.")
            return None
    except Exception as e:
        print(f"AI 호출 중 예외 발생: {e}")
        return None

def send_email(content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    if not all([gmail_user, gmail_pw, receiver_email]):
        print("이메일 환경 변수 세팅을 다시 확인해 주세요.")
        return

    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = f"[세방 HR 브리핑] 오늘의 실시간 인사·노무·노동법 동향 리포트"
    
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pw)
            server.sendmail(gmail_user, receiver_email, msg.as_string())
        print("📬 뉴스레터 메일이 성공적으로 발송되었습니다!")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

if __name__ == "__main__":
    raw_news = get_hr_news()
    
    if not raw_news:
        print("수집된 뉴스가 없어 기본 안내 메일을 발송합니다.")
        content = "오늘 수집된 새로운 실시간 인사노무 동향 뉴스가 없습니다."
    else:
        content = generate_newsletter_with_gemini(raw_news)
        
        # AI 요약 엔진이 일시적으로 다운되었을 때를 대비한 견고한 서브 백업 시스템
        if not content:
            content = "🔔 구글 AI 브리핑 엔진의 일시적 지연으로 인해 수집된 실시간 원본 뉴스 링크를 즉시 전달해 드립니다.\n\n"
            for idx, news in enumerate(raw_news, 1):
                content += f"[{idx}] {news['title']}\n매체: {news['source']} | 키워드: {news['keyword']}\n기사 링크: {news['url']}\n\n"
                
    send_email(content)
