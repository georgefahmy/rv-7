import requests
import re
from bs4 import BeautifulSoup as bs


thread_num = 535
url = f"https://vansairforce.net/community/archive/index.php/t-{thread_num}.html"

soup = bs(requests.get(url).content)

results = soup.find_all(string=re.compile("california", flags=re.I))

for i in results:
    print(i)
