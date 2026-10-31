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

  function sizeBoxes() {
    return Array.from(document.querySelectorAll("#sizes-group .inline-related")).filter(function (box) {
      return !box.classList.contains("empty-form");
    });
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

  function roleValues(box) {
    var map = { mafia: [], citizen: [], independent: [], werewolf: [] };
    box.querySelectorAll(".nested-roles tbody tr.nested-slot-row").forEach(function (row) {
      if (row.hidden) return;
      var side = row.querySelector("select[name$='-side']");
      var name = row.querySelector("input[name$='-name']");
      var desc = row.querySelector("textarea[name$='-description'], input[name$='-description']");
      if (!side || !name || !name.value.trim()) return;
      map[side.value].push({
        name: name.value,
        description: desc ? desc.value : "",
      });
    });
    return map;
  }

  function finalValues(box) {
    var items = [];
    box.querySelectorAll(".nested-finals tbody tr.nested-slot-row").forEach(function (row) {
      if (row.hidden) return;
      var name = row.querySelector("input[name$='-name']");
      var desc = row.querySelector("textarea[name$='-description'], input[name$='-description']");
      if (!name || !name.value.trim()) return;
      items.push({ name: name.value, description: desc ? desc.value : "" });
    });
    return items;
  }

  function findSource(box) {
    var players = number(field(box, "player_count"));
    if (!players) return null;
    var best = null;
    var bestPlayers = -1;
    sizeBoxes().forEach(function (other) {
      if (other === box) return;
      var count = number(field(other, "player_count"));
      if (count && count < players && count > bestPlayers) {
        best = other;
        bestPlayers = count;
      }
    });
    if (best) return best;
    var larger = Infinity;
    sizeBoxes().forEach(function (other) {
      if (other === box) return;
      var count = number(field(other, "player_count"));
      if (count && count !== players && count < larger) {
        best = other;
        larger = count;
      }
    });
    return best;
  }

  function copyCountsIfEmpty(box, source) {
    var destPlayers = number(field(box, "player_count"));
    var srcPlayers = number(field(source, "player_count"));
    if (!destPlayers || !srcPlayers) return;
    var destSides = SIDES.reduce(function (sum, side) {
      return sum + number(field(box, COUNT_FIELDS[side]));
    }, 0);
    if (destSides) return;
    var remaining = destPlayers;
    SIDES.forEach(function (side) {
      var input = field(box, COUNT_FIELDS[side]);
      if (!input) return;
      var value = Math.min(number(field(source, COUNT_FIELDS[side])), remaining);
      input.value = String(value);
      remaining -= value;
    });
    if (remaining > 0) {
      var citizen = field(box, "citizen_count");
      if (citizen) citizen.value = String(number(citizen) + remaining);
    }
    var destFinal = field(box, "final_move_count");
    var srcFinal = field(source, "final_move_count");
    if (destFinal && srcFinal && !number(destFinal)) destFinal.value = srcFinal.value;
  }

  function fillRolesFromSource(box, source) {
    var copied = roleValues(source);
    var used = { mafia: 0, citizen: 0, independent: 0, werewolf: 0 };
    box.querySelectorAll(".nested-roles tbody tr.nested-slot-row").forEach(function (row) {
      if (row.hidden) return;
      var side = row.querySelector("select[name$='-side']");
      var name = row.querySelector("input[name$='-name']");
      var desc = row.querySelector("textarea[name$='-description'], input[name$='-description']");
      if (!side || !name || name.value.trim()) return;
      var list = copied[side.value] || [];
      var index = used[side.value] || 0;
      if (!list[index]) return;
      name.value = list[index].name;
      if (desc) desc.value = list[index].description;
      used[side.value] = index + 1;
    });
  }

  function fillFinalsFromSource(box, source) {
    var copied = finalValues(source);
    var index = 0;
    box.querySelectorAll(".nested-finals tbody tr.nested-slot-row").forEach(function (row) {
      if (row.hidden) return;
      var name = row.querySelector("input[name$='-name']");
      var desc = row.querySelector("textarea[name$='-description'], input[name$='-description']");
      if (!name || name.value.trim() || !copied[index]) {
        if (name && name.value.trim()) index += 1;
        return;
      }
      name.value = copied[index].name;
      if (desc) desc.value = copied[index].description;
      index += 1;
    });
  }

  function syncBox(box) {
    if (!box || box.classList.contains("empty-form")) return;
    var source = findSource(box);
    if (source) copyCountsIfEmpty(box, source);
    var players = number(field(box, "player_count"));
    var finals = number(field(box, "final_move_count"));
    var hasFinal = document.getElementById("id_has_final_move");
    var finalOn = !hasFinal || hasFinal.checked;
    syncRows(box.querySelector(".nested-roles table"), players, sideList(box));
    var finalsWrap = box.querySelector(".nested-finals");
    if (finalsWrap) finalsWrap.hidden = !finalOn;
    syncRows(box.querySelector(".nested-finals table"), finalOn ? finals : 0, null);
    if (source) {
      fillRolesFromSource(box, source);
      if (finalOn) fillFinalsFromSource(box, source);
    }
  }

  function syncAll() {
    sizeBoxes().forEach(syncBox);
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

  document.addEventListener("click", function (event) {
    var link = event.target.closest("[data-clear-image]");
    if (!link) return;
    event.preventDefault();
    var wrap = link.closest("[data-clearable-image]");
    if (!wrap) return;
    var box = wrap.querySelector(".js-clear-image-box");
    if (box) box.checked = true;
    var image = wrap.querySelector("img");
    if (image) image.remove();
    link.textContent = "تصویر حذف می‌شود. تصویر جدید را انتخاب کنید.";
    link.setAttribute("aria-disabled", "true");
  });
})();
