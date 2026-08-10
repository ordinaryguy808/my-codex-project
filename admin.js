const list = document.querySelector('#card-list');
const dialog = document.querySelector('#card-dialog');
const form = document.querySelector('#card-form');
let cards = [];
let requests = [];
const productLabels = {CARD:'NFC Card', PLAQUE:'Review / Social Plaque', PROPERTY_SIGN_TAG:'Property Sign Tag'};

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));

function destinationLabel(value) {
  try { return new URL(value).hostname.replace(/^www\./, ''); } catch { return value; }
}

function render() {
  document.querySelector('#card-count').textContent = cards.length;
  document.querySelector('#active-count').textContent = cards.filter((card) => card.active).length;
  document.querySelector('#tap-count').textContent = cards.reduce((sum, card) => sum + card.total_taps, 0).toLocaleString();
  list.innerHTML = cards.length ? cards.map((card) => `<article class="card-row">
    <div><div class="card-id">${escapeHtml(card.tap_id)}</div><div class="customer">${escapeHtml(card.customer_name)}</div><span class="status ${card.active ? '' : 'inactive'}">${card.active ? 'ACTIVE' : 'INACTIVE'}</span></div>
    <div><div class="product-label">${escapeHtml(productLabels[card.product_type])}</div><div class="destination">${escapeHtml(destinationLabel(card.destination_url))}</div><div class="customer">${escapeHtml(card.destination_url)}</div></div>
    <div class="tap-total"><b>${card.total_taps.toLocaleString()}</b> taps</div><button class="edit" data-edit="${escapeHtml(card.tap_id)}">Edit</button>
  </article>`).join('') : '<p class="empty">No cards yet. Add your first tap card.</p>';
}

async function loadCards() {
  const response = await fetch('/api/cards');
  cards = await response.json();
  render();
}

async function loadRequests() {
  const response = await fetch('/api/requests'); requests = await response.json();
  document.querySelector('#request-count').textContent = `${requests.length} request${requests.length === 1 ? '' : 's'}`;
  document.querySelector('#request-list').innerHTML = requests.length ? requests.map((item) => `<article class="request-row"><div><b>${escapeHtml(item.request_id)}</b><small>${escapeHtml(item.customer_name)}${item.business_name ? ` · ${escapeHtml(item.business_name)}` : ''}</small></div><div><span>${escapeHtml(productLabels[item.product_type])}</span><small>${escapeHtml(item.destination_type.replaceAll('_',' '))}</small></div><span class="request-status">${escapeHtml(item.status)}</span><button class="edit" data-request="${escapeHtml(item.request_id)}">View</button></article>`).join('') : '<p class="empty">No customer requests yet.</p>';
}

function openForm(card = null) {
  form.reset(); document.querySelector('#form-error').textContent = '';
  document.querySelector('#original-card-id').value = card?.tap_id || '';
  document.querySelector('#card-id').value = card?.tap_id || '';
  document.querySelector('#card-id').disabled = Boolean(card);
  document.querySelector('#customer-name').value = card?.customer_name || '';
  document.querySelector('#destination-url').value = card?.destination_url || '';
  document.querySelector('#active').checked = card?.active ?? true;
  document.querySelector('#product-type').value = card?.product_type || 'CARD';
  document.querySelector('#form-mode').textContent = card ? 'EDIT DEVICE' : 'NEW DEVICE';
  document.querySelector('#form-title').textContent = card ? card.tap_id : 'Add a tap device';
  dialog.showModal();
}

document.querySelectorAll('[data-add]').forEach((button) => button.addEventListener('click', () => openForm()));
document.querySelector('.close').addEventListener('click', () => dialog.close());
list.addEventListener('click', (event) => { const id = event.target.dataset.edit; if (id) openForm(cards.find((card) => card.tap_id === id)); });
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const originalId = document.querySelector('#original-card-id').value;
  const payload = {tap_id: document.querySelector('#card-id').value, customer_name: document.querySelector('#customer-name').value, destination_url: document.querySelector('#destination-url').value, active: document.querySelector('#active').checked, product_type: document.querySelector('#product-type').value};
  const response = await fetch(originalId ? `/api/cards/${encodeURIComponent(originalId)}` : '/api/cards', {method: originalId ? 'PATCH' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) { document.querySelector('#form-error').textContent = result.error; return; }
  dialog.close(); await loadCards();
});

loadCards().catch(() => { list.innerHTML = '<p class="empty">Tap devices could not be loaded. Please refresh.</p>'; });
const requestDialog = document.querySelector('#request-dialog');
document.querySelector('.request-close').addEventListener('click', () => requestDialog.close());
document.querySelector('#request-list').addEventListener('click', (event) => {
  const item = requests.find((request) => request.request_id === event.target.dataset.request); if (!item) return;
  document.querySelector('#request-title').textContent = item.request_id;
  const files = item.uploaded_files.map((file) => `<a class="download" href="/api/requests/${encodeURIComponent(item.request_id)}/files/${encodeURIComponent(file.stored_name)}">Download ${escapeHtml(file.name)}</a>`).join('') || '<span class="muted">No uploads</span>';
  document.querySelector('#request-detail-body').innerHTML = `<dl><dt>Customer</dt><dd>${escapeHtml(item.customer_name)}</dd><dt>Business</dt><dd>${escapeHtml(item.business_name || '—')}</dd><dt>Email</dt><dd>${escapeHtml(item.email)}</dd><dt>Phone</dt><dd>${escapeHtml(item.phone || '—')}</dd><dt>Product</dt><dd>${escapeHtml(productLabels[item.product_type])}</dd><dt>Destination</dt><dd>${escapeHtml(item.destination_url)}</dd><dt>Design option</dt><dd>${escapeHtml(item.design_option.replaceAll('_',' '))}</dd><dt>Artwork</dt><dd>${files}</dd><dt>Design notes</dt><dd>${escapeHtml(item.design_notes || '—')}</dd><dt>Submitted</dt><dd>${new Date(item.created_at).toLocaleString()}</dd></dl><label>Status<select id="request-status">${['NEW','REVIEWING','APPROVED','FULFILLED','CANCELLED'].map((status) => `<option ${status === item.status ? 'selected' : ''}>${status}</option>`).join('')}</select></label>`;
  document.querySelector('#request-status').addEventListener('change', async (change) => { await fetch(`/api/requests/${encodeURIComponent(item.request_id)}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:change.target.value})}); await loadRequests(); });
  requestDialog.showModal();
});
loadRequests().catch(() => { document.querySelector('#request-list').innerHTML = '<p class="empty">Requests could not be loaded.</p>'; });
