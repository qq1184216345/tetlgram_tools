(() => {
  const site = window.ZHIYI_SITE || {};
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const yearEl = $("#year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  $$("[data-version]").forEach((el) => {
    el.textContent = site.version || "0.1.0";
  });

  // 与授权云版本清单同步（同域部署时可用）
  fetch("/app/version", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data || !data.version) return;
      site.version = data.version;
      const url = (data.download_url || data.url || "").trim();
      if (url) site.downloadUrl = url;
      $$("[data-version]").forEach((el) => {
        el.textContent = data.version;
      });
    })
    .catch(() => {});

  const email = site.email || "nb@zhiyinb.cc";
  $$("[data-email]").forEach((el) => {
    if (el.tagName === "A") {
      el.href = `mailto:${email}`;
      if (!el.textContent.trim()) el.textContent = email;
    } else {
      el.textContent = email;
    }
  });

  const telegram = (site.telegram || "").trim();
  $$("[data-telegram]").forEach((el) => {
    if (!telegram) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    if (el.tagName === "A") el.href = telegram;
  });

  const nav = $(".site-nav");
  const toggle = $(".nav-toggle");
  toggle?.addEventListener("click", () => {
    const open = nav?.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  $$(".site-nav a").forEach((link) => {
    link.addEventListener("click", () => {
      nav?.classList.remove("open");
      toggle?.setAttribute("aria-expanded", "false");
    });
  });

  const header = $(".site-header");
  const onScroll = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 12);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  const plansRoot = $("#plans");
  if (plansRoot && Array.isArray(site.plans)) {
    plansRoot.innerHTML = site.plans
      .map((plan) => {
        const featured = plan.featured ? " featured" : "";
        return `<article class="plan-card${featured} reveal">
          ${plan.featured ? '<p class="plan-badge">常用</p>' : ""}
          <h3>${escapeHtml(plan.name)}</h3>
          <p class="plan-days">${Number(plan.days) || ""} 天授权</p>
          <p class="plan-price">${escapeHtml(plan.price || "咨询报价")}</p>
          <p class="plan-note">${escapeHtml(plan.note || "")}</p>
          <a class="btn btn-ghost" href="#contact">联系开通</a>
        </article>`;
      })
      .join("");
  }

  const revealEls = $$(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );
    revealEls.forEach((el, i) => {
      el.style.setProperty("--delay", `${Math.min(i % 6, 5) * 70}ms`);
      io.observe(el);
    });
  } else {
    revealEls.forEach((el) => el.classList.add("in"));
  }

  $$(".faq-item").forEach((item) => {
    const btn = $("button", item);
    btn?.addEventListener("click", () => {
      const open = item.classList.contains("open");
      $$(".faq-item.open").forEach((other) => other.classList.remove("open"));
      if (!open) item.classList.add("open");
    });
  });

  const downloadBtns = $$("[data-download]");
  downloadBtns.forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const url = (site.downloadUrl || "").trim();
      if (!url) {
        event.preventDefault();
        const contact = document.querySelector("#contact");
        contact?.scrollIntoView({ behavior: "smooth" });
        flash("安装包尚未公开直链，请通过邮箱联系获取。");
        return;
      }
      btn.setAttribute("href", url);
    });
  });

  function flash(message) {
    let toast = $(".site-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "site-toast";
      toast.className = "site-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(flash._t);
    flash._t = window.setTimeout(() => toast.classList.remove("show"), 2800);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
})();
