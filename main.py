import os
import time
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# .env から環境変数を読み込む
load_dotenv()
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
NOTE_SEARCH_KEYWORD = os.environ.get("NOTE_SEARCH_KEYWORD")

# Notion APIのヘッダ
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# Seleniumの設定（WebDriverManagerを使用）
options = Options()
options.add_argument("--headless")  # ヘッドレスモード
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def scroll_down():
    """
    ページをスクロールして記事をすべて読み込む
    """
    for _ in range(5):  # 5回スクロール（必要に応じて回数調整）
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        time.sleep(1)  # スクロール後に少し待機

def scrape_note_articles(keyword):
    """
    指定キーワードで note.com の検索結果ページを開き、
    記事のタイトル・URL・著者・いいね数を取得して返す。
    """
    search_url = f"https://note.com/search?q={keyword}&context=note&mode=search"
    driver.get(search_url)
    time.sleep(5)  # ページのロードを待機

    # デバッグ用: HTML全体を出力（先頭2000文字）
    # soup = BeautifulSoup(driver.page_source, "html.parser")
    # print("===== [DEBUG] ページHTMLの一部を出力 =====")
    # print(soup.prettify()[:2000])
    # print("===================================")

    # 記事が表示されるまで待機
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".m-largeNoteWrapper__card"))
        )
    except:
        print("⚠️ 検索結果が表示されませんでした。")
        return []

    # 十分な記事を読み込むためにスクロール
    scroll_down()

    # 再度HTMLを取得
    soup = BeautifulSoup(driver.page_source, "html.parser")

    articles_data = []
    cards = soup.select(".m-largeNoteWrapper__card")
    if not cards:
        print("⚠️ 記事が見つかりませんでした。")
        return []

    for card in cards:
        # タイトル
        title_tag = card.select_one("h3.m-noteBodyTitle__title")
        title = title_tag.get_text(strip=True) if title_tag else "No Title"

        # URL
        a_tag = card.select_one("a.m-largeNoteWrapper__link")
        if not a_tag:
            continue
        relative_url = a_tag.get("href", "")
        if relative_url.startswith("/"):
            url = "https://note.com" + relative_url
        else:
            url = relative_url

        # 著者
        author_tag = card.select_one(".o-largeNoteSummary__userName")
        author = author_tag.get_text(strip=True) if author_tag else "不明"

        # いいね数
        like_tag = card.select_one("span.pl-2.text-sm.text-text-secondary")
        like_count_str = like_tag.get_text(strip=True) if like_tag else "0"
        like_count_str = like_count_str.replace(",", "")  # カンマ除去
        like_count = int(like_count_str) if like_count_str.isdigit() else 0

        articles_data.append({
            "title": title,
            "url": url,
            "author": author,
            "like_count": like_count
        })

    return articles_data

def create_notion_page(article, keyword):
    """
    Notion APIを使ってデータベースに記事を登録
    追加: '検索ワード'用のプロパティ "Keyword"
    """
    url = "https://api.notion.com/v1/pages"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {
                "title": [
                    {"type": "text", "text": {"content": article["title"]}}
                ]
            },
            "URL": {"url": article["url"]},
            "AUTHOR": {
                "rich_text": [
                    {"type": "text", "text": {"content": article["author"]}}
                ]
            },
            "LIKE": {"number": article["like_count"]},
            # ★ ここで検索ワードを Notion に書き込む
            "Keyword": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": keyword}
                    }
                ]
            }
        }
    }

    res = requests.post(url, headers=HEADERS, json=payload)

    if res.status_code in [200, 201]:
        print(f"✅ Notion登録成功: {article['title']}")
    else:
        print(f"❌ Notion登録失敗: {article['title']}")
        print("Status Code:", res.status_code)
        print("Response:", res.text)

def main():
    """
    メイン処理:
    1. Noteのスクレイピング
    2. Notionにデータ登録 (検索ワードを追加)
    """
    print(f"🔍 キーワード『{NOTE_SEARCH_KEYWORD}』でnote記事を検索中...")
    articles = scrape_note_articles(NOTE_SEARCH_KEYWORD)
    print(f"✅ 記事 {len(articles)} 件取得")

    for article in articles:
        # create_notion_page() に 検索キーワードを渡す
        create_notion_page(article, NOTE_SEARCH_KEYWORD)

    driver.quit()
    print("🎉 全記事の登録完了!")

if __name__ == "__main__":
    main()
