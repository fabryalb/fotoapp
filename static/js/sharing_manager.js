// Inserisci qui il codice JavaScript sharing_manager.js completo


function mostraPopup(link) {
  const box = document.getElementById("popup-link");
  const anchor = document.getElementById("link-generato");
  anchor.href = link;
  anchor.innerText = link;
  box.style.display = "block";
}

function copyLink() {
  const link = document.getElementById("link-generato").href;
  navigator.clipboard.writeText(link).then(() => alert("Link copiato negli appunti!"));
}

function shareWhatsApp() {
  const link = document.getElementById("link-generato").href;
  window.open(`https://wa.me/?text=${encodeURIComponent(link)}`, '_blank');
}

function mostraPopup(link) {
  const box = document.getElementById("popup-link");
  const anchor = document.getElementById("link-generato");
  const waBtn = document.getElementById("waShare");
  const tgBtn = document.getElementById("tgShare");
  const mailBtn = document.getElementById("emailShare");

  anchor.href = link;
  anchor.innerText = link;
  waBtn.href = `https://wa.me/?text=${encodeURIComponent(link)}`;
  tgBtn.href = `https://t.me/share/url?url=${encodeURIComponent(link)}`;
  mailBtn.href = `mailto:?subject=Condivisione foto&body=${encodeURIComponent(link)}`;
  box.style.display = "block";
}

function copyLink() {
  const link = document.getElementById("link-generato").href;
  navigator.clipboard.writeText(link).then(() => alert("Link copiato negli appunti!"));
}