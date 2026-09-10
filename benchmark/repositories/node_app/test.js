const test = require("node:test");
const assert = require("node:assert");
const { calculateMetrics, parseQueryString } = require("./index.js");

test("calculateMetrics calculates correctly", () => {
  const res = calculateMetrics([10, 20, 30]);
  assert.strictEqual(res.count, 3);
  assert.strictEqual(res.sum, 60);
  assert.strictEqual(res.average, 20);
});

test("calculateMetrics handles empty array", () => {
  const res = calculateMetrics([]);
  assert.strictEqual(res.count, 0);
  assert.strictEqual(res.sum, 0);
  assert.strictEqual(res.average, 0);
});

test("parseQueryString parses key values", () => {
  const res = parseQueryString("?page=2&limit=50");
  assert.strictEqual(res.page, "2");
  assert.strictEqual(res.limit, "50");
});
