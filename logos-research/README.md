# Logos Research Agent

> **Autonomous research monitoring for the Logos project**

This agent continuously monitors arXiv, GitHub, and industry sources for research relevant to Logos (Recurrent-Depth Transformer with LTI-stable injection, MoE, MLA, and ACT).

## Quick Start

### Run Once
```bash
cd /Users/ohmskiii/Documents/GitHub/logos/.vibe/skills/logos-research
python monitoring.py
```

### Run Continuously (Daemon Mode)
```bash
python monitoring.py --daemon
```

### Installation
```bash
pip install arxiv requests PyGithub feedparser
```

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Agent definition and instructions |
| `monitoring.py` | Main monitoring pipeline |
| `config.toml` | Configuration settings |
| `keywords.txt` | Search keywords for all sources |
| `digests/` | Daily research digests (auto-created) |

## Agent Capabilities

### Monitoring Sources
- **ArXiv**: New papers matching RDT, LTI-stable, MoE, MLA, ACT keywords
- **GitHub**: New repositories with relevant implementations
- **RSS Feeds**: Industry news from MarkTechPost, EmergentMind

### Relevance Classification
- **Critical**: All 5 key features (RDT + LTI-stable + MoE + MLA + ACT)
- **High**: 3-4 key features
- **Medium**: 2 key features
- **Low**: 1 key feature (filtered out)

### Output
- Daily markdown digests in `digests/` directory
- JSON version for programmatic access
- Critical findings highlighted for immediate attention

## Integration with Logos

The agent is configured to:
1. Monitor the research landscape
2. Generate actionable insights
3. Avoid duplicates with tracking files
4. Store outputs in the Logos project structure

### Directory Structure
```
logos/
└── .vibe/
    └── skills/
        └── logos-research/
            ├── SKILL.md          # Agent definition
            ├── config.toml      # Configuration
            ├── keywords.txt     # Search terms
            ├── monitoring.py    # Pipeline
            └── digests/          # Output
                └── 2026-05-05.md
```

## Configuration

Edit `config.toml` to customize:
- Monitoring frequency
- Keywords and queries
- Output paths
- API keys (arXiv, GitHub)
- Integration settings (auto-PR, webhooks)

## Keywords

### Primary Focus
- Recurrent-Depth Transformer (RDT)
- LTI-stable injection
- Mixture-of-Experts (MoE)
- Multi-Latent Attention (MLA)
- Adaptive Computation Time (ACT)

### Secondary Focus
- Grouped Query Attention (GQA)
- RetNet / Retentive Networks
- State Space Models (SSM)
- Long Context Methods
- Training Stability

See `keywords.txt` for full list.

## Usage Examples

### Manual Run
```bash
# From Logos project root
python .vibe/skills/logos-research/monitoring.py
```

### Scheduled Run (Cron)
```bash
# Add to crontab
0 3 * * * cd /Users/ohmskiii/Documents/GitHub/logos && python .vibe/skills/logos-research/monitoring.py >> .vibe/skills/logos-research/monitor.log 2>&1
```

### Docker (Optional)
```dockerfile
FROM python:3.11-slim
RUN pip install arxiv requests PyGithub feedparser
COPY .vibe/skills/logos-research /app
WORKDIR /app
CMD ["python", "monitoring.py", "--daemon"]
```

## Dependencies

- Python 3.10+
- `arxiv` - arXiv API client
- `requests` - HTTP requests
- `PyGithub` - GitHub API client
- `feedparser` - RSS feed parsing

Install all:
```bash
pip install arxiv requests PyGithub feedparser
```

## Output Format

### Daily Digest (Markdown)
```markdown
# Logos Research Digest - 2026-05-05

## New Papers
- [Paper Title](https://arxiv.org/abs/...) | arXiv | Relevance: HIGH
  - Summary: ...
  - Action: Review for Logos integration

## New Repositories
- [repo-name](https://github.com/...) | GitHub | Relevance: CRITICAL
  - Summary: ...
  - Action: Star and review

## Industry Updates
- [Article Title](https://...) | MarkTechPost | Relevance: MEDIUM
  - Summary: ...
  - Action: Read and extract insights
```

### JSON Output
```json
{
  "date": "2026-05-05",
  "papers": [...],
  "repositories": [...],
  "industry": [...]
}
```

## License

MIT License - see main Logos project for details.

## Support

For issues or questions, refer to the main Logos project documentation.
