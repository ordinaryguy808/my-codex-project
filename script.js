const redesignedFaq = document.querySelector('.faq');
if (redesignedFaq) redesignedFaq.style.display = 'block';

// Keep the product lineup clean until real product photography is ready.
// Remove the CSS-generated concept illustrations rather than presenting them
// as if they were finished product photos.
document.querySelectorAll('.product-art').forEach((art) => art.remove());

const productShowcase = document.querySelector('.product-showcase');
if (productShowcase) {
  const style = document.createElement('style');
  style.textContent = `
    .product-tile{position:relative;overflow:hidden}
    .product-tile::before{content:"";display:block;height:5px;background:linear-gradient(90deg,#7657e8,#a891ff)}
    .product-body{padding:34px 30px 32px;min-height:465px}
    .product-body h3{font-size:24px;letter-spacing:-.6px}
    .product-price{font-size:40px;margin:12px 0 18px}
    .product-body p{font-size:13px;line-height:1.7}
    .product-body p strong{color:#111218}
    .benefit-list{font-size:12px}
  `;
  document.head.appendChild(style);
}

document.querySelectorAll('.accordion details').forEach((item) => {
  item.addEventListener('toggle', () => {
    if (!item.open) return;
    document.querySelectorAll('.accordion details').forEach((other) => {
      if (other !== item) other.open = false;
    });
  });
});