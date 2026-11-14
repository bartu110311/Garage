const hex = document.getElementById('hex');
const menu = document.getElementById('menu');

function menuAyarla(ac) {
  menu.classList.toggle('acik', ac);
  menu.inert = !ac;                       // kapalıyken odaklanılamaz/tıklanamaz
  hex.setAttribute('aria-expanded', ac);
}
hex.addEventListener('click', () => menuAyarla(!menu.classList.contains('acik')));
addEventListener('keydown', e => { if (e.key === 'Escape') menuAyarla(false); });