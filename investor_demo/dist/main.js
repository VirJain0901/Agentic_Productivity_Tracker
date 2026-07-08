const CDN = {
    gsap: "https://cdn.jsdelivr.net/npm/gsap@3.12.5/+esm",
    lenis: "https://cdn.jsdelivr.net/npm/lenis@1.1.20/+esm",
};
const adapters = {};
let mode = "education";
let view = "overview";
let selectedIndex = 0;
let activeCommand = "Focus message";
let reviewRecorded = false;
let liveHealth = null;
let healthChecked = false;
const titles = {
    overview: ["Command Center", "Unified supervision for classrooms, teams, labs, and training floors."],
    people: ["People Directory", "Groups, roles, devices, status, location, and review state."],
    detail: ["Individual Detail", "Live screen, current activity, timeline, and audited interventions."],
    policy: ["Policy Center", "Rules, privacy controls, command permissions, and system flow."],
    insights: ["Insights", "Productivity, engagement, reports, and analytics readiness."],
    ops: ["Operations", "Health checks, legal gates, device last-seen, queue depth, and audit state."],
};
const datasets = {
    education: {
        label: "Education mode",
        group: "Grade 8 Algebra",
        peopleLabel: "Students",
        hero: "Teachers and admins can see learning activity, guide focus, confirm device health, and keep a clean audit record for sensitive actions.",
        people: [
            { id: "STU-014", name: "Aisha Rao", role: "Student", status: "Online", app: "Desmos", site: "classroom.google.com", focus: 94, queue: 0, screen: "focus", location: "Mumbai" },
            { id: "STU-018", name: "Kabir Sen", role: "Student", status: "Online", app: "Docs", site: "docs.google.com", focus: 88, queue: 0, screen: "docs", location: "Mumbai" },
            { id: "STU-021", name: "Maya Iyer", role: "Student", status: "Idle", app: "Chrome", site: "classroom.google.com", focus: 61, queue: 1, screen: "idle", location: "Remote" },
            { id: "STU-027", name: "Rohan Mehta", role: "Student", status: "Alert", app: "Chrome", site: "video.example", focus: 32, queue: 2, screen: "alert", location: "Mumbai" },
            { id: "STU-033", name: "Sara Khan", role: "Student", status: "Online", app: "GeoGebra", site: "geogebra.org", focus: 91, queue: 0, screen: "focus", location: "Mumbai" },
            { id: "STU-058", name: "Dev Shah", role: "Student", status: "Review", app: "YouTube", site: "youtube.com", focus: 49, queue: 1, screen: "alert", location: "Remote" },
        ],
    },
    workforce: {
        label: "Workforce mode",
        group: "Engineering Team",
        peopleLabel: "Employees",
        hero: "Managers and compliance teams can understand device status, policy activity, offline sync health, and productivity signals across distributed teams.",
        people: [
            { id: "EMP-014", name: "Priya Menon", role: "Engineer", status: "Online", app: "VS Code", site: "github.com", focus: 92, queue: 0, screen: "focus", location: "Bengaluru" },
            { id: "EMP-018", name: "Arjun Kale", role: "Analyst", status: "Online", app: "Excel", site: "sharepoint.com", focus: 86, queue: 0, screen: "docs", location: "Pune" },
            { id: "EMP-021", name: "Nisha Roy", role: "Support", status: "Idle", app: "Chrome", site: "crm.local", focus: 58, queue: 1, screen: "idle", location: "Remote" },
            { id: "EMP-027", name: "Karan Shah", role: "Engineer", status: "Alert", app: "Chrome", site: "streaming.example", focus: 35, queue: 3, screen: "alert", location: "Mumbai" },
            { id: "EMP-033", name: "Meera Jain", role: "HR", status: "Online", app: "Teams", site: "teams.microsoft.com", focus: 89, queue: 0, screen: "docs", location: "Delhi" },
            { id: "EMP-058", name: "Farhan Ali", role: "Ops", status: "Review", app: "Chrome", site: "unknown-site.example", focus: 52, queue: 2, screen: "alert", location: "Remote" },
        ],
    },
};
function el(id) {
    const target = document.getElementById(id);
    if (!target) {
        throw new Error(`Missing element: ${id}`);
    }
    return target;
}
function all(selector) {
    return Array.from(document.querySelectorAll(selector));
}
function currentDataset() {
    return datasets[mode];
}
function currentPeople() {
    return currentDataset().people;
}
function selectedPerson() {
    return currentPeople()[selectedIndex];
}
function isHealthPayload(value) {
    if (!value || typeof value !== "object")
        return false;
    const payload = value;
    return payload.schema_version === "1.0"
        && (payload.source === "live" || payload.source === "sample")
        && (payload.overall_status === "ok" || payload.overall_status === "degraded" || payload.overall_status === "down")
        && typeof payload.checked_at === "string"
        && Array.isArray(payload.down_services)
        && Array.isArray(payload.degraded_services)
        && Array.isArray(payload.unhealthy_device_ids)
        && typeof payload.service_status_counts === "object"
        && typeof payload.device_status_counts === "object";
}
function healthTone(status) {
    if (status === "ok")
        return "green";
    if (status === "down")
        return "red";
    return "amber";
}
async function refreshLiveHealth() {
    healthChecked = true;
    try {
        const response = await fetch("/api/v1/health/", {
            headers: { Accept: "application/json" },
            cache: "no-store",
        });
        if (!response.ok) {
            liveHealth = null;
            return;
        }
        const payload = await response.json();
        liveHealth = isHealthPayload(payload) ? payload : null;
    }
    catch {
        liveHealth = null;
    }
}
function statusTone(status) {
    if (status === "Online")
        return "green";
    if (status === "Alert")
        return "red";
    if (status === "Idle" || status === "Review")
        return "amber";
    return "";
}
function showToast(message) {
    const toast = el("toast");
    toast.textContent = message;
    toast.classList.add("show");
    adapters.gsap?.fromTo(toast, { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.2, ease: "power2.out" });
    window.setTimeout(() => {
        adapters.gsap?.to(toast, { autoAlpha: 0, y: 10, duration: 0.18 });
        toast.classList.remove("show");
    }, 2800);
}
function animateIn(selector) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches)
        return;
    const targets = all(selector);
    if (!targets.length || !adapters.gsap)
        return;
    adapters.gsap.fromTo(targets, { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.28, stagger: 0.035, ease: "power2.out" });
}
async function importOptional(url) {
    try {
        return await import(url);
    }
    catch {
        return undefined;
    }
}
async function loadAdapters() {
    const [gsapModule, lenisModule] = await Promise.all([
        importOptional(CDN.gsap),
        importOptional(CDN.lenis),
    ]);
    adapters.gsap = (gsapModule?.gsap ?? gsapModule?.default);
    adapters.Lenis = (lenisModule?.default ?? lenisModule?.Lenis);
    if (adapters.Lenis && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        adapters.lenis = new adapters.Lenis({ duration: 0.95, smoothWheel: true });
        const raf = (time) => {
            adapters.lenis?.raf(time);
            requestAnimationFrame(raf);
        };
        requestAnimationFrame(raf);
    }
    animateIn(".metric, .person-card, .panel, .hero-panel");
}
function renderContext() {
    const data = currentDataset();
    const people = currentPeople();
    const pending = people.reduce((sum, person) => sum + person.queue, 0);
    el("context-grid").innerHTML = [
        ["Workspace", data.group],
        ["Audience", data.label],
        ["Backend", liveHealth ? `Live ${liveHealth.overall_status}` : healthChecked ? "Sample fallback" : "Checking"],
        ["Pending queue", `${pending} demo events`],
        ["Governance", reviewRecorded ? "Review recorded" : "Legal gates visible"],
    ].map(([label, value]) => `<div class="context-item"><span>${label}</span><strong>${value}</strong></div>`).join("");
}
function renderMetrics() {
    const people = currentPeople();
    const online = people.filter((person) => person.status === "Online").length;
    const focus = Math.round(people.reduce((sum, person) => sum + person.focus, 0) / people.length);
    const review = people.filter((person) => person.status !== "Online").length;
    const pending = people.reduce((sum, person) => sum + person.queue, 0);
    el("metric-grid").innerHTML = [
        ["Online", `${online + 22}`, "Devices currently reporting heartbeat"],
        ["Backend", liveHealth ? liveHealth.overall_status : "Sample", liveHealth ? "Live /api/v1/health payload" : "No live v1 health endpoint"],
        ["Focus", `${focus}%`, "Average sample engagement"],
        ["Review", `${review}`, "People needing attention"],
        ["Queue", `${pending}`, "Events waiting to sync"],
    ].map(([label, value, note]) => `<div class="metric"><label>${label}</label><strong>${value}</strong><span>${note}</span></div>`).join("");
}
function renderOverview() {
    const data = currentDataset();
    el("mode-pill").textContent = data.label;
    el("hero-copy").textContent = data.hero;
    el("grid-title").textContent = `${data.peopleLabel} Workspace`;
    el("grid-subtitle").textContent = `${data.group} - screens, activity, status, and review state`;
    el("demo-proof").textContent = reviewRecorded ? "Governance review recorded" : "Live demo mode";
    renderContext();
    renderMetrics();
}
function renderPeopleGrid() {
    el("people-grid").innerHTML = currentPeople().map((person, index) => `
    <article class="person-card ${index === selectedIndex ? "selected" : ""}" data-person-index="${index}">
      <div class="screen-preview ${person.screen}"></div>
      <div class="person-body">
        <div class="row"><strong>${person.name}</strong><span class="status-pill ${statusTone(person.status)}">${person.status}</span></div>
        <div class="muted">${person.app} · ${person.site}</div>
        <div class="progress"><span style="width:${person.focus}%"></span></div>
        <div class="row"><span class="status-pill blue">${person.id}</span><span class="status-pill ${person.queue ? "amber" : "green"}">Queue ${person.queue}</span></div>
      </div>
    </article>
  `).join("");
    all("[data-person-index]").forEach((card) => {
        card.addEventListener("click", () => {
            selectedIndex = Number(card.dataset.personIndex);
            renderAll();
            setView("detail");
        });
    });
}
function renderPeopleTable() {
    const query = el("people-search").value.trim().toLowerCase();
    const rows = currentPeople().filter((person) => {
        return !query || `${person.name} ${person.id} ${person.role}`.toLowerCase().includes(query);
    });
    el("people-title").textContent = `${currentDataset().peopleLabel} Directory`;
    el("people-table").innerHTML = `
    <thead><tr><th>ID</th><th>Name</th><th>Role</th><th>Status</th><th>Current app</th><th>Location</th><th>Open</th></tr></thead>
    <tbody>
      ${rows.map((person) => {
        const index = currentPeople().findIndex((item) => item.id === person.id);
        return `<tr>
          <td>${person.id}</td><td>${person.name}</td><td>${person.role}</td>
          <td><span class="status-pill ${statusTone(person.status)}">${person.status}</span></td>
          <td>${person.app}</td><td>${person.location}</td>
          <td><button class="button" type="button" data-open-person="${index}">Open</button></td>
        </tr>`;
    }).join("")}
    </tbody>`;
    all("[data-open-person]").forEach((button) => {
        button.addEventListener("click", () => {
            selectedIndex = Number(button.dataset.openPerson);
            renderAll();
            setView("detail");
        });
    });
}
function renderDetail() {
    const person = selectedPerson();
    el("detail-name").textContent = person.name;
    el("detail-meta").textContent = `${person.role} - ${currentDataset().group} - ${person.id}`;
    const detailStatus = el("detail-status");
    detailStatus.textContent = person.status;
    detailStatus.className = `status-pill ${statusTone(person.status)}`;
    el("detail-screen").className = `screen-preview large ${person.screen}`;
    el("detail-facts").innerHTML = [
        ["Current app", person.app],
        ["Site", person.site],
        ["Focus", `${person.focus}%`],
        ["Queue", `${person.queue}`],
    ].map(([label, value]) => `<div class="fact"><span>${label}</span><strong>${value}</strong></div>`).join("");
    el("detail-feed").innerHTML = [
        ["Command ledger", "Demo commands are recorded with simulated acknowledgements."],
        ["Audit state", "Consent, retention, and command review states are visible before sensitive features can ship."],
        ["Sync health", `${person.queue} queued event(s) visible to operations.`],
    ].map(([title, body]) => `<div class="event"><strong>${title}</strong><span>${body}</span></div>`).join("");
}
function renderPolicy() {
    el("policy-grid").innerHTML = [
        ["Monitoring consent", "Policy acknowledgement", true],
        ["Screenshots", "Retention and access audit gated", false],
        ["Remote commands", "Legal review required", false],
    ].map(([title, body, enabled]) => `
    <article class="policy-card">
      <h3>${title}</h3>
      <p class="muted">${body}</p>
      <div class="policy-row"><span>Status</span><span class="switch ${enabled ? "on" : ""}"></span></div>
    </article>
  `).join("");
    el("flow-strip").innerHTML = [
        ["Python Agent", "Captures activity and idle events"],
        ["Local Queue", "Stores UUID events offline"],
        ["Sync API", "Returns accepted/duplicate/rejected"],
        ["Backend", "Canonical tenant-scoped records"],
        ["Realtime", "WebSocket room updates"],
        ["TypeScript UI", "Investor demo and future dashboard"],
    ].map(([title, body]) => `<div class="flow-card"><strong>${title}</strong><span>${body}</span></div>`).join("");
}
function renderInsights() {
    el("insight-metrics").innerHTML = [
        ["Productivity", "87%", "Sample trend, backend-owned"],
        ["Policy hits", "12", "2 marked high priority"],
        ["Reports", "4", "Export-ready demo views"],
        ["Risk scoring", "Gated", "Requires legal review"],
    ].map(([label, value, note]) => `<div class="metric"><label>${label}</label><strong>${value}</strong><span>${note}</span></div>`).join("");
    el("bar-chart").innerHTML = [["Mon", 64], ["Tue", 82], ["Wed", 73], ["Thu", 91], ["Fri", 78], ["Sat", 86]]
        .map(([label, height]) => `<div class="bar" style="height:${height}%"><span>${label}</span></div>`).join("");
    el("signals-table").innerHTML = `
    <thead><tr><th>Person</th><th>Signal</th><th>Action</th></tr></thead>
    <tbody>
      <tr><td>${currentPeople()[3].name}</td><td><span class="status-pill red">Restricted activity</span></td><td>Review</td></tr>
      <tr><td>${currentPeople()[2].name}</td><td><span class="status-pill amber">Idle threshold</span></td><td>Check in</td></tr>
      <tr><td>${currentPeople()[5].name}</td><td><span class="status-pill amber">Queue depth</span></td><td>Watch sync</td></tr>
      <tr><td>${currentDataset().group}</td><td><span class="status-pill green">High engagement</span></td><td>Export</td></tr>
    </tbody>`;
}
function renderOps() {
    el("governance-state").textContent = liveHealth
        ? `Live backend ${liveHealth.overall_status}`
        : reviewRecorded
            ? "Review recorded"
            : "Demo controls visible";
    el("governance-detail").textContent = liveHealth
        ? `Health checked at ${new Date(liveHealth.checked_at).toLocaleString()}. Source: ${liveHealth.source}.`
        : reviewRecorded
            ? "A local demo audit event has been recorded for the investor walkthrough."
            : "Sensitive production features remain gated until consent, audit, retention, and legal review are confirmed.";
    el("ops-table").innerHTML = `
    <thead><tr><th>Device</th><th>Health</th><th>Queue</th><th>Last seen</th></tr></thead>
    <tbody>
      ${liveHealth ? `
        <tr><td>Backend</td><td><span class="status-pill ${healthTone(liveHealth.overall_status)}">${liveHealth.overall_status}</span></td><td>${liveHealth.unhealthy_device_ids.length} unhealthy</td><td>Live</td></tr>
      ` : ""}
      ${currentPeople().slice(0, 5).map((person) => `
        <tr><td>${person.id}</td><td><span class="status-pill ${person.status === "Online" ? "green" : "amber"}">${person.status === "Online" ? "Healthy" : "Needs review"}</span></td><td>${person.queue}</td><td>${person.status === "Online" ? "15 sec ago" : "9 min ago"}</td></tr>
      `).join("")}
    </tbody>`;
    el("audit-table").innerHTML = `
    <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead>
    <tbody>
      <tr><td>Now</td><td>Admin</td><td>${reviewRecorded ? "Recorded governance review" : "Viewed dashboard"}</td><td>${currentDataset().group}</td></tr>
      <tr><td>09:31</td><td>System</td><td>Policy sync</td><td>${currentDataset().group}</td></tr>
      <tr><td>09:28</td><td>Supervisor</td><td>Snapshot review</td><td>${selectedPerson().name}</td></tr>
      <tr><td>09:15</td><td>System</td><td>Queue retry</td><td>${currentPeople()[5].id}</td></tr>
    </tbody>`;
}
function renderAll() {
    renderOverview();
    renderPeopleGrid();
    renderPeopleTable();
    renderDetail();
    renderPolicy();
    renderInsights();
    renderOps();
}
function setView(nextView) {
    view = nextView;
    all("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === nextView));
    all(".view").forEach((section) => section.classList.remove("active"));
    el(`view-${nextView}`).classList.add("active");
    el("page-title").textContent = titles[nextView][0];
    el("page-subtitle").textContent = titles[nextView][1];
    adapters.lenis?.scrollTo(document.body, { immediate: false });
    animateIn(`#view-${nextView} .metric, #view-${nextView} .panel, #view-${nextView} .person-card, #view-${nextView} .hero-panel`);
}
function openCommand(command) {
    activeCommand = command;
    const person = selectedPerson();
    el("modal-title").textContent = command;
    el("modal-subtitle").textContent = `${person.name} · ${person.id}`;
    el("command-scope").value = command === "Broadcast" ? "Current group" : "Selected person";
    el("command-payload").value = command === "Push URL"
        ? "https://classroom.google.com"
        : command === "Capture snapshot"
            ? "Audit-gated snapshot request"
            : "Please return to the assigned task.";
    const modal = el("command-modal");
    modal.classList.add("open");
    adapters.gsap?.fromTo(".modal", { autoAlpha: 0, y: 18, scale: 0.98 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.22, ease: "power2.out" });
}
function closeCommand() {
    el("command-modal").classList.remove("open");
}
function confirmCommand() {
    const person = selectedPerson();
    if (activeCommand === "Capture snapshot") {
        showToast("Snapshot remains legal-gated. Demo audit entry recorded only.");
    }
    else {
        showToast(`${activeCommand} acknowledged by ${person.name}. Demo audit entry recorded.`);
    }
    if (activeCommand === "Focus message") {
        person.screen = "locked";
        person.status = "Online";
        person.focus = Math.max(person.focus, 82);
    }
    closeCommand();
    renderAll();
}
function recordGovernanceReview() {
    reviewRecorded = true;
    renderAll();
    showToast("Governance review recorded in the demo audit trail.");
}
function bindEvents() {
    all("[data-view]").forEach((button) => {
        button.addEventListener("click", () => setView(button.dataset.view));
    });
    all("[data-mode]").forEach((button) => {
        button.addEventListener("click", () => {
            mode = button.dataset.mode;
            selectedIndex = 0;
            all("[data-mode]").forEach((item) => item.classList.toggle("active", item === button));
            renderAll();
            setView(view);
            showToast(`${currentDataset().label} loaded.`);
        });
    });
    all("[data-command]").forEach((button) => {
        button.addEventListener("click", () => openCommand(button.dataset.command ?? "Command"));
    });
    el("refresh-demo").addEventListener("click", () => {
        void refreshLiveHealth().then(() => {
            renderAll();
            animateIn(".metric, .person-card");
            showToast(liveHealth ? "Live backend health refreshed." : "Demo state refreshed with sample fallback.");
        });
    });
    el("theme-toggle").addEventListener("click", () => {
        document.body.dataset.theme = document.body.dataset.theme === "dark" ? "light" : "dark";
    });
    el("people-search").addEventListener("input", renderPeopleTable);
    el("modal-cancel").addEventListener("click", closeCommand);
    el("modal-confirm").addEventListener("click", confirmCommand);
    el("command-modal").addEventListener("click", (event) => {
        if (event.target === event.currentTarget)
            closeCommand();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape")
            closeCommand();
    });
    el("audit-review").addEventListener("click", recordGovernanceReview);
}
async function boot() {
    bindEvents();
    await refreshLiveHealth();
    renderAll();
    await loadAdapters();
}
void boot();
