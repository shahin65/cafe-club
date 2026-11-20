(function () {
  var root = document.querySelector("[data-staff-sizes]");
  if (!root) return;
  var list = root.querySelector("[data-size-list]");
  var addBtn = root.querySelector("[data-add-size]");
  var template = root.querySelector("[data-size-template]");
  var maxModes = 8;
  function blocks() {
    return list ? list.querySelectorAll("[data-size-block]") : [];
  }
  function reindex() {
    var items = blocks();
    Array.prototype.forEach.call(items, function (block, index) {
      var legend = block.querySelector("legend");
      if (legend) legend.textContent = "حالت " + (index + 1);
      Array.prototype.forEach.call(block.querySelectorAll("[name]"), function (el) {
        el.name = el.name.replace(/\d+$/, String(index));
      });
    });
    if (addBtn) addBtn.hidden = items.length >= maxModes;
  }
  if (addBtn && template && list) {
    addBtn.addEventListener("click", function () {
      if (blocks().length >= maxModes) return;
      list.appendChild(template.content.cloneNode(true));
      reindex();
    });
  }
  reindex();
})();
