'use strict';
const schedule = JSON.parse(document.getElementById('schedule').textContent);
const $ = id => document.getElementById(id);
const passes = schedule.passes.map(p => ({...p, duration: (Date.parse(p.los_utc) - Date.parse(p.aos_utc)) / 1000}));
const {passKey, passState, countdownUntil} = window.SmopsPassStatus;
const missions = [...new Set(passes.map(p => p.mission))].sort();
let sort = 'aos_utc', direction = 1;
let zone = 'UTC';
function formatTime(value, timeZone = zone) {
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone, year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));
  const fields = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${fields.year}-${fields.month}-${fields.day}, ${fields.hour}:${fields.minute}:${fields.second}`;
}
function zoneAbbreviation(value, timeZone) {
  return new Intl.DateTimeFormat('en-US', {timeZone, timeZoneName:'short'}).formatToParts(new Date(value)).find(part => part.type === 'timeZoneName').value;
}
function timeLine(value, timeZone, secondary = false) {
  const line = node('div', '', 'time-line' + (secondary ? 'time-secondary' : ''));
  const [date, time] = formatTime(value, timeZone).split(', ');
  line.append(node('span', date+' ', 'time-date'), node('span', time+' '),
    node('span', zoneAbbreviation(value, timeZone), 'time-zone'));
  return line;
}
function node(tag, text, className) {
  const result = document.createElement(tag);
  result.textContent = text;
  if (className) result.className = className;
  return result;
}
function priority(value) {
  const kind = value.startsWith('Delete') ? 'delete' : value.includes('Conflict') ? 'conflict' : '';
  return node('span', value.replace('_', ' · '), 'priority ' + kind);
}
function update() {
  const selectedZone = $('zone').value;
  const bothZones = selectedZone === 'both';
  zone = bothZones ? 'America/Denver' : selectedZone === 'local' ? Intl.DateTimeFormat().resolvedOptions().timeZone : selectedZone;
  const now = Date.now(), query = $('search').value.toLowerCase();
  const visible = passes.filter(p => (!$('mission').value || p.mission === $('mission').value)
    && (!$('upcoming').checked || Date.parse(p.los_utc) > now)
    && [p.mission,p.uhf,p.s_band].join(' ').toLowerCase().includes(query));
  visible.sort((a,b) => direction * (typeof a[sort] === 'number' ? a[sort]-b[sort] : a[sort].localeCompare(b[sort])));
  const activeKeys = new Set(passState(passes, now).active.map(passKey));
  const fragment = document.createDocumentFragment();
  for (const p of visible) {
    const tr = document.createElement('tr');
    const missionCell = node('td', p.mission, 'mission-name');
    if (activeKeys.has(passKey(p))) {
      tr.className = 'pass-active';
      missionCell.append(node('span', 'IN PASS', 'in-pass-badge'));
    }
    tr.append(missionCell);
    for (const key of ['aos_utc','los_utc']) {
      const td = document.createElement('td');
      td.append(timeLine(p[key], bothZones ? 'UTC' : zone));
      if (bothZones) td.append(timeLine(p[key], 'America/Denver', true));
      tr.append(td);
    }
    tr.append(node('td', Math.floor(p.duration/60)+'m '+String(p.duration%60).padStart(2,'0')+'s'));
    const elevation = node('td', p.elevation_deg.toFixed(2)+'°');
    if (p.s_band_candidate) {
      const star = node('span', ' ★', 'star');
      star.title = 'S-band downlink candidate';
      star.setAttribute('aria-label', 'S-band downlink candidate');
      elevation.append(star);
    }
    tr.append(elevation);
    for (const key of ['uhf','s_band']) {
      const td = document.createElement('td'); td.append(priority(p[key])); tr.append(td);
    }
    fragment.append(tr);
  }
  $('rows').replaceChildren(fragment);
  $('empty').hidden = visible.length > 0;
  $('shown').textContent = `${visible.length} of ${passes.length} passes`;
  $('zone-label').textContent = bothZones ? 'UTC + Mountain time (MST/MDT)' : 'Times in '+zone.replace('_',' ');
  $('updated').textContent = 'Last updated: '+new Date(schedule.message_at).toISOString().slice(0,19).replace('T',' ')+' UTC';
  $('range').textContent = `${formatTime(passes[0].aos_utc).split(',')[0]} – ${formatTime(passes[passes.length-1].los_utc).split(',')[0]} (${zone})`;
  updateSummary(now, passState(passes, now));
}
function renderActiveBanner(active) {
  $('active-banner').hidden = active.length === 0;
  $('active-heading').textContent = active.length === 1 ? 'PASS IN PROGRESS' : `${active.length} PASSES IN PROGRESS`;
  const cards = document.createDocumentFragment();
  for (const pass of active) {
    const card = node('article', '', 'active-pass');
    const info = node('div', '', 'active-info');
    info.append(node('h3', pass.mission));
    const times = node('div', '', 'active-los');
    times.append(node('span', 'LOS ' + formatTime(pass.los_utc, 'UTC') + ' UTC'),
      node('span', formatTime(pass.los_utc, 'America/Denver') + ' ' + zoneAbbreviation(pass.los_utc, 'America/Denver')));
    info.append(times);
    const timerGroup = node('div', '', 'active-timer-group');
    const timer = node('span', '', 'active-timer');
    timer.dataset.los = pass.los_utc;
    timer.setAttribute('role', 'timer');
    timer.setAttribute('aria-live', 'off');
    timer.setAttribute('aria-label', pass.mission + ' time remaining until LOS');
    timerGroup.append(timer, node('span', 'UNTIL LOS', 'active-timer-label'));
    card.append(info, timerGroup);
    cards.append(card);
  }
  $('active-passes').replaceChildren(cards);
}
function updateSummary(now, state) {
  const next = state.next;
  $('next').textContent = next ? next.mission+' · '+formatTime(next.aos_utc) : state.active.length ? 'No later passes' : 'No remaining passes';
  $('countdown').textContent = next ? countdownUntil(next.aos_utc, now)+' until AOS · '+zoneAbbreviation(next.aos_utc, zone) : state.active.length ? 'Current pass windows shown above' : 'Waiting for the next schedule update';
  const old = now-Date.parse(schedule.message_at) > 36*3600*1000;
  $('stale').hidden = !(state.expired || old);
  $('stale').textContent = state.expired ? 'This schedule has ended. A newer schedule has not been published yet.' : 'The latest published schedule email is over 36 hours old. Check its dates before relying on these times.';
}
let liveSignature = null;
function tick() {
  const now = Date.now();
  const state = passState(passes, now);
  const signature = JSON.stringify([state.active.map(passKey), state.next && passKey(state.next)]);
  if (signature !== liveSignature) {
    liveSignature = signature;
    renderActiveBanner(state.active);
    update();
  }
  for (const timer of document.querySelectorAll('.active-timer')) {
    timer.textContent = countdownUntil(timer.dataset.los, now);
  }
  updateSummary(now, state);
}

for (const mission of missions) $('mission').append(new Option(mission,mission));
$('total').textContent = passes.length;
$('missions').textContent = missions.length;
if (schedule.source_generated) $('source-time').textContent = 'Source schedule file generated '+schedule.source_generated+'.';
for (const id of ['mission','zone','upcoming']) $(id).addEventListener('change',update);
$('search').addEventListener('input',update);
for (const button of document.querySelectorAll('[data-sort]')) button.addEventListener('click',()=>{
  direction = sort===button.dataset.sort ? -direction : 1; sort=button.dataset.sort;
  for (const other of document.querySelectorAll('[data-sort]')) {
    other.parentElement.removeAttribute('aria-sort');
    const arrow=other.querySelector('span'); if(arrow) arrow.remove();
  }
  button.parentElement.setAttribute('aria-sort',direction===1?'ascending':'descending');
  button.append(node('span',direction===1?' ↑':' ↓'));
  update();
});
tick();
setInterval(tick,1000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });

const themePreference = window.matchMedia('(prefers-color-scheme: dark)');
function updateThemeToggle() {
  const theme = document.documentElement.dataset.theme;
  const dark = theme ? theme === 'dark' : themePreference.matches;
  $('theme-toggle').setAttribute('aria-pressed', String(dark));
  $('theme-toggle').textContent = dark ? '☀ Light mode' : '☾ Dark mode';
}
$('theme-toggle').addEventListener('click', () => {
  const theme = $('theme-toggle').getAttribute('aria-pressed') === 'true' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('smops-theme', theme); } catch (_) {}
  updateThemeToggle();
});
themePreference.addEventListener('change', updateThemeToggle);
updateThemeToggle();
