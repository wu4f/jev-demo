"use strict";

const config = JSON.parse(document.getElementById("demo-config").textContent);
const byId = (id) => document.getElementById(id);
const input = byId("state");
let latest = null;
let running = false;

const percent = (value) => `${(value * 100).toFixed(1)}%`;
const label = (name) => name.replaceAll("_", " ");

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function requestFor(text) {
  return { state: text, model: config.model, questions: config.questions };
}

function isStale() {
  return latest && input.value !== latest.text;
}

function updateInput() {
  byId("char-count").textContent = `${input.value.length} / 6000 characters`;
  if (!running) {
    byId("status").textContent = !config.network_allowed
      ? "TypeSafe access denied for your network. You can edit examples, but cannot run Jev."
      : latest
      ? isStale()
        ? "Out of date: these results belong to the input shown below. Run again to evaluate your edits."
        : "Live results from Jev. Probabilities are estimates, not guarantees."
      : "Edit the example, then run Jev to see real API results.";
  }
  byId("status").classList.toggle("notice", Boolean(isStale()));
  byId("request-json").textContent = JSON.stringify(
    requestFor(latest ? latest.text : input.value), null, 2
  );
  byId("request-caption").textContent = latest ? "(last completed run)" : "(preview)";
  updatePolicy();
}

function renderAnswers(run, target) {
  target.replaceChildren();
  target.append(node("h3", "Input for this run", "small-heading"), node("blockquote", run.text));
  for (const [name, answer] of Object.entries(run.response.answers)) {
    const card = node("article", undefined, "answer");
    const heading = node("div", undefined, "panel-heading");
    heading.append(node("h3", label(name)), node("span", answer.type, "tag"));
    card.append(heading);
    if (answer.type === "noul") {
      card.append(node("p", percent(answer.noul), "answer-value"));
      card.append(node("p", "Probability the statement is true", "meta"));
      const bar = node("progress");
      bar.max = 1;
      bar.value = answer.noul;
      bar.setAttribute("aria-label", `${label(name)} probability`);
      card.append(bar);
    } else {
      const value = answer.type === "choice" ? label(answer.choice) : answer.score.toFixed(2);
      card.append(node("p", value, "answer-value"));
      if (answer.type === "score") {
        card.append(node("p", `Position on levels 0–${config.questions[name].criteria.length - 1}`, "meta"));
      }
      card.append(node("p", `Returned confidence: ${percent(answer.confidence)}`, "meta"));
      for (const [option, probability] of Object.entries(answer.probabilities)) {
        const row = node("div", undefined, "probability");
        const description = answer.type === "score"
          ? `${option}: ${config.questions[name].criteria[Number(option)]}`
          : label(option);
        const caption = node("div", undefined, "probability-caption");
        caption.append(node("span", description), node("span", percent(probability)));
        const bar = node("progress");
        bar.max = 1;
        bar.value = probability;
        bar.setAttribute("aria-label", `${description} probability`);
        row.append(caption, bar);
        card.append(row);
      }
    }
    target.append(card);
  }
}

function updatePolicy() {
  if (config.slug === "guardrails") {
    const threshold = Number(byId("guardrail-threshold").value) / 100;
    byId("guardrail-value").textContent = percent(threshold);
    if (!latest) return;
    const flagged = Object.entries(latest.response.answers)
      .filter(([, answer]) => answer.noul >= threshold)
      .map(([name, answer]) => `${label(name)} (${percent(answer.noul)})`);
    const action = flagged.length
      ? `Flag for human review: ${flagged.join(", ")}.`
      : "No risks reach this threshold. Continue other checks; this is not proof of safety.";
    byId("guardrail-result").textContent = `${isStale() ? "Using the last run, not your edits: " : ""}${action}`;
    return;
  }
  if (config.slug !== "automation") return;
  const route = Number(byId("route-threshold").value) / 100;
  const urgent = Number(byId("urgent-threshold").value) / 100;
  byId("route-value").textContent = percent(route);
  byId("urgent-value").textContent = percent(urgent);
  if (!latest) return;
  const answers = latest.response.answers;
  const choice = answers.department;
  const probability = choice.probabilities[choice.choice];
  const action = probability >= route
    ? `Auto-route to ${label(choice.choice)} (${percent(probability)} ≥ ${percent(route)}).`
    : `Request human review (${percent(probability)} < ${percent(route)}).`;
  const urgency = answers.is_urgent.noul >= urgent ? " Flag as urgent." : " No urgency flag.";
  byId("policy-result").textContent = `${isStale() ? "Using the last run, not your edits: " : ""}${action}${urgency}`;
}

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = config.examples[Number(button.dataset.index)].text;
    updateInput();
  });
});
input.addEventListener("input", updateInput);
for (const id of ["route-threshold", "urgent-threshold", "guardrail-threshold"]) {
  byId(id)?.addEventListener("input", updatePolicy);
}

byId("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (running || !config.network_allowed) return;
  if (!input.value.trim()) {
    byId("error").textContent = "Enter some text to evaluate.";
    byId("error").hidden = false;
    return;
  }
  running = true;
  const text = input.value;
  byId("run").disabled = true;
  byId("run").textContent = "Asking Jev…";
  byId("error").hidden = true;
  byId("status").textContent = "Calling the real TypeSafe API…";
  document.querySelector(".results-panel").setAttribute("aria-busy", "true");
  try {
    const response = await fetch(`/api/demos/${config.slug}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(30000),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Invalid input. Use 1–6000 characters.");
    }
    if (latest) {
      renderAnswers(latest, byId("previous-result"));
      byId("previous").hidden = false;
    }
    latest = { text, ...data };
    renderAnswers(latest, byId("results"));
    byId("response-json").textContent = JSON.stringify(data.response, null, 2);
    byId("latency").textContent = `${data.elapsed_ms} ms · ${data.response.model}`;
  } catch (error) {
    byId("error").textContent = error.name === "TimeoutError"
      ? "The request timed out. Try again."
      : `Run failed: ${error.message}`;
    byId("error").hidden = false;
  } finally {
    running = false;
    byId("run").disabled = !config.network_allowed;
    byId("run").textContent = "Run Jev →";
    document.querySelector(".results-panel").setAttribute("aria-busy", "false");
    updateInput();
    if (!byId("error").hidden) {
      byId("status").textContent = latest
        ? "Latest attempt failed. Results below are from the last successful run."
        : "No results: the API call failed. See the error beside the input.";
    }
  }
});

updateInput();
