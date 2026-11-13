// Kontrola: výpočet v HTML (client-side) musí odpovídat souhrnu z Pythonu (data.json -> souhrn_vychozi).
// Spuštění: node tests/test_page.js
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "../docs/index.html"), "utf8");
const m = html.match(/\/\* CALC-START[\s\S]*?\*\/([\s\S]*?)\/\* CALC-END \*\//);
if (!m) throw new Error("CALC blok nenalezen");
const calc = new Function(m[1] + "; return {seriesFor, rebase, pct, annualize, startIndex};")();
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "../docs/data.json"), "utf8"));
const H = D.meta.vychozi_podil_bydleni, n = D.mesice.length;
let bad = 0;
const check = (name, got, want) => {
  const ok = Math.abs(got - want) <= 0.06;
  if (!ok) bad++;
  console.log((ok ? "OK   " : "CHYBA") + " " + name.padEnd(22) + got.toFixed(2).padStart(8) + " vs " + want);
};
for (const [k, s] of Object.entries(D.souhrn_vychozi)) {
  const arr = k === "cpi" ? D.cpi_replika : calc.seriesFor(D, k, H);
  check(k + " od začátku", calc.pct(arr, 0, n - 1), s.od_zacatku_pct);
  check(k + " meziročně", calc.pct(arr, n - 13, n - 1), s.mezirocne_pct);
  check(k + " ročně (p. a.)", calc.annualize(calc.pct(arr, 0, n - 1), n - 1), s.rocne_od_zacatku_pct);
}
check("annualize(100, 120)", calc.annualize(100, 120), 7.18);
check("annualize(21, 24)", calc.annualize(21, 24), 10.0);
check("annualize(5, 12)", calc.annualize(5, 12), 5.0);
// hc pole nesmí mít díry
for (const k of Object.keys(D.hc)) if (D.hc[k].some(v => v == null || !isFinite(v))) { bad++; console.log("CHYBA díry v hc." + k); }
if (D.mesice.length !== D.n.length) { bad++; console.log("CHYBA délky"); }
process.exit(bad ? 1 : 0);
