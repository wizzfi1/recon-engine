
const fileInput = document.getElementById("fileInput");
const pastelSelect = document.getElementById("pastelSelect");
const ixtracSelect = document.getElementById("ixtracSelect");
const runBtn = document.getElementById("runBtn");
const status = document.getElementById("status");
const spinner = document.getElementById("spinner");
const timestampToggle = document.getElementById("timestampToggle");

let uploadedFile = null;
let uploadMeta = null;

function setStatus(text, type = "info") {
  const colors = {
    info: "text-gray-600",
    success: "text-green-600",
    error: "text-red-600",
  };
  status.className = `text-sm mt-2 ${colors[type]}`;
  status.textContent = `Status: ${text}`;
}

/* ============================
   UPLOAD & SHEET DISCOVERY
============================ */
fileInput.addEventListener("change", async () => {
  uploadedFile = fileInput.files[0];
  if (!uploadedFile) return;

  setStatus("Reading sheets…");

  const formData = new FormData();
  formData.append("file", uploadedFile);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error("Failed to read workbook");
    }

    uploadMeta = await res.json();

    // Large file warning (ONLY HERE)
    if (uploadMeta.large_file) {
      const ok = confirm(
        `This workbook contains approximately ${uploadMeta.row_count.toLocaleString()} rows.\n\n` +
        "Processing may take several minutes.\n\nDo you want to continue?"
      );

      if (!ok) {
        uploadedFile = null;
        fileInput.value = "";
        setStatus("Cancelled by user");
        return;
      }
    }

    pastelSelect.innerHTML = "";
    ixtracSelect.innerHTML = "";

    uploadMeta.sheets.forEach(sheet => {
      pastelSelect.add(new Option(sheet, sheet));
      ixtracSelect.add(new Option(sheet, sheet));
    });

    setStatus("Sheets loaded. Ready to run.");

  } catch (err) {
    setStatus(err.message, "error");
  }
});

/* ============================
   RUN RECONCILIATION
============================ */
runBtn.addEventListener("click", async () => {
  if (!uploadedFile) {
    alert("Upload a file first");
    return;
  }

  if (pastelSelect.value === ixtracSelect.value) {
    setStatus("Pastel and IXTRAC sheets must be different.", "error");
    return;
  }

  runBtn.disabled = true;
  fileInput.disabled = true;
  spinner.classList.remove("hidden");

  setStatus("Running reconciliation…");
  await new Promise(r => setTimeout(r, 50)); // allow UI repaint

  const formData = new FormData();
  formData.append("file", uploadedFile);
  formData.append("pastel_sheet", pastelSelect.value);
  formData.append("ixtrac_sheet", ixtracSelect.value);
  formData.append("append_timestamp", timestampToggle.checked);

  try {
    const res = await fetch("/api/reconcile", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Reconciliation failed");
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    setStatus("Completed successfully.", "success");

  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    spinner.classList.add("hidden");
    runBtn.disabled = false;
    fileInput.disabled = false;
  }
});
