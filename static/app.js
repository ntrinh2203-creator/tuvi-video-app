const form = document.getElementById("render-form");
const submitBtn = document.getElementById("submit-btn");
const progressBox = document.getElementById("progress-box");
const logList = document.getElementById("log-list");
const resultBox = document.getElementById("result");
const preview = document.getElementById("preview");
const dlVideo = document.getElementById("dl-video");
const dlThumb = document.getElementById("dl-thumb");
const descriptionBox = document.getElementById("description-box");
const copyDescBtn = document.getElementById("copy-desc-btn");

const imagesInput = document.getElementById("images");
const imagesDrop = document.getElementById("images-drop");
const imagesChips = document.getElementById("images-chips");
const musicInput = document.getElementById("music");
const musicDrop = document.getElementById("music-drop");
const musicChips = document.getElementById("music-chips");

// ---------- Drag & drop + file chip previews ----------
function setupDropzone(dropEl, inputEl, onChange) {
  ["dragenter", "dragover"].forEach((evt) =>
    dropEl.addEventListener(evt, (e) => {
      e.preventDefault();
      dropEl.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropEl.addEventListener(evt, (e) => {
      e.preventDefault();
      dropEl.classList.remove("dragover");
    })
  );
  dropEl.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length) {
      inputEl.files = files;
      onChange();
    }
  });
  inputEl.addEventListener("change", onChange);
}

function renderImageChips() {
  imagesChips.innerHTML = "";
  const files = Array.from(imagesInput.files || []);
  files.forEach((file) => {
    const chip = document.createElement("span");
    chip.className = "file-chip";
    const img = document.createElement("img");
    img.className = "thumb";
    img.src = URL.createObjectURL(file);
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = file.name;
    chip.appendChild(img);
    chip.appendChild(name);
    imagesChips.appendChild(chip);
  });
  const label = imagesDrop.querySelector(".dropzone-text");
  label.innerHTML = files.length
    ? `<b>${files.length} ảnh đã chọn</b> — bấm để chọn lại`
    : "<b>Bấm để chọn ảnh</b> hoặc kéo-thả vào đây";
}

function renderMusicChips() {
  musicChips.innerHTML = "";
  const files = Array.from(musicInput.files || []);
  files.forEach((file) => {
    const chip = document.createElement("span");
    chip.className = "file-chip audio";
    chip.textContent = "🎵 " + file.name;
    musicChips.appendChild(chip);
  });
  const label = musicDrop.querySelector(".dropzone-text");
  label.innerHTML = files.length
    ? `<b>${files[0].name}</b> — bấm để đổi`
    : "<b>Bấm để chọn nhạc</b> (.mp3)";
}

setupDropzone(imagesDrop, imagesInput, renderImageChips);
setupDropzone(musicDrop, musicInput, renderMusicChips);

// ---------- Copy description ----------
copyDescBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(descriptionBox.value);
    copyDescBtn.textContent = "Đã copy ✓";
  } catch (e) {
    descriptionBox.select();
    document.execCommand("copy");
    copyDescBtn.textContent = "Đã copy ✓";
  }
  setTimeout(() => (copyDescBtn.textContent = "Copy mô tả"), 1500);
});

// ---------- Job polling ----------
let seenLogCount = 0;

function addLogLine(text, isErr) {
  const li = document.createElement("li");
  li.textContent = text;
  if (isErr) li.className = "err";
  logList.appendChild(li);
  logList.scrollTop = logList.scrollHeight;
}

async function poll(jobId) {
  try {
    const res = await fetch(`/status/${jobId}`);
    const data = await res.json();
    if (data.log) {
      for (let i = seenLogCount; i < data.log.length; i++) {
        addLogLine(data.log[i], data.log[i].startsWith("❌") || data.log[i].startsWith("⚠️"));
      }
      seenLogCount = data.log.length;
    }
    if (data.state === "done") {
      submitBtn.disabled = false;
      submitBtn.textContent = "✨ Tạo video";
      progressBox.classList.add("done");
      resultBox.hidden = false;
      preview.src = `/preview/${jobId}`;
      dlVideo.href = `/download/${jobId}/video`;
      dlThumb.href = `/download/${jobId}/thumbnail`;
      descriptionBox.value = data.description || "";
      resultBox.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (data.state === "error") {
      submitBtn.disabled = false;
      submitBtn.textContent = "✨ Tạo video";
      return;
    }
    setTimeout(() => poll(jobId), 1500);
  } catch (e) {
    addLogLine("Mất kết nối tới server, đang thử lại...", true);
    setTimeout(() => poll(jobId), 3000);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Đang xử lý...";
  progressBox.hidden = false;
  progressBox.classList.remove("done");
  resultBox.hidden = true;
  logList.innerHTML = "";
  seenLogCount = 0;
  progressBox.scrollIntoView({ behavior: "smooth", block: "start" });

  const formData = new FormData(form);
  try {
    const res = await fetch("/render", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      addLogLine("❌ " + (data.error || "Lỗi không xác định"), true);
      submitBtn.disabled = false;
      submitBtn.textContent = "✨ Tạo video";
      return;
    }
    addLogLine(`Đã nhận ${data.scenes} cảnh, ${data.images} ảnh. Đang xử lý...`);
    poll(data.job_id);
  } catch (err) {
    addLogLine("❌ Không gửi được yêu cầu tới server.", true);
    submitBtn.disabled = false;
    submitBtn.textContent = "✨ Tạo video";
  }
});
