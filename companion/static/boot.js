// Also works when the main bundle cannot load; no inline handlers or external dependencies.
window.addEventListener('error', event => {
  if (event.target?.id !== 'companion-app') return;
  document.querySelector('#loading').classList.add('hidden');
  const el=document.querySelector('#error');el.classList.remove('hidden');
  el.textContent = document.documentElement.lang === 'en'
    ? 'Could not load app.js. Extract the complete ZIP to a new folder and restart Companion.'
    : 'Nie udało się wczytać app.js. Rozpakuj pełną paczkę do nowego folderu i uruchom Companion ponownie.';
},true);
