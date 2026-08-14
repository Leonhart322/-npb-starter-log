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
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")


parser = ScheduleParser()
parser.feed(html)

current_date = None
games = []

for row in parser.rows:
    row_text = " | ".join(row)

    date_match = re.search(r"8/(\d{1,2})", row_text)

    if date_match:
        day = int(date_match.group(1))
        current_date = f"2026-08-{day:02d}"

    if current_date is None:
        continue

    if TARGET_TEAM not in row_text:
        continue

    # 球団名を「文章中に出てくる順番」で取得
    team_positions = []

    for team in TEAM_NAMES:
        position = row_text.find(team)

        if position != -1:
            team_positions.append((position, team))

    team_positions.sort()

    if len(team_positions) != 2:
        continue

    home_team = team_positions[0][1]
    away_team = team_positions[1][1]

    if TARGET_TEAM == home_team:
        home_away = "H"
        opponent = away_team
        starter_index = 0
    else:
        home_away = "V"
        opponent = home_team
        starter_index = 1

    # 予告先発を掲載順に取得
    starters = re.findall(
        r"先発\s*[：:]\s*([^\s|]+)",
        row_text
    )

    announced_starter = None

    if len(starters) >= 2:
        announced_starter = starters[starter_index]

    # 試合状態
    if "中止" in row_text:
        status = "CANCELLED"
    elif re.search(r"\d+\s*-\s*\d+", row_text):
        status = "FINISHED"
    else:
        status = "SCHEDULED"

    games.append({
        "date": current_date,
        "opponent": opponent,
        "homeAway": home_away,
        "status": status,
        "announcedStarter": announced_starter,
        "raw": row_text
    })


print("status: OK")
print("softbank games:", len(games))
print()

for game in games:
    print(
        game["date"],
        game["homeAway"],
        "vs",
        game["opponent"],
        "|",
        game["status"],
        "| 予告:",
        game["announcedStarter"]
    )

print()
print("=== 8/15 CHECK ===")

for game in games:
    if game["date"] == "2026-08-15":
        print(game)
