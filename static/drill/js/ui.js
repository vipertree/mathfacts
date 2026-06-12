/* App-wide UI controls: page zoom and the sound on/off toggle.
 * Both persist in localStorage so a student's preference sticks. */
(function () {
  // ---- zoom: scales the whole page (px and all) via the CSS `zoom` property
  const ZOOM_MIN = 0.7, ZOOM_MAX = 1.8, ZOOM_STEP = 0.1;
  function getZoom() {
    const z = parseFloat(localStorage.getItem('mf-zoom'));
    return isNaN(z) ? 1 : z;
  }
  function setZoom(z) {
    z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 10) / 10));
    document.documentElement.style.zoom = z;
    try { localStorage.setItem('mf-zoom', z); } catch (e) {}
  }
  const zin = document.getElementById('zoom-in');
  const zout = document.getElementById('zoom-out');
  if (zin) zin.addEventListener('click', () => setZoom(getZoom() + ZOOM_STEP));
  if (zout) zout.addEventListener('click', () => setZoom(getZoom() - ZOOM_STEP));

  // ---- sound mute: a global flag MFSound (on the practice page) reads
  window.MFSoundMuted = localStorage.getItem('mf-muted') === '1';
  const sbtn = document.getElementById('sound-toggle');
  function paintSound() {
    if (!sbtn) return;
    sbtn.textContent = window.MFSoundMuted ? '🔇' : '🔊';
    sbtn.classList.toggle('muted', window.MFSoundMuted);
  }
  if (sbtn) sbtn.addEventListener('click', () => {
    window.MFSoundMuted = !window.MFSoundMuted;
    try { localStorage.setItem('mf-muted', window.MFSoundMuted ? '1' : '0'); } catch (e) {}
    paintSound();
  });
  paintSound();
})();
