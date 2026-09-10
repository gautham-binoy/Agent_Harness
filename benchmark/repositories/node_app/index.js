/**
 * Minimal Node.js Service logic.
 */

function calculateMetrics(numbers) {
  if (!Array.isArray(numbers)) {
    throw new TypeError("Expected an array of numbers");
  }
  if (numbers.length === 0) {
    return { count: 0, sum: 0, average: 0 };
  }
  const sum = numbers.reduce((acc, val) => acc + val, 0);
  return {
    count: numbers.length,
    sum: sum,
    average: sum / numbers.length,
  };
}

function parseQueryString(qs) {
  if (!qs || typeof qs !== "string") return {};
  const cleaned = qs.startsWith("?") ? qs.slice(1) : qs;
  const params = {};
  for (const pair of cleaned.split("&")) {
    const [k, v] = pair.split("=");
    if (k) {
      params[decodeURIComponent(k)] = v ? decodeURIComponent(v) : "";
    }
  }
  return params;
}

module.exports = { calculateMetrics, parseQueryString };
