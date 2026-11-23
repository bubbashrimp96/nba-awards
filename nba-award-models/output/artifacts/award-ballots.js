(() => {
  const page = document.getElementById('ballots-page');
  const form = page.querySelector('form');
  const status = page.querySelector('[role="status"]');
  const content = page.querySelector('.ballots-content');
  const { award, season, view, search, minimum, order } = form.elements;
  const fanVote = voter => /^(vote fan|nba fan vote|fan vote)$/i.test(voter);
  const percent = value => (100 * value).toFixed(1) + '%';
  const gap = value => (value > 0 ? '+' : '') + (100 * value).toFixed(1) + ' pp';
  const rate = (count, total) => total ? percent(count / total) : '—';
  const pairs = count => count * (count - 1) / 2;
  const newGroup = () => ({
    ballots: 0, wins: 0, omitted: 0, expected: 0,
    peers: new Set(), agreement: 0, comparisons: 0, panelAgreement: 0, alternatives: new Map(),
  });

  function table(caption, labels, rows) {
    const wrapper = el('div', 'panel table-responsive');
    const grid = el('table', 'table');
    grid.createCaption().textContent = caption;
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

  function match(value) {
    return value.toLowerCase().includes(search.value.trim().toLowerCase());
  }

  function summarize(races, byOutlet) {
    const groups = new Map();
    for (const race of races) {
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
        if (!groups.has(idKey)) groups.set(idKey, {...newGroup(), label});
        const group = groups.get(idKey);
        group.ballots++;
        group.wins += Number(rank === 1);
        group.omitted += Number(rank === 0);
        group.expected += (winnerVotes - Number(rank === 1)) / (total - 1);
        if (byOutlet) {
          group.peers.add(id);
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
          if (!winner && samePick) {
            const label = pick + ' · ' + race.season + ' ' + race.award;
            group.alternatives.set(label, samePick);
          }
        }
      }
    }
    return [...groups].map(([id, group]) => ({
      id, ...group, difference: (group.wins - group.expected) / group.ballots,
    }));
  }

  let historyVoter;
  let historyMetric = 'rate';
  let stopChart = () => {};

  function historyChart(races) {
    const voters = summarize(races, false).sort((a, b) => b.ballots - a.ballots);
    if (!voters.length) return;
    const years = [...new Set(races.filter(race => race.ballots.length).map(race => race.season))];
    const results = years.map(year => [year, summarize(races.filter(race => race.season === year), false)]);
    const panel = el('section', 'voter-history');
    const head = el('div', 'history-head');
    const title = el('div');
    title.append(el('h2', '', 'Winner picks by season'),
      el('p', 'text-small', 'A success means the voter ranked the eventual winner first.'));
    const controls = el('div', 'history-controls');
    const voter = el('select');
    const defaultVoter = voters.find(group => match(group.label)) || voters[0];
    if (!voters.some(group => group.id === historyVoter)) historyVoter = defaultVoter.id;
    for (const group of [...voters].sort((a, b) => a.label.localeCompare(b.label))) {
      voter.add(new Option(group.label, group.id));
    }
    voter.value = historyVoter;
    const metric = el('select');
    metric.add(new Option('Success rate', 'rate'));
    metric.add(new Option('Number of successes', 'count'));
    metric.value = historyMetric;
    for (const [label, control] of [['Voter', voter], ['Measure', metric]]) {
      const field = el('label', '', label);
      field.append(control);
      controls.append(field);
    }
    head.append(title, controls);
    const cards = el('div', 'history-stats');
    const legend = el('div', 'history-legend');
    legend.append(el('span', 'history-key', 'Selected voter'), el('span', 'history-key benchmark', 'Other voters in the same races'));
    const chart = el('div', 'history-chart');
    const canvas = el('canvas');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Winner picks by season. Exact values are in the season breakdown below.');
    const hover = el('div', 'history-hover');
    hover.hidden = true;
    chart.append(canvas, hover);
    const details = el('details', 'history-details');
    details.append(el('summary', '', 'Season breakdown'));
    const breakdown = el('div');
    details.append(breakdown);
    panel.append(head, cards, legend, chart, details);
    content.append(panel);

    let series = [];
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
      const voterColor = color('--history-voter');
      const panelColor = color('--history-panel');
      const left = 43, right = width - 19, top = 15, bottom = height - 34;
      const rateMode = metric.value === 'rate';
      const step = rateMode ? 0.25 : Math.max(1, Math.ceil(Math.max(...series.map(point => point?.ballots || 0)) / 4));
      const max = rateMode ? 1 : step * Math.ceil(Math.max(...series.map(point => point?.ballots || 1)) / step);
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
        if (index % stride === 0 && (index === years.length - 1 || x(years.length - 1) - x(index) >= 50)
          || index === years.length - 1) ctx.fillText(year.replace('-', '–'), x(index), bottom + 19);
      });
      const values = key => series.map(point => point ? point[key] / (rateMode ? point.ballots : 1) : null);
      const line = (data, stroke, dashed) => {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = dashed ? 2 : 3;
        ctx.setLineDash(dashed ? [5, 5] : []);
        ctx.beginPath();
        let penDown = false;
        data.forEach((value, index) => {
          if (value === null) { penDown = false; return; }
          if (penDown) ctx.lineTo(x(index), y(value));
          else ctx.moveTo(x(index), y(value));
          penDown = true;
        });
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = stroke;
        data.forEach((value, index) => {
          if (value === null) return;
          ctx.beginPath();
          ctx.arc(x(index), y(value), dashed ? 2.5 : 4, 0, 2 * Math.PI);
          ctx.fill();
        });
      };
      line(values('expected'), panelColor, true);
      line(values('wins'), voterColor, false);
    }

    function update() {
      historyVoter = voter.value;
      historyMetric = metric.value;
      const group = voters.find(person => person.id === historyVoter);
      series = results.map(([, groups]) => groups.find(person => person.id === historyVoter));
      cards.replaceChildren();
      const stats = [['Winner picks', group.wins + ' / ' + group.ballots],
        ['Success rate', rate(group.wins, group.ballots)], ['Vs other voters', gap(group.difference)]];
      for (const [label, value] of stats) {
        const card = el('div', 'history-stat');
        card.append(el('span', '', label), el('strong', '', value));
        cards.append(card);
      }
      breakdown.replaceChildren(table(group.label + ' · season breakdown',
        ['Season', 'Winner picks', 'Ballots', 'Success rate', 'Other voters', 'Gap'],
        results.flatMap(([year], index) => {
          const point = series[index];
          return point ? [[year, point.wins, point.ballots, rate(point.wins, point.ballots),
            rate(point.expected, point.ballots), gap(point.difference)]] : [];
        })));
      hover.hidden = true;
      draw();
    }

    chart.addEventListener('pointermove', event => {
      if (!pointPositions.length) return;
      const cursor = event.clientX - chart.getBoundingClientRect().left;
      const index = pointPositions.reduce((best, position, i) =>
        Math.abs(position - cursor) < Math.abs(pointPositions[best] - cursor) ? i : best, 0);
      const point = series[index];
      hover.textContent = years[index] + (point
        ? ' · ' + point.wins + ' of ' + point.ballots + ' winner picks · ' + rate(point.wins, point.ballots)
          + ' · Other voters: ' + rate(point.expected, point.ballots)
        : ' · No ballot in this selection');
      hover.hidden = false;
      hover.style.left = Math.max(0, Math.min(chart.clientWidth - hover.offsetWidth, pointPositions[index] - hover.offsetWidth / 2)) + 'px';
    });
    chart.addEventListener('pointerleave', () => { hover.hidden = true; });
    voter.addEventListener('change', update);
    metric.addEventListener('change', update);
    const resize = new ResizeObserver(draw);
    resize.observe(chart);
    const theme = new MutationObserver(draw);
    theme.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
    stopChart = () => { resize.disconnect(); theme.disconnect(); };
    update();
  }

  function renderGroups(races, byOutlet) {
    const selected = summarize(races, byOutlet)
      .filter(group => group.ballots >= Number(minimum.value) && match(group.label));
    const sort = {
      ballots: (a, b) => b.ballots - a.ballots,
      aligned: (a, b) => b.difference - a.difference,
      contrarian: (a, b) => a.difference - b.difference,
      agreement: (a, b) => (b.comparisons ? (b.agreement - b.panelAgreement) / b.comparisons : -Infinity)
        - (a.comparisons ? (a.agreement - a.panelAgreement) / a.comparisons : -Infinity),
    };
    selected.sort((a, b) => sort[order.value](a, b) || b.ballots - a.ballots || a.label.localeCompare(b.label));
    const rows = selected.map(group => {
      const link = el('button', 'ballot-drill', group.label);
      link.type = 'button';
      link.addEventListener('click', () => {
        view.value = 'ballots';
        search.value = group.label;
        render();
      });
      const row = [link, group.ballots, byOutlet ? group.peers.size : [...group.peers].join(', '),
        rate(group.wins, group.ballots), rate(group.expected, group.ballots),
        gap(group.difference), rate(group.omitted, group.ballots)];
      if (byOutlet) {
        const alternative = [...group.alternatives].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
        row.push(group.comparisons, rate(group.agreement, group.comparisons),
          group.comparisons ? gap((group.agreement - group.panelAgreement) / group.comparisons) : '—',
          alternative ? alternative[0] + ' (' + alternative[1] + ' pairs)' : '—');
      }
      return row;
    });
    if (!rows.length) {
      content.append(el('p', 'na', 'No groups match these filters.'));
      return;
    }
    const labels = [byOutlet ? 'Publication' : 'Voter', 'Ballots', byOutlet ? 'Voters' : 'Publications',
      'Winner first', 'Panel winner first', 'Vs panel', 'Winner omitted'];
    if (byOutlet) labels.push('Same-race pairs', 'Same first pick', 'Agreement vs panel', 'Most-shared alternative');
    content.append(table(byOutlet ? 'Publication voting patterns' : 'Voter voting patterns', labels, rows));
  }

  function renderRaces(races, totalsOnly) {
    for (const race of [...races].reverse()) {
      const entries = race.ballots.map((record, index) => ({record, rank: race.winner_ranks[index]}))
        .filter(({record: [, voter, outlet, picks]}) => [voter, outlet, ...picks].some(match));
      const voteRows = race.totals.filter(([, name]) => match(name));
      if (search.value.trim() && !(totalsOnly || !race.ballots.length ? voteRows.length : entries.length)) continue;
      const card = el('details', 'hp-notes');
      card.open = season.value !== 'all';
      card.append(el('summary', '', race.season + ' · ' + race.award + ' · ' + race.winner
        + (race.ballots.length ? ' · ' + race.ballots.length + ' ballots' : ' · totals only')));
      const source = el('a', 'source-link', 'Voting totals source ↗');
      source.href = race.source;
      card.append(source);
      if (totalsOnly || !race.ballots.length) {
        card.append(table(race.season + ' ' + race.award + ' vote totals', ['Rank', 'Candidate', 'Points'], voteRows));
      } else {
        if (!race.points_match) {
          card.append(el('p', 'text-small', 'Archived ballot points differ from the separate published totals for this race.'));
        }
        const slots = Math.max(0, ...race.ballots.map(ballot => ballot[3].length));
        const columns = Array.from({length: slots}, (_, index) => ordinal(index + 1) + ' pick');
        const showBallots = () => {
          const rows = entries.map(({record: [, voter, outlet, picks, points], rank}) => {
            const choices = columns.map((_, index) => {
              if (!picks[index]) return null;
              const choice = el('span', '', picks[index]);
              choice.title = points[index] + ' voting points';
              return choice;
            });
            return [voter, outlet || '—', ...choices, rank ? ordinal(rank) : 'Omitted'];
          });
          card.append(table(race.season + ' ' + race.award + ' ballots', ['Voter', 'Publication', ...columns, 'Winner rank'], rows));
        };
        if (card.open) showBallots();
        else card.addEventListener('toggle', () => {
          if (card.open) showBallots();
        }, {once: true});
      }
      content.append(card);
    }
    if (!content.children.length) content.append(el('p', 'na', 'No races match these filters.'));
  }

  let races;
  function render() {
    if (!races) return;
    const byOutlet = view.value === 'outlets';
    const summary = byOutlet || view.value === 'voters';
    search.placeholder = view.value === 'totals' ? 'Candidate' : summary ? (byOutlet ? 'Publication' : 'Voter') : 'Voter, publication or candidate';
    minimum.closest('label').hidden = !summary;
    order.closest('label').hidden = !summary;
    order.querySelector('[value="agreement"]').disabled = !byOutlet;
    if (!byOutlet && order.value === 'agreement') order.value = 'ballots';
    const selected = races.filter(race => (award.value === 'all' || award.value === race.award)
      && (season.value === 'all' || season.value === race.season));
    const ballots = selected.reduce((count, race) => count + race.ballots.length, 0);
    status.textContent = selected.length + ' award races · ' + ballots.toLocaleString() + ' archived ballots';
    stopChart();
    stopChart = () => {};
    content.replaceChildren();
    if (view.value === 'voters' && ballots) historyChart(selected);
    if (summary && !ballots) {
      content.append(el('p', 'na', 'Individual ballots are unavailable for this selection. Choose Vote totals to see the published results.'));
    } else if (summary) {
      renderGroups(selected, byOutlet);
    } else {
      renderRaces(selected, view.value === 'totals');
    }
  }

  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', render);
  let request;
  window.loadAwardBallots = function () {
    if (request) return;
    status.textContent = 'Loading award voting history…';
    request = fetch('award-ballots.json').then(response => {
      if (!response.ok) throw new Error('Unable to load the ballot archive');
      return response.json();
    }).then(data => {
      races = data;
      for (const year of [...new Set(races.map(race => race.season))].reverse()) {
        season.add(new Option(year.replace('-', '–'), year));
      }
      render();
    }).catch(() => {
      status.textContent = 'The ballot archive could not be loaded. Open the app through its local server and reload.';
      request = null;
    });
  };
})();
