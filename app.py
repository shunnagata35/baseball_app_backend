from flask import Flask, request, jsonify
from flask_cors import CORS
import statsapi
import pandas as pd
from scipy.stats import pearsonr

app = Flask(__name__)
CORS(app)

def get_statsapi_summary(player_name):
    try:
        player = statsapi.lookup_player(player_name)[0]
        player_id = player['id']
        data = statsapi.get('people', {'personIds': player_id, 'hydrate': 'stats(group=[hitting],type=season)'})

        stats_list = data['people'][0].get('stats', [])
        if not stats_list or 'splits' not in stats_list[0]:
            print(f"No valid stat splits for {player_name}")
            return None

        stats = stats_list[0]['splits'][0]['stat']
        print(f"Raw stats for {player_name}:", stats)

        def safe_float(val):
            try:
                return float(val) if val not in ['--', None, ''] else 0.0
            except:
                return 0.0

        return {
            'Name': player['fullName'],
            'HR': safe_float(stats.get('homeRuns')),
            'SO': safe_float(stats.get('strikeOuts')),
            'BB': safe_float(stats.get('baseOnBalls')),
            'SB': safe_float(stats.get('stolenBases')),
            'PA': safe_float(stats.get('plateAppearances')),
            'AVG': safe_float(stats.get('avg')),
            'OPS': safe_float(stats.get('ops')),
            'wOBA': safe_float(stats.get('ops')) * 0.9
        }

    except Exception as e:
        print(f"Error fetching data for {player_name}: {e}")
        return None



@app.route('/calculate', methods=['POST'])
def calculate():
    formula = request.json['formula']
    
    # Instead of using a fixed list, reuse the same player list as in /leaderboard
    raw = statsapi.get('stats', {
        'stats': 'season',
        'group': 'hitting',
        'season': 2025,
        'sportIds': 1
    })

    standings = statsapi.standings_data(division="all", season=2025)
    team_games = {}
    for division in standings.values():
        for team in division["teams"]:
            team_id = team["team_id"]
            team_games[team_id] = team["w"] + team["l"]

    players = raw['stats'][0]['splits']
    qualified = []

    for player in players:
        stat = player['stat']
        team_id = player['team']['id']
        pa = int(stat.get('plateAppearances', 0))
        team_g = team_games.get(team_id, 162)
        
        if team_g == 0 or pa / team_g < 3.1:
            continue

        qualified.append({
            'Name': player['player']['fullName'],
            'Team': player['team']['name'],
            'HR': int(stat.get('homeRuns', 0)),
            'OPS': float(stat.get('ops', 0)),
            'AVG': float(stat.get('avg', 0)),
            'RBI': int(stat.get('rbi', 0)),
            'BB': int(stat.get('baseOnBalls', 0)),
            'SO': int(stat.get('strikeOuts', 0)),
            'PA': pa,
            'wOBA': float(stat.get('ops', 0)) * 0.9
        })

    df = pd.DataFrame(qualified)

    try:
        df['CustomMetric'] = df.eval(formula)
        correlations = {}
        for col in ['AVG', 'OPS', 'wOBA']:
            if df[col].nunique() > 1:
                correlations[col] = pearsonr(df['CustomMetric'], df[col])[0]

        # NO .head(50) here — return all qualified players
        top_players = df.sort_values('CustomMetric', ascending=False).to_dict(orient='records')
        return jsonify({'correlations': correlations, 'top_players': top_players})
    except Exception as e:
        print("Formula error:", formula)
        print("Error message:", e)
        return jsonify({'error': f"Invalid formula: {e}"}), 400



if __name__ == '__main__':
    app.run(debug=True)
