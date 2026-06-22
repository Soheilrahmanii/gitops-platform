const API_BASE = "http://localhost:8000";

const form = document.getElementById("provision-form");
const submitBtn = document.getElementById("submit-btn");
const resultSection = document.getElementById("result");
const resultList = document.getElementById("result-list");
const errorSection = document.getElementById("error");
const errorMessage = document.getElementById("error-message");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setLoading(true);
  hide(resultSection);
  hide(errorSection);

  const payload = {
    team_name: form.team_name.value.trim(),
    app_name: form.app_name.value.trim(),
    description: form.description.value.trim(),
  };

  try {
    const resp = await fetch(`${API_BASE}/provision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    renderResult(data);
  } catch (err) {
    renderError(err.message);
  } finally {
    setLoading(false);
  }
});

function renderResult(data) {
  resultList.innerHTML = "";

  const items = [
    { label: "GitHub repository", value: data.github_repo, link: true },
    { label: "Kubernetes namespace", value: data.namespace },
    { label: "ArgoCD application", value: data.argocd_app },
    { label: "Grafana dashboard", value: data.grafana_dashboard, link: true },
  ];

  for (const item of items) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${item.label}:</span> ${
      item.link
        ? `<a href="${item.value}" target="_blank" rel="noopener">${item.value}</a>`
        : `<code>${item.value}</code>`
    }`;
    resultList.appendChild(li);
  }

  show(resultSection);
}

function renderError(msg) {
  errorMessage.textContent = msg;
  show(errorSection);
}

function setLoading(loading) {
  submitBtn.disabled = loading;
  submitBtn.textContent = loading ? "Provisioning…" : "Provision";
}

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true; }
