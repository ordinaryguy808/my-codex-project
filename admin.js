const list = document.querySelector('#card-list');
const dialog = document.querySelector('#card-dialog');
const form = document.querySelector('#card-form');
let cards = [];
let requests = [];

const productNames = {
  CARD: 'Tappr Agent Card',
  PLAQUE: 'Tappr Open House Stand',
  PROPERTY_SIGN_TAG: 'Tappr Smart Sign Rider',
  AGENT_LAUNCH_KIT: 'Agent Launch Kit',
  LISTING_PRO_KIT: 'Listing Pro Kit',
  TEAM_LAUNCH_KIT: 'Team Launch Kit',
};
const designNames = {UPLOAD: 'Uploaded own design', TAPPR_DESIGN: 'Tappr Custom Design'};

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));

function destinationLabel(value) {
  try { return new URL(value).hostname.replace(/^www\./, ''); } catch { return value; }
}

function render() {
  document.querySelector('#card-count').textContent = cards.length;
  document.querySelector('#active-count').textContent = cards.filter((card) => card.active).length;
  document.querySelector('#tap-count').textContent = cards.reduce((sum, card) => sum + card.total_taps, 0).toLocaleString();
  list.innerHTML = cards.length ? cards.map((card) => `<article class="card-row">
    <div><div class="card-id">${escapeHtml(card.card_id)}</div><div class="customer">${escapeHtml(card.customer_name)}</div><div class="product-type">${escapeHtml(productNames[card.product_type] || card.product_type)}</div><span class="status ${card.active ? '' : 'inactive'}">${card.active ? 'ACTIVE' : 'INACTIVE'}</span></div>
    <div><div class="destination">${escapeHtml(destinationLabel(card.destination_url))}</div><div class="customer">${escapeHtml(card.destination_url)}</div></div>
    <div class="tap-total"><b>${card.total_taps.toLocaleString()}</b> taps</div><button class="edit" data-edit="${escapeHtml(card.card_id)}">Edit</button>
  </article>`).join('') : '<p class="empty">No Tap Devices yet. Add your first device.</p>';
}

function renderRequests() {
  const requestList = document.querySelector('#request-list');
  requestList.innerHTML = requests.length ? requests.map((request) => `<article class="request-row">
    <div class="request-heading"><b>#${request.request_id} · ${escapeHtml(request.customer_name)}</b><span>${escapeHtml(new Date(request.created_at).toLocaleString())}</span></div>
    <dl><div><dt>Business</dt><dd>${escapeHtml(request.business_name || '—')}</dd></div><div><dt>Contact</dt><dd>${escapeHtml(request.email)}${request.phone ? ` · ${escapeHtml(request.phone)}` : ''}</dd></div><div><dt>Product / package</dt><dd>${escapeHtml(productNames[request.product_type] || request.product_type)}</dd></div><div><dt>Destination</dt><dd>${escapeHtml(request.destination_type)} · <a href="${escapeHtml(request.destination_url)}" target="_blank" rel="noopener">${escapeHtml(request.destination_url)}</a></dd></div><div><dt>Design</dt><dd>${escapeHtml(designNames[request.design_option] || request.design_option)}</dd></div><div><dt>Artwork</dt><dd>${request.has_artwork ? `<a href="/api/requests/${request.request_id}/artwork">Download ${escapeHtml(request.original_file_name)}</a>` : 'None'}</dd></div><div><dt>Notes</dt><dd>${escapeHtml(request.design_notes || '—')}</dd></div></dl>
    <label>Status<select data-request-status="${request.request_id}">${['NEW','REVIEWING','APPROVED','FULFILLED','CANCELLED'].map((status) => `<option ${request.status === status ? 'selected' : ''}>${status}</option>`).join('')}</select></label>
  </article>`).join('') : '<p class="empty">No customer requests yet.</p>';
}

async function loadCards() {
  const response = await fetch('/api/cards');
  cards = await response.json();
  render();
}

async function loadRequests() {
  const response = await fetch('/api/requests');
  if (!response.ok) throw new Error('Could not load requests');
  requests = await response.json(); renderRequests();
}

function openForm(card = null) {
  form.reset(); document.querySelector('#form-error').textContent = '';
  document.querySelector('#original-card-id').value = card?.card_id || '';
  document.querySelector('#card-id').value = card?.card_id || '';
  document.querySelector('#card-id').disabled = Boolean(card);
  document.querySelector('#customer-name').value = card?.customer_name || '';
  document.querySelector('#destination-url').value = card?.destination_url || '';
  document.querySelector('#product-type').value = card?.product_type || 'CARD';
  document.querySelector('#active').checked = card?.active ?? true;
  document.querySelector('#form-mode').textContent = card ? 'EDIT TAP DEVICE' : 'NEW TAP DEVICE';
  document.querySelector('#form-title').textContent = card ? card.card_id : 'Add a Tap Device';
  dialog.showModal();
}

document.querySelectorAll('[data-add]').forEach((button) => button.addEventListener('click', () => openForm()));
document.querySelector('.close').addEventListener('click', () => dialog.close());
list.addEventListener('click', (event) => { const id = event.target.dataset.edit; if (id) openForm(cards.find((card) => card.card_id === id)); });
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const originalId = document.querySelector('#original-card-id').value;
  const payload = {card_id: document.querySelector('#card-id').value, customer_name: document.querySelector('#customer-name').value, product_type: document.querySelector('#product-type').value, destination_url: document.querySelector('#destination-url').value, active: document.querySelector('#active').checked};
  const response = await fetch(originalId ? `/api/cards/${encodeURIComponent(originalId)}` : '/api/cards', {method: originalId ? 'PATCH' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) { document.querySelector('#form-error').textContent = result.error; return; }
  dialog.close(); await loadCards();
});

document.querySelector('#request-list').addEventListener('change', async (event) => {
  const requestId = event.target.dataset.requestStatus;
  if (!requestId) return;
  const response = await fetch(`/api/requests/${requestId}`, {method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({status: event.target.value})});
  if (!response.ok) { alert('The request status could not be updated.'); await loadRequests(); return; }
  await loadRequests();
});

loadCards().catch(() => { list.innerHTML = '<p class="empty">Cards could not be loaded. Please refresh.</p>'; });
loadRequests().catch(() => { document.querySelector('#request-list').innerHTML = '<p class="empty">Requests could not be loaded. Please refresh.</p>'; });