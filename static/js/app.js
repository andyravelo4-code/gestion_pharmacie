/* Interactions légères PharmaGest */
document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const toggles = document.querySelectorAll("[data-toggle-sidebar]");

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
  }

  toggles.forEach(function (bouton) {
    bouton.addEventListener("click", function () {
      if (!sidebar) return;
      sidebar.classList.toggle("open");
      if (backdrop) backdrop.classList.toggle("show", sidebar.classList.contains("open"));
    });
  });
  if (backdrop) backdrop.addEventListener("click", closeSidebar);

  document.querySelectorAll("[data-confirm]").forEach(function (element) {
    element.addEventListener("click", function (event) {
      const message = element.getAttribute("data-confirm") || "Confirmer cette opération ?";
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
  });

  // Soumission unique : évite les doubles validations côté navigateur.
  document.querySelectorAll("form[data-submit-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      const bouton = form.querySelector("[type=submit]");
      if (bouton) {
        bouton.disabled = true;
        bouton.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1"></span>Traitement…';
      }
    });
  });

  // Fermeture automatique des alertes après 8 secondes.
  document.querySelectorAll(".alert.auto-dismiss").forEach(function (alerte) {
    window.setTimeout(function () {
      if (window.bootstrap) {
        const instance = bootstrap.Alert.getOrCreateInstance(alerte);
        instance.close();
      }
    }, 8000);
  });

  // Impression d'un reçu depuis la page de détail.
  document.querySelectorAll("[data-print]").forEach(function (bouton) {
    bouton.addEventListener("click", function () {
      window.print();
    });
  });
});
