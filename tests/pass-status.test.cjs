const test = require('node:test');
const assert = require('node:assert/strict');
const {passKey, passState, countdownUntil} = require('../web/pass-status.js');
const pass = {mission:'DEMO', aos_utc:'2026-09-17T20:00:00Z', los_utc:'2026-09-17T20:10:00Z'};
const time = text => Date.parse(text);

test('AOS is inclusive and LOS is exclusive', () => {
  assert.equal(passState([pass], time(pass.aos_utc)-1).active.length, 0);
  assert.equal(passState([pass], time(pass.aos_utc)).active.length, 1);
  assert.equal(passState([pass], time(pass.los_utc)-1).active.length, 1);
  assert.equal(passState([pass], time(pass.los_utc)).active.length, 0);
});
test('an active final pass does not mark the schedule expired', () => {
  const state = passState([pass], time('2026-09-17T20:05:00Z'));
  assert.equal(state.next, null);
  assert.equal(state.expired, false);
  assert.equal(passState([pass], time(pass.los_utc)).expired, true);
});
test('overlapping passes are all shown, soonest LOS first', () => {
  const second = {...pass, mission:'SECOND', los_utc:'2026-09-17T20:06:00Z'};
  const input = [pass, second];
  assert.deepEqual(passState(input, time('2026-09-17T20:05:00Z')).active, [second, pass]);
  assert.deepEqual(input, [pass, second]);
});
test('next pass is truly upcoming, even with overlapping active passes and unsorted input', () => {
  const later = {...pass, mission:'LATER', aos_utc:'2026-09-17T21:00:00Z', los_utc:'2026-09-17T21:10:00Z'};
  const soon = {...pass, mission:'SOON', aos_utc:'2026-09-17T20:08:00Z', los_utc:'2026-09-17T20:18:00Z'};
  assert.equal(passState([later, pass, soon], time('2026-09-17T20:05:00Z')).next, soon);
});
test('countdown rounds fractional seconds up and never goes negative', () => {
  assert.equal(countdownUntil(pass.los_utc, time('2026-09-17T20:00:00Z')), '10:00');
  assert.equal(countdownUntil(pass.los_utc, time(pass.los_utc)-1), '00:01');
  assert.equal(countdownUntil(pass.los_utc, time(pass.los_utc)), '00:00');
  assert.equal(countdownUntil(pass.los_utc, time(pass.los_utc)+1000), '00:00');
  assert.equal(countdownUntil(pass.los_utc, time('2026-09-17T18:59:59Z')), '1:10:01');
});
test('midnight and DST do not affect UTC pass windows', () => {
  const midnight = {...pass, aos_utc:'2026-12-31T23:59:00Z', los_utc:'2027-01-01T00:03:00Z'};
  assert.equal(passState([midnight], time('2027-01-01T00:00:00Z')).active.length, 1);
  const fallBack = {...pass, aos_utc:'2026-11-01T07:59:00Z', los_utc:'2026-11-01T08:03:00Z'};
  assert.equal(countdownUntil(fallBack.los_utc, time('2026-11-01T08:00:00Z')), '03:00');
});
test('after a suspended tab resumes, status uses wall-clock time', () => {
  const before = passState([pass], time(pass.aos_utc)-10000);
  const after = passState([pass], time(pass.los_utc)+10000);
  assert.equal(before.next, pass);
  assert.equal(after.next, null);
  assert.deepEqual(after.active, []);
  assert.equal(after.expired, true);
});
test('pass identity distinguishes overlapping passes of the same mission', () => {
  assert.notEqual(passKey(pass), passKey({...pass, aos_utc:'2026-09-17T20:01:00Z'}));
});
