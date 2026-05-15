import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. 구글 뉴스를 통해 실시간 진짜 뉴스 수집 (API 필요 없음)
# ==========================================
def get_hr_news():
    # 현재 가장 굵직한 실제 인사노무 이슈 키워드들입니다.
    keywords = ["삼성전자 교섭", "임단협 노사", "고용노동부 지침", "노동법 개정"]
    news_list = []
    
    # 구글이 로봇으로 의식하지 않도록 브라우저 정보 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("구글 뉴스에서 실시간 진짜 데이터를 검색 중입니다...")

    for keyword in keywords:
        # 구글 뉴스 RSS/검색 엔진을 활용해 최신 순으로 뉴스 포착
        url = f"https://www.google.com/search?q={keyword}&tbm=nws&lr=lang_ko"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 구글 뉴스 검색 결과 카드 레이아웃 추출
            articles = soup.select("div.So0B7b, div.Wlygcb, div.v7wOcf")
            
            # 구글의 레이아웃 변경 대비용 서브 선택자
            if not articles:
                articles = soup.select("div.nkSTFA")

            for article in articles[:3]: # 키워드당 최신 뉴스 3개씩 확보
                title_elem = article.select_one("div.n0wA1e, div.mCBkyc, a")
                link_elem = article.select_one("a")
                dsc_elem = article.select_one("div.GI748b, div.Y3v9ec")
                
                if not title_elem or not link_elem:
                    continue
                    
                title = title_elem.text.strip()
                link = link_elem['href']
                summary = dsc_elem.text.strip() if dsc_elem else "상세 내용은 링크를 참조하세요."
                
                # 구글 내부 링크가 아닌 실제 언론사 링크만 필터링
                if link.startswith("/url?q="):
                    link = link.split("/url?q=")[1].split("&")[0]
                
                if link.startswith("http") and not any(n['url'] == link for n in news_list):
                    news_list.append({
                        "keyword": keyword,
                        "title": title,
                        "summary": summary,
                        "url": link
                    })
        except Exception as e:
            print(f"[{keyword}] 구글 검색 중 스킵: {e}")
            
    return news_list

# ==========================================
# 2. Gemini AI 뉴스레터 생성
# ==========================================
def generate_newsletter_with_gemini(news_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: 
        raise ValueError("GEMINI_API_KEY가 존재하지 않습니다.")
        
    raw_news_text = ""
    for idx, news in enumerate(news_list, 1):
        raw_news_text += f"[{idx}] 키워드: {news['keyword']}\n제목: {news['title']}\n내용: {news['summary']}\n링크: {news['url']}\n\n"
    
    prompt = f"""
    당신은 기업의 CHO 전담 비서입니다. 아래 구글에서 실시간으로 수집된 실제 뉴스 데이터를 바탕으로 인사담당자가 반드시 읽어야 할 '일일 HR 뉴스레터'를 작성해 주세요.
    가짜 데이터가 아니라, 제공된 실시간 뉴스의 구체적인 내용(예: 삼성전자 교섭 상황 등)이 뉴스레터에 깊이 있게 녹아나야 합니다.
    메일 가독성을 위해 마크다운 기호(#, **)는 절대 쓰지 말고, 이모지와 일반 줄바꿈으로만 꾸며주세요.

    [실시간 뉴스 데이터]
    {raw_news_text}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise RuntimeError(f"AI 호출 실패: {response.text}")

# ==========================================
# 3. 메일 발송
# ==========================================
def send_email(content):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PW")
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = receiver_email
    msg['Subject'] = "[세방 HR 구글 브리핑] 오늘의 실시간 인사·노무 동향"
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_pw)
        server.sendmail(gmail_user, receiver_email, msg.as_string())
    print("구글 뉴스 기반 레터 발송 완료!")

if __name__ == "__main__":
    raw_news = get_hr_news()
    if not raw_news:
        print("구글에서 실시간 뉴스를 긁어오지 못했습니다. 소스를 재점검합니다.")
    else:
        content = generate_newsletter_with_gemini(raw_news)
        send_email(content)
