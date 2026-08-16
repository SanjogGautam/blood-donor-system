const form = document.getElementById("donorForm");
const donorIdField = document.getElementById("donorId");
const fullNameField = document.getElementById("fullName");
const bloodGroupField = document.getElementById("bloodGroup");
const phoneField = document.getElementById("phone");
const emailField = document.getElementById("email");
const notesField = document.getElementById("notes");
const submitBtn = document.getElementById("submitBtn");
const cancelEditBtn = document.getElementById("cancelEditBtn");
const donorListEl = document.getElementById("donorList");
const statusEl = document.getElementById("status");
const filterBloodGroup = document.getElementById("filterBloodGroup");

function setStatus(msg, isError = true) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? "#b71c1c" : "#2e7d32";
  if (msg) setTimeout(() => (statusEl.textContent = ""), 4000);
}

async function fetchDonors() {
  const group = filterBloodGroup.value;
  const url = group
    ? `${API_URL}/donor?bloodGroup=${encodeURIComponent(group)}`
    : `${API_URL}/donor`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const donors = await res.json();
    renderDonors(donors);
  } catch (err) {
    setStatus(`Failed to load donors: ${err.message}`);
    console.error(err);
  }
}

function renderDonors(donors) {
  donorListEl.innerHTML = "";
  if (!donors.length) {
    donorListEl.innerHTML = "<p>No donors found.</p>";
    return;
  }
  donors.forEach((d) => {
    const card = document.createElement("div");
    card.className = "donor-card";
    card.innerHTML = `
      <div>
        <span class="group">${d.bloodGroup}</span> — <strong>${d.fullName}</strong><br/>
        <small>${d.phone}${d.email ? " · " + d.email : ""}</small>
      </div>
      <div>
        <button type="button" data-edit="${d.donorId}">Edit</button>
        <button type="button" class="secondary" data-delete="${d.donorId}">Delete</button>
      </div>
    `;
    donorListEl.appendChild(card);
  });

  donorListEl.querySelectorAll("[data-edit]").forEach((btn) => {
    btn.addEventListener("click", () => loadForEdit(btn.dataset.edit, donors));
  });
  donorListEl.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", () => deleteDonor(btn.dataset.delete));
  });
}

function loadForEdit(donorId, donors) {
  const donor = donors.find((d) => d.donorId === donorId);
  if (!donor) return;
  donorIdField.value = donor.donorId;
  fullNameField.value = donor.fullName;
  bloodGroupField.value = donor.bloodGroup;
  phoneField.value = donor.phone;
  emailField.value = donor.email || "";
  notesField.value = donor.notes || "";
  submitBtn.textContent = "Update Donor";
  cancelEditBtn.style.display = "inline-block";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetForm() {
  form.reset();
  donorIdField.value = "";
  submitBtn.textContent = "Add Donor";
  cancelEditBtn.style.display = "none";
}

cancelEditBtn.addEventListener("click", resetForm);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const donorId = donorIdField.value;
  const payload = {
    fullName: fullNameField.value,
    bloodGroup: bloodGroupField.value,
    phone: phoneField.value,
    email: emailField.value,
    notes: notesField.value,
  };

  try {
    const res = await fetch(
      donorId ? `${API_URL}/donor/${donorId}` : `${API_URL}/donor`,
      {
        method: donorId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server responded ${res.status}`);
    }
    setStatus(donorId ? "Donor updated." : "Donor added.", false);
    resetForm();
    fetchDonors();
  } catch (err) {
    setStatus(`Failed to save donor: ${err.message}`);
    console.error(err);
  }
});

async function deleteDonor(donorId) {
  if (!confirm("Delete this donor?")) return;
  try {
    const res = await fetch(`${API_URL}/donor/${donorId}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    setStatus("Donor deleted.", false);
    fetchDonors();
  } catch (err) {
    setStatus(`Failed to delete donor: ${err.message}`);
    console.error(err);
  }
}

filterBloodGroup.addEventListener("change", fetchDonors);

fetchDonors();