const list = document.querySelector('#card-list');
const dialog = document.querySelector('#card-dialog');
const form = document.querySelector('#card-form');
let cards = [];

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));

function destinationLabel(value) {
  try { return new URL(value).hostname.replace(/^www\./, ''); } catch { return value; }
}

function render() {
  document.querySelector('#card-count').textContent = cards.length;
  document.querySelector('#active-count').textContent = cards.filter((card) => card.active).length;
  document.querySelector('#tap-count').textContent = cards.reduce((sum, card) => sum + card.total_taps, 0).toLocaleString();
  list.innerHTML = cards.length ? cards.map((card) => `<article class="card-row">
    <div><div class="card-id">${escapeHtml(card.card_id)}</div><div class="customer">${escapeHtml(card.customer_name)}</div><span class="status ${card.active ? '' : 'inactive'}">${card.active ? 'ACTIVE' : 'INACTIVE'}</span></div>
    <div><div class="destination">${escapeHtml(destinationLabel(card.destination_url))}</div><div class="customer">${escapeHtml(card.destination_url)}</div></div>
    <div class="tap-total"><b>${card.total_taps.toLocaleString()}</b> taps</div><button class="edit" data-edit="${escapeHtml(card.card_id)}">Edit</button>
  </article>`).join('') : '<p class="empty">No cards yet. Add your first tap card.</p>';
}

async function loadCards() {
  const response = await fetch('/api/cards');
  cards = await response.json();
  render();
}

function openForm(card = null) {
  form.reset(); document.querySelector('#form-error').textContent = '';
  document.querySelector('#original-card-id').value = card?.card_id || '';
  document.querySelector('#card-id').value = card?.card_id || '';
  document.querySelector('#card-id').disabled = Boolean(card);
  document.querySelector('#customer-name').value = card?.customer_name || '';
  document.querySelector('#destination-url').value = card?.destination_url || '';
  document.querySelector('#active').checked = card?.active ?? true;
  document.querySelector('#form-mode').textContent = card ? 'EDIT CARD' : 'NEW CARD';
  document.querySelector('#form-title').textContent = card ? card.card_id : 'Add a tap card';
  dialog.showModal();
}

document.querySelectorAll('[data-add]').forEach((button) => button.addEventListener('click', () => openForm()));
document.querySelector('.close').addEventListener('click', () => dialog.close());
list.addEventListener('click', (event) => { const id = event.target.dataset.edit; if (id) openForm(cards.find((card) => card.card_id === id)); });
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const originalId = document.querySelector('#original-card-id').value;
  const payload = {card_id: document.querySelector('#card-id').value, customer_name: document.querySelector('#customer-name').value, destination_url: document.querySelector('#destination-url').value, active: document.querySelector('#active').checked};
  const response = await fetch(originalId ? `/api/cards/${encodeURIComponent(originalId)}` : '/api/cards', {method: originalId ? 'PATCH' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) { document.querySelector('#form-error').textContent = result.error; return; }
  dialog.close(); await loadCards();
});

loadCards().catch(() => { list.innerHTML = '<p class="empty">Cards could not be loaded. Please refresh.</p>'; });
