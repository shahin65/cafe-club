(function () {
  var SIDES = ["mafia", "citizen", "independent", "werewolf"];
  var COUNT_FIELDS = {
    mafia: "mafia_count",
    citizen: "citizen_count",
    independent: "independent_count",
    werewolf: "werewolf_count",
  };

  function number(input) {
    if (!input) return 0;
    return parseInt(input.value, 10) || 0;
  }

  function field(box, suffix) {
    return box.querySelector('[name$="-' + suffix + '"]:not([name*="-roles-"]):not([name*="-finals-"])');
  }

  function sideList(box) {
    var list = [];
    SIDES.forEach(function (side) {
      var count = number(field(box, COUNT_FIELDS[side]));
      for (var index = 0; index < count; index += 1) list.push(side);
    });
    return list;
  }

  function syncRows(table, visible, assignSides) {
    if (!table) return;
    var rows = table.querySelectorAll("tbody tr.nested-slot-row");
    rows.forEach(function (row, index) {
      var show = index < visible;
      row.hidden = !show;
      row.querySelectorAll("input, select, textarea").forEach(function (input) {
        input.disabled = !show;
      });
      if (show && assignSides) {
        var side = row.querySelector("select[name$='-side']");
        if (side && assignSides[index]) side.value = assignSides[index];
      }
    });
  }

  function syncBox(box) {
    if (!box || box.classList.contains("empty-form")) return;
    var players = number(field(box, "player_count"));
    var finals = number(field(box, "final_move_count"));
    var hasFinal = document.getElementById("id_has_final_move");
    var finalOn = !hasFinal || hasFinal.checked;
    syncRows(box.querySelector(".nested-roles table"), players, sideList(box));
    var finalsWrap = box.querySelector(".nested-finals");
    if (finalsWrap) finalsWrap.hidden = !finalOn;
    syncRows(box.querySelector(".nested-finals table"), finalOn ? finals : 0, null);
  }

  function syncAll() {
    document.querySelectorAll("#sizes-group .inline-related").forEach(syncBox);
  }

  document.addEventListener("change", function (event) {
    var name = event.target && event.target.name;
    if (!name) return;
    if (
      name === "has_final_move" ||
      /-(player_count|mafia_count|citizen_count|independent_count|werewolf_count|final_move_count)$/.test(name)
    ) {
      syncAll();
    }
  });
  document.addEventListener("formset:added", syncAll);
  document.addEventListener("DOMContentLoaded", syncAll);
})();
