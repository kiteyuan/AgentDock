/**
 * Codex Pet atlas player — switchable community pets.
 * Atlas: 8×9 × 192×208; only cycle non-empty frames.
 */
(function (global) {
  const CELL_W = 192;
  const CELL_H = 208;

  const PETS = {
    "monthly-salary-cat": {
      label: "Monthly salary cat",
      src: "./sprites/monthly-salary-cat/spritesheet.webp",
      url: "https://codex-pets.net/#/pets/monthly-salary-cat",
    },
    "arona-v1": {
      label: "Arona",
      src: "./sprites/arona-v1/spritesheet.webp",
      url: "https://codex-pets.net/#/pets/arona-v1",
    },
  };

  const ROW = {
    idle: 0,
    waving: 3,
    failed: 5,
    waiting: 6,
    review: 8,
  };

  const FRAMES = {
    0: 6,
    1: 8,
    2: 8,
    3: 4,
    4: 5,
    5: 8,
    6: 6,
    7: 6,
    8: 6,
  };

  function moodRow(mood) {
    if (mood === "listen") return ROW.waiting;
    if (mood === "busy") return ROW.review;
    if (mood === "speak") return ROW.waving;
    if (mood === "err" || mood === "offline") return ROW.failed;
    return ROW.idle;
  }

  function createPixelBot(canvas, initialPetId) {
    canvas.width = CELL_W;
    canvas.height = CELL_H;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;

    let mood = "offline";
    let tick = 0;
    let timer = null;
    let sheet = null;
    let ready = false;
    let lastKey = "";
    let petId = PETS[initialPetId] ? initialPetId : "monthly-salary-cat";
    let loadGen = 0;

    function loadSheet(id) {
      const pet = PETS[id] || PETS["monthly-salary-cat"];
      petId = pet === PETS[id] ? id : "monthly-salary-cat";
      ready = false;
      sheet = null;
      lastKey = "";
      const gen = ++loadGen;
      const img = new Image();
      img.onload = () => {
        if (gen !== loadGen) return;
        sheet = img;
        ready = true;
        redraw(true);
      };
      img.onerror = () => {
        if (gen !== loadGen) return;
        console.warn("Missing spritesheet at", pet.src);
      };
      img.src = pet.src;
    }

    function redraw(force) {
      if (!ready || !sheet) return;
      const row = moodRow(mood);
      const n = FRAMES[row] || 1;
      const col = tick % n;
      const key = petId + ":" + row + ":" + col;
      if (!force && key === lastKey) return;
      lastKey = key;

      ctx.clearRect(0, 0, CELL_W, CELL_H);
      ctx.drawImage(
        sheet,
        col * CELL_W,
        row * CELL_H,
        CELL_W,
        CELL_H,
        0,
        0,
        CELL_W,
        CELL_H
      );
    }

    loadSheet(petId);

    return {
      setMood(next) {
        mood = next || "idle";
        tick = 0;
        lastKey = "";
        redraw(true);
      },
      setPet(id) {
        if (!PETS[id] || id === petId) return;
        loadSheet(id);
        tick = 0;
      },
      getPet() {
        return petId;
      },
      listPets() {
        return Object.keys(PETS).map((id) => ({ id, label: PETS[id].label, url: PETS[id].url }));
      },
      start() {
        if (timer) return;
        timer = setInterval(() => {
          tick += 1;
          redraw(false);
        }, 160);
        redraw(true);
      },
      stop() {
        if (timer) clearInterval(timer);
        timer = null;
      },
    };
  }

  global.PixelBot = { createPixelBot, PETS };
})(window);
