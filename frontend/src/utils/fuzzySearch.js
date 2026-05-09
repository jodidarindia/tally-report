// Fuzzy / normalized search helpers — ignore spaces & separator characters
// (- / ( ) ! : . , & _ ' ") in BOTH the search input and the target string,
// so "tvs 10" matches "TVS-10", "TVS(10)", "TVS/10", "TVS.10" etc.
//
// Mirrors backend/utils.py::fuzzy_normalize / fuzzy_match.

const FUZZY_STRIP_RE = /[\s\-/()!:.,&_'"]+/g;

export function fuzzyNormalize(s) {
  if (!s) return '';
  return String(s).replace(FUZZY_STRIP_RE, '').toLowerCase();
}

export function fuzzyMatch(haystack, needle) {
  if (!needle) return true;
  return fuzzyNormalize(haystack).includes(fuzzyNormalize(needle));
}

// Match any of the provided fields (strings OR arrays of strings).
export function fuzzyMatchAny(needle, fields) {
  if (!needle) return true;
  const n = fuzzyNormalize(needle);
  if (!n) return true;
  for (const f of fields) {
    if (Array.isArray(f)) {
      for (const v of f) {
        if (fuzzyNormalize(v).includes(n)) return true;
      }
    } else if (fuzzyNormalize(f).includes(n)) {
      return true;
    }
  }
  return false;
}
