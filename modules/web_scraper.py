
import requests
from bs4 import BeautifulSoup
import urllib.parse

def search_duckduckgo(query):
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return "No results found."

        soup = BeautifulSoup(response.text, "html.parser")
        snippets = soup.find_all("a", class_="result__snippet")

        results = []
        for snippet in snippets[:3]:
            results.append(snippet.get_text().strip())

        if results:
            return " ".join(results)
    except Exception as e:
        print(f"Search error: {e}")

    return "No results found."

# Compatible alias for existing imports
def search_bing(query):
    return search_duckduckgo(query)

