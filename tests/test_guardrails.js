"use strict";

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(`${__dirname}/../static/app.js`, "utf8");

class Element {
  constructor(value = "") {
    this.value = value;
    this.textContent = "";
    this.children = [];
    this.listeners = {};
    this.hidden = false;
    this.classList = { toggle() {} };
  }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(name, value) { this[name] = value; }
  fire(event) { return this.listeners[event]({ preventDefault() {} }); }
}

function page() {
  const ids = [
    "demo-config", "state", "char-count", "status", "request-json", "request-caption",
    "guardrail-threshold", "guardrail-value", "guardrail-result", "run-form", "run",
    "error", "results", "previous-result", "previous", "response-json", "latency",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  const probabilities = {
    prompt_injection: 0.9, prompt_leaking: 0.7, jailbreak: 0.2, data_exfiltration: 0.1,
  };
  elements["demo-config"].textContent = JSON.stringify({
    slug: "guardrails",
    model: "jev-test",
    network_allowed: true,
    questions: Object.fromEntries(Object.keys(probabilities).map((name) => [
      name, { type: "noul", instructions: name },
    ])),
    examples: [{ text: "An untrusted example" }],
  });
  elements.state.value = "Original input";
  elements["guardrail-threshold"].value = "70";
  elements.error.hidden = true;
  const example = new Element();
  example.dataset = { index: "0" };
  const calls = [];
  let fail = false;
  vm.runInNewContext(source, {
    document: {
      getElementById: (id) => elements[id] || null,
      createElement: () => new Element(),
      querySelectorAll: () => [example],
      querySelector: () => new Element(),
    },
    AbortSignal,
    fetch: async (url, options) => {
      calls.push({ url, options });
      return {
        ok: !fail,
        json: async () => fail ? { detail: "Jev timed out." } : {
          response: {
            model: "jev-test",
            answers: Object.fromEntries(Object.entries(probabilities).map(([name, noul]) => [
              name, { type: "noul", noul },
            ])),
          },
          elapsed_ms: 12,
        },
      };
    },
  });
  return {
    elements, calls, example,
    run: () => elements["run-form"].fire("submit"),
    failNext: () => { fail = true; },
    threshold: (value) => {
      elements["guardrail-threshold"].value = String(value);
      elements["guardrail-threshold"].fire("input");
    },
  };
}

test("guardrail policy flags independent risks at the inclusive threshold locally", async () => {
  const p = page();
  p.threshold(70);
  assert.equal(p.calls.length, 0);
  await p.run();
  assert.equal(p.calls.length, 1);
  assert.equal(p.calls[0].url, "/api/demos/guardrails/run");
  assert.deepEqual(JSON.parse(p.calls[0].options.body), { text: "Original input" });
  const result = () => p.elements["guardrail-result"].textContent;
  assert.match(result(), /Flag for human review: prompt injection \(90.0%\), prompt leaking \(70.0%\)/);
  assert.doesNotMatch(result(), /jailbreak/);
  p.threshold(95);
  assert.match(result(), /No risks reach this threshold/);
  assert.match(result(), /not proof of safety/);
  p.threshold(0);
  assert.match(result(), /jailbreak.*data exfiltration/);
  p.threshold(100);
  assert.match(result(), /No risks reach this threshold/);
  assert.equal(p.calls.length, 1);
});

test("editing and loading examples never run Jev and keep policy paired with its input", async () => {
  const p = page();
  p.example.fire("click");
  assert.equal(p.elements.state.value, "An untrusted example");
  assert.equal(p.calls.length, 0);
  await p.run();
  p.elements.state.value = "Edited input";
  p.elements.state.fire("input");
  assert.match(p.elements.status.textContent, /Out of date/);
  assert.match(p.elements["guardrail-result"].textContent, /Using the last run, not your edits/);
  assert.equal(JSON.parse(p.elements["request-json"].textContent).state, "An untrusted example");
  assert.equal(p.elements.results.children[1].textContent, "An untrusted example");
  p.threshold(80);
  assert.match(p.elements["guardrail-result"].textContent, /Using the last run, not your edits/);
  assert.equal(p.calls.length, 1);
});

test("a failed guardrails run preserves the last successful results and exposes the error", async () => {
  const p = page();
  await p.run();
  const previous = p.elements["response-json"].textContent;
  p.elements.state.value = "New input";
  p.failNext();
  await p.run();
  assert.equal(p.elements.error.hidden, false);
  assert.match(p.elements.error.textContent, /Run failed: Jev timed out/);
  assert.match(p.elements.status.textContent, /Latest attempt failed/);
  assert.equal(p.elements["response-json"].textContent, previous);
  assert.equal(p.elements.results.children[1].textContent, "Original input");
  assert.match(p.elements["guardrail-result"].textContent, /Using the last run, not your edits/);
});
