#!/usr/bin/env node
/**
 * Apify Actor Runner - Runs Apify actors and exports results.
 *
 * Usage:
 *   # Quick answer (display in chat, no file saved)
 *   node --env-file=.env scripts/run_actor.js --actor ACTOR_ID --input '{}' \
 *     --max-items "$MAX_ITEMS" --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD"
 *
 *   # Export to file
 *   node --env-file=.env scripts/run_actor.js --actor ACTOR_ID --input '{}' \
 *     --max-items "$MAX_ITEMS" --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \
 *     --output leads.csv --format csv
 */

import { parseArgs } from 'node:util';
import { readFileSync, statSync, writeFileSync } from 'node:fs';

// User-Agent for tracking skill usage in Apify analytics
const USER_AGENT = 'apify-agent-skills/apify-market-research-1.0.0';
const ACTOR_ID_PATTERN =
    /^(?:[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._-]*|[A-Za-z0-9]{17})$/u;
const OUTPUT_FORMATS = new Set(['csv', 'json']);

// Parse command-line arguments
function parseCliArgs() {
    const options = {
        actor: { type: 'string', short: 'a' },
        input: { type: 'string', short: 'i' },
        output: { type: 'string', short: 'o' },
        format: { type: 'string', short: 'f', default: 'csv' },
        timeout: { type: 'string', short: 't', default: '600' },
        'poll-interval': { type: 'string', default: '5' },
        'max-items': { type: 'string' },
        'max-total-charge-usd': { type: 'string' },
        help: { type: 'boolean', short: 'h' },
    };

    const { values } = parseArgs({ options, allowPositionals: false });

    if (values.help) {
        printHelp();
        process.exit(0);
    }

    if (!values.actor) {
        console.error('Error: --actor is required');
        printHelp();
        process.exit(1);
    }

    if (!values.input) {
        console.error('Error: --input is required');
        printHelp();
        process.exit(1);
    }

    if (!ACTOR_ID_PATTERN.test(values.actor)) {
        console.error('Error: --actor must be an owner/name or a 17-character Actor ID');
        process.exit(1);
    }

    if (!values['max-items']) {
        console.error('Error: --max-items is required');
        process.exit(1);
    }

    if (!values['max-total-charge-usd']) {
        console.error('Error: --max-total-charge-usd is required');
        process.exit(1);
    }

    const format = values.format || 'csv';
    if (!OUTPUT_FORMATS.has(format)) {
        console.error('Error: --format must be csv or json');
        process.exit(1);
    }

    return {
        actor: values.actor,
        input: values.input,
        output: values.output,
        format,
        timeout: parsePositiveInteger(values.timeout, '--timeout'),
        pollInterval: parsePositiveInteger(values['poll-interval'], '--poll-interval'),
        maxItems: parsePositiveInteger(values['max-items'], '--max-items'),
        maxTotalChargeUsd: parsePositiveNumber(
            values['max-total-charge-usd'],
            '--max-total-charge-usd',
        ),
    };
}

function parsePositiveInteger(value, option) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed <= 0) {
        console.error(`Error: ${option} must be a positive integer`);
        process.exit(1);
    }
    return parsed;
}

function parsePositiveNumber(value, option) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        console.error(`Error: ${option} must be a positive number`);
        process.exit(1);
    }
    return parsed;
}

function printHelp() {
    console.log(`
Apify Actor Runner - Run Apify actors and export results

Usage:
  node --env-file=.env scripts/run_actor.js --actor ACTOR_ID --input '{}' \\
    --max-items "$MAX_ITEMS" --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD"

Options:
  --actor, -a                 Actor ID (e.g., compass/crawler-google-places) [required]
  --input, -i                 Actor input as JSON string [required]
  --max-items                 Whole-run charged item cap [required]
  --max-total-charge-usd      Whole-run charge cap in USD [required]
  --output, -o                Output file path (optional - displays quick answer if omitted)
  --format, -f                Output format: csv, json (default: csv)
  --timeout, -t               Max wait time in seconds (default: 600)
  --poll-interval             Seconds between status checks (default: 5)
  --help, -h                  Show this help message

Output Formats:
  JSON (all data)     --output file.json --format json
  CSV (all data)      --output file.csv --format csv
  Quick answer        (no --output) - displays top 5 in chat

Examples:
  # Quick answer - display top 5 in chat
  node --env-file=.env scripts/run_actor.js \\
    --actor "compass/crawler-google-places" \\
    --input '{"searchStringsArray": ["coffee shops"], "locationQuery": "Seattle, USA"}' \\
    --max-items "$MAX_ITEMS" \\
    --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD"

  # Export all data to CSV
  node --env-file=.env scripts/run_actor.js \\
    --actor "compass/crawler-google-places" \\
    --input '{"searchStringsArray": ["coffee shops"], "locationQuery": "Seattle, USA"}' \\
    --max-items "$MAX_ITEMS" \\
    --max-total-charge-usd "$MAX_TOTAL_CHARGE_USD" \\
    --output leads.csv --format csv
`);
}

// Start an actor run and return { runId, datasetId }
async function startActor(token, actorId, inputJson, maxItems, maxTotalChargeUsd) {
    // Convert "author/actor" format to "author~actor" for API compatibility
    const apiActorId = actorId.replace('/', '~');
    const params = new URLSearchParams({
        maxItems: String(maxItems),
        maxTotalChargeUsd: String(maxTotalChargeUsd),
    });
    const url = `https://api.apify.com/v2/acts/${apiActorId}/runs?${params}`;

    let data;
    try {
        data = JSON.parse(inputJson);
    } catch (e) {
        console.error(`Error: Invalid JSON input: ${e.message}`);
        process.exit(1);
    }

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
            'User-Agent': `${USER_AGENT}/start_actor`,
        },
        body: JSON.stringify(data),
    });

    if (response.status === 404) {
        console.error(`Error: Actor '${actorId}' not found`);
        process.exit(1);
    }

    if (!response.ok) {
        const text = await response.text();
        console.error(`Error: API request failed (${response.status}): ${text}`);
        process.exit(1);
    }

    const result = await response.json();
    return {
        runId: result.data.id,
        datasetId: result.data.defaultDatasetId,
    };
}

// Poll run status until complete or timeout
async function pollUntilComplete(token, runId, timeout, interval) {
    const url = `https://api.apify.com/v2/actor-runs/${runId}`;
    const startTime = Date.now();
    let lastStatus = null;

    while (true) {
        const response = await fetch(url, {
            headers: {
                Authorization: `Bearer ${token}`,
                'User-Agent': `${USER_AGENT}/poll_run`,
            },
        });
        if (!response.ok) {
            const text = await response.text();
            console.error(`Error: Failed to get run status: ${text}`);
            process.exit(1);
        }

        const result = await response.json();
        const status = result.data.status;

        // Only print when status changes
        if (status !== lastStatus) {
            console.log(`Status: ${status}`);
            lastStatus = status;
        }

        if (['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'].includes(status)) {
            return status;
        }

        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed > timeout) {
            console.error(`Warning: Timeout after ${timeout}s, actor still running`);
            return 'TIMED-OUT';
        }

        await sleep(interval * 1000);
    }
}

// Download dataset items
async function downloadResults(token, datasetId, outputPath, format, maxItems) {
    const url = `https://api.apify.com/v2/datasets/${datasetId}/items?format=json&limit=${maxItems}`;

    const response = await fetch(url, {
        headers: {
            Authorization: `Bearer ${token}`,
            'User-Agent': `${USER_AGENT}/download_${format}`,
        },
    });

    if (!response.ok) {
        const text = await response.text();
        console.error(`Error: Failed to download results: ${text}`);
        process.exit(1);
    }

    const data = await response.json();

    if (format === 'json') {
        writeFileSync(outputPath, JSON.stringify(data, null, 2));
    } else {
        // CSV output
        if (data.length > 0) {
            const fieldnames = Object.keys(data[0]);
            const csvLines = [fieldnames.join(',')];

            for (const row of data) {
                const values = fieldnames.map((key) => {
                    let value = row[key];

                    // Truncate long text fields
                    if (typeof value === 'string' && value.length > 200) {
                        value = value.slice(0, 200) + '...';
                    } else if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
                        value = JSON.stringify(value) || '';
                    }

                    // CSV escape: wrap in quotes if contains comma, quote, or newline
                    if (value === null || value === undefined) {
                        return '';
                    }
                    const strValue = String(value);
                    if (strValue.includes(',') || strValue.includes('"') || strValue.includes('\n')) {
                        return `"${strValue.replace(/"/g, '""')}"`;
                    }
                    return strValue;
                });
                csvLines.push(values.join(','));
            }

            writeFileSync(outputPath, csvLines.join('\n'));
        } else {
            writeFileSync(outputPath, '');
        }
    }

    console.log(`Saved to: ${outputPath}`);
}

// Display top 5 results in chat format
async function displayQuickAnswer(token, datasetId, maxItems) {
    const url = `https://api.apify.com/v2/datasets/${datasetId}/items?format=json&limit=${maxItems}`;

    const response = await fetch(url, {
        headers: {
            Authorization: `Bearer ${token}`,
            'User-Agent': `${USER_AGENT}/quick_answer`,
        },
    });

    if (!response.ok) {
        const text = await response.text();
        console.error(`Error: Failed to download results: ${text}`);
        process.exit(1);
    }

    const data = await response.json();
    const total = data.length;

    if (total === 0) {
        console.log('\nNo results found.');
        return;
    }

    // Display top 5
    console.log(`\n${'='.repeat(60)}`);
    console.log(`TOP 5 RESULTS (of ${total} total)`);
    console.log('='.repeat(60));

    for (let i = 0; i < Math.min(5, data.length); i++) {
        const item = data[i];
        console.log(`\n--- Result ${i + 1} ---`);

        for (const [key, value] of Object.entries(item)) {
            let displayValue = value;

            // Truncate long values
            if (typeof value === 'string' && value.length > 100) {
                displayValue = value.slice(0, 100) + '...';
            } else if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
                const jsonStr = JSON.stringify(value);
                displayValue = jsonStr.length > 100 ? jsonStr.slice(0, 100) + '...' : jsonStr;
            }

            console.log(`  ${key}: ${displayValue}`);
        }
    }

    console.log(`\n${'='.repeat(60)}`);
    if (total > 5) {
        console.log(`Showing 5 of ${total} results.`);
    }
    console.log(`Full data available at: https://console.apify.com/storage/datasets/${datasetId}`);
    console.log('='.repeat(60));
}

// Report summary of downloaded data
function reportSummary(outputPath, format) {
    const stats = statSync(outputPath);
    const size = stats.size;

    let count;
    try {
        const content = readFileSync(outputPath, 'utf-8');
        if (format === 'json') {
            const data = JSON.parse(content);
            count = Array.isArray(data) ? data.length : 1;
        } else {
            // CSV - count lines minus header
            const lines = content.split('\n').filter((line) => line.trim());
            count = Math.max(0, lines.length - 1);
        }
    } catch {
        count = 'unknown';
    }

    console.log(`Records: ${count}`);
    console.log(`Size: ${size.toLocaleString()} bytes`);
}

// Helper: sleep for ms
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// Main function
async function main() {
    // Parse args first so --help works without token
    const args = parseCliArgs();

    // Check for APIFY_TOKEN
    const token = process.env.APIFY_TOKEN;
    if (!token) {
        console.error('Error: APIFY_TOKEN not found in .env file');
        console.error('');
        console.error('Add your token to .env file:');
        console.error('  APIFY_TOKEN=your_token_here');
        console.error('');
        console.error('Get your token: https://console.apify.com/account/integrations');
        process.exit(1);
    }

    // Start the actor run
    console.log(`Starting actor: ${args.actor}`);
    const { runId, datasetId } = await startActor(
        token,
        args.actor,
        args.input,
        args.maxItems,
        args.maxTotalChargeUsd,
    );
    console.log(`Run ID: ${runId}`);
    console.log(`Dataset ID: ${datasetId}`);

    // Poll for completion
    const status = await pollUntilComplete(token, runId, args.timeout, args.pollInterval);

    if (status !== 'SUCCEEDED') {
        console.error(`Error: Actor run ${status}`);
        console.error(`Details: https://console.apify.com/actors/runs/${runId}`);
        process.exit(1);
    }

    // Determine output mode
    if (args.output) {
        // File output mode
        await downloadResults(token, datasetId, args.output, args.format, args.maxItems);
        reportSummary(args.output, args.format);
    } else {
        // Quick answer mode - display in chat
        await displayQuickAnswer(token, datasetId, args.maxItems);
    }
}

main().catch((err) => {
    console.error(`Error: ${err.message}`);
    process.exit(1);
});
