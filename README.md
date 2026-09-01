# vela-listing-builder

Turns a structured product definition into a correctly-formed Etsy bulk-listing
CSV, with variations, ordered photos and mapped videos.

```
$ python -m builders.build_listings --products products.yaml --config config.yaml

Building 2 listing(s) at multiplier 1.60

=== Build summary ===
SKU                     vars photos      base     final video
PROD-001                   5      4     15.00     24.00     -
PROD-002                   0      1     20.00     32.00   yes

2 listings, 5 variation rows.

6 rows -> vela_import.csv
1 Vela Profile(s) to apply by hand -> post_import_todo.md
```

## The problem

Etsy has **no native bulk import for new listings**, so a catalogue build goes
through Vela's CSV. In the motivating case that meant 208 listings, most with
two variation axes, one product carrying 64 variation combinations, and 50+
videos needing mapping to the right listings.

Almost all the difficulty is in two places, and both fail *silently* when wrong:
the variation row layout and the photo ordering. A malformed file does not error
— it imports, and you find out later.

## The four rules that break imports

Enforced in code rather than documented, because every caller trusted to get
them right has eventually got one wrong:

1. **The first variation is embedded in the parent row**, not written as its own
   row. A parent plus N variation rows produces N+1 variations on Etsy, and the
   phantom extra carries the parent's own values.
2. **Every child row repeats both axis label fields.** Leaving them blank on
   child rows fails the import.
3. **Parent rows have every `Var*` field explicitly written**, empty where they
   should be empty. Building rows by mutating one shared dict lets stale values
   from the previous listing leak into the next parent — producing a file that
   looks valid and imports the wrong data, which is the worst combination
   available. There is a test named for exactly this.
4. **`Var Visibility` is the literal string `On`.** Not `show`, not `TRUE`,
   not `1`.

### And the photo column trap

Etsy's own *export* names image columns `IMAGE1…IMAGE10`. Vela's *import*
expects `Photo 1…Photo 10`. Feed Vela a file with the wrong spelling and **the
import succeeds with zero photos attached** — no error, no warning, a catalogue
of listings with no pictures. All three spellings are accepted on the way in,
and coverage below 95% triggers a loud warning.

## Photo order is a merchandising decision

Not alphabetical, not arbitrary. The layout lives in config:

```
slot 1      AI-rendered scene shot
slots 2-3   original photos 1-2
slots 4-6   infographics
slots 7-9   original photos 3-5
slot 10     original cover photo
```

A listing without infographics **collapses the gap** rather than leaving empty
slots — Etsy renders an empty slot as a missing image, not a skipped one. That
behaviour falls out of building the list by appending rather than assigning to
fixed indices.

Anything supplied that does not fit is **counted and reported**, never silently
discarded.

> One deliberate deviation from the written spec: it described the fourth block
> as "slots 7–9, original photos 3–6" — three slots for four photos, summing to
> eleven against Etsy's hard limit of ten. Three wins, because the alternative
> silently pushes the cover shot off the end. The sixth original is reported as
> dropped.

## Combination counts explode

Two axes multiply fast. One real listing reached **88 combinations** before being
trimmed to 64 by removing an outlier quantity tier and three low-demand colour
pairings.

So trimming is **declared in the input** as an `exclude` list, never done by hand
in the CSV afterwards. A hand-edited CSV cannot be rebuilt, and every rebuild
silently reintroduces what was trimmed. Listings above a configurable ceiling
warn.

## Video mapping

Videos arrive in a shared cloud folder with filenames matching nothing. Each is
mapped to the listing whose photos were **captured nearest in time**, using EXIF
capture time where available and file mtime otherwise. EXIF first because a file
copied through a cloud folder loses its mtime but keeps the time the shutter
fired.

Session-level guessing — "these were all shot the same day, so distribute them
across that day's listings" — produces wrong assignments and is explicitly
rejected. A day holds many listings; nearness *within* the day is the entire
signal, and averaging it away discards it.

Where two listings are close enough that the answer is genuinely ambiguous, the
video goes to a **review file with its candidates** rather than being assigned.
A wrong video is a product page showing a different product, and nobody checks.

**A Google Drive trap, encoded as a check.** Searching with
`parentId = '<folderID>'` returns **empty results** for folders owned by an
external account, even when the folder is plainly visible via
`sharedWithMe = true`. A zero-result query therefore has two very different
causes, and the tool names the likely one instead of reporting "no files found"
and sending you looking for a bug that is not there.

## Usage

```bash
pip install -r requirements.txt
python -m pytest                      # 79 tests
```

```bash
python -m builders.build_listings --products products.yaml --config config.yaml
python -m builders.build_listings --products products.yaml --only PROD-001,PROD-002
python -m builders.build_listings --products products.yaml --videos-dir ./videos
```

**Build two listings and import them before running the full set.** `--only` is
what makes the small version one flag rather than a hand-edited input file.
Every full rebuild that fails costs a re-import cycle.

### Input

```yaml
- sku: PROD-VAR-001
  title: Ancient Stone Golem
  description: A heavy hitter for any table.
  base_price: 15.00
  quantity: "100"
  tags: [fantasy, golem, terrain]
  axis_1: {type: Size, name: Size, values: [S, M, L]}
  axis_2: {type: Colour, name: Edge colour, values: [Red, Gold]}
  exclude: [[L, Gold]]           # declared here, never edited into the CSV
  photos:
    ai_scene: [scene.jpg]
    originals: [o1.jpg, o2.jpg, o3.jpg]
    infographics: [i1.jpg]
  profiles: [Name to write]      # applied by hand after import
```

Pricing applies a fixed multiplier from config in **one place**, and the build
summary prints base and final side by side so the arithmetic is auditable.

## Output

`vela_import.csv`, plus `post_import_todo.md`.

Custom buyer-input option lists — name-to-write fields, font and colour pickers
— **cannot be set through Vela's CSV at all**. They are applied afterwards via
Vela Profiles. Rather than dropping that silently, the TODO names which listings
need which profile, **grouped by profile**: the real workflow is to search the
listing set for one shared keyword and bulk-apply, so the useful unit is the
profile, not the product.

## Notes and limitations

**Provenance.** This ran in production, building a 208-listing Etsy catalogue
with two variation axes and 64 combinations on its largest product. That source
was lost and this repository is a rebuild from the specification those runs
produced — so the rules are proven and paid for, while the rebuilt code is
verified by its 79 tests rather than re-run against a live Vela import. Build
two listings first; that is the discipline the original runs taught anyway.

**Verified end to end on a written file**, not only in unit tests: a two-axis
listing with one excluded pair produced 5 variation rows rather than 6, both
axis labels repeated on every child row, `Var Visibility = On`, and the
following plain listing free of any leaked variation data.

**`common/` is vendored.** These modules also live in a broader toolkit repo,
duplicated deliberately so this one stands alone.

**Videos are mapped, not uploaded.** Vela's CSV does not carry video the way it
carries image URLs.

## Licence

MIT — see [LICENSE](LICENSE).
