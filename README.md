# Inflace bydlení: oficiální číslo vs. vaše situace

Experimentální alternativní index inflace postavený na bydlení. Oficiální CPI je průměr za všechny domácnosti
a neobsahuje ceny starších bytů ani splátku nové hypotéky. Tady se inflace počítá zvlášť pro čtyři situace:

| Situace | Složka bydlení |
|---|---|
| Kupuji byt | měsíční splátka na standardní byt = ceny starších bytů (HPI) × splátka při sazbě nových úvěrů (30 let) |
| Splácím hypotéku | splátka na 1 Kč jistiny při průměrné sazbě ze zůstatků úvěrů na bydlení |
| Vlastním bez hypotéky | žádná; jen koš bez nájmu a imputovaného nájmu |
| Bydlím v nájmu | nájemné z CPI (položka 041) |

Index = `podíl_bydlení × složka_bydlení + (1 − podíl_bydlení) × koš_bez_bydlení`, vůči průměru roku 2024 (váhy ČSÚ 2024).
Výchozí podíl bydlení je 30 % výdajů, v HTML jde nastavit posuvníkem.

## Struktura

```
config.json            váhy, referenční období, ID řad ARAD
src/fetch.py           stažení dat (ČSÚ, Eurostat/ČSÚ, ČNB ARAD), při selhání použije cache v data/
src/model.py           výpočet indexů
src/update.py          celý běh: stáhnout, spočítat, zapsat docs/data.json a graf
src/chart.py           statický graf 4:3 (docs/graf_inflace_bydleni.png)
docs/index.html        interaktivní stránka (čte data.json, počítá v prohlížeči)
tests/                 test_model.py (Python), test_page.js (shoda HTML s Pythonem)
.github/workflows/     měsíční automatická aktualizace
```

## Nasazení

1. Vytvořte na GitHubu repozitář (veřejný, aby šla data číst z Wixu) a nahrajte do něj obsah této složky.
2. **Settings → Secrets and variables → Actions → New repository secret**: název `ARAD_API_KEY`, hodnota je klíč z ČNB ARAD.
   Klíč nikdy nepatří do souborů v repozitáři.
3. **Actions → Měsíční aktualizace indexu → Run workflow** (první ruční běh). Dál běží sám denně 11.–25. v měsíci
   a commitne jen tehdy, když se data změnila.
4. Stránka:
   - GitHub Pages: **Settings → Pages → Branch main, složka /docs**, nebo
   - Wix: do prvku HTML vložte obsah `docs/index.html` a konstantu `DATA_URL` nastavte na
     `https://raw.githubusercontent.com/UZIVATEL/REPOZITAR/main/docs/data.json`.

Lokálně: `pip install -r requirements.txt`, `export ARAD_API_KEY=...`, `python src/update.py`.
Bez klíče se sazby vezmou z uložené cache v `data/arad_rates.csv`.

## Časování dat

- CPI (ČSÚ): kolem 10. dne v měsíci, za předchozí měsíc.
- Sazby (ČNB ARAD): zpoždění zhruba 6 týdnů. Index se počítá do posledního měsíce, který mají všechny zdroje.
- Ceny bytů (HPI): čtvrtletně se zpožděním; chybějící měsíce se dopočítají podle trendu posledních 12 měsíců
  a jsou v grafu označeny čárkovaně.

## Omezení (platí i pro text na webu)

- Pro celé období se používá jedna sada vah (2024); přepočet oficiálního CPI se od skutečné meziroční inflace
  liší od roku 2024 průměrně o 0,12 p. b., kumulativně od roku 2019 o necelé 2 p. b.
- Řady ČNB jsou „úvěry na bydlení“ (banky včetně stavebních spořitelen), ne čistě hypotéky.
- Průměrná sazba ze zůstatků nezachytí domácnosti, jimž právě skončila fixace.
- Tržní nájmy nových smluv zatím nejsou zahrnuty (veřejná dlouhá řada neexistuje), použito je nájemné z CPI.
- Ceny finančních aktiv se do indexu záměrně nezapočítávají.
- Nejde o oficiální statistiku ani o poradenství.

## Zdroje

Český statistický úřad (CPI, váhy, HPI), Eurostat (prc_hpi_q), Česká národní banka, systém ARAD.
