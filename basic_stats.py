import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests

MY_TEAM_ID = "68060831b57069886d0df010"
HTTP_CACHE_DIR = Path("http_cache")

def stable_str_hash(in_val: str) -> str:
    return hex(int(hashlib.md5(in_val.encode("utf-8")).hexdigest(), 16))[2:]

def get_json(url: str) -> dict:
    HTTP_CACHE_DIR.mkdir(exist_ok=True)

    cache = {}
    cache_file_path = HTTP_CACHE_DIR / f"{stable_str_hash(url)}.json"
    try:
        with open(cache_file_path) as cache_file:
            cache = json.load(cache_file)
    except FileNotFoundError:
        pass

    # Return from cache if the cache entry is less than 5 minutes old
    now = datetime.now(timezone.utc)
    if (
            url in cache and
            "__archived_at" in cache[url] and
            cache[url]["__archived_at"] > (now - timedelta(minutes=5)).isoformat()
    ):
        return cache[url]

    data = requests.get(url).json()
    cache[url] = data
    cache[url]["__archived_at"] = now.isoformat()
    with open(cache_file_path, "w") as cache_file:
        json.dump(cache, cache_file)

    return data

def main():
    team_obj = get_json(f"https://mmolb.com/api/team/{MY_TEAM_ID}")

    # Players has been a dictionary and a list
    try:
        player_list = team_obj["Players"].values()
    except AttributeError:
        player_list = team_obj["Players"]

    for player in player_list:
        player_obj = get_json(f"https://mmolb.com/api/player/{player['PlayerID']}")

        try:
            # I'm pretty sure IDs are lexicographically ordered, so we want the
            # maximum value to get stats for the latest season
            stats_obj = player_obj["Stats"][max(player_obj["Stats"].keys())]
        except ValueError:
            print("No stats for", player["FirstName"], player["LastName"])
            continue

        singles = stats_obj.get("singles", 0)
        doubles = stats_obj.get("doubles", 0)
        triples = stats_obj.get("triples", 0)
        home_runs = stats_obj.get("home_runs", 0)
        hits = singles + doubles + triples + home_runs
        bb = stats_obj.get("walked", 0)
        hbp = stats_obj.get("hit_by_pitch", 0)
        earned_runs = stats_obj.get("earned_runs", 0)

        try:
            ab = stats_obj["at_bats"]
        except KeyError:
            ba_str = None
        else:
            ba = hits / ab
            ba_str = f"BA: {ba:.3f} ({ab} AB)"

        try:
            pa = stats_obj["plate_appearances"]
            ab = stats_obj["at_bats"]
        except KeyError:
            ops_str = None
        else:
            obp = (hits + bb + hbp) / pa
            slg = (singles + 2 * doubles + 3 * triples + 4 * home_runs) / ab
            ops = obp + slg
            pa_str = dot_format(pa)
            ops_str = f"OBP: {obp:.3f}, SLG: {slg:.3f}, OPS: {ops:.3f} ({pa_str} PA)"

        try:
            ip = stats_obj["outs"] / 3
            hits_allowed = stats_obj.get("hits_allowed", 0)
            walks = stats_obj.get("walks", 0)
        except KeyError:
            era_str = None
        else:
            era = 9 * earned_runs / ip
            whip = (hits_allowed + walks) / ip
            ip_str = dot_format(ip)
            era_str = f"ERA: {era:.2f} WHIP: {whip:.2f} ({ip_str} IP)"

        stats_str = ", ".join(s for s in [ba_str, ops_str, era_str] if s is not None)
        if stats_str:
            print(player["Position"], player["FirstName"], player["LastName"], stats_str)


def dot_format(in_val: float) -> str:
    ip_whole = int(in_val)
    ip_remainder = int((in_val - ip_whole) / 3 * 10)
    if ip_remainder == 0:
        ip_str = f"{ip_whole}"
    else:
        ip_str = f"{ip_whole}.{ip_remainder}"
    return ip_str


if __name__ == '__main__':
    main()
