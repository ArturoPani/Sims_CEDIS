// Carga el nombre del usuario actual y lo muestra en el nav
(async function() {
  try {
    const res = await fetch('/me');
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById('navUser');
      if (el) {
        el.textContent = '👤 ' + data.username;
        if (data.is_admin) {
          const link = document.createElement('a');
          link.href = '/admin';
          link.textContent = ' ⚙️ Admin';
          link.style.cssText = 'color:#00d4ff; margin-left:10px; font-size:12px; text-decoration:none;';
          el.appendChild(link);
        }
      }
    }
  } catch(e) { /* silenciar */ }
})();
