(function () {
  var title = document.title || "tournament";

  function canvasToBlob(canvas) {
    return new Promise(function (resolve) {
      canvas.toBlob(function (blob) {
        resolve(blob);
      }, "image/png");
    });
  }

  function boardFor(button) {
    var id = button.getAttribute("data-share-target");
    if (id) return document.getElementById(id);
    return document.querySelector("[data-share-board]");
  }

  function capture(board) {
    if (!board || typeof html2canvas !== "function") return Promise.reject(new Error("html2canvas"));
    return html2canvas(board, {
      backgroundColor: "#12141c",
      scale: 2,
      useCORS: true,
      onclone: function (doc) {
        var clone = doc.getElementById(board.id) || doc.querySelector("[data-share-board]");
        if (!clone) return;
        clone.querySelectorAll(".tournament-share-kicker, .tournament-name, bdi").forEach(function (el) {
          el.style.letterSpacing = "0px";
          el.style.unicodeBidi = "isolate";
          el.style.direction = "rtl";
        });
      }
    });
  }

  function fileNameFor(board) {
    var heading = board && board.querySelector("h2, h1");
    var label = heading ? heading.textContent.trim() : "tournament";
    return "cafe-club-" + label.replace(/\s+/g, "-") + ".png";
  }

  document.querySelectorAll("[data-save-image]").forEach(function (button) {
    button.addEventListener("click", function () {
      var board = boardFor(button);
      capture(board)
        .then(function (canvas) {
          var link = document.createElement("a");
          link.download = fileNameFor(board);
          link.href = canvas.toDataURL("image/png");
          link.click();
        })
        .catch(function () {
          window.print();
        });
    });
  });

  document.querySelectorAll("[data-share-page]").forEach(function (button) {
    button.addEventListener("click", function () {
      var board = boardFor(button);
      capture(board)
        .then(canvasToBlob)
        .then(function (blob) {
          var file = new File([blob], fileNameFor(board), { type: "image/png" });
          if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
            return navigator.share({ files: [file], title: title, text: title });
          }
          if (navigator.share) {
            return navigator.share({ title: title, text: title, url: window.location.href });
          }
          var link = document.createElement("a");
          link.download = fileNameFor(board);
          link.href = URL.createObjectURL(blob);
          link.click();
        })
        .catch(function () {
          if (navigator.share) {
            navigator.share({ title: title, text: title, url: window.location.href });
          }
        });
    });
  });
})();
