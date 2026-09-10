/**
 * Hidden validation tests for Node.js sample repository.
 */

const test = require("node:test");
const assert = require("node:assert");
const { calculateMetrics, parseQueryString } = require("./index.js");

test("hidden: calculateMetrics with negative numbers", () => {
  const res = calculateMetrics([-5, -15, 20]);
  assert.strictEqual(res.count, 3);
  assert.strictEqual(res.sum, 0);
  assert.strictEqual(res.average, 0);
});

test("hidden: parseQueryString with empty query string", () => {
  const res = parseQueryString("");
  assert.deepStrictEqual(res, {});
});

test("hidden: parseQueryString with special characters", () => {
  const res = parseQueryString("?tag=ai%2Bagent&user=test");
  assert.strictEqual(res.tag, "ai+agent");
  assert.strictEqual(res.user, "test");
});
