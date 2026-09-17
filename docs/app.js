'use strict';
const schedule = JSON.parse(document.getElementById('schedule').textContent);
const $ = id => document.getElementById(id);
const passes = schedule.passes.map(p => ({...p, duration: (Date.parse(p.los_utc) - Date.parse(p.aos_utc)) / 1000}));
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
  const fragment = document.createDocumentFragment();
  for (const p of visible) {
    const tr = document.createElement('tr');
    tr.append(node('td', p.mission, 'mission-name'));
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
  const next = passes.find(p => Date.parse(p.los_utc) > now);
  $('next').textContent = next ? next.mission+' · '+formatTime(next.aos_utc) : 'No remaining passes';
  const seconds = next ? Math.round((Date.parse(next.aos_utc)-now)/1000) : 0;
  $('countdown').textContent = next ? (seconds <= 0 ? 'Pass in progress' : `In ${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}m`) + ' · '+zoneAbbreviation(next.aos_utc, zone) : 'Waiting for the next schedule update';
  const expired = !next, old = now-Date.parse(schedule.message_at) > 36*3600*1000;
  $('stale').hidden = !(expired || old);
  $('stale').textContent = expired ? 'This schedule has ended. A newer schedule has not been published yet.' : 'The latest published schedule email is over 36 hours old. Check its dates before relying on these times.';
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
update();
setInterval(update,30000);

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
