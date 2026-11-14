"""Download season-to-date inputs for the in-progress season (default 2026-27).

Sources (plain requests, no browser impersonation):
  Basketball Reference  per-game, totals, advanced, per-100-possession, preseason odds, coaches,
                        playoff probabilities (projected final wins)
  ESPN standings API    wins, losses, conference playoff seed
  sportsdataverse       NBA.com team advanced stats (team defensive rating), refreshed nightly
Basketball Reference asks for no more than ~20 requests/minute, so pages are spaced 4 seconds apart.
NBA.com clutch stats cannot be fetched this way (403 without a browser), so clutch data is
pasted into the app instead (see serve.py).
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, gzip, json, sys, time
import requests

ROOT = Path(__file__).resolve().parent
CURRENT_YEAR = 2027


def sources(year):
    bbref = 'https://www.basketball-reference.com/leagues/NBA_{year}_{page}.html'
    pages = {page: bbref.format(year=year, page=page) for page in ('per_game', 'totals', 'advanced', 'per_poss', 'preseason_odds', 'coaches')}
    # projected final records (Basketball Reference's season simulation); only published for the season in progress
    pages['playoff_prob'] = 'https://www.basketball-reference.com/friv/playoff_prob.html'
    pages['espn_standings'] = f'https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season={year}&type=0&level=2'
    pages['team_advanced'] = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_team_season_stats/team_season_stats_{year}.parquet'
    return pages


def raw_dir(year):
    path = ROOT / f'data/current/{year}/raw'
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch(year=CURRENT_YEAR, max_age_hours=6, log=print):
    """Refresh any source older than max_age_hours. Returns the manifest of fetch times."""
    out = raw_dir(year)
    manifest_path = out / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    session = requests.Session()
    session.headers['User-Agent'] = 'nba-award-models research script'
    now = datetime.now(timezone.utc)
    last_bbref = 0.0
    for name, url in sources(year).items():
        stamp = manifest.get(name, {}).get('fetched_at')
        if stamp and (now - datetime.fromisoformat(stamp)).total_seconds() < max_age_hours * 3600:
            continue
        if 'basketball-reference' in url:
            wait = 4 - (time.monotonic() - last_bbref)
            if wait > 0:
                time.sleep(wait)
            last_bbref = time.monotonic()
        response = session.get(url, timeout=40)
        if response.status_code == 429:
            raise RuntimeError(f'Basketball Reference rate limit hit (Retry-After {response.headers.get("Retry-After")}); try again later')
        if name == 'preseason_odds' and response.status_code == 404:
            log('preseason odds page not published; expectations will be blank')
            continue
        response.raise_for_status()
        suffix = '.parquet' if url.endswith('.parquet') else '.json' if 'espn' in url else '.html.gz'
        body = response.content if suffix != '.html.gz' else gzip.compress(response.content)
        (out / f'{name}{suffix}').write_bytes(body)
        manifest[name] = dict(url=url, fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), bytes=len(response.content))
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        log(f'fetched {name}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=CURRENT_YEAR)
    parser.add_argument('--force', action='store_true', help='ignore the 6-hour cache')
    args = parser.parse_args()
    try:
        fetch(args.year, max_age_hours=0 if args.force else 6)
    except Exception as error:
        print('fetch failed:', error, file=sys.stderr); sys.exit(1)
