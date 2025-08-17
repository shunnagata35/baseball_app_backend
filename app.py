from flask import Flask, request, jsonify
from flask_cors import CORS
import statsapi
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)

@app.route('/calculate', methods=['POST'])
def calculate():
    formula = request.json['formula']

    # Fetch raw 2025 hitting stats
    raw = statsapi.get('stats', {
        'stats': 'season',
        'group': 'hitting',
        'season': 2025,
        'sportIds': 1
    })

    # Get games played per team
    standings = statsapi.standings_data(division="all", season=2025)
    team_games = {
        team["team_id"]: team["w"] + team["l"]
        for div in standings.values() for team in div["teams"]
    }

    qualified = []
    for player in raw['stats'][0]['splits']:
        stat = player['stat']
        team_id = player['team']['id']
        pa = int(stat.get('plateAppearances', 0))
        team_g = team_games.get(team_id, 162)

        if team_g == 0 or pa / team_g < 3.1:
            continue

        qualified.append({
            'Name': player['player']['fullName'],
            'Team': player['team']['name'],
           "PA": int(stat.get("plateAppearances", 0)),
            "HR": int(stat.get("homeRuns", 0)),
            "SO": int(stat.get("strikeOuts", 0)),
            "BB": int(stat.get("baseOnBalls", 0)),
            "RBI": int(stat.get("rbi", 0)),
            "R": int(stat.get("runs", 0)),
            "H": int(stat.get("hits", 0)),
            "Doubles": int(stat.get("doubles", 0)),
            "Triples": int(stat.get("triples", 0)),
            "SB": int(stat.get("stolenBases", 0)),
            "CS": int(stat.get("caughtStealing", 0)),
            "GDP": int(stat.get("groundIntoDoublePlay", 0)),
            "SF": int(stat.get("sacFlies", 0)),
            "SH": int(stat.get("sacBunts", 0)),
            "HBP": int(stat.get("hitByPitch", 0)),
            "OPS": _safe_float(stat.get("ops", "0")),
            "AVG": _safe_float(stat.get("avg", "0")),
        })

    df = pd.DataFrame(qualified)

    try:
        df['CustomMetric'] = df.eval(formula)
        top_players = df.sort_values('CustomMetric', ascending=False).to_dict(orient='records')
        return jsonify(top_players)
    except Exception as e:
        return jsonify({'error': f"Invalid formula: {e}"}), 400
    
def _safe_float(x):
    try:
        if x in (None, "", "--"):
            return 0.0
        return float(x)
    except:
        return 0.0

def _collect_player_rows(season=2025):
    """Return a DataFrame of all hitters with numeric columns you can use in formulas."""
    raw = statsapi.get('stats', {
        'stats': 'season',
        'group': 'hitting',
        'season': season,
        'sportIds': 1
    })
    splits = raw['stats'][0]['splits']
    rows = []
    for p in splits:
        stat = p['stat']
        team = p.get('team', {})
        player_info = p.get('player', {})

        rows.append({
            "Name": player_info.get("fullName", ""),
            "Team": team.get("name", ""),
            # identifiers (uppercase, no spaces) so they're easy to use in formulas:
            "PA": int(stat.get("plateAppearances", 0)),
            "HR": int(stat.get("homeRuns", 0)),
            "SO": int(stat.get("strikeOuts", 0)),
            "BB": int(stat.get("baseOnBalls", 0)),
            "RBI": int(stat.get("rbi", 0)),
            "R": int(stat.get("runs", 0)),
            "H": int(stat.get("hits", 0)),
            "Doubles": int(stat.get("doubles", 0)),
            "Triples": int(stat.get("triples", 0)),
            "SB": int(stat.get("stolenBases", 0)),
            "CS": int(stat.get("caughtStealing", 0)),
            "GDP": int(stat.get("groundIntoDoublePlay", 0)),
            "SF": int(stat.get("sacFlies", 0)),
            "SH": int(stat.get("sacBunts", 0)),
            "HBP": int(stat.get("hitByPitch", 0)),
            "OPS": _safe_float(stat.get("ops", "0")),
            "AVG": _safe_float(stat.get("avg", "0")),
            
        })

    df = pd.DataFrame(rows)
    return df

def _team_games_map(season=2025):
    standings = statsapi.standings_data(division="all", season=season)
    return {t["team_id"]: t["w"] + t["l"] for div in standings.values() for t in div["teams"]}

def _attach_team_ids(df_players, season=2025):
    """Attach team_id to each row for qualification calc (PA / teamG)."""
    # statsapi splits already have team id in raw; if not, we infer by refetching
    # We’ll re-pull the same raw and align on (Name, Team) to get team_id
    raw = statsapi.get('stats', {
        'stats': 'season',
        'group': 'hitting',
        'season': season,
        'sportIds': 1
    })
    splits = raw['stats'][0]['splits']
    # build map (Name, Team) -> team_id
    m = {}
    for p in splits:
        nm = p.get('player', {}).get('fullName', '')
        tm = p.get('team', {}).get('name', '')
        tid = p.get('team', {}).get('id', None)
        if nm and tm and tid is not None:
            m[(nm, tm)] = tid
    df_players["team_id"] = df_players.apply(lambda r: m.get((r["Name"], r["Team"])), axis=1)
    return df_players

def _eval_two_formulas(df, x_formula, y_formula):
    # Let pandas parse with df.eval (column names must be valid identifiers; they are)
    # Raise helpful errors if a variable doesn’t exist
    try:
        x_vals = df.eval(x_formula)
    except Exception as e:
        return None, None, f"X formula error: {e}"

    try:
        y_vals = df.eval(y_formula)
    except Exception as e:
        return None, None, f"Y formula error: {e}"

    return x_vals, y_vals, None

def _response_from_xy(df, x_vals, y_vals, label_col):
    out = []
    for _, row in df.iterrows():
        out.append({
            "x": float(x_vals.loc[row.name]),
            "y": float(y_vals.loc[row.name]),
            "label": row[label_col]
        })
    # Pearson r
    if len(out) >= 2:
        r = float(np.corrcoef([pt["x"] for pt in out], [pt["y"] for pt in out])[0, 1])
    else:
        r = None
    return {
        "points": out,
        "r": r,
        "n": len(out)
    }

@app.route('/correlation/players', methods=['POST'])
def correlation_players():
    """
    Body: { "x_formula": "HR-SO", "y_formula": "R" }
    Returns: { points: [{x, y, label}], r: number, n: number }
    """
    data = request.get_json(force=True) or {}
    x_formula = data.get("x_formula", "").strip()
    y_formula = data.get("y_formula", "").strip()
    if not x_formula or not y_formula:
        return jsonify({"error": "x_formula and y_formula are required"}), 400

    season = int(data.get("season", 2025))

    # Players base DF
    df = _collect_player_rows(season)
    df = _attach_team_ids(df, season)

    # Get games per team and filter *qualified hitters*
    team_games = _team_games_map(season)
    df["team_g"] = df["team_id"].map(team_games).fillna(0).astype(int)
    df = df[(df["team_g"] > 0) & (df["PA"] / df["team_g"] >= 3.1)]

    x_vals, y_vals, err = _eval_two_formulas(df, x_formula, y_formula)
    if err:
        return jsonify({"error": err, "available_columns": list(df.columns)}), 400

    payload = _response_from_xy(df, x_vals, y_vals, label_col="Name")
    payload.update({
        "mode": "players",
        "x_formula": x_formula,
        "y_formula": y_formula
    })
    return jsonify(payload)

@app.route('/correlation/teams', methods=['POST'])
def correlation_teams():
    """
    Body: { "x_formula": "HR-SO", "y_formula": "R" }
    Team points are team totals (sum of player stats).
    """
    data = request.get_json(force=True) or {}
    x_formula = data.get("x_formula", "").strip()
    y_formula = data.get("y_formula", "").strip()
    if not x_formula or not y_formula:
        return jsonify({"error": "x_formula and y_formula are required"}), 400

    season = int(data.get("season", 2025))

    # Aggregate team totals from player rows
    df_players = _collect_player_rows(season)
    df_team = (
        df_players.groupby("Team", as_index=False)[
            ["PA","HR","SO","BB","RBI","R","H","Doubles","Triples","SB","CS","GDP","SF","SH"]
        ].sum()
    )
    # For rate stats like OPS/AVG, you could compute weighted versions; here we use team-level means as a fallback
    df_rate = df_players.groupby("Team", as_index=False)[["OPS", "AVG"]].mean()
    df = pd.merge(df_team, df_rate, on="Team", how="left")

    x_vals, y_vals, err = _eval_two_formulas(df, x_formula, y_formula)
    if err:
        return jsonify({"error": err, "available_columns": list(df.columns)}), 400

    payload = _response_from_xy(df, x_vals, y_vals, label_col="Team")
    payload.update({
        "mode": "teams",
        "x_formula": x_formula,
        "y_formula": y_formula
    })
    return jsonify(payload)

if __name__ == '__main__':
    app.run(debug=True)
