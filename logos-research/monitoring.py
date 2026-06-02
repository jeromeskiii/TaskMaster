#!/usr/bin/env python3
"""
Logos Research Monitoring Pipeline

Autonomously monitors arXiv, GitHub, and industry sources for research 
relevant to the Logos project (Recurrent-Depth Transformer).

Usage:
    python monitoring.py              # Run once
    python monitoring.py --daemon    # Run continuously (every 24h)
    python monitoring.py --digest    # Generate digest only
"""

import sys
import os
import json
import time
import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import arxiv
    import requests
    import feedparser
    from github import Github
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class Relevance(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ResearchItem:
    """A single research finding."""
    title: str
    url: str
    source: str
    relevance: Relevance
    date: str
    summary: str
    action: str
    keywords: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_markdown(self) -> str:
        return f"- [{self.title}]({self.url}) | {self.source} | Relevance: {self.relevance.value.upper()}\n  - Summary: {self.summary}\n  - Action: {self.action}\n"


@dataclass
class Digest:
    """Daily research digest."""
    date: str
    papers: List[ResearchItem]
    repositories: List[ResearchItem]
    industry: List[ResearchItem]
    
    def to_markdown(self) -> str:
        md = f"# Logos Research Digest - {self.date}\n\n"
        
        if self.papers:
            md += "## New Papers\n"
            for item in self.papers:
                md += item.to_markdown()
            md += "\n"
        
        if self.repositories:
            md += "## New Repositories\n"
            for item in self.repositories:
                md += item.to_markdown()
            md += "\n"
        
        if self.industry:
            md += "## Industry Updates\n"
            for item in self.industry:
                md += item.to_markdown()
            md += "\n"
        
        if not self.papers and not self.repositories and not self.industry:
            md += "No new findings today.\n"
        
        return md


class LogosMonitor:
    """Main monitoring class."""
    
    ARXIV_QUERY = [
        "recurrent depth transformer",
        "looped transformer",
        "RDT transformer",
        "LTI stable transformer",
        "spectral radius transformer",
        "mixture of experts transformer",
        "multi-latent attention",
        "MLA attention",
        "adaptive computation time",
        "ACT halting transformer",
    ]
    
    GITHUB_QUERY = [
        "recurrent-depth",
        "looped-transformer", 
        "RDT",
        "LTI-stable",
        "spectral-radius",
        "mixture-of-experts",
        "multi-latent-attention",
        "adaptive-computation",
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.base_path = Path(self.config.get('base_path', '/Users/ohmskiii/Documents/GitHub/logos'))
        self.skills_path = self.base_path / '.vibe' / 'skills' / 'logos-research'
        self.digests_path = self.skills_path / 'digests'
        self.papers_path = self.base_path / 'research' / 'papers'
        self.repos_path = self.base_path / 'research' / 'repos'
        
        # Ensure directories exist
        self.digests_path.mkdir(parents=True, exist_ok=True)
        self.papers_path.mkdir(parents=True, exist_ok=True)
        self.repos_path.mkdir(parents=True, exist_ok=True)
        
        # Tracked items (to avoid duplicates)
        self.tracked_papers = self._load_tracked('papers')
        self.tracked_repos = self._load_tracked('repos')
    
    def _load_config(self, path: Optional[str]) -> Dict:
        """Load configuration from file."""
        config_path = Path(path) if path else self.skills_path / 'config.toml'
        config = {}
        if config_path.exists():
            # Simple TOML parsing (for basic configs)
            with open(config_path) as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, val = line.split('=', 1)
                        config[key.strip()] = val.strip().strip('"').strip("'")
        return config
    
    def _load_tracked(self, category: str) -> set:
        """Load tracked items to avoid duplicates."""
        tracked_file = self.papers_path if category == 'papers' else self.repos_path
        tracked_file = tracked_file.with_suffix('.json')
        if tracked_file.exists():
            with open(tracked_file) as f:
                return set(json.load(f).get('items', []))
        return set()
    
    def _save_tracked(self, category: str, items: set):
        """Save tracked items."""
        tracked_file = self.papers_path if category == 'papers' else self.repos_path
        tracked_file = tracked_file.with_suffix('.json')
        with open(tracked_file, 'w') as f:
            json.dump({'items': list(items)}, f, indent=2)
    
    def _classify_relevance(self, title: str, summary: str) -> Relevance:
        """Classify item relevance based on keywords."""
        title_lower = title.lower()
        summary_lower = summary.lower()
        combined = f"{title_lower} {summary_lower}"
        
        # Count matching keywords
        score = 0
        keyword_sets = [
            ['recurrent', 'depth', 'transformer', 'rdt'],
            ['looped', 'transformer'],
            ['lti', 'stable', 'injection', 'spectral', 'radius'],
            ['mixture', 'experts', 'moe'],
            ['multi', 'latent', 'attention', 'mla'],
            ['adaptive', 'computation', 'time', 'act', 'halting'],
        ]
        
        for keywords in keyword_sets:
            if any(kw in combined for kw in keywords):
                score += 1
        
        if score >= 4:
            return Relevance.CRITICAL
        elif score >= 3:
            return Relevance.HIGH
        elif score >= 2:
            return Relevance.MEDIUM
        else:
            return Relevance.LOW
    
    def _extract_arxiv_papers(self) -> List[ResearchItem]:
        """Extract relevant papers from arXiv."""
        if not HAS_DEPS:
            return []
        
        items = []
        for query in self.ARXIV_QUERY:
            try:
                search = arxiv.Search(
                    query=query,
                    max_results=10,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )
                
                for result in search.results():
                    paper_id = result.entry_id.split('/')[-1]
                    if paper_id in self.tracked_papers:
                        continue
                    
                    relevance = self._classify_relevance(
                        result.title,
                        result.summary.replace('\n', ' ') if result.summary else ''
                    )
                    
                    # Only keep medium+ relevance
                    if relevance in [Relevance.CRITICAL, Relevance.HIGH, Relevance.MEDIUM]:
                        item = ResearchItem(
                            title=result.title,
                            url=result.entry_id,
                            source='arXiv',
                            relevance=relevance,
                            date=result.published.strftime('%Y-%m-%d'),
                            summary=result.summary.replace('\n', ' ')[:200] + '...' if result.summary else 'No summary',
                            action='Review for Logos integration',
                            keywords=[query]
                        )
                        items.append(item)
                        self.tracked_papers.add(paper_id)
                        
            except Exception as e:
                print(f"Error searching arXiv for '{query}': {e}")
        
        self._save_tracked('papers', self.tracked_papers)
        return items
    
    def _extract_github_repos(self) -> List[ResearchItem]:
        """Extract relevant repositories from GitHub."""
        if not HAS_DEPS:
            return []
        
        items = []
        try:
            g = Github()  # Uses GITHUB_TOKEN env var if available
            
            for query in self.GITHUB_QUERY:
                repos = g.search_repositories(query=query, sort='updated', order='desc')
                
                for repo in repos[:10]:
                    repo_id = f"{repo.owner.login}/{repo.name}"
                    if repo_id in self.tracked_repos:
                        continue
                    
                    relevance = self._classify_relevance(
                        repo.name + ' ' + (repo.description or ''),
                        repo.description or ''
                    )
                    
                    if relevance in [Relevance.CRITICAL, Relevance.HIGH, Relevance.MEDIUM]:
                        item = ResearchItem(
                            title=repo.name,
                            url=repo.html_url,
                            source='GitHub',
                            relevance=relevance,
                            date=repo.updated_at.strftime('%Y-%m-%d'),
                            summary=repo.description or 'No description',
                            action=f'Star and review at {repo.html_url}',
                            keywords=[query]
                        )
                        items.append(item)
                        self.tracked_repos.add(repo_id)
                        
        except Exception as e:
            print(f"Error searching GitHub: {e}")
        
        self._save_tracked('repos', self.tracked_repos)
        return items
    
    def _extract_industry_news(self) -> List[ResearchItem]:
        """Extract relevant industry news."""
        # RSS feeds to monitor
        feeds = [
            'https://marktechpost.com/feed/',
            'https://www.emergentmind.com/feed/',
        ]
        
        items = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.get('title', 'No title')
                    url = entry.get('link', '#')
                    published = entry.get('published', '')
                    
                    # Check relevance
                    relevance = self._classify_relevance(
                        title,
                        entry.get('summary', '')[:200]
                    )
                    
                    if relevance in [Relevance.CRITICAL, Relevance.HIGH, Relevance.MEDIUM]:
                        item = ResearchItem(
                            title=title,
                            url=url,
                            source=feed_url,
                            relevance=relevance,
                            date=published[:10] if published else '',
                            summary=entry.get('summary', '')[:200] + '...',
                            action='Read and extract insights',
                            keywords=[]
                        )
                        items.append(item)
                        
            except Exception as e:
                print(f"Error parsing feed {feed_url}: {e}")
        
        return items
    
    def generate_digest(self) -> Digest:
        """Generate a research digest."""
        papers = self._extract_arxiv_papers()
        repos = self._extract_github_repos()
        industry = self._extract_industry_news()
        
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        return Digest(date=date, papers=papers, repositories=repos, industry=industry)
    
    def save_digest(self, digest: Digest):
        """Save digest to file."""
        # Markdown version
        md_path = self.digests_path / f"{digest.date}.md"
        with open(md_path, 'w') as f:
            f.write(digest.to_markdown())
        
        # JSON version
        json_path = self.digests_path / f"{digest.date}.json"
        with open(json_path, 'w') as f:
            json.dump({
                'date': digest.date,
                'papers': [p.to_dict() for p in digest.papers],
                'repositories': [r.to_dict() for r in digest.repositories],
                'industry': [i.to_dict() for i in digest.industry]
            }, f, indent=2)
        
        print(f"✅ Digest saved: {md_path}")
    
    def run(self, daemon: bool = False):
        """Run monitoring pipeline."""
        print("🔍 Starting Logos research monitoring...")
        
        digest = self.generate_digest()
        
        # Print summary
        total = len(digest.papers) + len(digest.repositories) + len(digest.industry)
        print(f"📊 Found {total} items:")
        print(f"   - {len(digest.papers)} papers")
        print(f"   - {len(digest.repositories)} repositories")
        print(f"   - {len(digest.industry)} industry updates")
        
        # Critical items get immediate attention
        critical = [p for p in digest.papers if p.relevance == Relevance.CRITICAL]
        critical += [r for r in digest.repositories if r.relevance == Relevance.CRITICAL]
        critical += [i for i in digest.industry if i.relevance == Relevance.CRITICAL]
        
        if critical:
            print(f"\n⚠️  CRITICAL FINDINGS ({len(critical)}):")
            for item in critical:
                print(f"   - {item.title} ({item.source})")
        
        if total > 0:
            self.save_digest(digest)
        else:
            print("✅ No new findings today.")
        
        if daemon:
            print("\n⏳ Sleeping for 24 hours...")
            time.sleep(24 * 60 * 60)
            self.run(daemon=True)


def main():
    daemon = '--daemon' in sys.argv
    
    monitor = LogosMonitor()
    monitor.run(daemon=daemon)


if __name__ == '__main__':
    main()
