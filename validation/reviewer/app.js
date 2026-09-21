// 事实审核工作台

// ==================== 状态管理 ====================
const state = {
  facts: [],           // 所有事实
  filtered: [],        // 过滤后的事实
  selectedIndex: -1,   // 当前选中的事实索引
  filterConfidence: 'all',   // 可信度过滤
  filterStatus: 'all',       // 状态过滤
  filterCategory: 'all',     // 类别过滤
};

const ERROR_TYPES = {
  module_miscluster: '模块划分错误',
  call_missing: '调用链遗漏',
  call_wrong: '调用链错误',
  state_false_positive: '状态读写误报',
  state_false_negative: '状态读写漏报',
  module_desc_wrong: '模块职责描述错误',
  approach_wrong: '实现思路推断错误',
  pattern_false_positive: '设计模式误报',
  flow_missing: '业务流程遗漏',
  flow_wrong: '业务流程步骤错误',
  other: '其他错误',
};

// ==================== DOM 引用 ====================
const $ = (id) => document.getElementById(id);

// ==================== CSV 解析 ====================
function parseCSV(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]);
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length !== headers.length) continue;
    const row = {};
    headers.forEach((h, idx) => {
      row[h.trim()] = values[idx];
    });
    // 添加审核状态字段
    row._status = 'pending';  // pending / ok / error
    row._errorType = '';
    row._notes = '';
    rows.push(row);
  }

  return rows;
}

function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

function toCSV(rows) {
  if (!rows.length) return '';
  const headers = Object.keys(rows[0]).filter(k => !k.startsWith('_'));
  // 把审核字段加在最后
  const allHeaders = [...headers, 'is_error', 'error_type', 'notes'];

  let csv = allHeaders.map(h => `"${h}"`).join(',') + '\n';

  for (const row of rows) {
    const values = allHeaders.map(h => {
      if (h === 'is_error') return row._status === 'error' ? '1' : '';
      if (h === 'error_type') return row._errorType || '';
      if (h === 'notes') return row._notes || '';
      return row[h] || '';
    });
    csv += values.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',') + '\n';
  }

  return csv;
}

// ==================== 文件导入 ====================
$('fileInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const text = await file.text();
  const facts = parseCSV(text);

  if (facts.length === 0) {
    alert('CSV 文件解析失败或为空');
    return;
  }

  // 从文件名推断项目名
  const projectName = file.name.replace('_facts.csv', '').replace('.csv', '');
  $('projectName').textContent = projectName;

  state.facts = facts;
  state.selectedIndex = -1;
  applyFilters();
  renderAll();

  $('emptyState').classList.add('hidden');
  $('tableContainer').classList.remove('hidden');
  $('exportBtn').disabled = false;
  $('reportBtn').disabled = false;
});

// ==================== 过滤 ====================
function applyFilters() {
  state.filtered = state.facts.filter(f => {
    if (state.filterConfidence !== 'all' && f.confidence !== state.filterConfidence) return false;
    if (state.filterStatus !== 'all' && f._status !== state.filterStatus) return false;
    if (state.filterCategory !== 'all' && f.category !== state.filterCategory) return false;
    return true;
  });
}

// 可信度过滤按钮
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.filterConfidence = btn.dataset.filter;
    applyFilters();
    renderTable();
  });
});

// 状态过滤按钮
document.querySelectorAll('.status-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.filterStatus = btn.dataset.status;
    applyFilters();
    renderTable();
  });
});

// ==================== 渲染 ====================
function renderAll() {
  renderStats();
  renderCategories();
  renderTable();
}

function renderStats() {
  const total = state.facts.length;
  const ok = state.facts.filter(f => f._status === 'ok').length;
  const err = state.facts.filter(f => f._status === 'error').length;
  const reviewed = ok + err;

  $('totalCount').textContent = total;
  $('okCount').textContent = ok;
  $('errorCount').textContent = err;

  const pct = total > 0 ? (reviewed / total * 100) : 0;
  $('progressFill').style.width = pct + '%';
  $('progressText').textContent = `${reviewed} / ${total}（${pct.toFixed(0)}%）`;
}

function renderCategories() {
  const cats = {};
  state.facts.forEach(f => {
    if (!cats[f.category]) cats[f.category] = { total: 0, ok: 0, error: 0 };
    cats[f.category].total++;
    if (f._status === 'ok') cats[f.category].ok++;
    if (f._status === 'error') cats[f.category].error++;
  });

  const list = $('categoryList');
  list.innerHTML = '';

  // "全部" 选项
  const allItem = document.createElement('div');
  allItem.className = `sidebar-item px-3 py-2 rounded ${state.filterCategory === 'all' ? 'active' : ''}`;
  allItem.innerHTML = `
    <div class="flex justify-between items-center">
      <span class="text-sm text-slate-700">全部类别</span>
      <span class="text-xs text-slate-400">${state.facts.length}</span>
    </div>
  `;
  allItem.addEventListener('click', () => {
    state.filterCategory = 'all';
    applyFilters();
    renderAll();
  });
  list.appendChild(allItem);

  for (const [cat, data] of Object.entries(cats).sort((a, b) => b[1].total - a[1].total)) {
    const item = document.createElement('div');
    item.className = `sidebar-item px-3 py-2 rounded ${state.filterCategory === cat ? 'active' : ''}`;
    const statusDot = data.error > 0
      ? '<span class="w-2 h-2 bg-red-500 rounded-full inline-block mr-2"></span>'
      : data.ok > 0 && data.ok === data.total
      ? '<span class="w-2 h-2 bg-green-500 rounded-full inline-block mr-2"></span>'
      : '<span class="w-2 h-2 bg-slate-300 rounded-full inline-block mr-2"></span>';

    item.innerHTML = `
      <div class="flex justify-between items-center">
        <span class="text-sm text-slate-700">${statusDot}${cat}</span>
        <span class="text-xs text-slate-400">${data.total}</span>
      </div>
    `;
    item.addEventListener('click', () => {
      state.filterCategory = state.filterCategory === cat ? 'all' : cat;
      applyFilters();
      renderAll();
    });
    list.appendChild(item);
  }
}

function renderTable() {
  const tbody = $('factTableBody');
  tbody.innerHTML = '';

  state.filtered.forEach((fact, idx) => {
    const realIdx = state.facts.indexOf(fact);
    const tr = document.createElement('tr');
    tr.className = `fact-row border-b border-slate-100 cursor-pointer ${state.selectedIndex === realIdx ? 'bg-blue-50' : ''}`;

    const confBadge = fact.confidence === 'verified'
      ? '<span class="badge badge-verified">verified</span>'
      : '<span class="badge badge-inferred">inferred</span>';

    let statusBadge = '';
    if (fact._status === 'ok') statusBadge = '<span class="badge status-ok">已确认</span>';
    else if (fact._status === 'error') statusBadge = '<span class="badge status-error">有错误</span>';
    else statusBadge = '<span class="badge status-pending">待审核</span>';

    tr.innerHTML = `
      <td class="px-3 py-2 font-mono text-xs text-slate-500">${fact.fact_id}</td>
      <td class="px-3 py-2 text-slate-600">${fact.category || ''}</td>
      <td class="px-3 py-2 text-slate-600 text-xs">${fact.type || ''}</td>
      <td class="px-3 py-2 text-slate-800 max-w-md truncate">${fact.description || ''}</td>
      <td class="px-3 py-2 text-slate-500 text-xs font-mono">${fact.location || ''}</td>
      <td class="px-3 py-2">${confBadge}</td>
      <td class="px-3 py-2 text-slate-500 text-xs max-w-xs truncate">${fact.evidence || ''}</td>
      <td class="px-3 py-2 text-center">${statusBadge}</td>
      <td class="px-3 py-2 text-center">
        <button class="text-green-600 hover:text-green-800 mx-1" title="确认正确" onclick="event.stopPropagation(); markFact(${realIdx}, 'ok')">
          <i class="fa-solid fa-circle-check"></i>
        </button>
        <button class="text-red-600 hover:text-red-800 mx-1" title="标记错误" onclick="event.stopPropagation(); markFact(${realIdx}, 'error')">
          <i class="fa-solid fa-circle-xmark"></i>
        </button>
      </td>
    `;

    tr.addEventListener('click', () => selectFact(realIdx));
    tbody.appendChild(tr);
  });

  if (state.filtered.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="9" class="px-3 py-10 text-center text-slate-400">没有符合条件的事实</td>';
    tbody.appendChild(tr);
  }
}

// ==================== 详情面板 ====================
function selectFact(index) {
  state.selectedIndex = index;
  const fact = state.facts[index];

  $('detailId').textContent = fact.fact_id;
  $('detailCategory').textContent = `${fact.category} / ${fact.type}`;
  $('detailDescription').textContent = fact.description;
  $('detailLocation').textContent = fact.location;
  $('detailConfidence').innerHTML = fact.confidence === 'verified'
    ? '<span class="badge badge-verified">verified — 确定性结论，来自 AST 解析</span>'
    : '<span class="badge badge-inferred">inferred — 推断结论，需人工确认</span>';
  $('detailEvidence').textContent = fact.evidence;

  // 错误表单
  $('errorType').value = fact._errorType || '';
  $('errorNotes').value = fact._notes || '';

  if (fact._status === 'error') {
    $('errorFields').classList.remove('hidden');
  } else {
    $('errorFields').classList.add('hidden');
  }

  $('detailPanel').classList.remove('hidden');
  renderTable();
}

$('closePanel').addEventListener('click', () => {
  state.selectedIndex = -1;
  $('detailPanel').classList.add('hidden');
  renderTable();
});

// 快捷审核
function markFact(index, status) {
  state.facts[index]._status = status;
  if (status === 'ok') {
    state.facts[index]._errorType = '';
    state.facts[index]._notes = '';
  } else {
    // 如果是标记错误，显示详情面板让用户填
    selectFact(index);
    $('errorFields').classList.remove('hidden');
    $('errorType').focus();
  }
  renderStats();
  renderCategories();
  renderTable();
}

window.markFact = markFact;

$('markOkBtn').addEventListener('click', () => {
  if (state.selectedIndex < 0) return;
  markFact(state.selectedIndex, 'ok');
});

$('markErrorBtn').addEventListener('click', () => {
  if (state.selectedIndex < 0) return;
  markFact(state.selectedIndex, 'error');
});

$('saveErrorBtn').addEventListener('click', () => {
  if (state.selectedIndex < 0) return;
  const fact = state.facts[state.selectedIndex];
  fact._errorType = $('errorType').value;
  fact._notes = $('errorNotes').value;
  renderStats();
  renderCategories();
  renderTable();
  alert('已保存');
});

$('resetBtn').addEventListener('click', () => {
  if (state.selectedIndex < 0) return;
  if (!confirm('确定重置这条事实的审核状态吗？')) return;
  const fact = state.facts[state.selectedIndex];
  fact._status = 'pending';
  fact._errorType = '';
  fact._notes = '';
  $('errorFields').classList.add('hidden');
  renderStats();
  renderCategories();
  renderTable();
});

// 上一条 / 下一条
$('prevBtn').addEventListener('click', () => {
  if (state.filtered.length === 0) return;
  const currentFact = state.facts[state.selectedIndex];
  const currentFilteredIdx = state.filtered.indexOf(currentFact);
  const prevIdx = Math.max(0, currentFilteredIdx - 1);
  const realIdx = state.facts.indexOf(state.filtered[prevIdx]);
  selectFact(realIdx);
});

$('nextBtn').addEventListener('click', () => {
  if (state.filtered.length === 0) return;
  const currentFact = state.facts[state.selectedIndex];
  const currentFilteredIdx = state.filtered.indexOf(currentFact);
  const nextIdx = Math.min(state.filtered.length - 1, currentFilteredIdx + 1);
  const realIdx = state.facts.indexOf(state.filtered[nextIdx]);
  selectFact(realIdx);
});

// ==================== 导出 ====================
$('exportBtn').addEventListener('click', () => {
  const csv = toCSV(state.facts);
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = $('projectName').textContent + '_checked.csv';
  a.click();
  URL.revokeObjectURL(url);
});

// ==================== 报告 ====================
$('reportBtn').addEventListener('click', () => {
  const report = generateReport();
  $('reportContent').innerHTML = report;
  $('reportModal').classList.remove('hidden');
  $('reportModal').classList.add('flex');
});

$('closeReportBtn').addEventListener('click', () => {
  $('reportModal').classList.add('hidden');
  $('reportModal').classList.remove('flex');
});

$('reportModal').addEventListener('click', (e) => {
  if (e.target === $('reportModal')) {
    $('reportModal').classList.add('hidden');
    $('reportModal').classList.remove('flex');
  }
});

function generateReport() {
  const total = state.facts.length;
  const reviewed = state.facts.filter(f => f._status !== 'pending').length;
  const ok = state.facts.filter(f => f._status === 'ok').length;
  const errors = state.facts.filter(f => f._status === 'error');
  const errorRate = reviewed > 0 ? (errors.length / reviewed * 100) : 0;

  // 按类别统计
  const catStats = {};
  state.facts.forEach(f => {
    if (!catStats[f.category]) catStats[f.category] = { total: 0, errors: 0 };
    catStats[f.category].total++;
    if (f._status === 'error') catStats[f.category].errors++;
  });

  // 按错误类型统计
  const errorTypes = {};
  errors.forEach(f => {
    const et = f._errorType || 'other';
    const label = ERROR_TYPES[et] || et;
    errorTypes[label] = (errorTypes[label] || 0) + 1;
  });

  // 按可信度统计
  const verifiedErrors = state.facts.filter(f => f.confidence === 'verified' && f._status === 'error').length;
  const inferredErrors = state.facts.filter(f => f.confidence === 'inferred' && f._status === 'error').length;
  const verifiedTotal = state.facts.filter(f => f.confidence === 'verified').length;
  const inferredTotal = state.facts.filter(f => f.confidence === 'inferred').length;

  let html = '';

  html += `<div class="space-y-4">
    <div class="bg-blue-50 p-4 rounded">
      <h4 class="font-semibold text-blue-900 mb-2">项目：${$('projectName').textContent}</h4>
      <div class="grid grid-cols-4 gap-4 text-sm">
        <div><span class="text-blue-700">事实总数</span><br><span class="text-xl font-bold text-blue-900">${total}</span></div>
        <div><span class="text-blue-700">已审核</span><br><span class="text-xl font-bold text-blue-900">${reviewed}</span></div>
        <div><span class="text-green-700">正确</span><br><span class="text-xl font-bold text-green-600">${ok}</span></div>
        <div><span class="text-red-700">错误</span><br><span class="text-xl font-bold text-red-600">${errors.length}</span></div>
      </div>
    </div>
  `;

  if (reviewed > 0) {
    html += `
      <div>
        <h4 class="font-semibold text-slate-800 mb-2">错误率</h4>
        <p class="text-2xl font-bold ${errorRate > 10 ? 'text-red-600' : errorRate > 5 ? 'text-amber-600' : 'text-green-600'}">
          ${errorRate.toFixed(1)}%
        </p>
        <p class="text-sm text-slate-500">（已审核 ${reviewed} 条事实中，${errors.length} 条错误）</p>
      </div>
    `;
  }

  // 按可信度拆分
  html += `
    <div>
      <h4 class="font-semibold text-slate-800 mb-2">按可信度拆分</h4>
      <table class="w-full text-sm border border-slate-200 rounded">
        <thead class="bg-slate-50">
          <tr><th class="px-3 py-2 text-left">可信度</th><th class="px-3 py-2 text-right">总数</th><th class="px-3 py-2 text-right">错误数</th><th class="px-3 py-2 text-right">错误率</th></tr>
        </thead>
        <tbody>
          <tr class="border-t border-slate-200">
            <td class="px-3 py-2"><span class="badge badge-verified">verified</span></td>
            <td class="px-3 py-2 text-right">${verifiedTotal}</td>
            <td class="px-3 py-2 text-right">${verifiedErrors}</td>
            <td class="px-3 py-2 text-right">${verifiedTotal > 0 ? (verifiedErrors/verifiedTotal*100).toFixed(1) + '%' : '-'}</td>
          </tr>
          <tr class="border-t border-slate-200">
            <td class="px-3 py-2"><span class="badge badge-inferred">inferred</span></td>
            <td class="px-3 py-2 text-right">${inferredTotal}</td>
            <td class="px-3 py-2 text-right">${inferredErrors}</td>
            <td class="px-3 py-2 text-right">${inferredTotal > 0 ? (inferredErrors/inferredTotal*100).toFixed(1) + '%' : '-'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  `;

  // 按类别统计
  html += `
    <div>
      <h4 class="font-semibold text-slate-800 mb-2">按事实类别</h4>
      <table class="w-full text-sm border border-slate-200 rounded">
        <thead class="bg-slate-50">
          <tr><th class="px-3 py-2 text-left">类别</th><th class="px-3 py-2 text-right">总数</th><th class="px-3 py-2 text-right">错误数</th><th class="px-3 py-2 text-right">错误率</th></tr>
        </thead>
        <tbody>
  `;
  for (const [cat, data] of Object.entries(catStats).sort((a, b) => b[1].errors - a[1].errors)) {
    const rate = data.total > 0 ? (data.errors / data.total * 100).toFixed(1) + '%' : '-';
    html += `
      <tr class="border-t border-slate-200">
        <td class="px-3 py-2">${cat}</td>
        <td class="px-3 py-2 text-right">${data.total}</td>
        <td class="px-3 py-2 text-right ${data.errors > 0 ? 'text-red-600 font-medium' : ''}">${data.errors}</td>
        <td class="px-3 py-2 text-right">${rate}</td>
      </tr>
    `;
  }
  html += '</tbody></table></div>';

  // 错误类型分布
  if (errors.length > 0 && Object.keys(errorTypes).length > 0) {
    html += `
      <div>
        <h4 class="font-semibold text-slate-800 mb-2">错误类型分布</h4>
        <table class="w-full text-sm border border-slate-200 rounded">
          <thead class="bg-slate-50">
            <tr><th class="px-3 py-2 text-left">错误类型</th><th class="px-3 py-2 text-right">数量</th><th class="px-3 py-2 text-right">占比</th></tr>
          </thead>
          <tbody>
    `;
    for (const [et, count] of Object.entries(errorTypes).sort((a, b) => b[1] - a[1])) {
      const pct = (count / errors.length * 100).toFixed(1) + '%';
      html += `
        <tr class="border-t border-slate-200">
          <td class="px-3 py-2">${et}</td>
          <td class="px-3 py-2 text-right">${count}</td>
          <td class="px-3 py-2 text-right">${pct}</td>
        </tr>
      `;
    }
    html += '</tbody></table></div>';
  }

  // 错误详情列表
  if (errors.length > 0) {
    html += `
      <div>
        <h4 class="font-semibold text-slate-800 mb-2">错误详情（${errors.length} 条）</h4>
        <div class="max-h-64 overflow-y-auto border border-slate-200 rounded">
          <table class="w-full text-xs">
            <thead class="bg-slate-50 sticky top-0">
              <tr><th class="px-2 py-1 text-left">ID</th><th class="px-2 py-1 text-left">类别</th><th class="px-2 py-1 text-left">描述</th><th class="px-2 py-1 text-left">错误类型</th></tr>
            </thead>
            <tbody>
    `;
    errors.slice(0, 50).forEach(f => {
      const desc = f.description.length > 40 ? f.description.slice(0, 40) + '...' : f.description;
      const etLabel = ERROR_TYPES[f._errorType] || f._errorType || '未分类';
      html += `<tr class="border-t border-slate-100">
        <td class="px-2 py-1 font-mono text-slate-500">${f.fact_id}</td>
        <td class="px-2 py-1 text-slate-600">${f.category}</td>
        <td class="px-2 py-1">${desc}</td>
        <td class="px-2 py-1 text-red-600">${etLabel}</td>
      </tr>`;
    });
    if (errors.length > 50) {
      html += `<tr><td colspan="4" class="px-2 py-1 text-center text-slate-400">... 还有 ${errors.length - 50} 条</td></tr>`;
    }
    html += '</tbody></table></div></div>';
  }

  html += '</div>';

  return html;
}

// 键盘快捷键
document.addEventListener('keydown', (e) => {
  if (state.selectedIndex < 0) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

  if (e.key === 'ArrowUp' || e.key === 'k') {
    $('prevBtn').click();
  } else if (e.key === 'ArrowDown' || e.key === 'j') {
    $('nextBtn').click();
  } else if (e.key === 'y' || e.key === 'Y') {
    markFact(state.selectedIndex, 'ok');
    $('nextBtn').click();
  } else if (e.key === 'n' || e.key === 'N') {
    markFact(state.selectedIndex, 'error');
  }
});
