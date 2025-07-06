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
        stats = statsapi.player_stat_data(player['id'], group='hitting', type='season')
        s_list = stats.get('stats', [])

        if not s_list or not isinstance(s_list, list):
            return None

        s = s_list[0]

        def safe_float(val):
            try:
                return float(val)
            except:
                return 0.0

        return {
            'Name': player['fullName'],
            'HR': safe_float(s.get('homeRuns')),
            'SO': safe_float(s.get('strikeOuts')),
            'BB': safe_float(s.get('baseOnBalls')),
            'SB': safe_float(s.get('stolenBases')),
            'PA': safe_float(s.get('plateAppearances')),
            'AVG': safe_float(s.get('avg')),
            'OPS': safe_float(s.get('ops')),
            'wOBA': safe_float(s.get('ops')) * 0.9  # Estimated
        }

    except Exception as e:
        print(f"Error fetching data for {player_name}: {e}")
        return None


@app.route('/calculate', methods=['POST'])
def calculate():
    formula = request.json['formula']
    players = request.json.get('players', ['Shohei Ohtani', 'Aaron Judge', 'Mookie Betts'])

    all_data = []
    for name in players:
        stats = get_statsapi_summary(name)
        if stats:
            all_data.append(stats)

    df = pd.DataFrame(all_data)
    print("Data columns:", df.columns)

    try:
        df['CustomMetric'] = df.eval(formula)
        correlations = {}
        for col in ['AVG', 'OPS', 'wOBA']:
            if df[col].nunique() > 1:
                correlations[col] = pearsonr(df['CustomMetric'], df[col])[0]
        top_players = df.sort_values('CustomMetric', ascending=False).to_dict(orient='records')
        return jsonify({'correlations': correlations, 'top_players': top_players})
    except Exception as e:
        print("Formula error:", formula)
        print("Error message:", e)
        return jsonify({'error': f"Invalid formula: {e}"}), 400

if __name__ == '__main__':
    app.run(debug=True)
