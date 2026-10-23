const $ = (id) => document.getElementById(id);
const admin = location.pathname === "/admin";
const linkPage =
  location.pathname === "/verify" || location.pathname === "/reset";
let user = null,
  csrf = null,
  client = null,
  busy = false,
  mode = "login",
  linkToken = null,
  notice = null;
if (linkPage) {
  linkToken = new URLSearchParams(location.hash.slice(1)).get("token");
  history.replaceState({}, "", location.pathname);
  mode = location.pathname === "/verify" ? "verify" : "reset";
}
function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = error ? "error" : "";
}
// SERVER REQUESTS

async function api(path, data) {
  const response = await fetch(path, {
    method: data === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(20000),
    cache: "no-store",
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || "Request failed");
    error.status = response.status;
    throw error;
  }
  return result;
}
// ACCOUNT FORMS AND PAGE DISPLAY

function authMode(value) {
  mode = value;
  message("");
  render();
}
function render() {
  const access = !!user && (!admin || user.role === "admin") && !linkPage;
  $("account-panel").hidden = access;
  $("queue-panel").hidden = !access;
  $("sign-out").hidden = !user;
  $("join-form").hidden = admin || user?.role === "admin" || !!client;
  $("ticket").hidden = admin || !client;
  $("admin-controls").hidden = !admin;
  $("panel-title").textContent = admin
    ? "Manage the queue"
    : client
      ? "Your place in line"
      : "Join the queue";
  $("name").value = user ? user.name : "";
  if (client) {
    $("client-name").textContent = client.name;
    if (document.activeElement !== $("edit-issue") && document.activeElement !== $("edit-notes")) {
      $("edit-issue").value = client.issue || "";
      $("edit-notes").value = client.notes || "";
    }
  }
  const titles = {
    login: "Sign in",
    register: "Create your account",
    forgot: "Reset your password",
    resend: "Verify your email",
    verify: "Confirm your email",
    reset: "Choose a new password",
  };
  $("auth-title").textContent = titles[mode];
  $("auth-submit").textContent = {
    login: "Sign in",
    register: "Create account",
    forgot: "Send reset link",
    resend: "Send verification link",
    verify: "Verify email",
    reset: "Save new password",
  }[mode];
  $("auth-description").textContent =
    admin && user && user.role !== "admin"
      ? "Your account does not have administrator access. Use the Client page, or ask the administrator to assign access."
      : mode === "register"
        ? "Anyone can register. We’ll email a link to verify your address. Use a password with at least 12 characters."
        : mode === "verify"
          ? "Confirm your email to activate your account."
          : mode === "reset"
            ? "Choose a password with at least 12 characters. All existing sign-ins will be ended."
            : "Sign in to join the queue and keep your place across devices.";
  $("auth-name-row").hidden = mode !== "register";
  $("auth-name").required = mode === "register";
  const emailVisible = !["verify", "reset"].includes(mode);
  $("auth-email").hidden = !emailVisible;
  $("auth-email-label").hidden = !emailVisible;
  $("auth-email").required = emailVisible;
  const passwordVisible = ["login", "register", "reset"].includes(mode);
  $("auth-password-row").hidden = !passwordVisible;
  $("auth-password").required = passwordVisible;
  $("auth-password").autocomplete =
    mode === "login" ? "current-password" : "new-password";
  for (const id of [
    "auth-submit",
    "join-button",
    "leave-button",
    "serve-button",
    "update-ticket-button",
    "sign-out",
  ])
    if ($(id)) $(id).disabled = busy;
}
// LIVE QUEUE AND TURN NOTIFICATIONS

function notifyUser(title, body) {
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      new Notification(title, { body });
    } catch (e) {}
  }
}

if ("Notification" in window && Notification.permission === "default") {
  document.addEventListener("click", () => {
    Notification.requestPermission();
  }, { once: true });
}

function renderQueue(clients) {
  $("queue").replaceChildren();
  $("count").textContent = `${clients.length} waiting`;
  $("empty").hidden = !!clients.length;
  $("empty").textContent = "No one is waiting. You’re welcome to join.";
  for (const item of clients) {
    const row = document.createElement("li"),
      num = document.createElement("span"),
      person = document.createElement("div"),
      name = document.createElement("strong"),
      issue = document.createElement("span"),
      ahead = document.createElement("span");
    num.className = "number";
    num.textContent = item.position;
    person.className = "person";
    name.textContent = item.name;
    issue.textContent = item.issue;
    if (item.notes) {
      const notesP = document.createElement("p");
      notesP.className = "notes-text";
      notesP.textContent = `“${item.notes}”`;
      person.append(name, issue, notesP);
    } else {
      person.append(name, issue);
    }
    ahead.className = "ahead";
    ahead.textContent = `${item.people_ahead} ahead`;

    if (admin && user && user.role === "admin") {
      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "action-btn secondary";
      cancelBtn.textContent = "Cancel";
      cancelBtn.style.marginLeft = "8px";
      cancelBtn.addEventListener("click", () => {
        action(async () => {
          const res = await api("/cancel", { id: item.id });
          message(`${res.name}’s ticket was cancelled.`);
          await refresh();
        });
      });
      row.append(num, person, ahead, cancelBtn);
    } else {
      row.append(num, person, ahead);
    }
    $("queue").append(row);
  }
}

function renderHistory(historyItems) {
  const section = $("admin-history-section");
  if (!section) return;
  section.hidden = !admin || !user || user.role !== "admin";
  if (section.hidden) return;

  const list = $("history-list");
  list.replaceChildren();
  $("history-empty").hidden = !!historyItems.length;

  for (const item of historyItems) {
    const li = document.createElement("li");
    const info = document.createElement("div");
    const nameStr = document.createElement("strong");
    nameStr.textContent = item.name + " ";
    const issueSpan = document.createElement("span");
    issueSpan.textContent = `(${item.issue})`;
    issueSpan.style.color = "#637086";
    info.append(nameStr, issueSpan);

    if (item.notes) {
      const notesP = document.createElement("p");
      notesP.className = "notes-text";
      notesP.textContent = `“${item.notes}”`;
      info.append(notesP);
    }

    const tag = document.createElement("span");
    tag.className = `status-tag status-${item.status}`;
    tag.textContent = item.status;

    li.append(info, tag);
    list.append(li);
  }
}
async function refresh() {
  const me = await api("/auth/me");
  user = me.user;
  csrf = me.csrf;
  $("dev-mail-notice").hidden = !me.development_mail;
  if (!user) {
    client = null;
    $("queue").replaceChildren();
    $("count").textContent = "Sign in";
    $("empty").hidden = false;
    $("empty").textContent = "Sign in to view the queue.";
    $("connection").textContent = "Account access required";
    render();
    return;
  }
  if (admin && user.role !== "admin") {
    render();
    $("connection").textContent = "Administrator access required to manage queue";
    renderQueue((await api("/queue")).queue);
    return;
  }
  if (linkPage) {
    render();
    return;
  }
  renderQueue((await api("/queue")).queue);
  if (admin && user.role === "admin") {
    const historyRes = await api("/history");
    renderHistory(historyRes.history);
  }
  if (!admin) {
    client = (await api("/my-ticket")).client;
    if (client && client.status === "served") {
      $("turn-title").textContent = `${client.name}, it is now your turn!`;
      notifyUser("IT Help Desk - Your Turn!", `${client.name}, it is now your turn! Please proceed to the IT desk.`);
      notice = client.id;
      client = null;
      if (!$("turn-dialog").open) $("turn-dialog").showModal();
    } else if (client) {
      $("position").textContent = client.position;
      $("ahead").textContent = client.people_ahead;
      $("wait-time").textContent =
        client.estimated_wait_minutes === 0
          ? "Next!"
          : client.estimated_wait_minutes
          ? `~${client.estimated_wait_minutes} min`
          : "—";
    }
  }
  render();
  $("connection").textContent = "Live · updates every 2 seconds";
}
// BUTTONS AND FORM ACTIONS

async function action(task) {
  if (busy) return;
  busy = true;
  render();
  message("");
  try {
    await task();
  } catch (error) {
    message(
      error.message || "Cannot reach the server. Please try again.",
      true,
    );
  } finally {
    busy = false;
    render();
  }
}
$("auth-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(async () => {
    const email = $("auth-email").value.trim(),
      password = $("auth-password").value;
    const path = {
      login: "/auth/login",
      register: "/auth/register",
      forgot: "/auth/forgot",
      resend: "/auth/resend",
      verify: "/auth/verify",
      reset: "/auth/reset",
    }[mode];
    const data =
      mode === "verify"
        ? { token: linkToken }
        : mode === "reset"
          ? { token: linkToken, password }
          : mode === "register"
            ? { email, password, name: $("auth-name").value.trim() }
            : { email, password };
    const result = await api(path, data);
    $("auth-password").value = "";
    if (mode === "login") {
      user = result.user;
      csrf = result.csrf;
      if (user.role === "admin" && location.pathname !== "/admin") {
        location.assign("/admin");
        return;
      }
      if (user.role !== "admin" && location.pathname === "/admin") {
        location.assign("/");
        return;
      }
      await refresh();
      message("Signed in.");
    } else if (mode === "verify" || mode === "reset") {
      linkToken = null;
      location.assign("/");
    } else {
      message(result.message);
    }
  });
});
for (const value of ["login", "register", "forgot", "resend"])
  $("show-" + value).addEventListener("click", () => {
    if (linkPage) location.assign("/");
    else authMode(value);
  });
$("sign-out").addEventListener("click", () =>
  action(async () => {
    await api("/auth/logout", {});
    user = null;
    csrf = null;
    client = null;
    await refresh();
    message(
      "Signed out. Your queue place is kept until you leave or are called.",
    );
  }),
);
$("join-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(async () => {
    client = await api("/join", {
      issue: $("issue").value,
      notes: $("notes") ? $("notes").value.trim() : "",
    });
    $("issue").value = "";
    if ($("notes")) $("notes").value = "";
    message("You’re in the queue. Keep this page open.");
    await refresh();
  });
});
const editForm = $("edit-ticket-form");
if (editForm) {
  editForm.addEventListener("submit", (event) => {
    event.preventDefault();
    action(async () => {
      if (!client) return;
      client = await api("/update", {
        id: client.id,
        issue: $("edit-issue").value,
        notes: $("edit-notes").value.trim(),
      });
      message("Ticket updated successfully.");
      await refresh();
    });
  });
}
$("leave-button").addEventListener("click", () =>
  action(async () => {
    if (!client) return;
    await api("/leave", { id: client.id });
    client = null;
    message("You have left the queue.");
    await refresh();
  }),
);
$("serve-button").addEventListener("click", () =>
  action(async () => {
    const served = await api("/serve", {});
    message(`${served.name} has been called · ${served.issue}`);
    await refresh();
  }),
);
async function acknowledge() {
  if (!notice) return;
  const id = notice;
  await api("/acknowledge", { id });
  notice = null;
}
$("dismiss-turn").addEventListener("click", () =>
  action(async () => {
    await acknowledge();
    $("turn-dialog").close();
  }),
);
$("turn-dialog").addEventListener("cancel", (event) => {
  event.preventDefault();
  $("dismiss-turn").click();
});
// AUTOMATIC REFRESH

async function poll() {
  try {
    if (!busy) await refresh();
  } catch (error) {
    $("connection").textContent = "Connection interrupted · retrying…";
  } finally {
    setTimeout(poll, 2000);
  }
}
render();
poll();
