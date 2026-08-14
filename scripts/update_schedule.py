import re
import urllib.request
from html.parser import HTMLParser

URL = "https://npb.jp/games/2026/schedule_08_detail.html"

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
        self.cell_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []

        elif tag in ("td", "th") and self.current_row is not None:
            self.current_cell = []
            self.cell_depth = 1

        elif self.current_cell is not None:
            self.cell_depth += 1

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current_cell is not None:
            text = "".join(self.current_cell)
            text = re.sub(r"\s+", " ", text).strip()

            self.current_row.append(text)

            self.current_cell = None
            self.cell_depth = 0

        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)

            self.current_row = None

        elif self.current_cell is not None and self.cell_depth > 0:
            self.cell_depth -= 1

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

for row in parser.rows:
    row_text = " | ".join(row)

    date_match = re.search(r"8/(\d{1,2})", row_text)

    if date_match:
        day = int(date_match.group(1))
        current_date = f"2026-08-{day:02d}"

    if current_date is None:
        continue

    teams_found = []

    for team in TEAM_NAMES:
        if team in row_text:
            teams_found.append(team)

    if len(teams_found) == 2:
        games.append({
            "date": current_date,
            "team1": teams_found[0],
            "team2": teams_found[1],
            "raw": row_text
        })


print("status: OK")
print("rows:", len(parser.rows))
print("games found:", len(games))

print()
print("=== 8/15 ソフトバンク戦 ===")

found = False

for game in games:
    if (
        game["date"] == "2026-08-15"
        and "ソフトバンク" in (game["team1"], game["team2"])
    ):
        print(game)
        found = True

if not found:
    print("NOT FOUND")
