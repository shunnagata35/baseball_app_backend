import { useState } from 'react';
import axios from 'axios';

function App() {
  const [formula, setFormula] = useState('');
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    setError('');
    try {
      const res = await axios.post('http://localhost:5000/calculate', {
        formula,
        players: ['Shohei Ohtani', 'Aaron Judge', 'Mookie Betts']
      });
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong');
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Custom Baseball Metric Calculator</h1>
      <input
        type="text"
        placeholder="Enter formula (e.g., HR * 1.5 - SO)"
        value={formula}
        onChange={(e) => setFormula(e.target.value)}
        style={{ width: '400px', padding: '0.5rem' }}
      />
      <button onClick={handleSubmit} style={{ marginLeft: '1rem' }}>
        Calculate
      </button>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {results && (
        <div>
          <h2>Correlations</h2>
          <ul>
            {Object.entries(results.correlations).map(([k, v]) => (
              <li key={k}>{k}: {v.toFixed(3)}</li>
            ))}
          </ul>

          <h2>Top Players</h2>
          <table border="1" cellPadding="8">
            <thead>
              <tr>
                {Object.keys(results.top_players[0]).map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.top_players.map((player, i) => (
                <tr key={i}>
                  {Object.values(player).map((val, j) => (
                    <td key={j}>{val}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default App;
