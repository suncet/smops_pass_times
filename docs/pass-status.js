/* Pass windows are inclusive at AOS and exclusive at LOS. All times are UTC. */
(function (root) {
  'use strict';
  function passKey(pass) {
    return [pass.mission, pass.aos_utc, pass.los_utc].join('|');
  }
  function passState(passes, now) {
    const active = passes.filter(pass => Date.parse(pass.aos_utc) <= now && now < Date.parse(pass.los_utc));
    const future = passes.filter(pass => Date.parse(pass.aos_utc) > now);
    active.sort((a, b) => Date.parse(a.los_utc) - Date.parse(b.los_utc));
    future.sort((a, b) => Date.parse(a.aos_utc) - Date.parse(b.aos_utc));
    return {active, next: future[0] || null, expired: passes.every(pass => Date.parse(pass.los_utc) <= now)};
  }
  function countdownUntil(timestamp, now) {
    const seconds = Math.max(0, Math.ceil((Date.parse(timestamp) - now) / 1000));
    const hours = Math.floor(seconds / 3600);
    const minutes = String(Math.floor(seconds % 3600 / 60)).padStart(2, '0');
    const remainder = String(seconds % 60).padStart(2, '0');
    return (hours ? hours + ':' : '') + minutes + ':' + remainder;
  }
  const api = {passKey, passState, countdownUntil};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SmopsPassStatus = api;
})(typeof window !== 'undefined' ? window : globalThis);
