/* Demo interface client (spec 004, T008).
 * Posts the question to the governed /query API and renders the answer or
 * refusal, the sanitized trace, and the observational latency. No secrets or
 * endpoint details are ever embedded here. */
(function () {
  "use strict";

  var form = document.getElementById("ask-form");
  var input = document.getElementById("question");
  var btn = document.getElementById("ask-btn");
  var result = document.getElementById("result");
  var statusEl = document.getElementById("status");
  var answerEl = document.getElementById("answer");
  var latencyEl = document.getElementById("latency");
  var traceEl = document.getElementById("trace");

  function setStatus(status) {
    statusEl.textContent = status;
    statusEl.className = "badge badge-" + status;
  }

  function renderTrace(events) {
    traceEl.innerHTML = "";
    (events || []).forEach(function (ev) {
      var li = document.createElement("li");
      var detail = ev.detail ? " — " + ev.detail : "";
      li.textContent = ev.event + detail;
      traceEl.appendChild(li);
    });
  }

  function show(payload) {
    result.classList.remove("hidden");
    setStatus(payload.status || "unknown");
    answerEl.textContent = payload.answer || "";
    var ms = typeof payload.latency_ms === "number" ? payload.latency_ms : 0;
    latencyEl.textContent = ms.toFixed(0) + " ms";
    renderTrace(payload.trace);
  }

  function showError(message) {
    result.classList.remove("hidden");
    setStatus("dependency_error");
    answerEl.textContent = message;
    latencyEl.textContent = "—";
    renderTrace([]);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) { return; }
    btn.disabled = true;
    btn.textContent = "Asking…";
    fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q })
    })
      .then(function (r) { return r.json(); })
      .then(function (payload) { show(payload); })
      .catch(function () {
        showError("The request failed. Please try again.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Ask";
      });
  });

  Array.prototype.forEach.call(
    document.querySelectorAll(".example"),
    function (el) {
      el.addEventListener("click", function () {
        input.value = el.getAttribute("data-q");
        form.dispatchEvent(new Event("submit"));
      });
    }
  );
})();
