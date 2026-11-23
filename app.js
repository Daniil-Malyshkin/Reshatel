(async function bootReshатель() {
const PYODIDE_VERSION = '0.27.7';
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
let pyodide = null;
let currentSteps = [];
let selectedStep = -1;
const $ = (id) => document.getElementById(id);
const status = $('engineStatus');
const input = $('taskInput');
const solveBtn = $('solveBtn');

// Установка PWA: показываем кнопку только когда браузер сам сообщает,
// что приложение можно установить. После установки кнопка скрывается.
let deferredInstallPrompt = null;
const installButton = $('installBtn');
const isRunningInstalled = () => window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true;
if (installButton && isRunningInstalled()) installButton.hidden = true;
window.addEventListener('beforeinstallprompt', event => {
  if (isRunningInstalled()) return;
  event.preventDefault();
  deferredInstallPrompt = event;
  if (installButton) installButton.hidden = false;
});
installButton?.addEventListener('click', async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  try {
    const choice = await deferredInstallPrompt.userChoice;
    if (choice?.outcome === 'accepted') installButton.hidden = true;
  } catch (error) { console.warn('Не удалось открыть установку приложения:', error); }
  deferredInstallPrompt = null;
});
window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  if (installButton) installButton.hidden = true;
});
const getTaskText = () => String(input.value || '').replace(/\u00a0/g, ' ').replace(/([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)/g, s => '^' + [...s].map(ch => ch === '⁻' ? '-' : '⁰¹²³⁴⁵⁶⁷⁸⁹'.indexOf(ch)).join('')).trim();

function setStatus(kind, text) {
  status.className = `status ${kind || ''}`;
  status.querySelector('span').textContent = text;
  const splashStatus = $('startupStatus'); if (splashStatus) splashStatus.textContent = text;
}
function revealApplication() {
  const splash = $('startupScreen');
  if (splash) { splash.classList.add('is-hidden'); setTimeout(() => splash.remove(), 550); }
}
$('startupContinue')?.addEventListener('click', revealApplication);
$('startupRetry')?.addEventListener('click', () => { $('startupRetry').hidden = true; $('startupContinue').hidden = true; initEngine(); });
function toast(text) {
  const el = $('toast'); el.textContent = text; el.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('show'), 1900);
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function displayMath(value) {
  const superscripts = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻'};
  return String(value ?? '').replace(/\*\*/g, '^').replace(/\^\s*(-?\d+)/g, (_, digits) => [...digits].map(ch => superscripts[ch] || ch).join(''));
}
async function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = url; script.onload = resolve;
    script.onerror = () => reject(new Error('Не удалось загрузить локальный вычислительный модуль.'));
    document.head.appendChild(script);
  });
}
async function initEngine() {
  solveBtn.disabled = true;
  setStatus('', 'Загрузка математического ядра…');
  try {
    // Показываем интерфейс сразу: загрузка Pyodide/SymPy идёт в фоне.
    // Регистрация Service Worker не блокирует запуск вычислителя.
    if ('serviceWorker' in navigator && location.protocol !== 'file:') {
      navigator.serviceWorker.register('./service-worker.js').catch(error =>
        console.warn('Не удалось зарегистрировать офлайн-кэш:', error)
      );
    }
    await loadScript(PYODIDE_BASE + 'pyodide.js');
    pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
    setStatus('', 'Загрузка SymPy…');
    await pyodide.loadPackage('sympy');
    const response = await fetch('./solver.py');
    if (!response.ok) throw new Error('Не удалось открыть solver.py');
    const source = await response.text();
    pyodide.runPython(source);
    pyodide.runPython('from js import console\nconsole.log("Solver core ready")');
    solveBtn.disabled = false;
    setStatus('ready', navigator.onLine ? 'Вычислитель готов' : 'Работа без интернета');
    $('networkNote').textContent = 'Математические вычисления выполняются на устройстве';
    revealApplication();
  } catch (error) {
    console.error(error);
    setStatus('error', 'Не удалось загрузить вычислитель');
    $('networkNote').textContent = 'Для первой загрузки требуется интернет';
    $('startupStatus').textContent = 'Не удалось загрузить вычислитель. Проверь интернет.';
    $('startupRetry').hidden = false; $('startupContinue').hidden = false;
    toast('Не удалось подготовить вычислитель. Можно повторить загрузку.');
  }
}

function renderResult(result) {
  $('resultArea').hidden = false; $('welcomeNote').hidden = true;
  $('answerText').textContent = displayMath(result.answer || '—');
  currentSteps = result.steps || []; selectedStep = -1;
  $('stepCount').textContent = `${currentSteps.length} ${plural(currentSteps.length, 'шаг', 'шага', 'шагов')}`;
  $('clarifyBtn').disabled = true;
  $('stepsList').innerHTML = currentSteps.map((step, i) => `
    <article class="step-card" data-step="${i}" tabindex="0" role="button" aria-pressed="false">
      <div class="step-top"><span class="step-number">${i + 1}</span><span class="step-caption">ШАГ ${i + 1}</span></div>
      <div class="step-formula">${escapeHtml(displayMath(step.formula))}</div>
      ${step.explanation ? `<div class="step-explanation">${escapeHtml(step.explanation)}</div>` : ''}
    </article>`).join('');
  document.querySelectorAll('.step-card').forEach(card => {
    const choose = () => selectStep(Number(card.dataset.step));
    card.addEventListener('click', choose);
    card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } });
  });
}
function plural(n, one, few, many) {
  const n10=n%10,n100=n%100; if(n10===1&&n100!==11)return one; if(n10>=2&&n10<=4&&(n100<12||n100>14))return few; return many;
}
function selectStep(index) {
  selectedStep = index;
  document.querySelectorAll('.step-card').forEach((card, i) => {
    card.classList.toggle('selected', i === index); card.setAttribute('aria-pressed', String(i === index));
  });
  $('clarifyBtn').disabled = false;
}
function showClarification() {
  if (selectedStep < 0 || !currentSteps[selectedStep]) return;
  const step = currentSteps[selectedStep];
  let details = '';
  try {
    const json = JSON.stringify({formula:step.formula, explanation:step.explanation, task:getTaskText(), number:selectedStep+1});
    pyodide.globals.set('_clarify_data', json);
    details = pyodide.runPython(`d = __import__('json').loads(_clarify_data)\nbuild_step_clarification(d['formula'], d['explanation'], d['task'], d['number'])`).toString();
  } catch (e) { details = `${step.explanation}\n\nСопоставь формулу с предыдущим шагом и проверь, что преобразование сохраняет смысл исходной задачи.`; }
  $('modalTitle').textContent = `Уточнение шага ${selectedStep + 1}`;
  $('modalBody').textContent = details;
  $('clarifyModal').hidden = false;
}
function closeModal() { $('clarifyModal').hidden = true; }
async function solve() {
  const task = getTaskText(); if (!task) { input.focus(); toast('Сначала введи математическую задачу'); return; }
  if (!pyodide) { toast('Вычислитель ещё загружается'); return; }
  solveBtn.disabled = true; solveBtn.querySelector('span').textContent = 'Считаю…';
  try {
    pyodide.globals.set('_user_task', task);
    const json = pyodide.runPython("__import__('json').dumps(solve_for_web(_user_task))").toString();
    const result = JSON.parse(json);
    renderResult(result);
    saveHistory(task, result.answer || '—');
    $('userAnswer').value = ''; $('verifyFeedback').textContent = '';
    $('resultArea').scrollIntoView({behavior:'smooth', block:'start'});
  } catch (error) {
    console.error(error);
    const message = String(error.message || '');
    toast(message.length > 100 ? 'Не удалось разобрать пример. Проверь запись и скобки.' : (message || 'Не удалось решить задачу'));
  } finally { solveBtn.disabled = false; solveBtn.querySelector('span').textContent = 'Решить'; }
}

function insertAtCursor(value) {
  input.focus();

  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? input.value.length;
  const selected = input.value.slice(start, end);
  let text = value;
  let cursorOffset = null;

  // Кнопки клавиатуры раньше использовали шаблоны MathLive (#@ и #?).
  // В обычном textarea превращаем их в понятную текстовую математику.
  const templates = {
    '\\sqrt{#@}': { text: `sqrt(${selected})`, inside: 5 + selected.length },
    '\\sin(#@)': { text: `sin(${selected})`, inside: 4 + selected.length },
    '\\cos(#@)': { text: `cos(${selected})`, inside: 4 + selected.length },
    '\\tan(#@)': { text: `tan(${selected})`, inside: 4 + selected.length },
    '\\log(#@)': { text: `log(${selected})`, inside: 4 + selected.length },
    '\\left|#@\\right|': { text: `abs(${selected})`, inside: 4 + selected.length },
    '#@^{#?}': { text: `${selected}²`, inside: selected.length + 1 },
    '#@_{#?}': { text: `${selected}_()`, inside: selected.length + 2 },
    '\\frac{#?}{#?}': { text: `( )/( )`, inside: 2 },
    '\\sqrt[#?]{#@}': { text: 'root()()', inside: 5 },
  };
  const template = templates[String(value).trim()];
  if (template) {
    text = template.text;
    cursorOffset = template.inside;
  } else {
    text = text.replaceAll('\\times', '*').replaceAll('\\div', '/').replaceAll('\\pi', 'pi');
  }

  input.setRangeText(text, start, end, 'end');
  if (cursorOffset !== null) {
    const cursor = start + cursorOffset;
    input.setSelectionRange(cursor, cursor);
  }
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
const HISTORY_KEY = 'reshatel_history_v11';
let memoryHistory = [];
function readHistory() {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) { memoryHistory = parsed.slice(0, 30); return memoryHistory; }
    }
    for (const key of ['reshatel_history', 'reshatel_history_v10']) {
      const old = localStorage.getItem(key);
      if (old) {
        const parsed = JSON.parse(old);
        if (Array.isArray(parsed)) {
          memoryHistory = parsed.slice(0, 30);
          localStorage.setItem(HISTORY_KEY, JSON.stringify(memoryHistory));
          return memoryHistory;
        }
      }
    }
  } catch (error) { console.warn('Постоянное хранилище истории недоступно:', error); }
  return memoryHistory;
}
function saveHistory(task, answer) {
  const items = readHistory().filter(item => item.task !== task);
  items.unshift({ task, answer, date: new Date().toLocaleString('ru-RU') });
  memoryHistory = items.slice(0, 30);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(memoryHistory));
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    if (!Array.isArray(saved) || saved.length !== memoryHistory.length) throw new Error('Проверка сохранения истории не пройдена');
  } catch (error) {
    console.warn('Не удалось сохранить историю постоянно; временная копия сохранена.', error);
    toast('История доступна до закрытия этой вкладки');
  }
  renderHistory();
}
function renderHistory() {
  const host = $('historyList'); if (!host) return;
  const items = readHistory();
  const clearButton = $('clearHistoryBtn');
  if (clearButton) clearButton.disabled = !items.length;
  if (!items.length) { host.innerHTML = '<p class="history-empty">Здесь появятся решённые задачи.</p>'; return; }
  host.innerHTML = items.map((item, i) => `<button class="history-item" type="button" data-history="${i}"><span class="history-task">${escapeHtml(displayMath(item.task)).replaceAll('\n',' ↵ ')}</span><span class="history-answer">${escapeHtml(displayMath(item.answer))}</span><small>${escapeHtml(item.date || '')}</small></button>`).join('');
  host.querySelectorAll('[data-history]').forEach(btn => btn.addEventListener('click', () => {
    const item = readHistory()[Number(btn.dataset.history)]; if (!item) return;
    input.value = displayMath(item.task); input.focus();
    $('resultArea').hidden = true; $('welcomeNote').hidden = false;
    toast('Задача восстановлена из истории');
  }));
}
$('clearHistoryBtn')?.addEventListener('click', () => {
  memoryHistory = [];
  try { localStorage.removeItem(HISTORY_KEY); } catch (error) { console.warn(error); }
  renderHistory(); toast('История очищена');
});
function answerKey(value) {
  return String(value || '').toLowerCase()
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, ch => '^' + '⁰¹²³⁴⁵⁶⁷⁸⁹'.indexOf(ch))
    .replace(/\s+/g, '').replace(/[·×*]/g, '').replace(/,/g, '.')
    .replace(/−/g, '-').replace(/\\left|\\right/g, '')
    .replace(/[{}]/g, '').replace(/π/g, 'pi');
}
$('verifyBtn')?.addEventListener('click', () => {
  const entered = displayMath($('userAnswer').value.trim()); const expected = $('answerText').textContent.trim();
  const feedback = $('verifyFeedback');
  if (!entered) { feedback.textContent = 'Сначала введи свой ответ.'; feedback.className = 'verify-feedback'; return; }
  const ok = answerKey(entered) === answerKey(expected);
  feedback.textContent = ok ? 'Верно! Ответ совпадает.' : `Пока неверно. Правильный ответ: ${expected}`;
  feedback.className = `verify-feedback ${ok ? 'correct' : 'incorrect'}`;
});
renderHistory();

function formatInputPowers() {
  const before = input.value;
  const cursor = input.selectionStart ?? before.length;
  const left = before.slice(0, cursor);
  const right = before.slice(cursor);
  const toSuperscript = text => text.replace(/\^(-?\d+)/g, (_, digits) => [...digits].map(ch => ({'-':'⁻','0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}[ch])).join(''));
  const formattedLeft = toSuperscript(left);
  const formattedRight = toSuperscript(right);
  const formatted = formattedLeft + formattedRight;
  if (formatted !== before) {
    input.value = formatted;
    input.setSelectionRange(formattedLeft.length, formattedLeft.length);
  }
}
input.addEventListener('input', formatInputPowers);

document.querySelectorAll('.math-key[data-insert]').forEach(key => {
  key.addEventListener('mousedown', e => e.preventDefault());
  key.addEventListener('click', () => insertAtCursor(key.dataset.insert));
});
document.querySelectorAll('.math-key[data-action]').forEach(key => {
  key.addEventListener('mousedown', e => e.preventDefault());
  key.addEventListener('click', () => {
    if (key.dataset.action === 'clear') { input.value = ''; input.focus(); }
    if (key.dataset.action === 'toggle-case') {
      const upper = key.dataset.upper !== 'true';
      key.dataset.upper = String(upper);
      document.querySelectorAll('.keypad-letters [data-letter]').forEach(letter => {
        const value = upper ? letter.dataset.letter.toUpperCase() : letter.dataset.letter;
        letter.textContent = value; letter.dataset.insert = value;
      });
      key.classList.toggle('active', upper);
      input.focus();
    }
    if (key.dataset.action === 'backspace') {
      input.focus();
      if (typeof input.executeCommand === 'function') input.executeCommand('deleteBackward');
      else { const start = input.selectionStart ?? input.value.length, end = input.selectionEnd ?? input.value.length; if (start !== end) input.setRangeText('', start, end, 'end'); else if (start > 0) input.setRangeText('', start - 1, start, 'end'); }
    }
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
});
document.querySelectorAll('.keyboard-tab').forEach(tab => {
  tab.addEventListener('mousedown', e => e.preventDefault());
  tab.addEventListener('click', () => {
    const selected = tab.dataset.tab;
    document.querySelectorAll('.keyboard-tab').forEach(item => {
      const active = item === tab;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.keyboard-page').forEach(page => {
      const active = page.id === (selected === 'numbers' ? 'numbersPanel' : 'lettersPanel');
      page.classList.toggle('active', active);
      page.hidden = !active;
    });
  });
});

solveBtn.addEventListener('click', solve);
input.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    solve();
    return;
  }
  // Явно вставляем перевод строки: так Enter работает одинаково в разных браузерах.
  if (typeof input.getValue !== 'function') {
    e.preventDefault();
    insertAtCursor('\n');
  }
});
$('newlineBtn').addEventListener('click', () => insertAtCursor('\n'));
// В обычном текстовом поле явно обрабатываем вставку из PDF/Word и буфера обмена.
if (typeof input.getValue !== 'function') {
  input.addEventListener('paste', () => {
    setTimeout(() => input.dispatchEvent(new Event('input', { bubbles: true })), 0);
  });
}
$('clearBtn').addEventListener('click', () => {
  if (typeof input.setValue === 'function') input.setValue('');
  else input.value = '';
  $('resultArea').hidden = true; $('welcomeNote').hidden = false; input.focus();
});
$('clarifyBtn').addEventListener('click', showClarification);
$('closeModal').addEventListener('click', closeModal); $('modalDone').addEventListener('click', closeModal);
$('clarifyModal').addEventListener('click', e => { if (e.target.dataset.close) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
$('copyBtn').addEventListener('click', async () => {
  const value = $('answerText').textContent || '';
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
    } else {
      const helper = document.createElement('textarea');
      helper.value = value; helper.setAttribute('readonly', '');
      helper.style.position = 'fixed'; helper.style.opacity = '0';
      document.body.appendChild(helper); helper.select();
      const copied = document.execCommand('copy'); helper.remove();
      if (!copied) throw new Error('copy command failed');
    }
    toast('Ответ скопирован');
  } catch (error) { console.warn(error); toast('Не удалось скопировать ответ'); }
});
window.addEventListener('online', () => { if (pyodide) setStatus('ready','Вычислитель готов'); });
window.addEventListener('offline', () => { if (pyodide) setStatus('ready','Работа без интернета'); });
revealApplication();
initEngine();
})();
