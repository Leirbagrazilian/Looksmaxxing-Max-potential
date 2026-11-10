// Save checklist ticks immediately and update the counter.
document.querySelectorAll(".checklist").forEach((list) => {
  const day = list.dataset.day;
  const boxes = list.querySelectorAll("input[type=checkbox]");
  const update = () => {
    const done = [...boxes].filter((b) => b.checked).length;
    const count = document.getElementById("count");
    const bar = document.getElementById("pbar");
    if (count) count.textContent = `${done}/${boxes.length}`;
    if (bar) bar.style.width = `${Math.round((100 * done) / boxes.length)}%`;
  };
  boxes.forEach((b) =>
    b.addEventListener("change", async () => {
      try {
        const r = await fetch("/api/habit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ day, habit: b.dataset.habit, done: b.checked }),
        });
        if (!r.ok) throw new Error(r.status);
      } catch (e) {
        b.checked = !b.checked; // revert if it did not save
        alert("Could not save. Is the app still running?");
      }
      update();
    })
  );
});

// Show the chosen file name and a busy state while the photo is analysed.
document.querySelectorAll("form.upload").forEach((f) => {
  const input = f.querySelector("input[type=file]");
  const label = f.querySelector(".file span");
  input.addEventListener("change", () => {
    if (input.files[0]) label.textContent = input.files[0].name;
  });
  f.addEventListener("submit", () => {
    const btn = f.querySelector("button");
    btn.disabled = true;
    btn.textContent = "Analysing…";
  });
});
