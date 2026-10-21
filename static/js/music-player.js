(function () {
  var root = document.querySelector(".music-player");
  if (!root) return;

  var DB_NAME = "cafe-club-music";
  var list = root.querySelector(".music-list");
  var audio = root.querySelector(".music-audio");
  var fileInput = root.querySelector(".music-file");
  var playButton = root.querySelector(".music-play");
  var now = root.querySelector(".music-now");
  var tracks = [];
  var currentId = null;
  var objectUrl = "";

  function openDb() {
    return new Promise(function (resolve, reject) {
      var request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = function () {
        request.result.createObjectStore("tracks", {keyPath: "id"});
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error);
      };
    });
  }

  function withStore(mode, action) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("tracks", mode);
        var store = tx.objectStore("tracks");
        var result = action(store);
        tx.oncomplete = function () {
          resolve(result && result.result !== undefined ? result.result : result);
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function loadTracks() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("tracks", "readonly");
        var request = tx.objectStore("tracks").getAll();
        request.onsuccess = function () {
          resolve(request.result || []);
        };
        request.onerror = function () {
          reject(request.error);
        };
      });
    });
  }

  function saveTrack(track) {
    return withStore("readwrite", function (store) {
      return store.put(track);
    });
  }

  function deleteTrack(id) {
    return withStore("readwrite", function (store) {
      return store.delete(id);
    });
  }

  function setNow(text) {
    now.textContent = text;
  }

  function paintPlayButton() {
    var playing = !audio.paused && !audio.ended;
    playButton.textContent = playing ? playButton.dataset.pause : playButton.dataset.play;
    playButton.classList.toggle("is-playing", playing);
    playButton.disabled = tracks.length === 0;
  }

  function render() {
    list.innerHTML = "";
    tracks.forEach(function (track) {
      var item = document.createElement("li");
      if (track.id === currentId) item.className = "is-current";
      var choose = document.createElement("button");
      choose.type = "button";
      choose.className = "music-track";
      choose.textContent = track.name;
      choose.addEventListener("click", function () {
        playTrack(track.id);
      });
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "music-remove";
      remove.setAttribute("aria-label", "حذف آهنگ");
      remove.textContent = "×";
      remove.addEventListener("click", function () {
        removeTrack(track.id);
      });
      item.appendChild(choose);
      item.appendChild(remove);
      list.appendChild(item);
    });
    paintPlayButton();
    if (!tracks.length) setNow(now.dataset.empty || now.textContent);
  }

  function revokeUrl() {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = "";
    }
  }

  function playTrack(id) {
    var track = tracks.filter(function (item) {
      return item.id === id;
    })[0];
    if (!track) return;
    currentId = id;
    revokeUrl();
    objectUrl = URL.createObjectURL(track.blob);
    audio.src = objectUrl;
    setNow(track.name);
    render();
    audio.play().then(paintPlayButton).catch(paintPlayButton);
  }

  function playNext() {
    if (!tracks.length) return;
    var index = tracks.findIndex(function (track) {
      return track.id === currentId;
    });
    var next = tracks[(index + 1) % tracks.length];
    playTrack(next.id);
  }

  function removeTrack(id) {
    deleteTrack(id).then(function () {
      var wasCurrent = id === currentId;
      tracks = tracks.filter(function (track) {
        return track.id !== id;
      });
      if (wasCurrent) {
        audio.pause();
        audio.removeAttribute("src");
        revokeUrl();
        currentId = null;
        setNow(now.dataset.empty);
      }
      render();
    });
  }

  root.querySelector(".music-add").addEventListener("click", function () {
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    var files = Array.prototype.slice.call(fileInput.files || []);
    fileInput.value = "";
    var saves = files.filter(function (file) {
      return file.type.indexOf("audio/") === 0 || /\.(mp3|m4a|aac|ogg|wav|flac)$/i.test(file.name);
    }).map(function (file) {
      var track = {
        id: Date.now() + Math.random(),
        name: file.name.replace(/\.[^.]+$/, ""),
        blob: file
      };
      return saveTrack(track).then(function () {
        tracks.push(track);
      });
    });
    Promise.all(saves).then(render);
  });

  playButton.addEventListener("click", function () {
    if (!tracks.length) return;
    if (!audio.paused && !audio.ended) {
      audio.pause();
      paintPlayButton();
      return;
    }
    if (!currentId || audio.ended || !audio.src) {
      playTrack(currentId || tracks[0].id);
      return;
    }
    audio.play().then(paintPlayButton).catch(paintPlayButton);
  });

  audio.addEventListener("ended", function () {
    playNext();
  });
  audio.addEventListener("play", paintPlayButton);
  audio.addEventListener("pause", paintPlayButton);

  now.dataset.empty = now.textContent;
  loadTracks().then(function (saved) {
    tracks = saved;
    render();
  }).catch(function () {
    render();
  });
})();
