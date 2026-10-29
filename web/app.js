const $ = (id) => document.getElementById(id);
const currentPath = location.pathname;
const admin = currentPath === "/admin";
const clientPage = currentPath === "/client";
const homePage = currentPath === "/";
const linkPage = currentPath === "/verify" || currentPath === "/reset";

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
} else if ((clientPage || admin) && location.hash) {
  const hashVal = location.hash.slice(1);
  if (["login", "register", "forgot", "resend"].includes(hashVal)) {
    mode = hashVal;
  }
}

function message(text, error = false) {
  if ($("message")) {
    $("message").textContent = text;
    $("message").className = error ? "error" : "";
  }
}

function authMode(value) {
  mode = value;
  message("");
  render();
}

function render() {
  const isHome = homePage && !linkPage;
  if ($("landing-intro")) $("landing-intro").hidden = !isHome;
  if ($("landing-panel")) $("landing-panel").hidden = !isHome;
  if ($("portal-intro")) $("portal-intro").hidden = isHome;
  if ($("app-layout")) $("app-layout").hidden = isHome;

  if (isHome) {
    if (user) {
      if ($("landing-client-go")) {
        $("landing-client-go").textContent =
          user.role === "admin" ? "Go to Client Portal →" : "Go to Client Queue →";
      }
    } else {
      if ($("landing-client-go")) {
        $("landing-client-go").textContent = "Go to Client Portal →";
      }
    }
  } else {
    if (admin) {
      if ($("portal-eyebrow")) $("portal-eyebrow").textContent = "ADMINISTRATOR DASHBOARD";
      if ($("portal-heading")) $("portal-heading").textContent = "Manage Support Queue";
      if ($("portal-desc")) $("portal-desc").textContent = "Call clients and manage waiting IT support requests.";
    } else {
      if ($("portal-eyebrow")) $("portal-eyebrow").textContent = "IT SUPPORT";
      if ($("portal-heading")) $("portal-heading").textContent = "A little less waiting.\nA lot more clarity.";
      if ($("portal-desc")) $("portal-desc").textContent = "Join the queue, see your place, and we’ll let you know when it’s your turn.";
    }
  }

  const access = !isHome && !!user && (!admin || user.role === "admin") && !linkPage;
  if ($("account-panel")) $("account-panel").hidden = access;
  if ($("queue-panel")) $("queue-panel").hidden = !access;
  if ($("sign-out")) $("sign-out").hidden = !user;
  if ($("join-form")) $("join-form").hidden = admin || user?.role === "admin" || !!client;
  if ($("ticket")) $("ticket").hidden = admin || !client;
  if ($("admin-controls")) $("admin-controls").hidden = !admin;

  if ($("panel-title")) {
    $("panel-title").textContent = admin
      ? "Manage the queue"
      : client
        ? "Your place in line"
        : "Join the queue";
  }
  if ($("name")) $("name").value = user ? user.name : "";
  if (client && $("client-name")) $("client-name").textContent = client.name;

  const titles = {
    login: admin ? "Admin sign in" : "Sign in",
    register: "Create your account",
    forgot: "Reset your password",
    resend: "Verify your email",
    verify: "Confirm your email",
    reset: "Choose a new password",
  };
  if ($("auth-title")) $("auth-title").textContent = titles[mode];
  if ($("auth-eyebrow")) {
    $("auth-eyebrow").textContent =
      admin && mode === "login" ? "ADMIN ACCOUNT" : "YOUR ACCOUNT";
  }
  if ($("auth-submit")) {
    $("auth-submit").textContent = {
      login: admin ? "Sign in as admin" : "Sign in",
      register: "Create account",
      forgot: "Send reset link",
      resend: "Send verification link",
      verify: "Verify email",
      reset: "Save new password",
    }[mode];
  }
  if ($("switch-role")) {
    $("switch-role").hidden = linkPage || mode !== "login";
    $("switch-role").textContent = admin
      ? "Sign in as customer"
      : "Sign in as admin";
  }
  if ($("auth-description")) {
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
  }
  if ($("auth-name-row")) $("auth-name-row").hidden = mode !== "register";
  if ($("auth-name")) $("auth-name").required = mode === "register";

  const emailVisible = !["verify", "reset"].includes(mode);
  if ($("auth-email")) {
    $("auth-email").hidden = !emailVisible;
    $("auth-email").required = emailVisible;
  }
  if ($("auth-email-label")) $("auth-email-label").hidden = !emailVisible;

  const passwordVisible = ["login", "register", "reset"].includes(mode);
  if ($("auth-password-row")) $("auth-password-row").hidden = !passwordVisible;
  if ($("auth-password")) {
    $("auth-password").required = passwordVisible;
    $("auth-password").autocomplete =
      mode === "login" ? "current-password" : "new-password";
  }

  for (const id of [
    "auth-submit",
    "join-button",
    "leave-button",
    "serve-button",
    "sign-out",
  ]) {
    if ($(id)) $(id).disabled = busy;
  }
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

// LIVE QUEUE AND TURN NOTIFICATIONS

function renderQueue(clients) {
  if (!$("queue")) return;
  $("queue").replaceChildren();
  if ($("count")) $("count").textContent = `${clients.length} waiting`;
  if ($("empty")) {
    $("empty").hidden = !!clients.length;
    $("empty").textContent = "No one is waiting. You’re welcome to join.";
  }
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
    ahead.className = "ahead";
    ahead.textContent = `${item.people_ahead} ahead`;
    person.append(name, issue);
    row.append(num, person, ahead);
    $("queue").append(row);
  }
}

async function refresh() {
  const me = await api("/auth/me");
  user = me.user;
  csrf = me.csrf;
  if ($("dev-mail-notice")) $("dev-mail-notice").hidden = !me.development_mail;

  if (homePage && !linkPage) {
    render();
    return;
  }

  if (!user) {
    client = null;
    if ($("queue")) $("queue").replaceChildren();
    if ($("count")) $("count").textContent = "Sign in";
    if ($("empty")) {
      $("empty").hidden = false;
      $("empty").textContent = "Sign in to view the queue.";
    }
    if ($("connection")) $("connection").textContent = "Account access required";
    render();
    return;
  }

  if (user.role === "admin" && !admin && !linkPage && !homePage) {
    location.replace("/admin");
    return;
  }
  if (admin && user.role !== "admin") {
    render();
    if ($("connection")) $("connection").textContent = "Administrator access required";
    return;
  }
  if (linkPage) {
    render();
    return;
  }

  renderQueue((await api("/queue")).queue);
  if (!admin) {
    client = (await api("/my-ticket")).client;
    if (client && client.status === "served") {
      if ($("turn-title")) $("turn-title").textContent = `${client.name}, it is now your turn!`;
      notice = client.id;
      client = null;
      if ($("turn-dialog") && !$("turn-dialog").open) $("turn-dialog").showModal();
    } else if (client) {
      if ($("position")) $("position").textContent = client.position;
      if ($("ahead")) $("ahead").textContent = client.people_ahead;
    }
  }
  render();
  if ($("connection")) $("connection").textContent = "Live · updates every 2 seconds";
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

if ($("auth-form")) {
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
      if ($("auth-password")) $("auth-password").value = "";
      if (mode === "login") {
        user = result.user;
        csrf = result.csrf;
        await refresh();
        message("Signed in.");
      } else if (mode === "verify" || mode === "reset") {
        linkToken = null;
        location.assign("/client");
      } else {
        message(result.message);
      }
    });
  });
}

for (const value of ["login", "register", "forgot", "resend"]) {
  if ($("show-" + value)) {
    $("show-" + value).addEventListener("click", () => {
      if (linkPage) location.assign("/client");
      else authMode(value);
    });
  }
}

if ($("switch-role")) {
  $("switch-role").addEventListener("click", () => {
    location.assign(admin ? "/client" : "/admin");
  });
}

if ($("sign-out")) {
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
}

if ($("join-form")) {
  $("join-form").addEventListener("submit", (event) => {
    event.preventDefault();
    action(async () => {
      client = await api("/join", { issue: $("issue").value });
      if ($("issue")) $("issue").value = "";
      message("You’re in the queue. Keep this page open.");
      await refresh();
    });
  });
}

if ($("leave-button")) {
  $("leave-button").addEventListener("click", () =>
    action(async () => {
      if (!client) return;
      await api("/leave", { id: client.id });
      client = null;
      message("You have left the queue.");
      await refresh();
    }),
  );
}

if ($("serve-button")) {
  $("serve-button").addEventListener("click", () =>
    action(async () => {
      const served = await api("/serve", {});
      message(`${served.name} has been called · ${served.issue}`);
      await refresh();
    }),
  );
}

async function acknowledge() {
  if (!notice) return;
  const id = notice;
  await api("/acknowledge", { id });
  notice = null;
}

if ($("dismiss-turn")) {
  $("dismiss-turn").addEventListener("click", () =>
    action(async () => {
      await acknowledge();
      if ($("turn-dialog")) $("turn-dialog").close();
    }),
  );
}

if ($("turn-dialog")) {
  $("turn-dialog").addEventListener("cancel", (event) => {
    event.preventDefault();
    if ($("dismiss-turn")) $("dismiss-turn").click();
  });
}

// LANDING PAGE EVENT LISTENERS

if ($("landing-client-go")) {
  $("landing-client-go").addEventListener("click", () => {
    location.assign("/client");
  });
}
if ($("landing-client-signin")) {
  $("landing-client-signin").addEventListener("click", () => {
    location.assign("/client#login");
  });
}
if ($("landing-client-register")) {
  $("landing-client-register").addEventListener("click", () => {
    location.assign("/client#register");
  });
}
if ($("landing-admin-go")) {
  $("landing-admin-go").addEventListener("click", () => {
    location.assign("/admin");
  });
}

// AUTOMATIC REFRESH

async function poll() {
  try {
    if (!busy) await refresh();
  } catch (error) {
    if ($("connection")) $("connection").textContent = "Connection interrupted · retrying…";
  } finally {
    setTimeout(poll, 2000);
  }
}

render();
poll();
