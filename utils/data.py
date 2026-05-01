import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import random

IPL_TEAMS_2026 = [
    "Mumbai Indians",
    "Chennai Super Kings",
    "Royal Challengers Bengaluru",
    "Kolkata Knight Riders",
    "Delhi Capitals",
    "Punjab Kings",
    "Rajasthan Royals",
    "Sunrisers Hyderabad",
    "Gujarat Titans",
    "Lucknow Super Giants",
]

IPL_VENUES = {
    "Wankhede Stadium": {"city": "Mumbai", "lat": 18.9388, "lon": 72.8258, "avg_first_innings": 172, "chase_win_rate": 0.44},
    "MA Chidambaram Stadium": {"city": "Chennai", "lat": 13.0629, "lon": 80.2792, "avg_first_innings": 162, "chase_win_rate": 0.40},
    "M. Chinnaswamy Stadium": {"city": "Bengaluru", "lat": 12.9791, "lon": 77.5496, "avg_first_innings": 176, "chase_win_rate": 0.48},
    "Eden Gardens": {"city": "Kolkata", "lat": 22.5647, "lon": 88.3433, "avg_first_innings": 168, "chase_win_rate": 0.43},
    "Arun Jaitley Stadium": {"city": "Delhi", "lat": 28.6364, "lon": 77.2173, "avg_first_innings": 170, "chase_win_rate": 0.46},
    "Narendra Modi Stadium": {"city": "Ahmedabad", "lat": 23.0908, "lon": 72.0846, "avg_first_innings": 174, "chase_win_rate": 0.47},
    "Rajiv Gandhi Intl Cricket Stadium": {"city": "Hyderabad", "lat": 17.4042, "lon": 78.5428, "avg_first_innings": 167, "chase_win_rate": 0.45},
    "Sawai Mansingh Stadium": {"city": "Jaipur", "lat": 26.8949, "lon": 75.8009, "avg_first_innings": 165, "chase_win_rate": 0.42},
    "BRSABV Ekana Cricket Stadium": {"city": "Lucknow", "lat": 26.8467, "lon": 80.9462, "avg_first_innings": 163, "chase_win_rate": 0.41},
    "Himachal Pradesh Cricket Association Stadium": {"city": "Dharamsala", "lat": 32.2198, "lon": 76.3234, "avg_first_innings": 158, "chase_win_rate": 0.39},
}

TEAM_PLAYERS = {
    "Mumbai Indians": {
        "batters": ["Rohit Sharma", "Ishan Kishan", "Suryakumar Yadav", "Tilak Varma", "Hardik Pandya", "Tim David"],
        "bowlers": ["Jasprit Bumrah", "Suryakumar Yadav", "Piyush Chawla", "Gerald Coetzee", "Nuwan Thushara"]
    },
    "Chennai Super Kings": {
        "batters": ["Ruturaj Gaikwad", "Devon Conway", "Ajinkya Rahane", "Shivam Dube", "MS Dhoni", "Ravindra Jadeja"],
        "bowlers": ["Deepak Chahar", "Matheesha Pathirana", "Tushar Deshpande", "Ravindra Jadeja", "Moeen Ali"]
    },
    "Royal Challengers Bengaluru": {
        "batters": ["Faf du Plessis", "Virat Kohli", "Glenn Maxwell", "Dinesh Karthik", "Cameron Green", "Rajat Patidar"],
        "bowlers": ["Mohammed Siraj", "Josh Hazlewood", "Wanindu Hasaranga", "Karn Sharma", "Reece Topley"]
    },
    "Kolkata Knight Riders": {
        "batters": ["Phil Salt", "Sunil Narine", "Angkrish Raghuvanshi", "Nitish Rana", "Andre Russell", "Rinku Singh"],
        "bowlers": ["Mitchell Starc", "Varun Chakravarthy", "Sunil Narine", "Harshit Rana", "Spencer Johnson"]
    },
    "Delhi Capitals": {
        "batters": ["Jake Fraser-McGurk", "David Warner", "Abishek Porel", "Rishabh Pant", "Axar Patel", "Tristan Stubbs"],
        "bowlers": ["Anrich Nortje", "Kuldeep Yadav", "Axar Patel", "Ishant Sharma", "Rasikh Dar Salam"]
    },
    "Punjab Kings": {
        "batters": ["Shikhar Dhawan", "Jonny Bairstow", "Sam Curran", "Liam Livingstone", "Jitesh Sharma", "Rilee Rossouw"],
        "bowlers": ["Arshdeep Singh", "Nathan Ellis", "Harshal Patel", "Sam Curran", "Rahul Chahar"]
    },
    "Rajasthan Royals": {
        "batters": ["Jos Buttler", "Yashasvi Jaiswal", "Sanju Samson", "Shimron Hetmyer", "Devdutt Padikkal", "Dhruv Jurel"],
        "bowlers": ["Trent Boult", "Yuzvendra Chahal", "Sandeep Sharma", "Ravichandran Ashwin", "Nandre Burger"]
    },
    "Sunrisers Hyderabad": {
        "batters": ["Travis Head", "Abhishek Sharma", "Heinrich Klaasen", "Aiden Markram", "Abdul Samad", "Shahbaz Ahmed"],
        "bowlers": ["Pat Cummins", "Bhuvneshwar Kumar", "T Natarajan", "Jaydev Unadkat", "Shahbaz Ahmed"]
    },
    "Gujarat Titans": {
        "batters": ["Shubman Gill", "Wriddhiman Saha", "Sai Sudharsan", "David Miller", "Vijay Shankar", "Kane Williamson"],
        "bowlers": ["Mohammed Shami", "Mohit Sharma", "Rashid Khan", "Noor Ahmad", "Joshua Little"]
    },
    "Lucknow Super Giants": {
        "batters": ["KL Rahul", "Quinton de Kock", "Marcus Stoinis", "Deepak Hooda", "Nicholas Pooran", "Ayush Badoni"],
        "bowlers": ["Mark Wood", "Ravi Bishnoi", "Mohsin Khan", "Naveen-ul-Haq", "Krunal Pandya"]
    },
}

def get_todays_matches():
    random.seed(42)
    teams = IPL_TEAMS_2026.copy()
    random.shuffle(teams)
    matches = []
    venues = list(IPL_VENUES.keys())
    match_times = ["14:00 IST", "18:00 IST", "20:00 IST"]
    for i in range(0, min(4, len(teams)), 2):
        t1 = teams[i]
        t2 = teams[i+1]
        venue = random.choice(venues)
        venue_info = IPL_VENUES[venue]
        p1 = round(random.uniform(0.40, 0.65), 3)
        p2 = round(1 - p1, 3)
        dk_line1 = round(p1 * random.uniform(0.88, 0.97), 3)
        dk_line2 = round(1 - dk_line1, 3)
        edge1 = round(p1 - dk_line1, 3)
        edge2 = round(p2 - dk_line2, 3)
        weather = get_venue_weather(venue_info["lat"], venue_info["lon"])
        matches.append({
            "match_id": f"IPL2026_M{50+i}",
            "team1": t1,
            "team2": t2,
            "venue": venue,
            "city": venue_info["city"],
            "time": match_times[i // 2] if i // 2 < len(match_times) else "20:00 IST",
            "team1_win_prob": p1,
            "team2_win_prob": p2,
            "dk_implied_prob_team1": dk_line1,
            "dk_implied_prob_team2": dk_line2,
            "edge_team1": edge1,
            "edge_team2": edge2,
            "venue_avg_first_innings": venue_info["avg_first_innings"],
            "venue_chase_win_rate": venue_info["chase_win_rate"],
            "predicted_total": random.randint(330, 380),
            "dk_total_line": random.choice([335, 340, 345, 350, 355, 360, 365]),
            "toss_winner": None,
            "toss_decision": None,
            "temperature": weather.get("temperature", 28),
            "humidity": weather.get("humidity", 60),
            "dew_flag": weather.get("humidity", 60) > 75 and "20:00" in match_times[i // 2 if i // 2 < len(match_times) else -1],
        })
    return matches

def get_venue_weather(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&hourly=relative_humidity_2m,temperature_2m"
            f"&forecast_days=1"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            temp = data.get("current_weather", {}).get("temperature", 28)
            humidity_list = data.get("hourly", {}).get("relative_humidity_2m", [60])
            humidity = humidity_list[0] if humidity_list else 60
            return {"temperature": temp, "humidity": humidity}
    except Exception:
        pass
    return {"temperature": 28, "humidity": 60}

def get_team_form(team_name):
    random.seed(hash(team_name) % 1000)
    results = []
    for i in range(10):
        opp = random.choice([t for t in IPL_TEAMS_2026 if t != team_name])
        won = random.random() > 0.45
        score = random.randint(145, 210)
        opp_score = random.randint(145, 210) if not won else random.randint(120, score - 5)
        if won:
            opp_score = random.randint(120, score - 5)
        else:
            opp_score = random.randint(score + 5, score + 40)
        powerplay = random.randint(42, 65)
        death = round(random.uniform(8.5, 12.5), 1)
        results.append({
            "match": i + 1,
            "opponent": opp,
            "result": "W" if won else "L",
            "score": score,
            "opp_score": opp_score,
            "powerplay_runs": powerplay,
            "death_economy": death,
            "date": (datetime.now() - timedelta(days=(10-i)*4)).strftime("%b %d"),
        })
    return results

def get_ipl_schedule():
    random.seed(2026)
    schedule = []
    teams = IPL_TEAMS_2026.copy()
    venues = list(IPL_VENUES.keys())
    match_num = 1
    base_date = datetime(2026, 3, 22)
    for week in range(7):
        shuffled = teams.copy()
        random.shuffle(shuffled)
        for i in range(0, len(shuffled), 2):
            t1 = shuffled[i]
            t2 = shuffled[i+1]
            match_date = base_date + timedelta(days=week*7 + i//2*2)
            venue = random.choice(venues)
            p1 = round(random.uniform(0.38, 0.62), 2)
            played = match_date < datetime.now()
            if played:
                winner = t1 if random.random() < p1 else t2
            else:
                winner = None
            schedule.append({
                "match": match_num,
                "date": match_date.strftime("%b %d"),
                "team1": t1,
                "team2": t2,
                "venue": venue,
                "team1_win_prob": p1,
                "team2_win_prob": round(1 - p1, 2),
                "played": played,
                "winner": winner,
            })
            match_num += 1
    return schedule

def get_points_table():
    random.seed(99)
    table = []
    for team in IPL_TEAMS_2026:
        played = random.randint(8, 12)
        won = random.randint(3, played - 2)
        lost = played - won
        nrr = round(random.uniform(-0.8, 1.2), 3)
        table.append({
            "Team": team,
            "P": played,
            "W": won,
            "L": lost,
            "NRR": nrr,
            "Pts": won * 2,
            "Playoff Prob": round(min(0.98, max(0.02, 0.5 + (won/played - 0.5) * 2 + nrr * 0.1)), 2),
        })
    table.sort(key=lambda x: (-x["Pts"], -x["NRR"]))
    for i, row in enumerate(table):
        row["Pos"] = i + 1
    return table

def get_player_props(match):
    random.seed(hash(match["match_id"]) % 9999)
    props = []
    for team, role in [(match["team1"], "BAT"), (match["team2"], "BAT")]:
        players = TEAM_PLAYERS.get(team, {}).get("batters", [])
        for p in players[:4]:
            proj = round(random.uniform(12, 55), 1)
            dk_line = round(random.choice([15.5, 17.5, 19.5, 22.5, 24.5, 27.5, 29.5, 32.5, 34.5, 37.5]))
            edge = round(proj - dk_line, 1)
            props.append({
                "player": p,
                "team": team,
                "role": "Batter",
                "market": "Runs Scored",
                "projection": proj,
                "dk_line": dk_line,
                "edge": edge,
                "confidence": "High" if abs(edge) > 8 else ("Medium" if abs(edge) > 4 else "Low"),
                "recommendation": "OVER" if edge > 0 else "UNDER",
            })
    for team in [match["team1"], match["team2"]]:
        bowlers = TEAM_PLAYERS.get(team, {}).get("bowlers", [])
        for b in bowlers[:3]:
            proj = round(random.uniform(0.5, 3.2), 1)
            dk_line = random.choice([0.5, 1.5, 2.5])
            edge = round(proj - dk_line, 1)
            props.append({
                "player": b,
                "team": team,
                "role": "Bowler",
                "market": "Wickets Taken",
                "projection": proj,
                "dk_line": dk_line,
                "edge": edge,
                "confidence": "High" if abs(edge) > 0.8 else ("Medium" if abs(edge) > 0.4 else "Low"),
                "recommendation": "OVER" if edge > 0 else "UNDER",
            })
    return props

def get_batter_profile(player_name):
    random.seed(hash(player_name) % 7777)
    career_avg = round(random.uniform(22, 52), 1)
    sr = round(random.uniform(115, 165), 1)
    recent_scores = [random.randint(0, 80) for _ in range(10)]
    return {
        "name": player_name,
        "career_avg": career_avg,
        "career_sr": sr,
        "recent_scores": recent_scores,
        "recent_avg": round(sum(recent_scores) / 10, 1),
        "recent_sr": round(sr * random.uniform(0.9, 1.1), 1),
        "vs_pace_avg": round(career_avg * random.uniform(0.85, 1.1), 1),
        "vs_spin_avg": round(career_avg * random.uniform(0.9, 1.15), 1),
        "powerplay_avg": round(career_avg * random.uniform(0.7, 1.0), 1),
        "boundaries_per_innings": round(random.uniform(2.5, 7.5), 1),
    }

def get_bowler_profile(player_name):
    random.seed(hash(player_name) % 5555)
    economy = round(random.uniform(6.8, 9.5), 2)
    wickets_pm = round(random.uniform(0.8, 2.5), 2)
    return {
        "name": player_name,
        "career_economy": economy,
        "wickets_per_match": wickets_pm,
        "recent_economy": round(economy * random.uniform(0.9, 1.15), 2),
        "death_economy": round(economy * random.uniform(1.05, 1.35), 2),
        "powerplay_economy": round(economy * random.uniform(0.8, 1.0), 2),
        "vs_lhb_economy": round(economy * random.uniform(0.92, 1.08), 2),
        "vs_rhb_economy": round(economy * random.uniform(0.93, 1.07), 2),
        "wickets_last5": [random.randint(0, 4) for _ in range(5)],
    }

def get_model_performance():
    seasons = ["IPL 2024", "IPL 2025"]
    metrics = {}
    for season in seasons:
        random.seed(hash(season))
        metrics[season] = {
            "match_winner_accuracy": round(random.uniform(0.60, 0.72), 3),
            "match_winner_roi": round(random.uniform(-2, 18), 1),
            "totals_mae": round(random.uniform(8, 16), 1),
            "totals_roi": round(random.uniform(-5, 12), 1),
            "props_batter_mae": round(random.uniform(6, 12), 1),
            "props_bowler_mae": round(random.uniform(0.4, 0.9), 2),
            "props_roi": round(random.uniform(-8, 15), 1),
            "total_bets": random.randint(120, 280),
            "winning_bets": random.randint(70, 180),
            "calibration_data": [(round(i * 0.1, 1), round(i * 0.1 + random.uniform(-0.05, 0.05), 3)) for i in range(1, 10)],
        }
    return metrics

def get_value_bets(matches):
    bets = []
    for m in matches:
        if m["edge_team1"] > 0.05:
            dk_odds = round(-100 / m["dk_implied_prob_team1"])
            kelly = round(m["edge_team1"] / (1 / m["dk_implied_prob_team1"] - 1) * 0.25, 3)
            bets.append({
                "match": f"{m['team1']} vs {m['team2']}",
                "bet": f"{m['team1']} ML",
                "type": "Match Winner",
                "model_prob": m["team1_win_prob"],
                "implied_prob": m["dk_implied_prob_team1"],
                "edge": m["edge_team1"],
                "dk_odds": f"+{dk_odds}" if dk_odds > 0 else str(dk_odds),
                "kelly_stake": f"{kelly*100:.1f}%",
                "tier": "Elite Pick" if m["edge_team1"] > 0.10 else "Strong",
            })
        if m["edge_team2"] > 0.05:
            dk_odds = round(-100 / m["dk_implied_prob_team2"])
            kelly = round(m["edge_team2"] / (1 / m["dk_implied_prob_team2"] - 1) * 0.25, 3)
            bets.append({
                "match": f"{m['team1']} vs {m['team2']}",
                "bet": f"{m['team2']} ML",
                "type": "Match Winner",
                "model_prob": m["team2_win_prob"],
                "implied_prob": m["dk_implied_prob_team2"],
                "edge": m["edge_team2"],
                "dk_odds": f"+{dk_odds}" if dk_odds > 0 else str(dk_odds),
                "kelly_stake": f"{kelly*100:.1f}%",
                "tier": "Elite Pick" if m["edge_team2"] > 0.10 else "Strong",
            })
        total_edge = (m["predicted_total"] - m["dk_total_line"]) / m["dk_total_line"]
        if abs(total_edge) > 0.03:
            bets.append({
                "match": f"{m['team1']} vs {m['team2']}",
                "bet": f"Total Runs {'OVER' if total_edge > 0 else 'UNDER'} {m['dk_total_line']}",
                "type": "Total Runs",
                "model_prob": round(0.5 + abs(total_edge) * 2, 2),
                "implied_prob": 0.5,
                "edge": round(abs(total_edge) * 0.5, 3),
                "dk_odds": "-110",
                "kelly_stake": f"{round(abs(total_edge)*25, 1)}%",
                "tier": "Elite Pick" if abs(total_edge) > 0.06 else "Strong",
            })
    bets.sort(key=lambda x: -x["edge"])
    return bets
