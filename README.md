# Rift Draft v18 — Rank-aware draft analysis

This is an update to the **Rift-Draft-v2** public GitHub Pages application. It adds a rank-bracket dropdown, per-rank role dataset loading, source diagnostics, explicit abstention when rank data is missing, and an **optional** first-party Riot Games API collector.

## What is supported now

- The original 26.22 snapshot and 20-patch historical data work unchanged in **Baseline · rank not specified** mode.
- Searchable rank selector: Gold+, Platinum+, Emerald+, Diamond+, Master+.
- If rank-specific data is published for a role, that role uses *only the selected bracket's own stats*; baseline data is **not** silently substituted. Selected-bracket matchup data overrides baseline and is appropriately sample-shrunk.
- The badge beside the selector shows sample region, patch, sampled match count, and caveat; Data health displays rank/role coverage.
- Champions with too few rank-sample games are **UNRATED**. Baseline win rates, rank sample estimates, and historical data cannot be accidentally mixed.
- The companion official Riot collector requires an `RIOT_API_KEY` secret and outputs just aggregated champion statistics, not PUUIDs or match IDs.

## Important: rank brackets are not pre-populated

We investigated current sources. The existing `shizukaziye/lol-pool-coverage` publication contains single-patch and historical *role*-specific data, but no explicit player-rank bracket. We found live third-party services with tier-specific results, yet not a complete, clearly licensed, directly downloadable tier/role/champion matchup dataset that we could safely bundle. The private Lolalytics API explicitly prohibits third-party reuse. Therefore this package does **not** invent any rank-specific win rates.

The included collector uses Riot's official League-V4 and Match-V5 endpoints, and requires a **Riot production API key for a publicly deployed app**. Development keys last only 24 hours; personal keys are not authorized for public products. The collector samples from players who *currently* belong to each tier; games are bucketed by sampled player's tier, **not** by independently verified ranks of all ten players. This is a noisy rank-anchored cohort proxy, **not** a full-lobby MMR/rank dataset. Publish only if you accept that limitation. It currently runs for NA1; its `--platform` option supports other supported Riot platforms.

The GitHub workflow attempts a small scheduled collection when an API secret is configured. At default limits (`--max-requests 600`, eight seed players per tier, four matches each), it is a *pilot*, not a statistically complete sample. Small or missing samples result in UNRATED picks. To obtain reliable coverage across 173 champions and five roles you will need a substantial authorized, deduplicated data pipeline and possibly production-scale API access.

## Updating the existing website

Replace these files in your `RiftZealot/Rift-Draft-v2` GitHub repository, preserving their paths:

1. `site/index.html`
2. `.github/workflows/deploy.yml`
3. Add new `scripts/collect_ranked.py`

The existing `scripts/sync_data.py` can stay exactly as it is. Commit the edits to `main`; check **Actions → Publish Rift Draft and refresh stats**. After the workflow succeeds, your existing URL remains `https://riftzealot.github.io/Rift-Draft-v2/`.

If you have *approved* Riot production API access, add `RIOT_API_KEY` at **Repository Settings → Secrets and variables → Actions → New repository secret**. **Never put the key in an HTML file, commit, or chat.** The workflow uses the secret server-side. If you do not have a key, the website still runs in baseline mode, and clearly tells visitors when a rank bracket lacks data.

If an API run fails or the provider rate-limits it, the deploy job fails and your **previous successful GitHub Pages version remains online**. Inspect its Actions logs; avoid pretending an incomplete dataset is current. Never expose the secret in logs.

### Optional own pre-aggregated datasets

If you acquire a rank-labeled dataset from a provider with redistribution permission, transform it to the public JSON schema and host it at `site/data/ranks/<bracket>/<role>.json`, including `rank_bracket`, `patch`, `lane`, `tierlist` keyed by numeric champion ID, `matchups` keyed by champion/opposing role/opponent, observed game counts, `sample_matches`, rank definition, region, and source. Set `manifest.ranks[bracket][role]` with verified `available`, `patch` and `sample_matches`. The front end only uses rank-specific files with a matching current patch. The **Import missing JSON** control also understands rank-labeled JSON for the current browser session.

## Testing

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
node tests/js_logic_smoke.js
```

The Python tests cover patch rejection, complete match composition, no duplicate matches, bracket aggregation, and rank publication. The JS test covers baseline picks, an unavailable rank bracket, a loaded rank bracket changing the recommendation, and blind-risk conditionality. All tests use **explicit synthetic fixtures**, never represented as actual player observations.

## Sources and licensing

- Riot Developer Portal and production API access: https://developer.riotgames.com/docs/portal
- Current default data provider (no declared rank bracket): https://github.com/shizukaziye/lol-pool-coverage
- Lolalytics private API restrictions: https://a3.lolalytics.com/

Independent tool; not endorsed by Riot Games. Read Riot's policies before public monetization. Commercial use and redistribution of third-party datasets require separate permission.
