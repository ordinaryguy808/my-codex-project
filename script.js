const redesignedFaq = document.querySelector('.faq');
if (redesignedFaq) redesignedFaq.style.display = 'block';

document.querySelectorAll('.accordion details').forEach((item) => {
  item.addEventListener('toggle', () => {
    if (!item.open) return;
    document.querySelectorAll('.accordion details').forEach((other) => {
      if (other !== item) other.open = false;
    });
  });
});