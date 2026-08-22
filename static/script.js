/* ==========================================================================
   Fare Tracker — 前端行為
   1. 回程日期 min：不能選比出發日期早的日期
   2. 機場 autocomplete：origin / destination 輸入框打字時查詢機場建議
      （依賴後端 /api/airports?q= 路由，該路由完成前這段會 fetch 失敗，
       但不影響表單照常送出查詢，只是沒有下拉建議可選）
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    setupReturnDateMin();
    setupAirportAutocomplete('origin');
    setupAirportAutocomplete('destination');
});

/* ------------------------------------------------------------------------
   1. 回程日期不能早於出發日期
   ------------------------------------------------------------------------ */

function setupReturnDateMin() {
    const departInput = document.getElementById('depart_date');
    const returnInput = document.getElementById('return_date');

    if (!departInput || !returnInput) return;

    function updateReturnDateMin() {
        returnInput.min = departInput.value;
    }

    departInput.addEventListener('change', updateReturnDateMin);
    updateReturnDateMin();
}

/* ------------------------------------------------------------------------
   2. 機場關鍵字 autocomplete
   ------------------------------------------------------------------------ */

const AUTOCOMPLETE_DEBOUNCE_MS = 250;
const AUTOCOMPLETE_MIN_CHARS = 1;

function setupAirportAutocomplete(inputId) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(inputId + '_suggestions');

    if (!input || !list) return;

    let debounceTimer = null;
    let activeIndex = -1;
    let currentItems = [];

    input.addEventListener('input', () => {
        const query = input.value.trim();

        clearTimeout(debounceTimer);

        if (query.length < AUTOCOMPLETE_MIN_CHARS) {
            closeList();
            return;
        }

        debounceTimer = setTimeout(() => fetchSuggestions(query), AUTOCOMPLETE_DEBOUNCE_MS);
    });

    input.addEventListener('keydown', (e) => {
        if (!list.classList.contains('is-open')) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveActive(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveActive(-1);
        } else if (e.key === 'Enter') {
            if (activeIndex >= 0 && currentItems[activeIndex]) {
                e.preventDefault();
                selectAirport(currentItems[activeIndex]);
            }
        } else if (e.key === 'Escape') {
            closeList();
        }
    });

    // 點輸入框以外的地方時關閉下拉選單
    document.addEventListener('click', (e) => {
        if (e.target !== input && !list.contains(e.target)) {
            closeList();
        }
    });

    async function fetchSuggestions(query) {
        try {
            const res = await fetch('/api/airports?q=' + encodeURIComponent(query));
            if (!res.ok) {
                closeList();
                return;
            }
            const data = await res.json();
            renderList(data.airports || []);
        } catch (err) {
            // 後端路由還沒做好，或網路錯誤：安靜失敗，不影響使用者手動輸入代碼
            closeList();
        }
    }

    function renderList(airports) {
        currentItems = airports;
        activeIndex = -1;
        list.innerHTML = '';

        if (airports.length === 0) {
            const li = document.createElement('li');
            li.className = 'empty';
            li.textContent = '查無符合的機場';
            list.appendChild(li);
            openList();
            return;
        }

        airports.forEach((airport, index) => {
            const li = document.createElement('li');
            li.setAttribute('role', 'option');
            li.dataset.index = index;

            const nameSpan = document.createElement('span');
            nameSpan.textContent = airport.name_zh || airport.name_en;

            const codeSpan = document.createElement('span');
            codeSpan.className = 'code';
            codeSpan.textContent = airport.code;

            li.appendChild(nameSpan);
            li.appendChild(codeSpan);

            li.addEventListener('click', () => selectAirport(airport));
            li.addEventListener('mouseenter', () => setActive(index));

            list.appendChild(li);
        });

        openList();
    }

    function selectAirport(airport) {
        input.value = airport.code;
        closeList();
    }

    function moveActive(delta) {
        if (currentItems.length === 0) return;
        const next = Math.min(Math.max(activeIndex + delta, 0), currentItems.length - 1);
        setActive(next);
    }

    function setActive(index) {
        const items = list.querySelectorAll('li[role="option"]');
        items.forEach((item) => item.classList.remove('is-active'));
        if (items[index]) {
            items[index].classList.add('is-active');
            items[index].scrollIntoView({ block: 'nearest' });
        }
        activeIndex = index;
    }

    function openList() {
        list.classList.add('is-open');
    }

    function closeList() {
        list.classList.remove('is-open');
        list.innerHTML = '';
        currentItems = [];
        activeIndex = -1;
    }
}