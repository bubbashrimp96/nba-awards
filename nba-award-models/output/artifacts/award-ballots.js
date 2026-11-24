(() => {
  const page = document.getElementById('ballots-page');
  const status = page.querySelector('[role="status"]');
  const content = page.querySelector('.ballots-content');
  const tabBar = page.querySelector('.voting-tabs');
  const awardBar = page.querySelector('.voting-awards');
  const seasonBar = page.querySelector('.voting-seasons');
  const form = page.querySelector('form');
  const { search, minimum } = form.elements;
  const AWARDS = {MVP: 'Most Valuable Player', ROY: 'Rookie of the Year', DPOY: 'Defensive Player of the Year',
    MIP: 'Most Improved Player', SMOY: 'Sixth Man of the Year', CPOY: 'Clutch Player of the Year', COY: 'Coach of the Year'};
  const TABS = [['seasons', 'By season'], ['voters', 'Voters'], ['publications', 'Publications'], ['tendencies', 'Tendencies']];
  const STAT_SETS = {
    MVP: ['ppg', 'per', 'ws48', 'bpm', 'vorp', 'ts', 'apg', 'rpg', 'wins'],
    ROY: ['ppg', 'per', 'ws48', 'bpm', 'mpg', 'rpg', 'apg', 'wins'],
    DPOY: ['dbpm', 'dws', 'blk', 'stl', 'drb', 'drtg', 'wins'],
    MIP: ['d_ppg', 'd_per', 'd_bpm', 'd_mpg', 'ppg', 'age', 'wins'],
    SMOY: ['ppg', 'per', 'ws48', 'bpm', 'mpg', 'wins'],
    CPOY: ['ppg', 'per', 'ws48', 'bpm', 'usg', 'wins'],
  };
  const STAT_INFO = {
    ppg: ['PPG', 'Points per game', 1], rpg: ['RPG', 'Rebounds per game', 1], apg: ['APG', 'Assists per game', 1],
    mpg: ['MPG', 'Minutes per game', 1], per: ['PER', 'Player efficiency rating', 1], ws48: ['WS/48', 'Win shares per 48', 3],
    bpm: ['BPM', 'Box plus/minus', 1], vorp: ['VORP', 'Value over replacement', 1], ts: ['TS%', 'True shooting', 3],
    usg: ['USG%', 'Usage rate', 1], dbpm: ['DBPM', 'Defensive box plus/minus', 1], dws: ['DWS', 'Defensive win shares', 1],
    blk: ['BLK', 'Blocks per game', 1], stl: ['STL', 'Steals per game', 1], drb: ['DRB%', 'Defensive rebound rate', 1],
    drtg: ['DRtg', 'Defensive rating (lower is better)', 0, true], wins: ['Team W', 'Team wins', 0],
    age: ['Age', 'Age (higher = older)', 0], d_ppg: ['Δ PPG', 'Scoring jump on last season', 1],
    d_per: ['Δ PER', 'PER jump on last season', 1], d_bpm: ['Δ BPM', 'BPM jump on last season', 1],
    d_mpg: ['Δ MPG', 'Minutes jump on last season', 1],
  };
  const POSITIONS = [['G', 'Guards'], ['F', 'Forwards'], ['C', 'Centres']];
  const fanVote = voter => /^(vote fan|nba fan vote|fan vote)$/i.test(voter);
  const percent = value => (100 * value).toFixed(1) + '%';
  const gap = value => (value > 0 ? '+' : '') + (100 * value).toFixed(1) + ' pp';
  const rate = (count, total) => total ? percent(count / total) : '—';
  const pairs = count => count * (count - 1) / 2;
  const dash = s => s.replace('-', '–');
  const nameKey = name => {
    const k = name.trim().replace(/\s+(jr\.?|sr\.?|ii|iii|iv)$/i, '').normalize('NFKD')
      .replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');
    return k === 'louiswilliams' ? 'louwilliams' : k;
  };
  const newGroup = () => ({
    ballots: 0, wins: 0, omitted: 0, expected: 0,
    peers: new Set(), agreement: 0, comparisons: 0, panelAgreement: 0, alternatives: new Map(),
  });
  const state = {tAward: 'MVP', tGroup: 'voters', tSort: null, tRecency: '4',
    tab: 'seasons', season: null, scoreSeason: 'all', award: 'all', id: null,
    sort: {voters: ['difference', -1], publications: ['difference', -1]}};
  let candidates, candidateRequest;
  let races, ballotSeasons = [], allSeasons = [];
  let stopChart = () => {};

  function match(value) {
    return !!value && value.toLowerCase().includes(search.value.trim().toLowerCase());
  }

  function table(caption, labels, rows, cls = '') {
    const wrapper = el('div', 'panel table-responsive');
    const grid = el('table', 'table ' + cls);
    if (caption) grid.createCaption().textContent = caption;
    const head = grid.createTHead().insertRow();
    for (const label of labels) {
      const cell = el('th', '', label);
      cell.scope = 'col';
      head.append(cell);
    }
    const body = grid.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      for (const value of row) {
        const cell = tr.insertCell();
        if (value instanceof Node) cell.append(value);
        else cell.textContent = value ?? '—';
      }
    }
    wrapper.append(grid);
    return wrapper;
  }

  function hashFor(tab, arg) {
    return '#voting/' + tab + (arg ? '/' + encodeURIComponent(arg) : '');
  }

  function link(text, tab, arg) {
    const a = el('a', 'ballot-drill', text);
    a.href = hashFor(tab, arg);
    return a;
  }

  function pickChips(picks, winner) {
    const list = el('span', 'pick-chips');
    picks.forEach((pick, index) => {
      const chip = el('span', 'pick-chip' + (nameKey(pick) === nameKey(winner) ? ' is-winner' : ''));
      chip.append(el('b', '', String(index + 1)), document.createTextNode(pick));
      list.append(chip);
    });
    return list;
  }

  function bar(value, label) {
    const wrap = el('span', 'vote-bar');
    const fill = el('span', 'vote-bar-fill');
    fill.style.width = Math.max(0, Math.min(100, 100 * value)) + '%';
    wrap.append(fill, el('span', 'vote-bar-label', label));
    return wrap;
  }

  function signed(value, text) {
    const span = el('span', value > 0.0005 ? 'is-pos' : value < -0.0005 ? 'is-neg' : '', text);
    return span;
  }

  function summarize(subset, byOutlet) {
    const groups = new Map();
    for (const race of subset) {
      const ballots = race.ballots.map((record, index) => ({ record, rank: race.winner_ranks[index] }))
        .filter(({record}) => !fanVote(record[1]) && record[3].length);
      const total = ballots.length;
      if (total < 2) continue;
      const winnerVotes = ballots.filter(({rank}) => rank === 1).length;
      const firstChoices = new Map();
      const outlets = new Map();
      for (const {record: [id, voter, outlet, picks], rank} of ballots) {
        const label = byOutlet ? outlet : voter;
        const idKey = byOutlet ? outlet : id;
        firstChoices.set(picks[0], (firstChoices.get(picks[0]) || 0) + 1);
        if (!idKey) continue;
        if (!groups.has(idKey)) groups.set(idKey, {...newGroup(), label, seasons: new Set()});
        const group = groups.get(idKey);
        group.ballots++;
        group.seasons.add(race.season);
        group.wins += Number(rank === 1);
        group.omitted += Number(rank === 0);
        group.expected += (winnerVotes - Number(rank === 1)) / (total - 1);
        if (byOutlet) {
          group.peers.add(voter);
          if (!outlets.has(outlet)) outlets.set(outlet, []);
          outlets.get(outlet).push({pick: picks[0], rank});
        } else if (outlet) {
          group.peers.add(outlet);
        }
      }
      const panelAgreement = [...firstChoices.values()].reduce((sum, count) => sum + pairs(count), 0) / pairs(total);
      for (const [outlet, votes] of outlets) {
        const group = groups.get(outlet);
        const ownPairs = pairs(votes.length);
        group.comparisons += ownPairs;
        group.panelAgreement += panelAgreement * ownPairs;
        const picks = new Map();
        for (const vote of votes) {
          const tally = picks.get(vote.pick) || {count: 0, winner: vote.rank === 1};
          tally.count++;
          picks.set(vote.pick, tally);
        }
        for (const [pick, {count, winner}] of picks) {
          const samePick = pairs(count);
          group.agreement += samePick;
          if (!winner && samePick) group.alternatives.set(pick + ' · ' + dash(race.season) + ' ' + race.award, samePick);
        }
      }
    }
    return [...groups].map(([id, group]) => ({
      id, ...group,
      winRate: group.wins / group.ballots,
      panelRate: group.expected / group.ballots,
      omitRate: group.omitted / group.ballots,
      difference: (group.wins - group.expected) / group.ballots,
      sameRate: group.comparisons ? group.agreement / group.comparisons : null,
      agreementGap: group.comparisons ? (group.agreement - group.panelAgreement) / group.comparisons : null,
    }));
  }

  /* ---------- filter bars ---------- */
  function pills(container, items, current, onPick) {
    container.replaceChildren();
    for (const [value, label, hint] of items) {
      const button = el('button', '', label);
      button.type = 'button';
      if (hint) button.title = hint;
      button.setAttribute('aria-pressed', String(value === current));
      button.addEventListener('click', () => onPick(value));
      container.append(button);
    }
  }

  function drawBars() {
    pills(tabBar, TABS, state.tab, tab => { location.hash = hashFor(tab); });
    if (state.tab === 'tendencies') {
      pills(awardBar, Object.keys(STAT_SETS).map(key => [key, key === 'SMOY' ? '6MOY' : key, AWARDS[key]]),
        state.tAward, value => { state.tAward = value; state.tSort = null; location.hash = hashFor('tendencies', value); });
    } else pills(awardBar, [['all', 'All awards'], ...Object.keys(AWARDS).map(key => [key, key === 'SMOY' ? '6MOY' : key, AWARDS[key]])],
      state.award, value => { state.award = value; render(); });
    if (state.tab === 'seasons') {
      pills(seasonBar, allSeasons.map(year => [year, dash(year), ballotSeasons.includes(year) ? 'Named ballots available' : 'Vote totals only']),
        state.season, year => { location.hash = hashFor('seasons', year); });
      seasonBar.querySelectorAll('button').forEach((button, index) => {
        if (!ballotSeasons.includes(allSeasons[index])) button.classList.add('totals-only');
      });
    } else {
      pills(seasonBar, [['all', 'All seasons'], ...ballotSeasons.map(year => [year, dash(year)])],
        state.scoreSeason, year => { state.scoreSeason = year; render(); });
    }
    const summary = state.tab !== 'seasons';
    minimum.closest('label').hidden = !summary || !!state.id;
    search.placeholder = state.tab === 'seasons' ? 'Find a player, voter or publication'
      : state.tab === 'publications' ? 'Find a publication' : 'Find a voter or publication';
    if (state.tab === 'tendencies') minimum.closest('label').hidden = false;
  }

  /* ---------- seasons tab ---------- */
  function distribution(race) {
    const ballots = race.ballots;
    const slots = Math.max(0, ...ballots.map(ballot => ballot[3].length));
    const counts = new Map();
    for (const [, , , picks] of ballots) {
      picks.forEach((pick, index) => {
        const key = nameKey(pick);
        if (!counts.has(key)) counts.set(key, {name: pick, slots: Array(slots).fill(0)});
        counts.get(key).slots[index]++;
      });
    }
    const rows = race.totals.map(([rank, name, points]) => ({rank, name, points}));
    for (const [key, {name}] of counts) if (!rows.some(row => nameKey(row.name) === key)) rows.push({rank: null, name, points: null});
    const firstPoints = ballots[0]?.[4]?.[0];
    const max = ballots.length && firstPoints ? ballots.length * firstPoints : Math.max(...rows.map(row => row.points || 0));
    const labels = ['Rank', AWARDS[race.award] === 'Coach of the Year' ? 'Coach' : 'Candidate', 'Points',
      ballots.length ? 'Share of max points' : 'Points vs winner',
      ...Array.from({length: slots}, (_, index) => ordinal(index + 1))];
    const body = rows.map(row => {
      const name = el('span', match(row.name) && search.value.trim() ? 'hit' : '', row.name);
      if (nameKey(row.name) === nameKey(race.winner)) name.classList.add('race-winner');
      const share = row.points == null || !max ? '—' : bar(row.points / max, percent(row.points / max));
      const slotCells = (counts.get(nameKey(row.name))?.slots || Array(slots).fill(0)).map(count => count || '');
      return [row.rank ?? '—', name, row.points == null ? '—' : row.points.toLocaleString(), share, ...slotCells];
    });
    return table('', labels, body, 'vote-distribution');
  }

  function ballotTable(race) {
    const query = search.value.trim();
    const entries = race.ballots.map((record, index) => ({record, rank: race.winner_ranks[index]}))
      .filter(({record: [, voter, outlet, picks]}) => !query || [voter, outlet, ...picks].some(match));
    const rows = entries.map(({record: [id, voter, outlet, picks], rank}) => [
      fanVote(voter) ? el('span', '', voter) : link(voter, 'voters', id),
      outlet ? link(outlet, 'publications', outlet) : '—',
      pickChips(picks, race.winner),
      rank ? ordinal(rank) : 'Omitted',
    ]);
    return table('', ['Voter', 'Publication', 'Ballot', 'Winner placed'], rows, 'ballot-list');
  }

  function renderSeason() {
    const year = state.season;
    const selected = races.filter(race => race.season === year && (state.award === 'all' || race.award === state.award));
    const ballots = selected.reduce((count, race) => count + race.ballots.length, 0);
    status.textContent = dash(year) + ' · ' + selected.length + ' award races · '
      + (ballots ? ballots.toLocaleString() + ' named ballots' : 'vote totals only (named ballots start in 2013–14)');
    const query = search.value.trim();
    const grid = el('div', 'vote-races');
    for (const race of selected) {
      const card = el('section', 'vote-race');
      const head = el('div', 'vote-race-head');
      const title = el('div');
      title.append(el('p', 'eyebrow', AWARDS[race.award] || race.award), el('h2', '', race.winner));
      const meta = el('div', 'vote-race-meta');
      meta.append(el('span', '', race.ballots.length ? race.ballots.length + ' ballots' : 'Totals only'));
      const source = el('a', 'source-link', 'Source ↗');
      source.href = race.source;
      source.target = '_blank';
      source.rel = 'noopener noreferrer';
      meta.append(source);
      head.append(title, meta);
      card.append(head);
      if (race.ballots.length && race.points_match === false) {
        card.append(el('p', 'text-small flag-note', 'Archived ballots differ slightly from the published totals for this race.'));
      }
      card.append(distribution(race));
      if (race.ballots.length) {
        const details = el('details', 'race-ballots');
        details.append(el('summary', '', 'Individual ballots (' + race.ballots.length + ')'));
        const fill = () => { if (!details.dataset.filled) { details.dataset.filled = '1'; details.append(ballotTable(race)); } };
        if (query) { details.open = true; fill(); }
        else details.addEventListener('toggle', () => { if (details.open) fill(); });
        card.append(details);
      }
      grid.append(card);
    }
    if (!selected.length) grid.append(el('p', 'na', 'No races for this award in ' + dash(year) + '.'));
    content.append(grid);
  }

  /* ---------- leaderboards ---------- */
  function leaderboard(subset, byOutlet) {
    const key = byOutlet ? 'publications' : 'voters';
    const groups = summarize(subset, byOutlet);
    const minBallots = Number(minimum.value) || 1;
    const shown = groups.filter(group => group.ballots >= minBallots
      && (match(group.label) || (!byOutlet && [...group.peers].some(match))));
    const columns = [
      ['label', byOutlet ? 'Publication' : 'Voter', group => link(group.label, key, group.id)],
      ['peers', byOutlet ? 'Voters' : 'Publication', group => byOutlet ? group.peers.size : [...group.peers].join(', ') || '—'],
      ['ballots', 'Ballots', group => group.ballots],
      ['winRate', 'Picked winner', group => bar(group.winRate, rate(group.wins, group.ballots))],
      ['panelRate', 'Panel', group => percent(group.panelRate)],
      ['difference', 'Vs panel', group => signed(group.difference, gap(group.difference))],
      ['omitRate', 'Left winner off', group => percent(group.omitRate)],
    ];
    if (byOutlet) {
      columns.push(['sameRate', 'Colleagues agree', group => group.sameRate == null ? '—' : percent(group.sameRate)],
        ['agreementGap', 'Agreement vs panel', group => group.agreementGap == null ? '—' : signed(group.agreementGap, gap(group.agreementGap))]);
    }
    const [sortKey, direction] = state.sort[key];
    const value = (group, k) => k === 'label' ? group.label.toLowerCase() : k === 'peers' ? (byOutlet ? group.peers.size : [...group.peers].join(', ').toLowerCase()) : group[k];
    shown.sort((a, b) => {
      const x = value(a, sortKey), y = value(b, sortKey);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * direction || b.ballots - a.ballots;
    });

    const wrapper = el('div', 'panel table-responsive');
    const grid = el('table', 'table leaderboard');
    const head = grid.createTHead().insertRow();
    head.append(el('th', '', '#'));
    for (const [k, label] of columns) {
      const th = el('th');
      th.scope = 'col';
      const button = el('button', 'sort-head', label + (k === sortKey ? (direction > 0 ? ' ▲' : ' ▼') : ''));
      button.type = 'button';
      th.setAttribute('aria-sort', k === sortKey ? (direction > 0 ? 'ascending' : 'descending') : 'none');
      button.addEventListener('click', () => {
        state.sort[key] = [k, k === sortKey ? -direction : (k === 'label' || k === 'peers' ? 1 : -1)];
        render();
      });
      th.append(button);
      head.append(th);
    }
    const body = grid.createTBody();
    shown.forEach((group, index) => {
      const tr = body.insertRow();
      if (group.id === state.id) tr.className = 'is-selected';
      tr.insertCell().textContent = index + 1;
      for (const [, , render] of columns) {
        const cell = tr.insertCell();
        const v = render(group);
        if (v instanceof Node) cell.append(v); else cell.textContent = v;
      }
      tr.addEventListener('click', event => {
        if (event.target.closest('a')) return;
        location.hash = hashFor(key, group.id);
      });
    });
    wrapper.append(grid);
    if (!shown.length) wrapper.append(el('p', 'na', 'Nothing matches these filters. Try a lower minimum.'));
    return {wrapper, count: shown.length, total: groups.length};
  }

  /* ---------- detail ---------- */
  function historyChart(subset, byOutlet, id) {
    const years = [...new Set(subset.filter(race => race.ballots.length).map(race => race.season))];
    const results = years.map(year => summarize(subset.filter(race => race.season === year), byOutlet).find(group => group.id === id));
    if (results.filter(Boolean).length < 2) return null;
    const panel = el('section', 'voter-history');
    const head = el('div', 'history-head');
    const title = el('div');
    title.append(el('h3', '', 'Winner picks by season'),
      el('p', 'text-small', 'Share of ballots with the eventual winner first, against the rest of the panel in the same races.'));
    const controls = el('div', 'history-controls');
    const metric = el('select');
    metric.add(new Option('Success rate', 'rate'));
    metric.add(new Option('Number of successes', 'count'));
    const field = el('label', '', 'Measure');
    field.append(metric);
    controls.append(field);
    head.append(title, controls);
    const legend = el('div', 'history-legend');
    legend.append(el('span', 'history-key', byOutlet ? 'This publication' : 'This voter'),
      el('span', 'history-key benchmark', 'Rest of the panel'));
    const chart = el('div', 'history-chart');
    const canvas = el('canvas');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Winner picks by season. Exact values are in the ballot list below.');
    const hover = el('div', 'history-hover');
    hover.hidden = true;
    chart.append(canvas, hover);
    panel.append(head, legend, chart);

    let pointPositions = [];
    function draw() {
      const ctx = canvas.getContext?.('2d');
      const width = chart.clientWidth;
      if (!ctx || !width) return;
      const height = chart.clientHeight;
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      const styles = getComputedStyle(panel);
      const color = name => styles.getPropertyValue(name).trim();
      const left = 43, right = width - 19, top = 15, bottom = height - 34;
      const rateMode = metric.value === 'rate';
      const most = Math.max(1, ...results.map(point => point?.ballots || 0));
      const step = rateMode ? 0.25 : Math.max(1, Math.ceil(most / 4));
      const max = rateMode ? 1 : step * Math.ceil(most / step);
      const y = value => bottom - (bottom - top) * value / max;
      const x = index => years.length === 1 ? (left + right) / 2 : left + (right - left) * index / (years.length - 1);
      pointPositions = years.map((_, index) => x(index));
      ctx.font = '11px system-ui';
      ctx.fillStyle = color('--fg-2');
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let tick = 0; tick <= max; tick += step) {
        ctx.strokeStyle = color('--panel-bd');
        ctx.beginPath();
        ctx.moveTo(left, y(tick));
        ctx.lineTo(right, y(tick));
        ctx.stroke();
        ctx.fillText(rateMode ? Math.round(tick * 100) + '%' : tick, left - 8, y(tick));
      }
      ctx.textAlign = 'center';
      const stride = Math.max(1, Math.ceil(years.length / Math.max(2, Math.floor((right - left) / 62))));
      years.forEach((year, index) => {
        if (index % stride === 0 || index === years.length - 1) ctx.fillText(dash(year), x(index), bottom + 19);
      });
      const values = k => results.map(point => point ? point[k] / (rateMode ? point.ballots : 1) : null);
      const line = (data, stroke, dashed) => {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = dashed ? 2 : 3;
        ctx.setLineDash(dashed ? [5, 5] : []);
        ctx.beginPath();
        let penDown = false;
        data.forEach((v, index) => {
          if (v === null) { penDown = false; return; }
          if (penDown) ctx.lineTo(x(index), y(v)); else ctx.moveTo(x(index), y(v));
          penDown = true;
        });
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = stroke;
        data.forEach((v, index) => {
          if (v === null) return;
          ctx.beginPath();
          ctx.arc(x(index), y(v), dashed ? 2.5 : 4, 0, 2 * Math.PI);
          ctx.fill();
        });
      };
      line(values('expected'), color('--history-panel'), true);
      line(values('wins'), color('--history-voter'), false);
    }
    chart.addEventListener('pointermove', event => {
      if (!pointPositions.length) return;
      const cursor = event.clientX - chart.getBoundingClientRect().left;
      const index = pointPositions.reduce((best, position, i) =>
        Math.abs(position - cursor) < Math.abs(pointPositions[best] - cursor) ? i : best, 0);
      const point = results[index];
      hover.textContent = dash(years[index]) + (point
        ? ' · ' + point.wins + ' of ' + point.ballots + ' winner picks · ' + rate(point.wins, point.ballots)
          + ' · Panel ' + rate(point.expected, point.ballots)
        : ' · No ballot');
      hover.hidden = false;
      hover.style.left = Math.max(0, Math.min(chart.clientWidth - hover.offsetWidth, pointPositions[index] - hover.offsetWidth / 2)) + 'px';
    });
    chart.addEventListener('pointerleave', () => { hover.hidden = true; });
    metric.addEventListener('change', draw);
    const resize = new ResizeObserver(draw);
    resize.observe(chart);
    const theme = new MutationObserver(draw);
    theme.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
    stopChart = () => { resize.disconnect(); theme.disconnect(); };
    return panel;
  }

  function detail(subset, byOutlet, id) {
    const key = byOutlet ? 'publications' : 'voters';
    const group = summarize(subset, byOutlet).find(item => item.id === id);
    const panel = el('section', 'vote-detail');
    const head = el('div', 'vote-detail-head');
    const close = el('a', 'vote-detail-close', '✕ Close');
    close.href = hashFor(key);
    if (!group) {
      head.append(el('h2', '', byOutlet ? id : 'Voter'), close);
      panel.append(head, el('p', 'na', 'No ballots for this selection. Try All awards or All seasons.'));
      return panel;
    }
    const title = el('div');
    title.append(el('p', 'eyebrow', byOutlet ? 'Publication' : 'Voter'), el('h2', '', group.label));
    const seasons = [...group.seasons].sort();
    const sub = byOutlet
      ? group.peers.size + ' voters · ' + dash(seasons[0]) + ' to ' + dash(seasons.at(-1))
      : ([...group.peers].join(', ') || 'No publication listed') + ' · ' + dash(seasons[0]) + ' to ' + dash(seasons.at(-1));
    title.append(el('p', 'text-small', sub));
    head.append(title, close);
    const cards = el('div', 'history-stats vote-detail-stats');
    const stats = [['Ballots', group.ballots], ['Picked winner', group.wins + ' · ' + rate(group.wins, group.ballots)],
      ['Vs panel', signed(group.difference, gap(group.difference))], ['Left winner off', rate(group.omitted, group.ballots)]];
    if (byOutlet && group.sameRate != null) stats.push(['Colleagues agree', percent(group.sameRate)]);
    for (const [label, value] of stats) {
      const card = el('div', 'history-stat');
      const strong = el('strong');
      if (value instanceof Node) strong.append(value); else strong.textContent = value;
      card.append(el('span', '', label), strong);
      cards.append(card);
    }
    panel.append(head, cards);
    const chart = historyChart(subset, byOutlet, id);
    if (chart) panel.append(chart);

    const firsts = new Map();
    const rows = [];
    for (const race of [...subset].reverse()) {
      const finalOrder = race.totals.map(([, name]) => nameKey(name));
      race.ballots.forEach((record, index) => {
        const [voterId, voter, outlet, picks] = record;
        if ((byOutlet ? outlet : voterId) !== id || fanVote(voter)) return;
        firsts.set(picks[0], (firsts.get(picks[0]) || 0) + 1);
        const rank = race.winner_ranks[index];
        const top = finalOrder.slice(0, picks.length);
        const hits = picks.filter(pick => top.includes(nameKey(pick))).length;
        const row = [link(dash(race.season), 'seasons', race.season), race.award, pickChips(picks, race.winner),
          rank ? ordinal(rank) : 'Omitted', hits + ' / ' + picks.length];
        if (byOutlet) row.splice(2, 0, link(voter, 'voters', voterId));
        rows.push(row);
      });
    }
    const labels = ['Season', 'Award', 'Ballot', 'Winner placed', 'Picks in final top ' + 'N'];
    if (byOutlet) labels.splice(2, 0, 'Voter');
    const favourites = [...firsts].sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([name, count]) => name + ' (' + count + ')').join(' · ');
    if (favourites) panel.append(el('p', 'text-small vote-favourites', 'Most common first picks: ' + favourites));
    const list = el('details', 'race-ballots');
    list.open = rows.length <= 40;
    list.append(el('summary', '', 'Every ballot (' + rows.length + ')'));
    list.append(table('', labels, rows, 'ballot-list'));
    list.append(el('p', 'text-small', '“Picks in final top N” counts how many names on the ballot finished in the top N of the final vote, where N is the number of ballot slots.'));
    panel.append(list);
    return panel;
  }

  /* ---------- tendencies ---------- */
  const dimLabel = dim => dim.startsWith('pos_') ? POSITIONS.find(([p]) => 'pos_' + p === dim)[1] : STAT_INFO[dim][0];
  const dimTitle = dim => dim.startsWith('pos_') ? 'Share of ballot points given to ' + dimLabel(dim).toLowerCase() : STAT_INFO[dim][1];
  const mean = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
  const lean = value => {
    if (value == null) return '—';
    const n = Math.round(100 * value);
    return (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n);
  };
  let candidatesFailed = false;
  const RECENCY = [['0', 'Off'], ['8', 'Light'], ['4', 'Standard'], ['2', 'Strong']];
  const startYear = season => Number(season.slice(0, 4));

  function loadCandidates() {
    candidateRequest ||= fetch('award-candidates.json').then(response => {
      if (!response.ok) throw new Error('missing');
      return response.json();
    }).then(data => { candidates = data; }).catch(() => { candidatesFailed = true; });
    return candidateRequest;
  }

  function percentiles(pool, stat) {
    const lower = STAT_INFO[stat][3];
    const values = pool.filter(([, row]) => row?.[stat] != null).map(([name, row]) => [name, lower ? -row[stat] : row[stat]]);
    const result = new Map();
    if (values.length < 2) return result;
    const sorted = values.map(([, v]) => v).sort((a, b) => a - b);
    for (const [name, v] of values) {
      result.set(name, (sorted.indexOf(v) + sorted.lastIndexOf(v)) / 2 / (sorted.length - 1));
    }
    return result;
  }

  function tendencyData() {
    const award = state.tAward;
    const stats = STAT_SETS[award];
    const dims = [...stats, ...POSITIONS.map(([p]) => 'pos_' + p)];
    const byOutlet = state.tGroup === 'publications';
    const subset = races.filter(race => race.award === award && race.ballots.length
      && (state.scoreSeason === 'all' || race.season === state.scoreSeason));
    const groups = new Map();
    const halfLife = Number(state.tRecency);
    const latest = Math.max(...subset.map(race => startYear(race.season)));
    const weightOf = season => halfLife ? 0.5 ** ((latest - startYear(season)) / halfLife) : 1;
    const winners = Object.fromEntries(dims.map(dim => [dim, []]));
    for (const race of subset) {
      const lookup = candidates[race.season] || {};
      const rowOf = name => lookup[nameKey(name)];
      const names = [...new Set([...race.totals.map(entry => entry[1]), ...race.ballots.flatMap(ballot => ballot[3])].map(nameKey))];
      const pool = names.map(key => [key, lookup[key]]);
      const pct = Object.fromEntries(stats.map(stat => [stat, percentiles(pool, stat)]));
      const scored = [];
      for (const record of race.ballots) {
        const [, voter, , picks, points] = record;
        if (fanVote(voter) || !picks.length) continue;
        const score = {};
        for (const stat of stats) {
          let num = 0, den = 0;
          picks.forEach((pick, i) => {
            const v = pct[stat].get(nameKey(pick));
            if (v != null) { num += points[i] * v; den += points[i]; }
          });
          score[stat] = den ? num / den : null;
        }
        const share = {G: 0, F: 0, C: 0};
        let den = 0;
        picks.forEach((pick, i) => {
          const pos = rowOf(pick)?.pos;
          if (pos) { share[pos] += points[i]; den += points[i]; }
        });
        for (const [p] of POSITIONS) score['pos_' + p] = den ? share[p] / den : null;
        scored.push({record, score});
      }
      if (scored.length < 2) continue;
      const panel = {};
      for (const dim of dims) panel[dim] = mean(scored.map(item => item.score[dim]).filter(v => v != null));
      for (const stat of stats) {
        const v = pct[stat].get(nameKey(race.winner));
        if (v != null) winners[stat].push(v);
      }
      for (const [p] of POSITIONS) if (panel['pos_' + p] != null) winners['pos_' + p].push(panel['pos_' + p]);
      for (const {record, score} of scored) {
        const [id, voter, outlet] = record;
        const key = byOutlet ? outlet : id;
        if (!key) continue;
        if (!groups.has(key)) {
          groups.set(key, {id: key, label: byOutlet ? outlet : voter, peers: new Set(), ballots: 0,
            dev: Object.fromEntries(dims.map(dim => [dim, []])), items: []});
        }
        const group = groups.get(key);
        group.ballots++;
        if (byOutlet ? voter : outlet) group.peers.add(byOutlet ? voter : outlet);
        const w = weightOf(race.season);
        for (const dim of dims) if (score[dim] != null && panel[dim] != null) group.dev[dim].push([score[dim] - panel[dim], w]);
        group.items.push({race, record, score, panel, lookup});
      }
    }
    for (const group of groups.values()) {
      group.lean = {};
      group.t = {};
      for (const dim of dims) {
        const xs = group.dev[dim];
        const total = xs.reduce((a, [, w]) => a + w, 0);
        if (!total) { group.lean[dim] = null; group.t[dim] = 0; continue; }
        const m = xs.reduce((a, [v, w]) => a + v * w, 0) / total;
        group.lean[dim] = m;
        // Kish effective sample size keeps the consistency test honest when old ballots are down-weighted.
        const effective = total ** 2 / xs.reduce((a, [, w]) => a + w * w, 0);
        const variance = xs.length > 1 ? xs.reduce((a, [v, w]) => a + w * (v - m) ** 2, 0) / total * effective / Math.max(1, effective - 1) : 0;
        group.t[dim] = variance > 0 ? m / Math.sqrt(variance / effective) : 0;
        group.effective = Math.max(group.effective || 0, effective);
      }
    }
    return {award, stats, dims, subset, winners, groups: [...groups.values()]};
  }

  function heat(group, dim) {
    const value = group.lean[dim];
    const t = group.t[dim] || 0;
    const cell = el('span', 'heat' + (Math.abs(t) >= 2 ? ' strong' : ''), lean(value));
    if (value != null) {
      const alpha = Math.min(1, Math.abs(value) / (dim.startsWith('pos_') ? 0.3 : 0.2));
      cell.style.background = 'color-mix(in srgb, var(' + (value > 0 ? '--win' : '--loss') + ') ' + Math.round(alpha * 50) + '%, transparent)';
      cell.title = dimTitle(dim) + ': ' + lean(value) + (dim.startsWith('pos_') ? ' share points' : ' percentile points')
        + ' vs the panel over ' + group.dev[dim].length + ' ballots'
        + (Number(state.tRecency) ? ', recent seasons weighted more' : '') + (Math.abs(t) >= 2 ? ' · consistent lean' : '');
    }
    return cell;
  }

  function describe(group, dims) {
    const strong = dims.filter(dim => group.lean[dim] != null && Math.abs(group.t[dim]) >= 2 && Math.abs(group.lean[dim]) >= 0.05)
      .sort((a, b) => Math.abs(group.lean[b]) - Math.abs(group.lean[a]));
    if (!strong.length) return 'No consistent lean: this ' + (state.tGroup === 'publications' ? 'publication' : 'voter') + '’s picks look like the rest of the panel’s on every measure.';
    const word = dim => dim.startsWith('pos_') ? dimLabel(dim).toLowerCase() : 'higher ' + dimLabel(dim);
    const towards = strong.filter(dim => group.lean[dim] > 0).slice(0, 3).map(dim => word(dim) + ' (' + lean(group.lean[dim]) + ')');
    const away = strong.filter(dim => group.lean[dim] < 0).slice(0, 3).map(dim => word(dim) + ' (' + lean(group.lean[dim]) + ')');
    return [towards.length ? 'Leans towards ' + towards.join(', ') : '', away.length ? 'away from ' + away.join(', ') : '']
      .filter(Boolean).join('; ') + ', compared with the rest of the panel in the same races.';
  }

  function tendencyDetail(data, id) {
    const group = data.groups.find(item => item.id === id);
    const panel = el('section', 'vote-detail');
    const head = el('div', 'vote-detail-head');
    const close = el('a', 'vote-detail-close', '✕ Close');
    close.href = hashFor('tendencies', data.award);
    if (!group) {
      head.append(el('h2', '', id), close);
      panel.append(head, el('p', 'na', 'No ' + data.award + ' ballots for this selection.'));
      return panel;
    }
    const title = el('div');
    title.append(el('p', 'eyebrow', data.award + ' tendencies'), el('h2', '', group.label),
      el('p', 'text-small', group.ballots + ' ' + data.award + ' ballots · ' + ([...group.peers].join(', ') || '—')));
    const history = link('Full voting history →', state.tGroup, group.id);
    history.classList.add('vote-detail-history');
    const actions = el('div', 'vote-detail-actions');
    actions.append(history, close);
    head.append(title, actions);
    panel.append(head, el('p', 'tend-summary', describe(group, data.dims)));

    const chart = el('div', 'div-bars');
    for (const dim of data.dims) {
      const value = group.lean[dim];
      const row = el('div', 'div-row' + (Math.abs(group.t[dim] || 0) >= 2 ? ' strong' : ''));
      row.title = dimTitle(dim);
      const track = el('span', 'div-track');
      const fill = el('span', 'div-fill ' + (value >= 0 ? 'pos' : 'neg'));
      fill.style.width = Math.min(50, Math.abs(value || 0) * 100 * (dim.startsWith('pos_') ? 1 : 1.6)) + '%';
      track.append(fill);
      row.append(el('span', 'div-name', dimLabel(dim)), track, el('span', 'div-value', lean(value)));
      chart.append(row);
    }
    panel.append(chart, el('p', 'text-small', 'Bars show how far this ' + (state.tGroup === 'publications' ? 'publication' : 'voter')
      + '’s picks sit above (right) or below (left) the panel average. Stats are percentile points within each race’s candidates. Positions are points of ballot share. Bold rows are consistent across ballots (|t| ≥ 2).'
      + (Number(state.tRecency) ? ' Recent seasons count more: a ballot’s weight halves every ' + state.tRecency + ' seasons back.' : '')));

    const shown = data.stats.slice(0, 4);
    const rows = [...group.items].reverse().map(({race, record, score, panel: avg, lookup}) => {
      const [voterId, voter, , picks] = record;
      const chips = el('span', 'pick-chips');
      picks.forEach((pick, index) => {
        const stats = lookup[nameKey(pick)];
        const chip = el('span', 'pick-chip' + (nameKey(pick) === nameKey(race.winner) ? ' is-winner' : ''));
        chip.append(el('b', '', String(index + 1)), document.createTextNode(pick));
        if (stats) {
          chip.append(el('i', '', (stats.pos || '') + ' · ' + shown.map(stat => STAT_INFO[stat][0] + ' '
            + (stats[stat] == null ? '—' : Number(stats[stat]).toFixed(STAT_INFO[stat][2]))).join(' · ')));
        }
        chips.append(chip);
      });
      const row = [link(dash(race.season), 'seasons', race.season), chips,
        ...shown.map(stat => score[stat] == null ? '—' : Math.round(100 * score[stat]) + ' (' + lean(score[stat] - avg[stat]) + ')')];
      if (state.tGroup === 'publications') row.splice(1, 0, link(voter, 'voters', voterId));
      return row;
    });
    const labels = ['Season', 'Ballot', ...shown.map(stat => STAT_INFO[stat][0] + ' pct (vs panel)')];
    if (state.tGroup === 'publications') labels.splice(1, 0, 'Voter');
    const list = el('details', 'race-ballots');
    list.open = rows.length <= 15;
    list.append(el('summary', '', 'Ballots (' + rows.length + ')'), table('', labels, rows, 'ballot-list'));
    panel.append(list);
    return panel;
  }

  function renderTendencies() {
    if (!candidates) {
      if (candidatesFailed) { status.textContent = 'Player stats (award-candidates.json) could not be loaded.'; return; }
      status.textContent = 'Loading player stats…';
      loadCandidates().then(() => render());
      return;
    }
    const data = tendencyData();
    const award = data.award;
    const byOutlet = state.tGroup === 'publications';

    const intro = el('section', 'tend-card');
    intro.append(el('h2', '', 'What wins ' + AWARDS[award]),
      el('p', 'text-small', 'Each player is ranked against everyone who got a vote in the same race (0 = lowest, 100 = highest). The bars show where the winner ranked on average across '
        + data.subset.length + ' races, and the share of all ballot points that went to each position.'));
    const bars = el('div', 'tend-bars');
    for (const dim of data.dims) {
      const m = mean(data.winners[dim]);
      if (m == null) continue;
      const row = el('div', 'tend-bar-row');
      row.title = dimTitle(dim);
      row.append(el('span', 'tend-bar-name', dimLabel(dim)),
        bar(m, dim.startsWith('pos_') ? percent(m) + ' of points' : 'Winner avg ' + ordinal(Math.round(100 * m)) + ' pct'));
      bars.append(row);
    }
    intro.append(bars);
    content.append(intro);

    if (state.id) content.append(tendencyDetail(data, state.id));

    const card = el('section', 'tend-card');
    const head = el('div', 'tend-head');
    const text = el('div');
    text.append(el('h2', '', (byOutlet ? 'Publication' : 'Voter') + ' tendencies · ' + award),
      el('p', 'text-small', 'Each cell is the lean against the rest of the panel in the same races: + means their picks rank higher on that stat (or give more points to that position). Bold = consistent across ballots. Click a column to sort, or a row for the breakdown.'));
    const toggle = el('div', 'voting-pills');
    pills(toggle, [['voters', 'By voter'], ['publications', 'By publication']], state.tGroup, value => {
      state.tGroup = value;
      location.hash = hashFor('tendencies', award);
    });
    const recency = el('div', 'voting-pills');
    pills(recency, RECENCY, state.tRecency, value => { state.tRecency = value; render(); });
    recency.title = 'Weight recent seasons more. Light, Standard and Strong halve a ballot’s weight every 8, 4 or 2 seasons back from the latest season.';
    const controls = el('div', 'tend-controls');
    const recencyLabel = el('label', '', 'Recent seasons');
    recencyLabel.append(recency);
    controls.append(toggle, recencyLabel);
    head.append(text, controls);
    card.append(head);

    const minBallots = Number(minimum.value) || 1;
    const shown = data.groups.filter(group => group.ballots >= minBallots && (match(group.label) || [...group.peers].some(match)));
    const [sortKey, direction] = state.tSort || ['ballots', -1];
    const value = (group, key) => key === 'ballots' ? group.ballots : key === 'label' ? group.label.toLowerCase() : group.lean[key];
    shown.sort((a, b) => {
      const x = value(a, sortKey), y = value(b, sortKey);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * direction || b.ballots - a.ballots;
    });
    const wrapper = el('div', 'panel table-responsive');
    const grid = el('table', 'table leaderboard tend-matrix');
    const headRow = grid.createTHead().insertRow();
    headRow.append(el('th', '', '#'));
    for (const [key, label, title] of [['label', byOutlet ? 'Publication' : 'Voter'], ['ballots', 'Ballots'],
      ...data.dims.map(dim => [dim, dimLabel(dim), dimTitle(dim)])]) {
      const th = el('th');
      th.scope = 'col';
      if (title) th.title = title;
      if (key.startsWith('pos_') && key === 'pos_G') th.classList.add('tend-split');
      const button = el('button', 'sort-head', label + (key === sortKey ? (direction > 0 ? ' ▲' : ' ▼') : ''));
      button.type = 'button';
      button.addEventListener('click', () => {
        state.tSort = [key, key === sortKey ? -direction : key === 'label' ? 1 : -1];
        render();
      });
      th.append(button);
      headRow.append(th);
    }
    const body = grid.createTBody();
    shown.forEach((group, index) => {
      const tr = body.insertRow();
      if (group.id === state.id) tr.className = 'is-selected';
      tr.insertCell().textContent = index + 1;
      const name = el('a', 'ballot-drill', group.label);
      name.href = hashFor('tendencies', award + '~' + group.id);
      tr.insertCell().append(name);
      tr.insertCell().textContent = group.ballots;
      for (const dim of data.dims) {
        const cell = tr.insertCell();
        if (dim === 'pos_G') cell.className = 'tend-split';
        cell.append(heat(group, dim));
      }
      tr.addEventListener('click', event => {
        if (event.target.closest('a')) return;
        location.hash = hashFor('tendencies', award + '~' + group.id);
      });
    });
    wrapper.append(grid);
    if (!shown.length) wrapper.append(el('p', 'na', 'Nothing matches these filters. Try a lower minimum.'));
    card.append(wrapper);
    content.append(card);
    status.textContent = data.subset.length + ' ' + award + ' races with named ballots · showing ' + shown.length + ' of '
      + data.groups.length + (byOutlet ? ' publications' : ' voters') + (award === 'CPOY' ? ' · CPOY uses full-season stats (clutch splits are not archived per player)' : '');
    if (state.id) content.querySelector('.vote-detail')?.scrollIntoView({block: 'start'});
  }

  /* ---------- render ---------- */
  function render() {
    if (!races) return;
    stopChart();
    stopChart = () => {};
    content.replaceChildren();
    drawBars();
    if (state.tab === 'seasons') { renderSeason(); return; }
    if (state.tab === 'tendencies') { renderTendencies(); return; }
    const byOutlet = state.tab === 'publications';
    const subset = races.filter(race => race.ballots.length
      && (state.award === 'all' || race.award === state.award)
      && (state.scoreSeason === 'all' || race.season === state.scoreSeason));
    const ballots = subset.reduce((count, race) => count + race.ballots.length, 0);
    if (state.id) content.append(detail(subset, byOutlet, state.id));
    const board = leaderboard(subset, byOutlet);
    status.textContent = subset.length + ' races · ' + ballots.toLocaleString() + ' ballots · showing '
      + board.count + ' of ' + board.total + (byOutlet ? ' publications' : ' voters')
      + '. Click a column to sort, or a row for the full history.';
    content.append(board.wrapper);
  }

  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', render);

  let request;
  function apply(tab, arg) {
    state.tab = TABS.some(([key]) => key === tab) ? tab : tab === 'outlets' ? 'publications' : 'seasons';
    arg = arg ? decodeURIComponent(arg) : null;
    if (state.tab === 'tendencies') {
      const [awardKey, ...rest] = (arg || '').split('~');
      if (STAT_SETS[awardKey]) state.tAward = awardKey;
      state.id = rest.join('~') || null;
    } else if (state.tab === 'seasons') {
      state.id = null;
      state.season = allSeasons.includes(arg) ? arg : (allSeasons.includes(state.season) ? state.season : allSeasons[0]);
    } else {
      state.id = arg;
    }
    const heading = page.querySelector('#voting-title');
    heading.textContent = {seasons: 'Voting by season', voters: 'Voter success', publications: 'Publication success', tendencies: 'Voting tendencies'}[state.tab];
    render();
    if (state.id) content.querySelector('.vote-detail')?.scrollIntoView({block: 'start'});
  }

  window.votingTab = tab => TABS.some(([key]) => key === tab) ? tab : tab === 'outlets' ? 'publications' : 'seasons';
  window.loadAwardBallots = function (tab, arg) {
    if (races) { apply(tab, arg); return; }
    status.textContent = 'Loading award voting history…';
    if (!request) {
      request = fetch('award-ballots.json').then(response => {
        if (!response.ok) throw new Error('Unable to load the ballot archive');
        return response.json();
      }).then(data => {
        races = data;
        allSeasons = [...new Set(races.map(race => race.season))].sort().reverse();
        ballotSeasons = [...new Set(races.filter(race => race.ballots.length).map(race => race.season))].sort().reverse();
      }).catch(() => {
        status.textContent = 'The ballot archive could not be loaded. Open the app through its local server and reload.';
        request = null;
      });
    }
    request?.then(() => { if (races) apply(tab, arg); });
  };
})();
