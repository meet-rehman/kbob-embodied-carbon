# Embodied carbon questions in plain language (KBOB prototype)

A small prototype: describe a building material in your own words, give a quantity, and get its environmental impact from the Swiss KBOB life cycle data.

**Status: prototype. Do not use its numbers for project decisions.** The screenshots on this page are from the first version (May 2026), which had two errors in reading the data. I found both later and corrected them in the code here. The corrected search has not been re-run yet, and the compliance check is still a placeholder. This page documents the failures, because they are the useful part.

## The idea

Swiss architects and engineers calculate grey energy (Graue Energie) by looking up each material in the KBOB list, copying its values into a spreadsheet and multiplying by quantities. Existing tools for this are form-based.

The question behind this prototype: can a plain-language description such as "Brettsperrholz CLT Holzdecke" be matched to the right KBOB entry automatically?

## How it works

1. **Input:** a material description in German and a quantity in kg.
2. **Search:** the description is compared with the KBOB material names using a sentence-embedding model. The three closest entries are shown with their similarity score.
3. **Calculation:** the quantity is multiplied by the values of the best match: greenhouse gas emissions (GWP), environmental impact points (UBP) and primary energy (PE).
4. **Check:** the result per m² of floor area is compared with a threshold.
5. **Report:** a language model writes a short summary that names the matched KBOB entry.

The tool runs in the terminal. The first version loaded 100 materials. The corrected version loads 348.

## Three test runs

| Query | Quantity | Best match | Score | Correct? |
|---|---|---|---|---|
| Beton Stahlbeton Bodenplatte | 15,000 kg | Hanfbeton, ARBIO | 0.523 | **No.** Hemp concrete, not a reinforced concrete slab |
| Brettsperrholz CLT Holzdecke | 5,000 kg | Brettsperrholz, Produktion Schweiz | 0.644 | Yes |
| Wärmedämmung Mineralwolle Aussenwand | 800 kg | Glaswolle, SUPAFIL | 0.579 | Plausible. Glass wool is one kind of mineral wool, stone wool came second (0.541) |

### Run 1: a wrong match, explained convincingly

![Reinforced concrete slab matched to hemp concrete](screenshots/01-concrete-slab-wrong-match.jpg)

The query asks for a reinforced concrete floor slab. The best match is hemp concrete (0.523). Ordinary concrete is in the list and came second and third (0.418 and 0.415). Both concrete entries are marked "ohne Bewehrung" (without reinforcement), so a reinforced slab is really two materials, concrete plus reinforcing steel. The tool can only return one.

The more important observation is the report. The language model did not question the match. It wrote that hemp concrete was "selected due to its relevance in concrete applications and sustainability attributes". A wrong retrieval result came back as a confident, well-worded explanation.

### Run 2: a correct match

![Cross-laminated timber matched correctly](screenshots/02-clt-ceiling.jpg)

### Run 3: an ambiguous query

![Mineral wool insulation](screenshots/03-mineral-wool-insulation.jpg)

"Mineralwolle" covers both glass wool and stone wool. The two candidates scored 0.579 and 0.541. The tool picked the first without telling the user that the choice was close.

## Known errors in the first version

| Problem | What I see | Consequence |
|---|---|---|
| **GWP values were far too low** (corrected) | 800 kg of glass wool gave 8.56 kg CO₂-eq, about 0.01 kg per kg. The KBOB value is 1.14. | The parser read the wrong column: renewable primary energy for disposal, in place of total greenhouse gas emissions. See below. |
| **The compliance check is a placeholder** | One material is compared with fixed limits (GWP 10, PE 50) per m² of an assumed floor area. | "Compliant" and "exceeds limit" mean nothing here. Real limit values apply to a whole building per m² and year over its lifetime (SIA 2032), not to a single material. |
| **Only 100 materials** (corrected) | The tool loaded only the manufacturer-specific entries and skipped all 248 generic ones, such as "Hochbaubeton" or "Glaswolle". | A query for ordinary concrete could only match branded products. This is one reason the first run landed on hemp concrete. |
| **No handling of close or weak matches** | The first result is always used. | Wrong and ambiguous matches pass silently. |
| **The report repeats whatever it is given** | The summary justified the hemp concrete match. | The text adds confidence without adding a check. |
| **German only** | Material names are searched in German only. | Queries in other languages match poorly. |

## The two reading errors, found and corrected

After publishing the screenshots I compared the parsed values with the KBOB spreadsheet row by row.

**1. Wrong column for greenhouse gas emissions.** The spreadsheet has 31 columns under merged headers. The parser took column 19, which is renewable primary energy for disposal. Greenhouse gas emissions are in column 25. Primary energy and UBP were read from the right columns, which is why only the carbon figure looked wrong.

**2. Wrong filter on the ID.** A comment in the code said "skip manufacturer-specific entries". The condition did the opposite: it kept only IDs with three parts, such as `10.001.02`, and dropped the generic ones, such as `10.001`.

The same three matches with the correct column:

| Match | Quantity | GWP in the first version (wrong column) | GWP with the correct column |
|---|---|---|---|
| Hanfbeton, ARBIO | 15,000 kg | 0.24 kg CO₂-eq | 4,680 kg CO₂-eq |
| Brettsperrholz, Produktion Schweiz | 5,000 kg | 30.75 kg CO₂-eq | 1,250 kg CO₂-eq |
| Glaswolle, SUPAFIL | 800 kg | 8.56 kg CO₂-eq | 912 kg CO₂-eq |

The right-hand values are recalculated by hand from the KBOB spreadsheet for the matches shown in the screenshots. With the generic entries now loaded, the search may return different matches. That run is still to do.

The lesson is plain: a result that is wrong by a factor of 100 passed through the calculation, the compliance check and the written report without any of them objecting. It only showed when the figure was compared with a typical value for glass wool.

## What I take from it

- Matching plain language to a material list works when the description contains the material's actual name.
- The risky step is not the search. It is the report layer that turns any search result into a fluent answer.
- A tool like this needs a stop rule: if the best score is low, or the two best scores are close, it should ask the user to choose.

This is the same pattern I found in my thesis work on building regulations: the answer that sounds most certain is not always the one with the best source behind it.

## Next steps

- Re-run the three test queries with the corrected data and compare the matches.
- Add a test that checks a few parsed values against the spreadsheet.
- Ask the user to confirm the match when scores are low or close.
- Remove the compliance check, or replace it with the SIA 2032 method for a whole building.
- Accept a material schedule exported from a BIM model.

## Code

| File | What it does |
|---|---|
| [`kbob_parser.py`](kbob_parser.py) | Reads the KBOB spreadsheet, writes the materials to JSON and builds the embeddings |
| [`query.py`](query.py) | Search, calculation, placeholder check and report |

To run it: `pip install -r requirements.txt`, put the KBOB spreadsheet at `data/kbob_v8.xlsx`, copy `.env.example` to `.env` and add an OpenAI API key, then run `python kbob_parser.py` and `python query.py`.

## Data

The values come from the KBOB life cycle data for the construction sector (Ökobilanzdaten im Baubereich), published by KBOB, ecobau and IPB. The data file is not included in this repository. Download it from the official source.

## Disclaimer

This is a learning prototype. It is not an approved tool for SIA 2032 or Minergie-ECO calculations and must not be used for project decisions.

Author: Abdul Rehman, [github.com/meet-rehman](https://github.com/meet-rehman)
