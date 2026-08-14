import re
import urllib.request
from html.parser import HTMLParser

URL = "https://npb.jp/games/2026/schedule_08_detail.html"

TARGET_TEAM = "ソフトバンク"

TEAM_NAMES = [
    "巨人",
    "ヤクルト",
    "DeNA",
    "中日",
    "阪神",
    "広島",
    "ソフトバンク",
    "日本ハム",
    "ロッテ",
    "楽天",
    "西武",
    "オリックス",
]


class ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []

        elif tag in ("td", "th") and self.current_row is not None:
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current_cell is not None:
            text = "".join(self.current_cell)
            text = re.sub(r"\s+", " ", text).strip()

            if text:
                self.current_row.append(text)

            self.current_cell = None

        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)

            self.current_row = None

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)


request = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urllib.request.urlopen(request, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")


parser = ScheduleParser()
parser.feed(html)

current_date = None

games = []
seen = set()

for row in parser.rows:
    row_text = " | ".join(row)

    # 日付を取得
    date_match = re.search(r"8/(\d{1,2})", row_text)

    if date_match:
        day = int(date_match.group(1))
        current_date = f"2026-08-{day:02d}"

    if current_date is None:
        continue

    # ソフトバンクを含まない行は無視
    if TARGET_TEAM not in row_text:
        continue

    # この行に含まれる球団名を抽出
    teams_found = []

    for team in TEAM_NAMES:
        if team in row_text:
            teams_found.append(team)

    # 2球団ちょうど含まれる行だけ採用
    if len(teams_found) != 2:
        continue

    # 同じ行を重複登録しない
    key = (current_date, row_text)

    if key in seen:
        continue

    seen.add(key)

    opponent = (
        teams_found[1]
        if teams_found[0] == TARGET_TEAM
        else teams_found[0]
    )

    games.append({
        "date": current_date,
        "opponent": opponent,
        "raw": row_text
    })


print("status: OK")
print("total rows:", len(parser.rows))
print("softbank games found:", len(games))
print()

for game in games:
    print(
        game["date"],
        TARGET_TEAM,
        "vs",
        game["opponent"]
    )
    print("  ", game["raw"])
    print()
