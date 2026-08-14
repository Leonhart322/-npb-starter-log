import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUTPUT_FILE = Path("data/games_2026.json")

TARGET_TEAM = "ソフトバンク"
TARGET_TEAM_ID = "H"

MONTHS = range(3, 11)

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


def fetch_html(month):
    url = (
        f"https://npb.jp/games/2026/"
        f"schedule_{month:02d}_detail.html"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        return response.read().decode(
            "utf-8",
            errors="replace"
        )


def parse_month(month):
    html = fetch_html(month)

    parser = ScheduleParser()
    parser.feed(html)

    current_date = None
    games = []
    seen_dates = set()

    for row in parser.rows:
        row_text = " | ".join(row)

        date_match = re.search(
            rf"{month}/(\d{{1,2}})",
            row_text
        )

        if date_match:
            day = int(date_match.group(1))
            current_date = (
                f"2026-{month:02d}-{day:02d}"
            )

        if current_date is None:
            continue

        if TARGET_TEAM not in row_text:
            continue

        team_positions = []

        for team in TEAM_NAMES:
            position = row_text.find(team)

            if position != -1:
                team_positions.append(
                    (position, team)
                )

        team_positions.sort()

        # NPB12球団同士の試合だけを採用
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

        # 同じ球団が同日に複数登録されるのを防ぐ
        if current_date in seen_dates:
            continue

        seen_dates.add(current_date)

        starters = re.findall(
            r"先発\s*[：:]\s*([^\s|]+)",
            row_text
        )

        announced_starter = None

        if len(starters) >= 2:
            announced_starter = (
                starters[starter_index]
            )

        if "中止" in row_text or "ノーゲーム" in row_text:
            status = "CANCELLED"

        elif re.search(
            r"\d+\s*-\s*\d+",
            row_text
        ):
            status = "FINISHED"

        else:
            status = "SCHEDULED"

        opponent_id = TEAM_IDS[opponent]

        games.append({
            "gameId": (
                f"{current_date}-"
                f"{TARGET_TEAM_ID}-"
                f"{opponent_id}-"
                f"{home_away}"
            ),
            "date": current_date,
            "teamId": TARGET_TEAM_ID,
            "opponentId": opponent_id,
            "homeAway": home_away,
            "status": status,
            "starter": None,
            "announcedStarter": (
                announced_starter
            )
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


def merge_games(
    existing_data,
    new_games
):
    existing_games = (
        existing_data.get("games", [])
    )

    existing_map = {}

    for game in existing_games:
        key = (
            game.get("date"),
            game.get("teamId")
        )
        existing_map[key] = game

    merged = []

    for new_game in new_games:
        key = (
            new_game["date"],
            new_game["teamId"]
        )

        old_game = existing_map.get(key)

        if old_game:
            # 実際の先発登板データは残す
            if old_game.get(
                "starter"
            ) is not None:
                new_game["starter"] = (
                    old_game["starter"]
                )

            # 終了済みなら予告先発は消す
            if (
                new_game["status"]
                == "FINISHED"
            ):
                new_game[
                    "announcedStarter"
                ] = None

        merged.append(new_game)

    new_keys = {
        (
            game["date"],
            game["teamId"]
        )
        for game in new_games
    }

    # 今回の対象外データは残す
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


all_games = []

for month in MONTHS:
    month_games = parse_month(month)

    print(
        f"{month}月:",
        len(month_games),
        "games"
    )

    all_games.extend(month_games)


existing_data = load_existing()

output_data = merge_games(
    existing_data,
    all_games
)

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


print()
print("status: OK")
print(
    "SoftBank regular-season games:",
    len(all_games)
)
print("saved:", OUTPUT_FILE)

for game in all_games:
    if game["date"] in (
        "2026-03-27",
        "2026-08-15",
        "2026-10-01",
        "2026-10-02",
    ):
        print(game)
        print()

print("=== CHECK ===")

cancelled_games = [
    game for game in all_games
    if game["status"] == "CANCELLED"
]

finished_games = [
    game for game in all_games
    if game["status"] == "FINISHED"
]

scheduled_games = [
    game for game in all_games
    if game["status"] == "SCHEDULED"
]

print("total records:", len(all_games))
print("cancelled:", len(cancelled_games))
print("finished:", len(finished_games))
print("scheduled:", len(scheduled_games))

print()
print("=== CANCELLED GAMES ===")

for game in cancelled_games:
    print(
        game["date"],
        game["homeAway"],
        "vs",
        game["opponentId"]
    )


class BoxScoreParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.in_heading = False
        self.heading_text = []

        self.in_softbank = False

        self.current_row = None
        self.current_cell = None

        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h3", "h4"):
            self.in_heading = True
            self.heading_text = []

        elif tag == "tr":
            self.current_row = []

        elif (
            tag in ("td", "th")
            and self.current_row is not None
        ):
            self.current_cell = []

    def handle_endtag(self, tag):
        if (
            tag in ("h3", "h4")
            and self.in_heading
        ):
            heading = "".join(
                self.heading_text
            )

            heading = re.sub(
                r"\s+",
                " ",
                heading
            ).strip()

            # 一時的な検証用
            # NPBのh3/h4をHTMLParserが
            # 実際にどう読んでいるか確認する
            print(
                "DEBUG HEADING:",
                repr(heading)
            )

            self.in_softbank = (
                "福岡ソフトバンクホークス"
                in heading
            )

            self.in_heading = False
            self.heading_text = []

        elif (
            tag in ("td", "th")
            and self.current_cell is not None
        ):
            text = "".join(
                self.current_cell
            )

            text = re.sub(
                r"\s+",
                " ",
                text
            ).strip()

            # 空セルも残す
            self.current_row.append(text)

            self.current_cell = None

        elif (
            tag == "tr"
            and self.current_row is not None
        ):
            if (
                self.in_softbank
                and self.current_row
            ):
                self.rows.append(
                    self.current_row
                )

            self.current_row = None

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text.append(data)

        if self.current_cell is not None:
            self.current_cell.append(data)


def get_softbank_starter(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        page_html = response.read().decode(
            "utf-8",
            errors="replace"
        )

    parser = BoxScoreParser()
    parser.feed(page_html)

    pitcher_header_index = None

    for i, row in enumerate(
        parser.rows
    ):
        row_text = " ".join(row)

        if (
            "投手" in row_text
            and "投球数" in row_text
            and "打者" in row_text
            and "投球回" in row_text
            and "失点" in row_text
            and "自責点" in row_text
        ):
            pitcher_header_index = i
            break

    if pitcher_header_index is None:
        return None

    # 投手表ヘッダーの次から探す
    for row in parser.rows[
        pitcher_header_index + 1:
    ]:
        # 空欄を含めても通常14列
        if len(row) < 14:
            continue

        # 先頭列：○ / ● / 空欄など
        mark = row[0]

        # 2列目が投手名
        name = row[1]

        if not name:
            continue

        if name == "チーム計":
            return None

        try:
            pitches = int(
                row[2]
            )

            innings = re.sub(
                r"\s+",
                "",
                row[4]
            )

            runs = int(
                row[12]
            )

            earned_runs = int(
                row[13]
            )

        except (
            ValueError,
            IndexError
        ):
            continue

        if mark == "○":
            decision = "W"

        elif mark == "●":
            decision = "L"

        else:
            decision = "ND"

        return {
            "name": name,
            "pitches": pitches,
            "innings": innings,
            "runs": runs,
            "earnedRuns": earned_runs,
            "decision": decision
        }

    return None


print()
print("=== STARTER RECHECK ===")

test_urls = {
    "2026-04-18":
        "https://npb.jp/scores/2026/0418/h-b-02/box.html",

    "2026-04-19":
        "https://npb.jp/scores/2026/0419/h-b-03/box.html",
}

for date, url in test_urls.items():
    result = get_softbank_starter(
        url
    )

    print(
        date,
        result
    )
