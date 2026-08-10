const form = document.querySelector('#customize-form');
const artwork = document.querySelector('#artwork');
const preview = document.querySelector('#preview');
const message = document.querySelector('#form-message');
const maxBytes = 10 * 1024 * 1024;

function updateDesignOption() {
  const uploadOwn = form.elements.design_option.value === 'UPLOAD';
  artwork.required = uploadOwn;
  document.querySelector('#artwork-label').firstChild.textContent = uploadOwn ? 'Your design' : 'Optional logo, photo, or reference artwork';
}

form.elements.design_option.forEach((radio) => radio.addEventListener('change', updateDesignOption));
artwork.addEventListener('change', () => {
  preview.replaceChildren();
  const file = artwork.files[0];
  if (!file) return;
  if (file.size > maxBytes) { message.textContent = 'Uploaded files must be 10 MB or smaller.'; artwork.value = ''; return; }
  message.textContent = '';
  if (['image/png', 'image/jpeg'].includes(file.type)) {
    const image = document.createElement('img'); image.alt = `Preview of ${file.name}`;
    image.src = URL.createObjectURL(file); image.onload = () => URL.revokeObjectURL(image.src); preview.append(image);
  } else { preview.textContent = file.name; }
});
form.addEventListener('submit', async (event) => {
  event.preventDefault(); message.className = ''; message.textContent = 'Submitting…';
  try {
    const response = await fetch('/api/requests', {method: 'POST', body: new FormData(form)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Your request could not be submitted.');
    form.reset(); preview.replaceChildren(); updateDesignOption();
    message.className = 'success'; message.textContent = `Thank you. Request #${result.request_id} has been submitted for review.`;
  } catch (error) { message.textContent = error.message; }
});
updateDesignOption();
