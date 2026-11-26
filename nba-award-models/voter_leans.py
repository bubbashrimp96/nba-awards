"""Per-voter ballot leans: a ranked-choice (Plackett-Luce) model of every archived award ballot.

Each ballot is a top-k ranking of the race's named candidates. A voter v ranks candidate c by
    utility = alpha[race, c] + beta[v] . z[race, c]
alpha is the panel consensus for that candidate in that race (a free fixed effect, so the leans
cannot be confused with who was actually better). z is the candidate's standing inside the race
on the same measures as the Voting > Tendencies tab (within-race percentile, centred on 0) plus
position. beta[v] is the voter's lean, shrunk to zero with a ridge penalty, so a voter with few or
inconsistent ballots looks like the panel. Older races count less (recency half-life).

project() applies last season's panel to this season's candidates: the model's share is the
consensus, each voter's lean multiplies a candidate's odds by exp(beta . z), and the panel-lean
share is the average voter's resulting first-choice probability.
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

from build_award_ballots import ballot_key

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'output/artifacts'
OUTPUT = ARTIFACTS / 'voter-leans.json'
# Same measures as the Voting > Tendencies tab (award-ballots.js STAT_SETS).
STAT_SETS = {
    'MVP': ['ppg', 'per', 'ws48', 'bpm', 'vorp', 'ts', 'apg', 'rpg', 'wins'],
    'ROY': ['ppg', 'per', 'ws48', 'bpm', 'mpg', 'rpg', 'apg', 'wins'],
    'DPOY': ['dbpm', 'dws', 'blk', 'stl', 'drb', 'drtg', 'wins'],
    'MIP': ['d_ppg', 'd_per', 'd_bpm', 'd_mpg', 'ppg', 'age', 'wins'],
    'SMOY': ['ppg', 'per', 'ws48', 'bpm', 'mpg', 'wins'],
    'CPOY': ['ppg', 'per', 'ws48', 'bpm', 'usg', 'wins'],
}
LOWER = {'drtg'}
POSITIONS = ['G', 'F', 'C']
HALF_LIFE = 4.0
LAMBDAS = (1.0, 3.0, 10.0, 30.0, 100.0)
# Player affinity only where the same players stay in contention year to year (validated: MVP, DPOY).
PLAYER_LAMBDA = {'MVP': 3.0, 'DPOY': 3.0}
CALIBRATION_GAP = 8.0
FAN = {'vote fan', 'nba fan vote', 'fan vote'}


def dims(award):
    return STAT_SETS[award] + ['pos_' + p for p in POSITIONS]


def percentile(values, lower=False):
    """Mid-rank percentile in [0, 1], matching the Tendencies tab; None stays None."""
    present = [(-v if lower else v) for v in values if v is not None]
    out = []
    if len(present) < 2:
        return [None] * len(values)
    ordered = sorted(present)
    n = len(ordered) - 1
    for v in values:
        if v is None:
            out.append(None)
            continue
        v = -v if lower else v
        lo = ordered.index(v)
        hi = len(ordered) - 1 - ordered[::-1].index(v)
        out.append((lo + hi) / 2 / n)
    return out


def features(award, rows):
    """rows: list of candidate stat dicts (or None). Returns z (n x D): percentile - 0.5, position one-hot."""
    stats = STAT_SETS[award]
    z = np.zeros((len(rows), len(stats) + len(POSITIONS)))
    for j, stat in enumerate(stats):
        pct = percentile([(row or {}).get(stat) for row in rows], stat in LOWER)
        z[:, j] = [0.0 if p is None else p - 0.5 for p in pct]
    for i, row in enumerate(rows):
        pos = (row or {}).get('pos')
        if pos in POSITIONS:
            z[i, len(stats) + POSITIONS.index(pos)] = 1.0
    return z


def races_for(award):
    races = json.loads((ARTIFACTS / 'award-ballots.json').read_text())
    candidates = json.loads((ARTIFACTS / 'award-candidates.json').read_text())
    out = []
    for race in races:
        if race['award'] != award or not race['ballots']:
            continue
        lookup = candidates.get(race['season'], {})
        names = []
        for name in [entry[1] for entry in race['totals']] + [p for b in race['ballots'] for p in b[3]]:
            key = ballot_key(name)
            if key not in names:
                names.append(key)
        index = {key: i for i, key in enumerate(names)}
        ballots = []
        for voter_id, voter, outlet, picks, _points in race['ballots']:
            if voter.strip().lower() in FAN or not picks:
                continue
            ballots.append(dict(voter=voter_id, name=voter, outlet=outlet, picks=[index[ballot_key(p)] for p in picks]))
        out.append(dict(season=race['season'], year=int(race['season'][:4]) + 1, names=names,
                        z=features(award, [lookup.get(k) for k in names]), ballots=ballots))
    return out


def fit(award, races, lam, half_life=HALF_LIFE, fixed_beta=None, lam_player=None, fixed_gamma=None):
    """Maximise the recency-weighted Plackett-Luce likelihood. fixed_beta: dict voter -> beta (fit alpha only)."""
    D = len(dims(award))
    voters = sorted({b['voter'] for race in races for b in race['ballots']})
    vindex = {v: i for i, v in enumerate(voters)}
    latest = max(race['year'] for race in races)
    offsets, total = [], 0
    for race in races:
        offsets.append(total)
        total += len(race['names'])
    prepared = []
    for race, off in zip(races, offsets):
        n = len(race['names'])
        k = max(len(b['picks']) for b in race['ballots'])
        picks = np.full((len(race['ballots']), k), -1)
        for i, b in enumerate(race['ballots']):
            picks[i, :len(b['picks'])] = b['picks']
        who = np.array([vindex[b['voter']] for b in race['ballots']])
        weight = 0.5 ** ((latest - race['year']) / half_life) if half_life else 1.0
        prepared.append((off, n, race['z'], picks, who, weight))
    free_beta = fixed_beta is None
    use_gamma = free_beta and lam_player is not None
    pairs = sorted({(b['voter'], race['names'][p]) for race in races for b in race['ballots'] for p in b['picks']}) if use_gamma else []
    pindex = {pair: i for i, pair in enumerate(pairs)}
    for race in races:
        # Player affinity: a persistent voter x player term, only where that voter has ranked that player.
        race['_gmap'] = np.array([[pindex.get((b['voter'], name), -1) for name in race['names']] for b in race['ballots']])
        race['_gfix'] = np.array([[(fixed_gamma or {}).get((b['voter'], name), 0.0) for name in race['names']] for b in race['ballots']])
    fixed = np.zeros((len(voters), D))
    if not free_beta:
        for v, i in vindex.items():
            if v in fixed_beta:
                fixed[i] = fixed_beta[v]

    nb = len(voters) * D if free_beta else 0
    def unpack(theta):
        alpha = theta[:total]
        beta = theta[total:total + nb].reshape(len(voters), D) if free_beta else fixed
        gamma = theta[total + nb:]
        return alpha, beta, gamma

    def objective(theta):
        alpha, beta, gamma = unpack(theta)
        g_gamma = np.zeros_like(gamma)
        if use_gamma:
            loss_g = 0.5 * lam_player * gamma @ gamma
            g_gamma += lam_player * gamma
        else:
            loss_g = 0.0
        loss = 0.5 * 1e-3 * alpha @ alpha + loss_g
        g_alpha = 1e-3 * alpha.copy()
        g_beta = np.zeros_like(beta)
        if free_beta:
            loss += 0.5 * lam * np.sum(beta * beta)
            g_beta += lam * beta
        for (off, n, z, picks, who, weight), race in zip(prepared, races):
            u = alpha[off:off + n][None, :] + beta[who] @ z.T + race['_gfix']  # ballots x candidates
            gm = race['_gmap']
            if use_gamma:
                u = u + np.where(gm >= 0, gamma[np.maximum(gm, 0)], 0.0)
            avail = np.ones_like(u, dtype=bool)
            g_u = np.zeros_like(u)
            rows = np.arange(len(who))
            for step in range(picks.shape[1]):
                pick = picks[:, step]
                active = pick >= 0
                if not active.any():
                    break
                masked = np.where(avail, u, -np.inf)
                lse = logsumexp(masked, axis=1)
                p = np.where(avail, np.exp(masked - lse[:, None]), 0.0)
                r = rows[active]
                loss -= weight * np.sum(u[r, pick[active]] - lse[active])
                g_u[r] += weight * p[active]
                g_u[r, pick[active]] -= weight
                avail[r, pick[active]] = False
            g_alpha[off:off + n] += g_u.sum(axis=0)
            if free_beta:
                np.add.at(g_beta, who, g_u @ z)
            if use_gamma:
                sel = gm >= 0
                np.add.at(g_gamma, gm[sel], g_u[sel])
        grad = np.concatenate([g_alpha, g_beta.ravel(), g_gamma]) if free_beta else g_alpha
        return loss, grad

    size = total + nb + len(pairs)
    result = minimize(objective, np.zeros(size), jac=True, method='L-BFGS-B', options=dict(maxiter=3000))
    alpha, beta, gamma = unpack(result.x)
    return dict(voters=voters, beta={v: beta[i] for v, i in vindex.items()}, gamma={pair: gamma[i] for pair, i in pindex.items()},
                alpha=[alpha[off:off + len(r['names'])] for r, off in zip(races, offsets)], converged=bool(result.success))


def ballot_loglik(alpha, z, beta, picks):
    u = alpha + z @ beta
    avail = np.ones(len(u), dtype=bool)
    total = 0.0
    for pick in picks:
        total += u[pick] - logsumexp(u[avail])
        avail[pick] = False
    return total


def validate(award, races, lam, tests=3, lam_player=None):
    """Out-of-sample check: leans fitted on seasons before S, consensus refitted on S, scored on S's ballots."""
    rows = []
    for test in races[-tests:]:
        train = [r for r in races if r['year'] < test['year']]
        if len(train) < 3:
            continue
        trained = fit(award, train, lam, lam_player=lam_player)
        leans, gam = trained['beta'], trained['gamma']
        D = len(dims(award))
        with_lean = fit(award, [test], lam, fixed_beta=leans, fixed_gamma=gam)
        without = fit(award, [test], lam, fixed_beta={})
        gain, first_hits, first_base, n = 0.0, 0, 0, 0
        for b in test['ballots']:
            beta = leans.get(b['voter'])
            if beta is None:
                continue
            a1, a0 = with_lean['alpha'][0], without['alpha'][0]
            a1 = a1 + np.array([gam.get((b['voter'], name), 0.0) for name in test['names']])
            gain += ballot_loglik(a1, test['z'], beta, b['picks']) - ballot_loglik(a0, test['z'], np.zeros(D), b['picks'])
            first_hits += int(np.argmax(a1 + test['z'] @ beta) == b['picks'][0])
            first_base += int(np.argmax(a0) == b['picks'][0])
            n += 1
        rows.append(dict(season=test['season'], ballots=n, loglik_gain=gain / n if n else None,
                         first_pick_hit=first_hits / n if n else None, first_pick_base=first_base / n if n else None))
    return rows


def choose_lambda(award, races):
    scores = {}
    for lam in LAMBDAS:
        rows = [r for r in validate(award, races, lam, lam_player=PLAYER_LAMBDA.get(award)) if r['ballots']]
        scores[lam] = sum(r['loglik_gain'] * r['ballots'] for r in rows) / max(1, sum(r['ballots'] for r in rows))
    return max(scores, key=scores.get), scores




def model_scores(award):
    """{year: {name_key: model score}} from each award's final fitted model, to put ballots and shares on one scale."""
    if award == 'CPOY':
        import build_clutch
        model = json.loads((ROOT / 'clutch_model/model.json').read_text())
        data = build_clutch.candidates()
        out = {}
        for year, frame in data.groupby('year'):
            scores = build_clutch.design(frame.reset_index(drop=True)) @ np.array(model['coefficients'])
            out[int(year)] = {ballot_key(n): float(s) for n, s in zip(frame.player, scores)}
        return out
    from revised_award_core import load_namespace, features_for
    model = json.loads((ROOT / 'revised_awards/models.json').read_text())[award]
    ns = load_namespace(award)
    out = {}
    for group in ns['make_groups'](features_for(award)):
        scores = group['x'] @ np.array(model['coefficients'])
        out[int(group['year'])] = {ballot_key(n): float(s) for n, s in zip(group['g']['Player Name'], scores)}
    return out


def calibrate(award, races, alphas):
    """Slope of the ballot consensus (alpha) on the model score, within race, through the race means.
    Ballot utility = k * model score, so a voter's lean of L on the ballot scale moves the model share by exp(L / k)."""
    scores = model_scores(award)
    num = den = 0.0
    matched = 0
    for race, alpha in zip(races, alphas):
        lookup = scores.get(race['year'], {})
        pairs = [(a, lookup[n]) for a, n in zip(alpha, race['names']) if n in lookup]
        if len(pairs) < 3:
            continue
        a, s = np.array(pairs).T
        keep = s >= s.max() - CALIBRATION_GAP  # far-out-of-contention names (one stray 5th) would dominate the slope
        if keep.sum() < 3:
            continue
        a, s = a[keep] - a[keep].mean(), s[keep] - s[keep].mean()
        num += a @ s
        den += s @ s
        matched += int(keep.sum())
    return (num / den if den else 1.0), matched


def build(awards=None):
    payload = {}
    ballots = json.loads((ARTIFACTS / 'award-ballots.json').read_text())
    for award in awards or STAT_SETS:
        races = races_for(award)
        lam, scores = choose_lambda(award, races)
        lam_player = PLAYER_LAMBDA.get(award)
        validation = validate(award, races, lam, lam_player=lam_player)
        full = fit(award, races, lam, lam_player=lam_player)
        k, matched = calibrate(award, races, full['alpha'])
        latest = races[-1]
        panel_race = next(r for r in ballots if r['award'] == award and r['season'] == latest['season'])
        history = {}
        for race in races[:-1]:
            for b in race['ballots']:
                history[b['voter']] = history.get(b['voter'], 0) + 1
        voters = []
        for voter_id, voter, outlet, picks, points in panel_race['ballots']:
            if voter.strip().lower() in FAN or not picks:
                continue
            beta = full['beta'].get(voter_id)
            gamma = {p: round(float(g), 4) for (v, p), g in full['gamma'].items() if v == voter_id and abs(g) > 1e-3}
            voters.append(dict(id=voter_id, name=voter, outlet=outlet, prior_ballots=history.get(voter_id, 0),
                               beta=[round(float(x), 4) for x in beta], gamma=gamma, points=points))
        payload[award] = dict(
            panel_season=latest['season'], dims=dims(award), lam=lam, lam_player=lam_player, half_life=HALF_LIFE,
            k=round(float(k), 4), calibration_candidates=matched, races=len(races), seasons=[r['season'] for r in races],
            lambda_scores={str(l): round(float(v), 4) for l, v in scores.items()},
            validation=[{key: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for key, v in row.items()} for row in validation],
            pool_size=int(np.median([len(r['names']) for r in races[-5:]])), voters=voters)
        print(award, 'lambda', lam, 'k', round(k, 2), 'validation', [(r['season'], round(r['loglik_gain'], 3)) for r in validation], flush=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n')
    return payload


def project(award, leans, ranking, rows, sims=4000, seed=0):
    """Apply last season's panel to this season's candidates.

    ranking: the award's full model ranking [{player, team, share}], best first.
    rows: {name_key: candidate stats dict in the award-candidates.json schema}.
    """
    spec = leans[award]
    pool = ranking[:spec['pool_size']]
    keys = [ballot_key(r['player']) for r in pool]
    share = np.array([r['share'] for r in pool])
    share = share / share.sum()
    log_share = np.log(np.maximum(share, 1e-12))
    z = features(award, [rows.get(k) for k in keys])
    k = max(spec['k'], 0.25)
    lean = np.array([z @ np.array(v['beta']) + np.array([v['gamma'].get(key, 0.0) for key in keys]) for v in spec['voters']])
    lean -= lean.mean(axis=1, keepdims=True)  # only relative leans move a ballot
    panel = lean.mean(axis=0)
    adjusted = softmax(log_share + panel / k)
    # Ballots: ballot-scale utility = k * log share + lean; most likely ballot = order by utility; Gumbel draws for points.
    rng = np.random.default_rng(seed)
    points = np.array(spec['voters'][0]['points'], dtype=float)
    depth = len(points)
    base_u = k * log_share
    totals = {True: np.zeros(len(pool)), False: np.zeros(len(pool))}
    firsts = {True: np.zeros(len(pool)), False: np.zeros(len(pool))}
    wins = {True: np.zeros(len(pool)), False: np.zeros(len(pool))}
    for with_lean in (True, False):
        u = base_u[None, :] + (lean if with_lean else np.zeros_like(lean))  # voters x candidates
        sim_points = np.zeros((sims, len(pool)))
        for v in range(len(spec['voters'])):
            draw = u[v][None, :] + rng.gumbel(size=(sims, len(pool)))
            order = np.argsort(-draw, axis=1)[:, :depth]
            np.add.at(sim_points, (np.arange(sims)[:, None], order), points[None, :len(order[0])])
            firsts[with_lean] += np.bincount(order[:, 0], minlength=len(pool)) / sims
        totals[with_lean] = sim_points.mean(axis=0)
        wins[with_lean] = np.bincount(sim_points.argmax(axis=1), minlength=len(pool)) / sims
    max_points = points[0] * len(spec['voters'])
    consensus = [keys[i] for i in np.argsort(-base_u)[:depth]]
    candidates = []
    for i, r in enumerate(pool):
        candidates.append(dict(player=r['player'], team=r.get('team'), model_share=float(share[i]), lean_share=float(adjusted[i]),
                               lean=float(panel[i]), vote_share=float(totals[True][i] / max_points), vote_share_neutral=float(totals[False][i] / max_points),
                               first_votes=float(firsts[True][i]), first_votes_neutral=float(firsts[False][i]),
                               panel_win=float(wins[True][i]), panel_win_neutral=float(wins[False][i]),
                               stats_found=keys[i] in rows))
    order = np.argsort(-adjusted)
    candidates = [candidates[i] for i in order]
    names = {key: r['player'] for key, r in zip(keys, pool)}
    voters = []
    for v, spec_v in enumerate(spec['voters']):
        u = base_u + lean[v]
        ballot = [keys[i] for i in np.argsort(-u)[:depth]]
        top = np.argsort(-np.abs(lean[v]))[:2]
        voters.append(dict(id=spec_v['id'], name=spec_v['name'], outlet=spec_v['outlet'], prior_ballots=spec_v['prior_ballots'],
                           ballot=[names[key] for key in ballot], differs=ballot != consensus,
                           leans={names[keys[i]]: round(float(lean[v][i]), 3) for i in top if abs(lean[v][i]) >= 0.05}))
    return dict(panel_season=spec['panel_season'], k=spec['k'], pool=len(pool), voters_n=len(voters),
                voters_with_history=sum(1 for v in spec['voters'] if v['prior_ballots']),
                consensus_ballot=[names[key] for key in consensus], candidates=candidates, voters=voters,
                validation=spec['validation'], differs=sum(v['differs'] for v in voters))


if __name__ == '__main__':
    import sys
    build(sys.argv[1:] or None)
