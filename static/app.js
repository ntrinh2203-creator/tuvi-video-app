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

let seenLogCount = 0;

function addLogLine(text, isErr) {
  const li = document.createElement("li");
  li.textContent = text;
  if (isErr) li.className = "err";
  logList.appendChild(li);
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
      submitBtn.textContent = "Tạo video";
      resultBox.hidden = false;
      preview.src = `/preview/${jobId}`;
      dlVideo.href = `/download/${jobId}/video`;
      dlThumb.href = `/download/${jobId}/thumbnail`;
      descriptionBox.value = data.description || "";
      return;
    }
    if (data.state === "error") {
      submitBtn.disabled = false;
      submitBtn.textContent = "Tạo video";
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
  resultBox.hidden = true;
  logList.innerHTML = "";
  seenLogCount = 0;

  const formData = new FormData(form);
  try {
    const res = await fetch("/render", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      addLogLine("❌ " + (data.error || "Lỗi không xác định"), true);
      submitBtn.disabled = false;
      submitBtn.textContent = "Tạo video";
      return;
    }
    addLogLine(`Đã nhận ${data.scenes} cảnh, ${data.images} ảnh. Đang xử lý...`);
    poll(data.job_id);
  } catch (err) {
    addLogLine("❌ Không gửi được yêu cầu tới server.", true);
    submitBtn.disabled = false;
    submitBtn.textContent = "Tạo video";
  }
});
