"""Serve the dashboard locally with in-app refresh of the current-season projections.

    python3 serve.py            # http://127.0.0.1:8000/  (localhost only)
    python3 serve.py --port 8080

Endpoints used by the Projections page:
  POST /api/refresh     re-download season-to-date sources (fetch_current.py), team win totals (fetch_team_wins.py)
                        and odds (fetch_odds.py), then re-project
  POST /api/odds        re-download Polymarket/Kalshi award odds only (a few seconds), then re-project
  POST /api/odds-history  re-download daily odds movement (fetch_odds_history.py, a few minutes), then re-project
  POST /api/clutch      body = clutch table copied from NBA.com; saved, then re-project
  POST /api/preseason   body = "TEAM total" lines; saved as this season's preseason win totals, then re-project
Each run happens in a fresh subprocess (project_current.py patches file reads at import time).
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, re, subprocess, sys, threading, webbrowser

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'output/artifacts'
PAGE = 'nba-award-models-browser.html'
YEAR = 2027
SEASON = f'{YEAR-1}-{str(YEAR)[-2:]}'
LOCK = threading.Lock()
TEAM_NAMES = {'atlanta hawks': 'ATL', 'boston celtics': 'BOS', 'brooklyn nets': 'BRK', 'charlotte hornets': 'CHO', 'chicago bulls': 'CHI',
              'cleveland cavaliers': 'CLE', 'dallas mavericks': 'DAL', 'denver nuggets': 'DEN', 'detroit pistons': 'DET',
              'golden state warriors': 'GSW', 'houston rockets': 'HOU', 'indiana pacers': 'IND', 'la clippers': 'LAC',
              'los angeles clippers': 'LAC', 'los angeles lakers': 'LAL', 'memphis grizzlies': 'MEM', 'miami heat': 'MIA',
              'milwaukee bucks': 'MIL', 'minnesota timberwolves': 'MIN', 'new orleans pelicans': 'NOP', 'new york knicks': 'NYK',
              'oklahoma city thunder': 'OKC', 'orlando magic': 'ORL', 'philadelphia 76ers': 'PHI', 'phoenix suns': 'PHO',
              'portland trail blazers': 'POR', 'sacramento kings': 'SAC', 'san antonio spurs': 'SAS', 'toronto raptors': 'TOR',
              'utah jazz': 'UTA', 'washington wizards': 'WAS'}
CODES = set(TEAM_NAMES.values())
ALIASES = {'BKN': 'BRK', 'PHX': 'PHO', 'CHA': 'CHO', 'GS': 'GSW', 'NY': 'NYK', 'SA': 'SAS', 'NO': 'NOP', 'WSH': 'WAS', 'UTAH': 'UTA'}


PYTHON = str(ROOT / '.venv/bin/python') if (ROOT / '.venv/bin/python').exists() else sys.executable


def run(*args):
    result = subprocess.run([PYTHON, *args], cwd=ROOT, capture_output=True, text=True, timeout=900)
    log = (result.stdout + result.stderr)[-4000:]
    if result.returncode:
        raise RuntimeError(log.strip().splitlines()[-1] if log.strip() else f'{args[0]} failed')
    return log


def project():
    run('project_current.py', '--year', str(YEAR))
    return json.loads((SITE / 'projections.json').read_text())


def parse_clutch(text):
    """Parse a table copied from NBA.com clutch-traditional (tab or comma separated)."""
    lines = [line for line in text.replace('\r', '').split('\n') if line.strip()]
    split = (lambda line: line.split('\t')) if any('\t' in line for line in lines) else (lambda line: line.split(','))
    header_index = next((i for i, line in enumerate(lines) if {'PLAYER', 'TEAM', 'PTS'} <= {c.strip().upper() for c in split(line)}), None)
    if header_index is None:
        raise ValueError('Could not find a header row with PLAYER, TEAM and PTS')
    header = [c.strip().upper() for c in split(lines[header_index])]
    need = ['PLAYER', 'TEAM', 'GP', 'W', 'L', 'PTS', 'FGM', 'FGA', '+/-']
    missing = [c for c in need if c not in header]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    optional = ['3PM', 'FTM', 'AST', 'TOV']
    rows = []
    for line in lines[header_index + 1:]:
        cells = [c.strip() for c in split(line)]
        if len(cells) < len(header):
            continue
        cell = dict(zip(header, cells))
        if not cell['PLAYER'] or not re.fullmatch(r'-?\d+', cell['GP'] or ''):
            continue
        values = [cell['PLAYER'].upper(), cell['TEAM'].upper(), *[cell[c] for c in ('GP', 'W', 'L', 'PTS', 'FGM', 'FGA')],
                  *[cell.get(c, '0') or '0' for c in optional], cell['+/-']]
        # raw_chunks column order: player,team,gp,w,l,pts,fgm,fga,fg3m,ftm,ast,tov,plus_minus
        rows.append(','.join(v.replace(',', '') for v in values))
    if len(rows) < 10:
        raise ValueError(f'Only {len(rows)} player rows found; paste the whole table (rows per page: All)')
    return rows


def save_clutch(text):
    rows = parse_clutch(text)
    path = ROOT / 'data/clutch/raw_chunks.json'
    chunks = json.loads(path.read_text())
    chunks[SEASON] = ';'.join(rows)
    path.write_text(json.dumps(chunks, ensure_ascii=False))
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    (ROOT / 'data/clutch/current_meta.json').write_text(json.dumps(dict(season=SEASON, pasted_at=stamp, rows=len(rows)), indent=2) + '\n')
    return len(rows)


def save_preseason(text):
    totals = {}
    for line in text.replace('\r', '').split('\n'):
        match = re.match(r'\s*(.+?)[\s,;:\t]+(\d{1,2}(?:\.\d+)?)\s*$', line)
        if not match:
            continue
        team = match[1].strip().strip('"').strip()
        code = ALIASES.get(team.upper(), team.upper())
        if code not in CODES:
            code = TEAM_NAMES.get(team.lower())
        if code:
            totals[code] = float(match[2])
    if len(totals) != 30:
        missing = sorted(CODES - set(totals))
        raise ValueError(f'Need all 30 teams; recognised {len(totals)}. Missing: {", ".join(missing)}')
    path = ROOT / f'data/current/{YEAR}/preseason_wins.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('Tm,preseason_win_total\n' + ''.join(f'{t},{v}\n' for t, v in sorted(totals.items())))
    return len(totals)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def do_GET(self):
        if self.path in ('/', ''):
            self.send_response(302); self.send_header('Location', '/' + PAGE + '#projections'); self.end_headers(); return
        if self.path.startswith('/api/status'):
            return self.reply(200, dict(ok=True, season=SEASON))
        return super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > 2_000_000:
            return self.reply(413, dict(ok=False, error='Paste too large'))
        text = self.rfile.read(length).decode('utf-8', 'replace')
        if not LOCK.acquire(blocking=False):
            return self.reply(409, dict(ok=False, error='A refresh is already running'))
        try:
            if self.path == '/api/refresh':
                run('fetch_current.py', '--year', str(YEAR), '--force')
                message = 'Fetched fresh season-to-date data, team win totals and odds, and re-projected'
                try:  # projected wins = sportsbook win totals; falls back to Basketball Reference's projection
                    run('fetch_team_wins.py', '--year', str(YEAR))
                except RuntimeError as error:
                    message = f'Fetched fresh data and re-projected (team win totals failed, using Basketball Reference projections: {error})'
                try:
                    run('fetch_odds.py', '--year', str(YEAR))
                except RuntimeError as error:  # stats refresh still counts if the markets are down
                    message = f'Fetched fresh season-to-date data and re-projected (odds failed: {error})'
            elif self.path == '/api/odds-history':
                run('fetch_odds_history.py', '--year', str(YEAR))
                message = 'Fetched odds movement and re-projected'
            elif self.path == '/api/odds':
                run('fetch_odds.py', '--year', str(YEAR))
                message = 'Fetched current odds and re-projected'
            elif self.path == '/api/clutch':
                message = f'Saved {save_clutch(text)} clutch rows and re-projected'
            elif self.path == '/api/preseason':
                message = f'Saved {save_preseason(text)} preseason win totals and re-projected'
            else:
                return self.reply(404, dict(ok=False, error='Unknown endpoint'))
            return self.reply(200, dict(ok=True, message=message, projections=project()))
        except Exception as error:
            return self.reply(400 if isinstance(error, ValueError) else 500, dict(ok=False, error=str(error)))
        finally:
            LOCK.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{args.port}/'
    print('Serving', url, '(Ctrl+C to stop)')
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
