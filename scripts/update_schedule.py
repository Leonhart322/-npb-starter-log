import urllib.request

URL = "https://npb.jp/games/2026/schedule_08_detail.html"

with urllib.request.urlopen(URL, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")

print("status: OK")
print("bytes:", len(html))
print("contains ソフトバンク:", "ソフトバンク" in html)
