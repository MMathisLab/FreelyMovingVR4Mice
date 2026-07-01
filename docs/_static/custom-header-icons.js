document.addEventListener("DOMContentLoaded", function () {
  var iconLinks = document.querySelector(".bd-sidebar-primary .navbar-icon-links");
  var headerEnd = document.querySelector(".bd-header-article .header-article-items__end");

  if (!iconLinks || !headerEnd) {
    return;
  }

  if (headerEnd.querySelector(".navbar-icon-links")) {
    return;
  }

  headerEnd.insertBefore(iconLinks, headerEnd.firstChild);
});
