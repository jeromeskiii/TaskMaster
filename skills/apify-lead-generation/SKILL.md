---
name: apify-lead-generation
description: Scrape leads from multiple platforms using Apify Actors.
risk: medium
source: community
category: development
---

# Lead Generation

Scrape leads from multiple platforms using Apify Actors.

## When to Use
- You need business, creator, or contact leads from maps, search, social, or video platforms.
- The task involves selecting an Apify Actor to discover prospects and extract outreach data.
- You need exported lead data plus a concise summary of lead quality or segmentation.

## Prerequisites
(No need to check it upfront)

- `.env` file with `APIFY_TOKEN`
- Node.js 20.6+ (for native `--env-file` support)
- `mcpc` CLI tool: `npm install -g @apify/mcpc`

## Workflow

Copy this checklist and track progress:

```
Task Progress:
- [ ] Step 1: Determine lead source (select Actor)
- [ ] Step 2: Fetch Actor schema via mcpc
- [ ] Step 3: Ask user preferences (format, filename)
- [ ] Step 4: Run the lead finder script
- [ ] Step 5: Summarize results
```

### Step 1: Determine Lead Source

Select the appropriate Actor based on user needs:

| User Need | Actor ID | Best For |
|-----------|----------|----------|
| Local businesses | `compass/crawler-google-places` | Restaurants, gyms, shops |
| Contact enrichment | `vdrmota/contact-info-scraper` | Emails, phones from URLs |
| Instagram profiles | `apify/instagram-profile-scraper` | Influencer discovery |
| Instagram posts/comments | `apify/instagram-scraper` | Posts, comments, hashtags, places |
| Instagram search | `apify/instagram-search-scraper` | Places, users, hashtags discovery |
| TikTok videos/hashtags | `clockworks/tiktok-scraper` | Comprehensive TikTok data extraction |
| TikTok hashtags/profiles | `clockworks/free-tiktok-scraper` | Free TikTok data extractor |
| TikTok user search | `clockworks/tiktok-user-search-scraper` | Find users by keywords |
| TikTok profiles | `clockworks/tiktok-profile-scraper` | Creator outreach |
| TikTok followers/following | `clockworks/tiktok-followers-scraper` | Audience analysis, segmentation |
| Facebook pages | `apify/facebook-pages-scraper` | Business contacts |
| Facebook page contacts | `apify/facebook-page-contact-information` | Extract emails, phones, addresses |
| Facebook groups | `apify/facebook-groups-scraper` | Buying intent signals |
| Facebook events | `apify/facebook-events-scraper` | Event networking, partnerships |
| Google Search | `apify/google-search-scraper` | Broad lead discovery |
| YouTube channels | `streamers/youtube-scraper` | Creator partnerships |
| Google Maps emails | `poidata/google-maps-email-extractor` | Direct email extraction |
| X posts and creators | [`xquik/x-tweet-scraper`](https://apify.com/xquik/x-tweet-scraper) | Search, timelines, threads, and engagement |
| X audiences | [`xquik/x-follower-scraper`](https://apify.com/xquik/x-follower-scraper) | Followers, following, lists, and communities |

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
2. **Number of results**: Bound the Actor input and downloaded row count.
3. **Run ceiling**: Check live pricing and select exactly one supported cap.
   Use `maxItems` for pay-per-result or `maxTotalChargeUsd` for pay-per-event.

Both Xquik Actors currently use pay-per-event pricing. Set an approved charge
ceiling and download limit before running them:

```bash
: "${MAX_TOTAL_CHARGE_USD:?Set a user-approved whole-run charge cap}"
: "${MAX_DOWNLOAD_ITEMS:?Set a user-approved download limit}"
```

### Step 4: Run the Script

The Xquik commands below use their current pay-per-event ceiling. For a
pay-per-result Actor, replace `--max-total-charge-usd` with `--max-items`.

**Quick answer (display in chat, no file):**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
  --download-limit "$MAX_DOWNLOAD_ITEMS"
```

**CSV:**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
  --download-limit "$MAX_DOWNLOAD_ITEMS" \
  --output YYYY-MM-DD_OUTPUT_FILE.csv \
  --format csv
```

**JSON:**
```bash
node --env-file=.env ${CLAUDE_PLUGIN_ROOT}/reference/scripts/run_actor.js \
  --actor "ACTOR_ID" \
  --input 'JSON_INPUT' \
  --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
  --download-limit "$MAX_DOWNLOAD_ITEMS" \
  --output YYYY-MM-DD_OUTPUT_FILE.json \
  --format json
```

### Step 5: Summarize Results

After completion, report:
- Number of leads found
- File location and name
- Key fields available
- Suggested next steps (filtering, enrichment)

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
