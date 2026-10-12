/* Demo interface client (spec 004, T008; spec 008 gallery/overview/guidance).
 * Posts the question to the governed /query API and renders the answer or
 * refusal, the sanitized trace, and the observational latency. No secrets or
 * endpoint details are ever embedded here.
 *
 * spec 008: the example gallery, placeholder rotation, and typing
 * suggestions all come from the curated static asset /static/examples.json.
 * If that fetch fails, the page still accepts free-text questions
 * (graceful degradation, spec 008 edge cases). */
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
  var galleryToggle = document.getElementById("gallery-toggle");
  var gallery = document.getElementById("gallery");
  var suggestionsEl = document.getElementById("suggestions");

  var EXAMPLES_URL = "/static/examples.json";
  var PLACEHOLDER_INTERVAL_MS = 4000;
  var SUGGESTION_MIN_CHARS = 3;
  var SUGGESTION_MAX_ITEMS = 5;

  var curatedQuestions = [];
  var placeholderTimer = null;
  var placeholderIndex = 0;
  var userTouchedInput = false;
  var suggestionItems = [];
  var suggestionIndex = -1;

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

  function submitQuestion(q) {
    input.value = q;
    form.dispatchEvent(new Event("submit"));
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) { return; }
    closeSuggestions();
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

  /* -- Gallery (US1) ---------------------------------------------------- */

  function renderGallery(data) {
    gallery.innerHTML = "";
    data.categories.forEach(function (category) {
      var entries = data.examples.filter(function (e) {
        return e.category === category;
      });
      if (!entries.length) { return; }
      var section = document.createElement("div");
      section.className = "gallery-category";
      var heading = document.createElement("h3");
      heading.textContent = category;
      section.appendChild(heading);
      entries.forEach(function (entry) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "gallery-example";
        b.setAttribute("data-q", entry.question);
        b.textContent = entry.question;
        if (entry.outcome === "refusal_demo") {
          b.className += " gallery-example-refusal";
          b.title = entry.note || "Demonstration of a refused request.";
        }
        b.addEventListener("click", function () {
          submitQuestion(entry.question);
        });
        section.appendChild(b);
        if (entry.note) {
          var note = document.createElement("p");
          note.className = "gallery-note";
          note.textContent = entry.note;
          section.appendChild(note);
        }
      });
      gallery.appendChild(section);
    });
  }

  galleryToggle.addEventListener("click", function () {
    var open = gallery.classList.toggle("hidden");
    galleryToggle.setAttribute("aria-expanded", open ? "false" : "true");
  });

  /* -- Placeholder rotation (US3) --------------------------------------- */

  function rotatePlaceholder() {
    if (userTouchedInput || input.value || !curatedQuestions.length) {
      return;
    }
    input.placeholder = "e.g. " + curatedQuestions[placeholderIndex];
    placeholderIndex = (placeholderIndex + 1) % curatedQuestions.length;
  }

  function startPlaceholderRotation() {
    if (curatedQuestions.length < 3 || placeholderTimer !== null) {
      return;
    }
    placeholderTimer = setInterval(
      rotatePlaceholder, PLACEHOLDER_INTERVAL_MS);
  }

  function stopPlaceholderRotation() {
    userTouchedInput = true;
    if (placeholderTimer !== null) {
      clearInterval(placeholderTimer);
      placeholderTimer = null;
    }
  }

  /* -- Typing suggestions (US3) ----------------------------------------- */

  function closeSuggestions() {
    suggestionsEl.classList.add("hidden");
    suggestionsEl.innerHTML = "";
    suggestionItems = [];
    suggestionIndex = -1;
  }

  function highlightSuggestion(index) {
    suggestionIndex = index;
    suggestionItems.forEach(function (el, i) {
      el.classList.toggle("suggestion-active", i === index);
    });
  }

  function updateSuggestions() {
    var q = input.value.trim().toLowerCase();
    if (q.length < SUGGESTION_MIN_CHARS || !curatedQuestions.length) {
      closeSuggestions();
      return;
    }
    var matches = curatedQuestions.filter(function (candidate) {
      return candidate.toLowerCase().indexOf(q) !== -1;
    }).slice(0, SUGGESTION_MAX_ITEMS);
    if (!matches.length) {
      closeSuggestions();
      return;
    }
    suggestionsEl.innerHTML = "";
    suggestionItems = matches.map(function (question) {
      var item = document.createElement("div");
      item.className = "suggestion";
      item.setAttribute("role", "option");
      item.textContent = question;
      item.addEventListener("mousedown", function (e) {
        // mousedown (not click) so the fill happens before input blur.
        e.preventDefault();
        input.value = question;
        closeSuggestions();
        input.focus();
      });
      suggestionsEl.appendChild(item);
      return item;
    });
    suggestionIndex = -1;
    suggestionsEl.classList.remove("hidden");
  }

  input.addEventListener("input", function () {
    stopPlaceholderRotation();
    updateSuggestions();
  });

  input.addEventListener("keydown", function (e) {
    if (suggestionsEl.classList.contains("hidden")) { return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlightSuggestion((suggestionIndex + 1) % suggestionItems.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlightSuggestion(
        (suggestionIndex - 1 + suggestionItems.length)
        % suggestionItems.length);
    } else if (e.key === "Enter" && suggestionIndex >= 0) {
      e.preventDefault();
      input.value = suggestionItems[suggestionIndex].textContent;
      closeSuggestions();
    } else if (e.key === "Escape") {
      closeSuggestions();
    }
  });

  input.addEventListener("blur", function () {
    closeSuggestions();
  });

  /* -- Load curated content once; degrade gracefully on failure --------- */

  fetch(EXAMPLES_URL)
    .then(function (r) {
      if (!r.ok) { throw new Error("examples unavailable"); }
      return r.json();
    })
    .then(function (data) {
      var examples = (data && data.examples) || [];
      if (!examples.length) { throw new Error("examples empty"); }
      curatedQuestions = examples.map(function (e) { return e.question; });
      renderGallery(data);
      startPlaceholderRotation();
    })
    .catch(function () {
      // Graceful degradation: hide discovery aids, keep free-text flow.
      gallery.classList.add("hidden");
      galleryToggle.classList.add("hidden");
      closeSuggestions();
    });
})();
