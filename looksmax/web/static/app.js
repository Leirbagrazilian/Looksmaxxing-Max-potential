const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

function toast(html) {
  const t = $("#toast");
  if (!t) return;
  t.innerHTML = html;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 1800);
}

// Segmented controls: quest blocks (data-slot) and progress panes (data-pane).
$$(".seg").forEach((seg) => {
  seg.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    $$("button", seg).forEach((x) => x.classList.toggle("on", x === b));
    const key = b.dataset.slot ? "slot" : "pane";
    const val = b.dataset[key];
    $$(`[data-${key}]:not(button)`).forEach((p) => (p.hidden = p.dataset[key] !== val));
  });
});

// Quests: save ticks instantly, update ring, counters, XP and rank chip.
$$(".quests").forEach((q) => {
  const day = q.dataset.day;
  const boxes = $$("input[type=checkbox]", q);
  const refresh = () => {
    const done = boxes.filter((b) => b.checked);
    const pct = boxes.length ? Math.round((100 * done.length) / boxes.length) : 0;
    $("#count").textContent = done.length;
    $("#ring").style.setProperty("--p", pct);
    $("#xp-today").textContent = "+" + done.reduce((s, b) => s + +b.dataset.xp, 0);
    $$("[data-count]").forEach((c) => {
      const list = $$(`.checklist[data-slot="${c.dataset.count}"] input`);
      c.textContent = `${list.filter((b) => b.checked).length}/${list.length}`;
    });
    const coach = $("#coach");
    const left = boxes.filter((b) => !b.checked);
    if (!left.length) coach.textContent = `All ${boxes.length} quests cleared. Nice work.`;
    else if (done.length) coach.textContent = `${done.length} done, ${left.length} to go. Next: ${left[0].closest("label").querySelector(".lbl").firstChild.textContent.trim().toLowerCase()}.`;
  };
  boxes.forEach((b) =>
    b.addEventListener("change", async () => {
      b.closest("li").classList.toggle("done", b.checked);
      try {
        const r = await fetch("/api/habit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ day, habit: b.dataset.habit, done: b.checked }),
        });
        if (!r.ok) throw new Error(r.status);
        const j = await r.json();
        const chip = $(".rankchip");
        if (chip) {
          chip.title = `${j.rank.xp} XP`;
          $(".tier", chip).textContent = j.rank.tier;
          $(".rname", chip).textContent = j.rank.name;
          $("b", chip).style.setProperty("--p", Math.round(100 * j.rank.progress) + "%");
        }
        if (b.checked) toast(`<span class="gold">+${b.dataset.xp} XP</span>${boxes.every((x) => x.checked) ? "All quests cleared" : "Quest cleared"}`);
      } catch (e) {
        b.checked = !b.checked;
        b.closest("li").classList.toggle("done", b.checked);
        toast("Couldn't save. Is the app still running?");
      }
      refresh();
    })
  );
});

// Upload: show file name, busy state while analysing.
$$("form.upload").forEach((f) => {
  const input = $("input[type=file]", f);
  const label = $(".file span", f);
  input.addEventListener("change", () => input.files[0] && (label.textContent = input.files[0].name));
  f.addEventListener("submit", () => {
    const btn = $("button", f);
    btn.disabled = true;
    btn.textContent = "Analysing your face…";
  });
});
