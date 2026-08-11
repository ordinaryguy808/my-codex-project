const form = document.querySelector('#customize-form');
const artwork = document.querySelector('#artwork');
const preview = document.querySelector('#preview');
const message = document.querySelector('#form-message');
const productSelect = document.querySelector('#product-type');
const maxBytes = 10 * 1024 * 1024;

const offers = {
  CARD: {name: 'Tappr Agent Card', price: 79, description: 'One NFC + QR agent card with its own Tap ID.'},
  PLAQUE: {name: 'Tappr Open House Stand', price: 129, description: 'One tabletop NFC + QR display that can be reused for future open houses.'},
  PROPERTY_SIGN_TAG: {name: 'Tappr Smart Sign Rider', price: 149, description: 'One reusable NFC + QR property-sign attachment.'},
  AGENT_LAUNCH_KIT: {name: 'Agent Launch Kit', price: 299, package: true, description: '1 Agent Card + 1 Open House Stand + 1 Smart Sign Rider. Professional design included.'},
  LISTING_PRO_KIT: {name: 'Listing Pro Kit', price: 499, package: true, description: '1 Agent Card + 1 Open House Stand + 3 Smart Sign Riders. Professional design included.'},
  TEAM_LAUNCH_KIT: {name: 'Team Launch Kit', price: 999, package: true, description: '3 Agent Cards + 2 Open House Stands + 6 Smart Sign Riders. Coordinated professional design included.'},
};

function currentOffer() {
  return offers[productSelect.value] || offers.CARD;
}

function updateDesignOption() {
  const uploadOwn = form.elements.design_option.value === 'UPLOAD';
  artwork.required = uploadOwn;
  document.querySelector('#artwork-label').firstChild.textContent = uploadOwn ? 'Your design' : 'Optional logo, photo, or reference artwork';
  updateEstimate();
}

function updateEstimate() {
  const offer = currentOffer();
  const wantsDesign = form.elements.design_option.value === 'TAPPR_DESIGN';
  const designPrice = offer.package ? 0 : (wantsDesign ? 59 : 0);
  const designText = offer.package ? 'Included' : `$${designPrice}`;

  document.querySelector('#selection-description').innerHTML = `<b>${offer.name}</b><br>${offer.description}`;
  document.querySelector('#estimate-product-name').textContent = offer.name;
  document.querySelector('#estimate-product-price').textContent = `$${offer.price}`;
  document.querySelector('#estimate-design-price').textContent = designText;
  document.querySelector('#estimate-total').textContent = `$${offer.price + designPrice}`;
}

function applyQuerySelection() {
  const params = new URLSearchParams(window.location.search);
  const product = params.get('product');
  const packageName = params.get('package');
  const packageMap = {
    'agent-launch': 'AGENT_LAUNCH_KIT',
    'listing-pro': 'LISTING_PRO_KIT',
    'team-launch': 'TEAM_LAUNCH_KIT',
  };
  const desired = packageName ? packageMap[packageName] : product;
  if (desired && offers[desired]) productSelect.value = desired;
}

form.elements.design_option.forEach((radio) => radio.addEventListener('change', updateDesignOption));
productSelect.addEventListener('change', updateEstimate);

artwork.addEventListener('change', () => {
  preview.replaceChildren();
  const file = artwork.files[0];
  if (!file) return;
  if (file.size > maxBytes) {
    message.textContent = 'Uploaded files must be 10 MB or smaller.';
    artwork.value = '';
    return;
  }
  message.textContent = '';
  if (['image/png', 'image/jpeg'].includes(file.type)) {
    const image = document.createElement('img');
    image.alt = `Preview of ${file.name}`;
    image.src = URL.createObjectURL(file);
    image.onload = () => URL.revokeObjectURL(image.src);
    preview.append(image);
  } else {
    preview.textContent = file.name;
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = 'Submitting…';
  try {
    const response = await fetch('/api/requests', {method: 'POST', body: new FormData(form)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Your request could not be submitted.');
    form.reset();
    preview.replaceChildren();
    applyQuerySelection();
    updateDesignOption();
    updateEstimate();
    message.className = 'success';
    message.textContent = `Thank you. Request #${result.request_id} has been submitted for review.`;
  } catch (error) {
    message.textContent = error.message;
  }
});

applyQuerySelection();
updateDesignOption();
updateEstimate();