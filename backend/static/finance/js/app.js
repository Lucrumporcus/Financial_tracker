(() => {
  const csrf = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
  const request = async (url, options = {}) => {
    const headers = { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), 'X-CSRFToken': decodeURIComponent(csrf()), ...(options.headers || {}) };
    const response = await fetch(url, { ...options, headers });
    if (response.status === 204) return null;
    const contentType = response.headers.get('content-type') || '';
    const body = contentType.includes('json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error(typeof body === 'string' ? body : JSON.stringify(body));
    return body;
  };
  const notify = (message, kind = 'status') => {
    const notice = document.querySelector('#app-notice');
    if (!notice) return;
    notice.textContent = message;
    notice.dataset.kind = kind;
    notice.hidden = !message;
  };
  const tell = error => notify(error.message || 'Не удалось выполнить запрос.', 'error');
  const money = value => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format(Number(value || 0));
  const escapeHtml = value => { const el = document.createElement('span'); el.textContent = value; return el.innerHTML; };
  const escapeAttribute = value => escapeHtml(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  async function loadSummary(query = '') {
    const nodes = document.querySelectorAll('[data-summary]');
    if (!nodes.length) return;
    try {
      const data = await request(`/api/operations/summary/${query}`);
      nodes.forEach(node => {
        const income = node.querySelector('[data-income]');
        const expense = node.querySelector('[data-expense]');
        const balance = node.querySelector('[data-balance]');
        if (income) income.textContent = money(data.income);
        if (expense) expense.textContent = money(data.expense);
        if (balance) balance.textContent = money(data.balance);
      });
    } catch (error) { tell(error); }
  }

  async function initGroups() {
    const list = document.querySelector('#groups-list');
    if (!list) return;
    const currentUser = document.querySelector('#groups-panel')?.dataset.currentUser;
    const groupForm = document.querySelector('#group-form');
    const roleNames = { OWNER: 'Владелец', MEMBER: 'Участник', OBSERVER: 'Наблюдатель' };

    const load = async () => {
      const groups = await request('/api/groups/');
      list.innerHTML = groups.length ? '' : '<p class="muted">Пока нет групп. Создайте первую.</p>';
      groups.forEach(group => {
        const card = document.createElement('article');
        card.className = 'group-card';
        card.dataset.groupId = group.id;
        card.innerHTML = `
          <div class="group-card-header">
            <div><h3>${escapeHtml(group.name)}</h3><small class="muted">Создана ${new Date(group.created_at).toLocaleDateString('ru-RU')}</small></div>
            <div class="group-actions">
              <button class="button secondary" type="button" data-members-toggle>Участники</button>
            </div>
          </div>
          <section class="members-panel" data-members-panel hidden>
            <div class="members-panel-heading">
              <p class="muted" data-group-feedback aria-live="polite"></p>
              <button class="button danger" type="button" data-group-delete hidden>Удалить группу</button>
            </div>
            <form class="member-add-form form-row" data-member-add>
              <label class="form-field">Имя пользователя
                <input class="form-control" name="invite_username" required autocomplete="off" placeholder="Точный username">
              </label>
              <label class="form-field">Роль
                <select class="form-control" name="role"><option value="MEMBER">Участник</option><option value="OBSERVER">Наблюдатель</option></select>
              </label>
              <div class="form-actions"><button class="button primary">Добавить</button></div>
            </form>
            <div class="members-list" data-members-list><p class="muted">Загрузка участников…</p></div>
          </section>`;
        list.append(card);
      });
    };

    const loadMembers = async card => {
      const groupId = card.dataset.groupId;
      const membersList = card.querySelector('[data-members-list]');
      const feedback = card.querySelector('[data-group-feedback]');
      try {
        const members = await request(`/api/groups/${groupId}/members/`);
        const currentMembership = members.find(member => String(member.user) === String(currentUser));
        const isOwner = currentMembership?.role === 'OWNER';
        const ownerCount = members.filter(member => member.role === 'OWNER').length;
        const addForm = card.querySelector('[data-member-add]');
        addForm.hidden = !isOwner;
        card.querySelector('[data-group-delete]').hidden = !isOwner;
        feedback.textContent = currentMembership ? `Ваша роль: ${roleNames[currentMembership.role]}` : 'Нет доступа к списку участников.';
        membersList.innerHTML = members.length ? '' : '<p class="muted">В группе пока нет участников.</p>';
        members.forEach(member => {
          const row = document.createElement('div');
          row.className = 'member-row';
          const roleControl = isOwner && member.role !== 'OWNER'
            ? `<form class="member-role-form" data-member-role="${member.id}"><select class="form-control" name="role" aria-label="Роль участника"><option value="MEMBER" ${member.role === 'MEMBER' ? 'selected' : ''}>Участник</option><option value="OBSERVER" ${member.role === 'OBSERVER' ? 'selected' : ''}>Наблюдатель</option></select><button class="button ghost small">Сохранить</button></form>`
            : `<span class="role-badge role-${member.role.toLowerCase()}">${roleNames[member.role]}</span>`;
          const removeControl = isOwner
            ? `<button class="button danger small" type="button" data-member-remove="${member.id}" ${member.role === 'OWNER' && ownerCount === 1 ? 'disabled title="В группе должен остаться хотя бы один владелец"' : ''}>Убрать</button>`
            : '';
          row.innerHTML = `<div class="member-identity"><strong>${escapeHtml(member.member_username || member.user)}</strong><small>${escapeHtml(member.user)}</small></div><div class="member-controls">${roleControl}${removeControl}</div>`;
          membersList.append(row);
        });
      } catch (error) {
        feedback.textContent = error.message;
        membersList.innerHTML = '';
      }
    };

    try { await load(); } catch (error) { tell(error); }

    if (groupForm) groupForm.addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget;
      try { await request('/api/groups/', { method: 'POST', body: JSON.stringify({ name: new FormData(form).get('name') }) }); form.reset(); await load(); }
      catch (error) { tell(error); }
    });

    list.addEventListener('click', async event => {
      const card = event.target.closest('[data-group-id]');
      if (!card) return;
      if (event.target.closest('[data-members-toggle]')) {
        const panel = card.querySelector('[data-members-panel]');
        if (!panel) return;
        panel.hidden = !panel.hidden;
        if (!panel.hidden) await loadMembers(card);
        return;
      }
      if (event.target.closest('[data-group-delete]')) {
        try { await request(`/api/groups/${card.dataset.groupId}/`, { method: 'DELETE' }); await load(); notify('Группа удалена.'); }
        catch (error) { tell(error); }
        return;
      }
      const removeButton = event.target.closest('[data-member-remove]');
      if (removeButton) {
        try {
          await request(`/api/groups/${card.dataset.groupId}/members/${removeButton.dataset.memberRemove}/`, { method: 'DELETE' });
          await loadMembers(card);
          notify('Участник удалён из группы.');
        } catch (error) { card.querySelector('[data-group-feedback]').textContent = error.message; }
      }
    });

    list.addEventListener('submit', async event => {
      const card = event.target.closest('[data-group-id]');
      if (!card) return;
      event.preventDefault();
      const feedback = card.querySelector('[data-group-feedback]');
      const addForm = event.target.closest('[data-member-add]');
      const roleForm = event.target.closest('[data-member-role]');
      try {
        if (addForm) {
          const form = addForm;
          const data = Object.fromEntries(new FormData(form));
          await request(`/api/groups/${card.dataset.groupId}/members/`, { method: 'POST', body: JSON.stringify(data) });
          form.reset();
        } else if (roleForm) {
          const data = Object.fromEntries(new FormData(roleForm));
          await request(`/api/groups/${card.dataset.groupId}/members/${roleForm.dataset.memberRole}/`, { method: 'PATCH', body: JSON.stringify(data) });
        } else return;
        feedback.textContent = 'Изменения сохранены.';
        await loadMembers(card);
      } catch (error) { feedback.textContent = error.message; }
    });
  }

  async function initOperations() {
    const tbody = document.querySelector('#operations-list'); if (!tbody) return;
    let [categories, groups] = await Promise.all([request('/api/categories/'), request('/api/groups/')]);
    const categorySelect = document.querySelector('#category-select');
    const operationForm = document.querySelector('#operation-form');
    const groupSelect = document.querySelector('#group-select');
    if (!categorySelect || !operationForm || !groupSelect) return;
    const operationType = operationForm.elements.namedItem('type');
    const filterForm = document.querySelector('#filter-form');
    const filterGroup = filterForm?.elements.namedItem('group');
    const filterCategory = filterForm?.elements.namedItem('category');
    const filterType = filterForm?.elements.namedItem('type');
    const categoryForm = document.querySelector('#category-form');
    const categoryGroupSelect = categoryForm?.elements.namedItem('group');
    const categoryList = document.querySelector('#categories-list');
    const categoriesPanel = document.querySelector('#categories-panel');
    const categoryFeedback = document.querySelector('#category-feedback');
    const currentUser = categoriesPanel?.dataset.currentUser;
    const groupCanManage = new Map();
    const groupRoles = new Map();

    groups.forEach(group => groupSelect.add(new Option(group.name, group.id)));
    const replaceCategoryOptions = (select, groupId, type, placeholder) => {
      if (!select) return;
      const previousValue = select.value;
      const available = categories.filter(category =>
        (groupId === null || String(category.group || '') === String(groupId || '')) && (!type || category.type === type)
      );
      select.replaceChildren(new Option(placeholder, ''));
      available.forEach(category => select.add(new Option(category.name, category.id)));
      select.value = available.some(category => String(category.id) === previousValue) ? previousValue : '';
    };
    const refreshOperationCategories = () => replaceCategoryOptions(
      categorySelect, groupSelect.value, operationType?.value, 'Выберите категорию',
    );
    const refreshFilterCategories = () => replaceCategoryOptions(
      filterCategory, filterGroup?.value || null, filterType?.value, 'Все категории',
    );
    const refreshCategories = () => {
      refreshOperationCategories();
      refreshFilterCategories();
    };
    const renderCategoryList = () => {
      if (!categoryList) return;
      if (!categories.length) {
        categoryList.innerHTML = '<p class="muted">Категорий пока нет.</p>';
        return;
      }
      categoryList.innerHTML = '';
      categories.forEach(category => {
        const isOwner = category.group
          ? groupCanManage.get(String(category.group)) === true
          : String(category.user) === String(currentUser);
        const groupName = groups.find(group => String(group.id) === String(category.group))?.name;
        const typeName = category.type === 'INCOME' ? 'Доход' : 'Расход';
        const row = document.createElement('article');
        row.className = 'category-row';
        const content = `<div class="category-title"><strong>${escapeHtml(category.name)}</strong><small>${typeName} · ${escapeHtml(groupName || 'Личная')}</small></div>`;
        if (!isOwner) {
          row.innerHTML = content;
        } else {
          row.innerHTML = `${content}<form class="category-edit-form" data-category-edit="${category.id}">
            <label class="form-field">Название<input class="form-control" name="name" value="${escapeAttribute(category.name)}" maxlength="255" required></label>
            <label class="form-field">Тип<select class="form-control" name="type"><option value="EXPENSE" ${category.type === 'EXPENSE' ? 'selected' : ''}>Расход</option><option value="INCOME" ${category.type === 'INCOME' ? 'selected' : ''}>Доход</option></select></label>
            <div class="category-actions"><button class="button secondary small">Сохранить</button><button class="button danger small" type="button" data-category-delete="${category.id}">Удалить</button></div>
          </form>`;
        }
        categoryList.append(row);
      });
    };
    groupSelect.addEventListener('change', refreshOperationCategories);
    operationType?.addEventListener('change', refreshOperationCategories);
    refreshOperationCategories();
    if (filterForm) {
      groups.forEach(group => filterGroup?.add(new Option(group.name, group.id)));
      refreshFilterCategories();
      filterGroup?.addEventListener('change', refreshFilterCategories);
      filterType?.addEventListener('change', refreshFilterCategories);
    }
    if (categoryList || categoryGroupSelect) {
      const ownerResults = await Promise.all(groups.map(async group => {
        const groupId = String(group.id);
        try {
          const members = await request(`/api/groups/${groupId}/members/`);
          const membership = members.find(member => String(member.user) === String(currentUser));
          return [groupId, membership?.role || null];
        } catch (_) {
          return [groupId, false];
        }
      }));
      ownerResults.forEach(([groupId, role]) => {
        groupRoles.set(groupId, role);
        groupCanManage.set(groupId, role === 'OWNER');
      });
      groups.filter(group => groupCanManage.get(String(group.id))).forEach(group => {
        categoryGroupSelect?.add(new Option(group.name, group.id));
      });
      if (categoryList) renderCategoryList();
    }
    let operationsQuery = '';
    const load = async query => {
      if (query !== undefined) operationsQuery = query;
      const operations = await request(`/api/operations/${operationsQuery}`);
      tbody.innerHTML = operations.length ? '' : '<tr><td colspan="7" class="muted">Операций пока нет.</td></tr>';
      operations.forEach(operation => {
        const row = document.createElement('tr');
        const role = operation.group ? groupRoles.get(String(operation.group)) : null;
        const canManage = operation.group
          ? role === 'OWNER' || (role === 'MEMBER' && String(operation.user) === String(currentUser))
          : String(operation.user) === String(currentUser);
        const actions = canManage
          ? `<div class="row-actions"><button class="button ghost small" type="button" data-op-edit="${operation.id}" data-amount="${operation.amount}">Изменить сумму</button><button class="button danger small" type="button" data-op-delete="${operation.id}">Удалить</button></div>`
          : '';
        row.innerHTML = `<td>${operation.date}</td><td>${operation.type === 'INCOME' ? 'Доход' : 'Расход'}</td><td>${escapeHtml(categories.find(item => item.id === operation.category)?.name || 'Категория')}</td><td>${escapeHtml(groups.find(item => item.id === operation.group)?.name || 'Личная')}</td><td>${money(operation.amount)}</td><td>${escapeHtml(operation.description || '')}</td><td>${actions}</td>`;
        tbody.append(row);
      });
    };
    await load();
    operationForm.addEventListener('submit', async event => {
      const form = event.currentTarget;
      event.preventDefault(); const data = Object.fromEntries(new FormData(form)); data.group = data.group || null;
      try { await request('/api/operations/', { method: 'POST', body: JSON.stringify(data) }); form.reset(); refreshCategories(); await load(); await loadSummary(); }
      catch (error) { tell(error); }
    });
    if (categoryForm) categoryForm.addEventListener('submit', async event => {
      const form = event.currentTarget;
      event.preventDefault();
      try {
        const data = Object.fromEntries(new FormData(form));
        data.group = data.group || null;
        const created = await request('/api/categories/', { method: 'POST', body: JSON.stringify(data) });
        categories.push(created);
        form.reset();
        renderCategoryList();
        refreshCategories();
        if (categoryFeedback) categoryFeedback.textContent = 'Категория добавлена.';
      }
      catch (error) { tell(error); }
    });
    if (categoryList) {
      categoryList.addEventListener('submit', async event => {
        const form = event.target.closest('[data-category-edit]');
        if (!form) return;
        event.preventDefault();
        try {
          const updated = await request(`/api/categories/${form.dataset.categoryEdit}/`, {
            method: 'PATCH', body: JSON.stringify(Object.fromEntries(new FormData(form))),
          });
          categories = categories.map(category => category.id === updated.id ? updated : category);
          renderCategoryList();
          refreshCategories();
          if (categoryFeedback) categoryFeedback.textContent = 'Изменения категории сохранены.';
        } catch (error) {
          if (categoryFeedback) categoryFeedback.textContent = error.message;
        }
      });
      categoryList.addEventListener('click', async event => {
        const button = event.target.closest('[data-category-delete]');
        if (!button) return;
        try {
          await request(`/api/categories/${button.dataset.categoryDelete}/`, { method: 'DELETE' });
          categories = categories.filter(category => String(category.id) !== String(button.dataset.categoryDelete));
          renderCategoryList();
          refreshCategories();
          if (categoryFeedback) categoryFeedback.textContent = 'Категория удалена.';
          notify('Категория удалена.');
        } catch (error) {
          if (categoryFeedback) categoryFeedback.textContent = error.message;
        }
      });
    }
    if (filterForm) filterForm.addEventListener('submit', async event => {
      event.preventDefault(); const params = new URLSearchParams(new FormData(event.currentTarget));
      try { await load(`?${params}`); } catch (error) { tell(error); }
    });
    if (filterForm) filterForm.addEventListener('reset', () => setTimeout(() => {
      refreshFilterCategories();
      load('').catch(tell);
    }, 0));
    tbody.addEventListener('submit', async event => {
      const form = event.target.closest('[data-op-edit-form]');
      if (!form) return;
      event.preventDefault();
      try {
        await request(`/api/operations/${form.dataset.opEditForm}/`, {
          method: 'PATCH', body: JSON.stringify({ amount: new FormData(form).get('amount') }),
        });
        await load();
        await loadSummary();
        notify('Сумма операции изменена.');
      } catch (error) { tell(error); }
    });
    tbody.addEventListener('click', async event => {
      const deleteButton = event.target.closest('[data-op-delete]');
      if (deleteButton) {
        try { await request(`/api/operations/${deleteButton.dataset.opDelete}/`, { method: 'DELETE' }); await load(); await loadSummary(); notify('Операция удалена.'); } catch (error) { tell(error); }
        return;
      }
      const cancelButton = event.target.closest('[data-op-edit-cancel]');
      if (cancelButton) { load().catch(tell); return; }
      const editButton = event.target.closest('[data-op-edit]'); if (!editButton) return;
      const cell = editButton.closest('td');
      if (!cell) return;
      cell.innerHTML = `<form class="row-edit-form" data-op-edit-form="${editButton.dataset.opEdit}"><input class="form-control" name="amount" type="number" min="0.01" step="0.01" value="${escapeAttribute(editButton.dataset.amount)}" aria-label="Новая сумма" required><button class="button secondary small">Сохранить</button><button class="button ghost small" type="button" data-op-edit-cancel>Отмена</button></form>`;
    });
    const importForm = document.querySelector('#import-form');
    if (importForm) importForm.addEventListener('submit', async event => {
      const form = event.currentTarget;
      event.preventDefault();
      try { const result = await request('/api/operations/import-csv/', { method: 'POST', body: new FormData(form) }); notify(`Импортировано операций: ${result.created}.`); form.reset(); await load(); await loadSummary(); }
      catch (error) { tell(error); }
    });
  }

  async function initStatistics() {
    const form = document.querySelector('#statistics-filter'); if (!form) return;
    const groupSelect = form.elements.namedItem('group');
    const categorySelect = form.elements.namedItem('category');
    if (!groupSelect || !categorySelect) return;
    try {
      const [categories, groups] = await Promise.all([request('/api/categories/'), request('/api/groups/')]);
      groups.forEach(group => groupSelect.add(new Option(group.name, group.id)));
      categories.forEach(category => categorySelect.add(new Option(`${category.name} · ${category.type === 'INCOME' ? 'доход' : 'расход'}`, category.id)));
    } catch (error) { tell(error); }
    const refresh = () => {
      const params = new URLSearchParams(new FormData(form));
      for (const [key, value] of params.entries()) if (!value) params.delete(key);
      const query = params.size ? `?${params}` : '';
      loadSummary(query);
    };
    form.addEventListener('submit', event => { event.preventDefault(); refresh(); });
    form.addEventListener('reset', () => setTimeout(refresh, 0));
  }

  document.addEventListener('DOMContentLoaded', () => { loadSummary(); initGroups(); initOperations().catch(tell); initStatistics(); });
})();
