import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://npb.jp/games/2026/schedule_08_detail.html"
OUTPUT_FILE = Path("data/games_2026.json")

TARGET_TEAM = "ソフトバンク"
TARGET_TEAM_ID = "H"

TEAM_IDS = {
    "巨人": "G",
    "ヤクルト": "S",
    "DeNA": "DB",
    "中日": "D",
    "阪神": "T",
    "広島": "C",
    "ソフトバンク": "H",
    "日本ハム": "F",
    "ロッテ": "M",
    "楽天": "E",
    "西武": "L",
    "オリックス": "B",
}

TEAM_NAMES = list(TEAM_IDS.keys())


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


def fetch_html():
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_schedule(html):
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

        starters = re.findall(
            r"先発\s*[：:]\s*([^\s|]+)",
            row_text
        )

        announced_starter = None

        if len(starters) >= 2:
            announced_starter = starters[starter_index]

        if "中止" in row_text:
            status = "CANCELLED"
        elif re.search(r"\d+\s*-\s*\d+", row_text):
            status = "FINISHED"
        else:
            status = "SCHEDULED"

        opponent_id = TEAM_IDS[opponent]

        games.append({
            "gameId": (
                f"{current_date}-{TARGET_TEAM_ID}-"
                f"{opponent_id}-{home_away}"
            ),
            "date": current_date,
            "teamId": TARGET_TEAM_ID,
            "opponentId": opponent_id,
            "homeAway": home_away,
            "status": status,
            "starter": None,
            "announcedStarter": announced_starter
        })

    return games


def load_existing():
    if not OUTPUT_FILE.exists():
        return {
            "season": 2026,
            "games": []
        }

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def merge_games(existing_data, new_games):
    existing_games = existing_data.get("games", [])

    existing_map = {}

    for game in existing_games:
        key = (
            game.get("date"),
            game.get("teamId")
        )
        existing_map[key] = game

    merged = []

    # 今回取得した8月ソフトバンク戦
    for new_game in new_games:
        key = (
            new_game["date"],
            new_game["teamId"]
        )

        old_game = existing_map.get(key)

        # 既存の先発実績があれば残す
        if old_game:
            if old_game.get("starter") is not None:
                new_game["starter"] = old_game["starter"]

            # 試合終了後は予告先発を表示しない
            if new_game["status"] == "FINISHED":
                new_game["announcedStarter"] = None

        merged.append(new_game)

    # 8月ソフトバンク戦以外の既存データは残す
    new_keys = {
        (game["date"], game["teamId"])
        for game in new_games
    }

    for old_game in existing_games:
        key = (
            old_game.get("date"),
            old_game.get("teamId")
        )

        if key not in new_keys:
            merged.append(old_game)

    merged.sort(
        key=lambda game: (
            game.get("date", ""),
            game.get("teamId", "")
        )
    )

    return {
        "season": 2026,
        "games": merged
    }


html = fetch_html()
new_games = parse_schedule(html)

existing_data = load_existing()
output_data = merge_games(existing_data, new_games)

with OUTPUT_FILE.open(
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        output_data,
        file,
        ensure_ascii=False,
        indent=2
    )

print("status: OK")
print("August SoftBank games:", len(new_games))
print("saved:", OUTPUT_FILE)

for game in new_games:
    if game["date"] in (
        "2026-08-11",
        "2026-08-13",
        "2026-08-15",
        "2026-08-18"
    ):
        print(game)
