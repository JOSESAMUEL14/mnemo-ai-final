// Keyboard shortcuts for Mnemo AI
document.addEventListener('keydown', function(e) {
  // Don't trigger if typing in input field
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;

  // Ctrl + J = Journal
  if (e.ctrlKey && e.key === 'j') { 
    e.preventDefault(); 
    window.location.href = '/journal'; 
  }
  // Ctrl + C = Chat
  if (e.ctrlKey && e.key === 'c') { 
    e.preventDefault(); 
    window.location.href = '/chat'; 
  }
  // Ctrl + I = Insights
  if (e.ctrlKey && e.key === 'i') { 
    e.preventDefault(); 
    window.location.href = '/insights'; 
  }
  // Ctrl + D = Dashboard
  if (e.ctrlKey && e.key === 'd') { 
    e.preventDefault(); 
    window.location.href = '/dashboard'; 
  }
  // ? = Show help modal
  if (e.key === '?' && !e.ctrlKey && !e.metaKey) { 
    e.preventDefault(); 
    showShortcutsHelp(); 
  }
});

// Help modal function
function showShortcutsHelp() {
  const existing = document.getElementById('shortcuts-help');
  if (existing) { 
    existing.remove(); 
    return; 
  }

  const modal = document.createElement('div');
  modal.id = 'shortcuts-help';
  modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:9999;';

  modal.innerHTML = `
    <div style="background:var(--bg-card, #1a1a2e);border:1px solid var(--border-card, rgba(255,255,255,0.1));border-radius:16px;padding:32px;max-width:400px;width:90%;color:var(--text-primary, #fff);">
      <h2 style="margin:0 0 16px 0;font-size:20px;">⌨️ Keyboard Shortcuts</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div><strong>Ctrl+J</strong></div><div>Journal</div>
        <div><strong>Ctrl+C</strong></div><div>Chat</div>
        <div><strong>Ctrl+I</strong></div><div>Insights</div>
        <div><strong>Ctrl+D</strong></div><div>Dashboard</div>
        <div><strong>?</strong></div><div>Help</div>
      </div>
      <button onclick="this.closest('#shortcuts-help').remove()" style="margin-top:20px;padding:8px 24px;background:#7c3aed;color:#fff;border:none;border-radius:8px;cursor:pointer;">Close</button>
    </div>
  `;

  document.body.appendChild(modal);
}