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
print()
print("=== STARTER TEST 2026-08-11 ===")

TEST_URL = "https://npb.jp/scores/2026/0811/h-m-15/box.html"

request = urllib.request.Request(
    TEST_URL,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    test_html = response.read().decode(
        "utf-8",
        errors="replace"
    )

# HTMLタグを簡易的に除去
test_text = re.sub(r"<[^>]+>", " ", test_html)
test_text = re.sub(r"\s+", " ", test_text)

print("page bytes:", len(test_html))
print("contains モイネロ:", "モイネロ" in test_text)

# モイネロ周辺を表示して、成績表の実際の並びを確認
position = test_text.find("モイネロ")

if position != -1:
    start = max(0, position - 150)
    end = min(len(test_text), position + 500)

    print("=== モイネロ周辺 ===")
    print(test_text[start:end])
else:
    print("モイネロ NOT FOUND")
print()
print("=== STARTER PARSE TEST ===")

# HTMLエンティティを少し整える
clean_text = test_text.replace("&nbsp;", " ")
clean_text = re.sub(r"\s+", " ", clean_text)

# 「モイネロ」の後ろに続く投手成績の数値を取得
match = re.search(
    r"([○●△]?)\s*モイネロ\s+"
    r"(\d+)\s+"      # 球数
    r"(\d+)\s+"      # 打者
    r"([0-9.]+)\s+"  # 投球回
    r"(\d+)\s+"      # 被安打
    r"(\d+)\s+"      # 被本塁打
    r"(\d+)\s+"      # 四球
    r"(\d+)\s+"      # 死球
    r"(\d+)\s+"      # 奪三振
    r"(\d+)\s+"      # 暴投
    r"(\d+)\s+"      # ボーク
    r"(\d+)\s+"      # 失点
    r"(\d+)",         # 自責点
    clean_text
)

if match:
    decision_mark = match.group(1)

    if decision_mark == "○":
        decision = "W"
    elif decision_mark == "●":
        decision = "L"
    else:
        decision = "ND"

    starter_data = {
        "name": "モイネロ",
        "pitches": int(match.group(2)),
        "innings": match.group(4),
        "runs": int(match.group(12)),
        "earnedRuns": int(match.group(13)),
        "decision": decision
    }

    print(starter_data)
else:
    print("STARTER PARSE FAILED")
import html as html_module

print()
print("=== GENERIC STARTER TEST ===")


def get_softbank_starter(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        page_html = response.read().decode(
            "utf-8",
            errors="replace"
        )

    text = re.sub(r"<[^>]+>", " ", page_html)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text)

    # ソフトバンクの成績欄を探す
    team_pos = text.rfind("福岡ソフトバンクホークス")

    if team_pos == -1:
        return None

    team_text = text[team_pos:]

    # ソフトバンクの投手成績表を探す
    header_pos = team_text.find(
        "投手 投球数 打者 投球回"
    )

    if header_pos == -1:
        return None

    pitcher_text = team_text[
        header_pos + len("投手 投球数 打者 投球回"):
    ]

    # 投手成績表の最初の投手＝先発投手
    match = re.search(
        r"([○●]?)\s*"
        r"([^\s]+)\s+"
        r"(\d+)\s+"                 # 球数
        r"(\d+)\s+"                 # 打者
        r"(\d+(?:\s*\.\s*[12])?)\s+"  # 投球回
        r"(\d+)\s+"                 # 安打
        r"(\d+)\s+"                 # 本塁打
        r"(\d+)\s+"                 # 四球
        r"(\d+)\s+"                 # 死球
        r"(\d+)\s+"                 # 三振
        r"(\d+)\s+"                 # 暴投
        r"(\d+)\s+"                 # ボーク
        r"(\d+)\s+"                 # 失点
        r"(\d+)",                    # 自責点
        pitcher_text
    )

    if not match:
        return None

    mark = match.group(1)

    if mark == "○":
        decision = "W"
    elif mark == "●":
        decision = "L"
    else:
        decision = "ND"

    innings = re.sub(
        r"\s+",
        "",
        match.group(5)
    )

    return {
        "name": match.group(2),
        "pitches": int(match.group(3)),
        "innings": innings,
        "runs": int(match.group(13)),
        "earnedRuns": int(match.group(14)),
        "decision": decision
    }


test_games = [
    (
        "8/11",
        "https://npb.jp/scores/2026/0811/h-m-15/box.html"
    ),
    (
        "8/13",
        "https://npb.jp/scores/2026/0813/h-m-17/box.html"
    )
]

for label, url in test_games:
    result = get_softbank_starter(url)
    print(label, result)
from urllib.parse import urljoin

print()
print("=== GAME URL TEST ===")

SCHEDULE_URL = "https://npb.jp/games/2026/schedule_08_detail.html"

request = urllib.request.Request(
    SCHEDULE_URL,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    schedule_html = response.read().decode(
        "utf-8",
        errors="replace"
    )

# 試合詳細ページへのリンク候補を全部取得
links = re.findall(
    r'href=["\']([^"\']+)["\']',
    schedule_html
)

score_links = []

for link in links:
    full_url = urljoin(SCHEDULE_URL, link)

    if "/scores/2026/" in full_url:
        score_links.append(full_url)

# 重複除去
score_links = list(dict.fromkeys(score_links))

print("score links found:", len(score_links))

for target in ("0811", "0813"):
    print()
    print("DATE:", target)

    found = False

    for url in score_links:
        if f"/{target}/" in url:
            print(url)
            found = True

    if not found:
        print("NOT FOUND")
