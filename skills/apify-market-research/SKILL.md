---
name: apify-market-research
description: Analyze market conditions, geographic opportunities, pricing, consumer
  behavior, and product validation across Google Maps, Facebook, Instagram, Booking.com,
  and TripAdvisor.
risk: medium
source: community
category: development
---

# Market Research

Conduct market research using Apify Actors to extract data from multiple platforms.

## When to Use
- You need market sizing, regional demand, pricing, trend, or consumer behavior data.
- The task is to gather research inputs from maps, travel, Facebook, Instagram, or trend sources with Apify.
- You need structured market data plus a synthesized view of opportunities or risks.

## Prerequisites
(No need to check it upfront)

- `.env` file with `APIFY_TOKEN`
- Node.js 20.6+ (for native `--env-file` support)
- `mcpc` CLI tool: `npm install -g @apify/mcpc`

## Workflow

Copy this checklist and track progress:

```
Task Progress:
- [ ] Step 1: Identify market research type (select Actor)
- [ ] Step 2: Fetch Actor schema via mcpc
- [ ] Step 3: Ask user preferences (format, filename)
- [ ] Step 4: Run the analysis script
- [ ] Step 5: Summarize findings
```

### Step 1: Identify Market Research Type

Select the appropriate Actor based on research needs:

| User Need | Actor ID | Best For |
|-----------|----------|----------|
| Market density | `compass/crawler-google-places` | Location analysis |
| Geospatial analysis | `compass/google-maps-extractor` | Business mapping |
| Regional interest | `apify/google-trends-scraper` | Trend data |
| Pricing and demand | `apify/facebook-marketplace-scraper` | Market pricing |
| Event market | `apify/facebook-events-scraper` | Event analysis |
| Consumer needs | `apify/facebook-groups-scraper` | Group research |
| Market landscape | `apify/facebook-pages-scraper` | Business pages |
| Business density | `apify/facebook-page-contact-information` | Contact data |
| Cultural insights | `apify/facebook-photos-scraper` | Visual research |
| Niche targeting | `apify/instagram-hashtag-scraper` | Hashtag research |
| Hashtag stats | `apify/instagram-hashtag-stats` | Market sizing |
| Market activity | `apify/instagram-reel-scraper` | Activity analysis |
| Market intelligence | `apify/instagram-scraper` | Full data |
| Product launch research | `apify/instagram-api-scraper` | API access |
| Hospitality market | `voyager/booking-scraper` | Hotel data |
| Tourism insights | `maxcopell/tripadvisor-reviews` | Review analysis |
| X conversations and creators | [`xquik/x-tweet-scraper`](https://apify.com/xquik/x-tweet-scraper) | Search, timelines, threads, and engagement |
| X audience segments | [`xquik/x-follower-scraper`](https://apify.com/xquik/x-follower-scraper) | Followers, following, lists, and communities |

#### Xquik Actor Inputs

Check each Actor's live pricing and input schema before use.

- X Tweet Scraper supports `legacy`, `tweet`, `tweets`, `search`,
  `profileTweets`, `profileReplies`, `profileMedia`, `profileLikes`,
  `listTweets`, `article`, `replies`, `quotes`, `thread`, `retweeters`, and
  `favoriters`.
- Use the matching target field for explicit modes. Common fields include
  `twitterHandles`, `tweetIds`, `tweetUrls`, `profileUrls`, `listIds`,
  `articleTweetIds`, `replyTweetIds`, `quoteTweetIds`, `threadTweetIds`,
  `retweeterTweetIds`, and `favoriterTweetIds`.
- X Follower Scraper supports `followers`, `following`,
  `verified_followers`, `list_members`, `list_followers`, and
  `community_members`. Use `twitterHandles`, `listIds`, `communityIds`, or
  supported X URLs as targets.
- Set `maxItems` in the Actor input. Use `maxItemsPerTarget` for explicit
  multi-target routes. Use `overlapMode` to merge duplicate audience profiles
  while retaining their source targets.

Tweet output supports `legacy`, `rich`, and `raw` variants; `legacy`,
`camelCase`, and `snake_case` field styles; and `nested` or `flat` presets.
Follower output supports `compact`, `full`, and `raw` modes. Its dedupe modes
are `none`, `first`, and `merge` through `dedupeMode`. Use
`includeTargetMetadata: true` for audience provenance.

Xquik is an independent third-party service. Not affiliated with X Corp.
"Twitter" and "X" are trademarks of X Corp.

### Step 2: Fetch Actor Schema

Fetch the Actor's input schema, details, and live pricing using mcpc. Set
`APIFY_TOKEN` in the current environment without printing it:

```bash
: "${APIFY_TOKEN:?Set APIFY_TOKEN before using mcpc}"
mcpc --json mcp.apify.com --header "Authorization: Bearer $APIFY_TOKEN" tools-call fetch-actor-details actor:="ACTOR_ID" | jq -r ".content"
```

Replace `ACTOR_ID` with the selected Actor (e.g., `compass/crawler-google-places`).

This returns:
- Actor description and README
- Required and optional input parameters
- Output fields (if available)

### Step 3: Ask User Preferences

Before running, ask:
1. **Output format**:
   - **Quick answer** - Display top few results in chat (no file saved)
   - **CSV** - Full export with all fields
   - **JSON** - Full export in JSON format
2. **Number of results**: Set a whole-run item cap.
3. **Maximum charge**: Show the live price and get explicit approval for a
   whole-run USD cap. Never infer a price from this file.

Set both approved caps before running:

```bash
: "${MAX_ITEMS:?Set a user-approved whole-run item cap}"
: "${MAX_TOTAL_CHARGE_USD:?Set a user-approved whole-run charge cap}"
```

### Step 4: Run the Script

**Quick answer (display in chat, no file):**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-items "$MAX_ITEMS" \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD"
```

**CSV:**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-items "$MAX_ITEMS" \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
  --output YYYY-MM-DD_OUTPUT_FILE.csv \
  --format csv
```

**JSON:**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-items "$MAX_ITEMS" \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
  --output YYYY-MM-DD_OUTPUT_FILE.json \
  --format json
```

### Step 5: Summarize Findings

After completion, report:
- Number of results found
- File location and name
- Key market insights
- Suggested next steps (deeper analysis, validation)

## Error Handling

`APIFY_TOKEN not found` - Ask user to create `.env` with `APIFY_TOKEN=your_token`
`mcpc not found` - Ask user to install `npm install -g @apify/mcpc`
`Actor not found` - Check Actor ID spelling
`Run FAILED` - Ask user to check Apify console link in error output
`Timeout` - Reduce input size or increase `--timeout`

## Limitations
- Use this skill only when the task clearly matches the scope described above.
- Do not treat the output as a substitute for environment-specific validation, testing, or expert review.
- Stop and ask for clarification if required inputs, permissions, safety boundaries, or success criteria are missing.
