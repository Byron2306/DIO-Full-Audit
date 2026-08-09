/**
 * Seraph Shield Popup Script
 */

// Update stats
function updateStats() {
  chrome.runtime.sendMessage({ type: 'getStats' }, (stats) => {
    if (stats) {
      document.getElementById('pagesScanned').textContent = formatNumber(stats.pagesScanned);
      document.getElementById('threatsBlocked').textContent = formatNumber(stats.threatsBlocked);
      document.getElementById('phishingBlocked').textContent = formatNumber(stats.phishingBlocked);
      document.getElementById('malwareBlocked').textContent = formatNumber(stats.malwareBlocked);
    }
  });
}

function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
}

// Toggle handlers
document.querySelectorAll('.toggle').forEach(toggle => {
  toggle.addEventListener('click', () => {
    toggle.classList.toggle('active');
    const feature = toggle.dataset.feature;
    const enabled = toggle.classList.contains('active');
    
    chrome.storage.local.get('seraphSettings', (result) => {
      const settings = result.seraphSettings || {};
      settings[`${feature}Enabled`] = enabled;
      chrome.storage.local.set({ seraphSettings: settings });
    });
  });
});

// Load settings
chrome.storage.local.get('seraphSettings', (result) => {
  const settings = result.seraphSettings || {};
  document.querySelectorAll('.toggle').forEach(toggle => {
    const feature = toggle.dataset.feature;
    const enabled = settings[`${feature}Enabled`] !== false; // Default true
    toggle.classList.toggle('active', enabled);
  });
});

// Settings button
document.getElementById('openSettings').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

// Update stats on load and periodically
updateStats();
setInterval(updateStats, 2000);
