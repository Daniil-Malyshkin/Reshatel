(async function bootReshатель() {
const PYODIDE_VERSION = '314.0.7';
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
let pyodide = null;
let currentSteps = [];
let selectedStep = -1;
let deferredInstall = null;
const $ = (id) => document.getElementById(id);
const status = $('engineStatus');
const input = $('taskInput');
const solveBtn = $('solveBtn');
const getTaskText = () => String(input.value || '').replace(/\u00a0/g, ' ').trim();

function setStatus(kind, text) {
  status.className = `status ${kind || ''}`;
  status.querySelector('span').textContent = text;
}
function toast(text) {
  const el = $('toast'); el.textContent = text; el.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('show'), 1900);
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
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
    if ('serviceWorker' in navigator && location.protocol !== 'file:') {
      await navigator.serviceWorker.register('./service-worker.js');
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller && !sessionStorage.getItem('sw-reloaded')) {
        sessionStorage.setItem('sw-reloaded', '1'); location.reload(); return;
      }
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
  } catch (error) {
    console.error(error);
    setStatus('error', 'Не удалось загрузить вычислитель');
    $('networkNote').textContent = 'Для первой загрузки требуется интернет';
    toast('Не удалось подготовить вычислитель. Проверь подключение и обнови страницу.');
  }
}

function renderResult(result) {
  $('resultArea').hidden = false; $('welcomeNote').hidden = true;
  $('answerText').textContent = result.answer || '—';
  currentSteps = result.steps || []; selectedStep = -1;
  $('stepCount').textContent = `${currentSteps.length} ${plural(currentSteps.length, 'шаг', 'шага', 'шагов')}`;
  $('clarifyBtn').disabled = true;
  $('stepsList').innerHTML = currentSteps.map((step, i) => `
    <article class="step-card" data-step="${i}" tabindex="0" role="button" aria-pressed="false">
      <div class="step-top"><span class="step-number">${i + 1}</span><span class="step-caption">ШАГ ${i + 1}</span></div>
      <div class="step-formula">${escapeHtml(step.formula)}</div>
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
    renderResult(JSON.parse(json));
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
    '#@^{#?}': { text: `${selected}^()`, inside: selected.length + 2 },
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
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeModal(); closeInstallHelp(); } });
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
function isAppleMobile() {
  return /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}
function showInstallHelp() {
  const body = $('installHelpBody');
  if (isAppleMobile()) {
    body.textContent = '1. Открой «Решатель» в Safari.\n2. Нажми кнопку «Поделиться» (квадрат со стрелкой вверх).\n3. Выбери «На экран Домой» или «Добавить на экран Домой».\n4. Подтверди добавление кнопкой «Добавить».\n\nЕсли такого пункта нет, прокрути список действий вниз или открой сайт именно в Safari.';
  } else if (/Android/i.test(navigator.userAgent)) {
    body.textContent = '1. Открой сайт в Chrome.\n2. Нажми меню ⋮.\n3. Выбери «Установить приложение» или «Добавить на главный экран».\n4. Подтверди установку.\n\nПеред установкой дождись статуса «Вычислитель готов», чтобы математическое ядро успело загрузиться.';
  } else {
    body.textContent = 'Открой сайт в поддерживаемом браузере. Если браузер предлагает установить приложение, используй команду «Установить» или «Создать ярлык» в меню браузера. На компьютере доступность установки зависит от браузера и способа размещения сайта.';
  }
  $('installHelpModal').hidden = false;
}
function closeInstallHelp() { $('installHelpModal').hidden = true; }
$('closeInstallHelp').addEventListener('click', closeInstallHelp);
$('installHelpDone').addEventListener('click', closeInstallHelp);
$('installHelpModal').addEventListener('click', e => { if (e.target.dataset.installClose) closeInstallHelp(); });
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault(); deferredInstall = e;
  $('installBtn').textContent = 'Установить';
  $('installBtn').hidden = false;
});
$('installBtn').addEventListener('click', async () => {
  if (deferredInstall) {
    deferredInstall.prompt();
    await deferredInstall.userChoice;
    deferredInstall = null;
    $('installBtn').hidden = true;
    return;
  }
  showInstallHelp();
});
// iOS Safari does not support beforeinstallprompt: show the manual Add to Home Screen guide.
if (isAppleMobile() && !window.navigator.standalone && !window.matchMedia('(display-mode: standalone)').matches) {
  $('installBtn').textContent = 'Как установить';
  $('installBtn').hidden = false;
} else if (/Android/i.test(navigator.userAgent)) {
  $('installBtn').textContent = 'Как установить';
  $('installBtn').hidden = false;
}
window.addEventListener('online', () => { if (pyodide) setStatus('ready','Вычислитель готов'); });
window.addEventListener('offline', () => { if (pyodide) setStatus('ready','Работа без интернета'); });
initEngine();
})();
