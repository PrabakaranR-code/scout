"""PubMed biomedical literature via the official, keyless NCBI E-utilities.

Two calls per search (esearch for IDs, esummary for metadata), both inside
this adapter's single fan-out slot. NCBI allows up to 3 requests/second
without a key; SCOUT stays well under that.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import quote_plus

import httpx

from scout.adapters.base import BaseAdapter
from scout.schema import SearchResult

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedAdapter(BaseAdapter):
    name: ClassVar[str] = "pubmed"
    category = "science"
    rate_limit: ClassVar[float] = 1.0
    timeout: ClassVar[float] = 10.0

    async def fetch(self, client: httpx.AsyncClient, query: str, limit: int) -> Any:
        search_url = (
            f"{_EUTILS}/esearch.fcgi?db=pubmed&term={quote_plus(query)}"
            f"&retmax={min(limit, 30)}&retmode=json&sort=relevance"
        )
        esearch = (await self.get(client, search_url)).json()
        ids = (
            esearch.get("esearchresult", {}).get("idlist", [])
            if isinstance(esearch, dict)
            else []
        )
        ids = [str(i) for i in ids if str(i).isdigit()]
        if not ids:
            return {"esummary": None}
        summary_url = (
            f"{_EUTILS}/esummary.fcgi?db=pubmed&id={','.join(ids)}&retmode=json"
        )
        return {"esummary": (await self.get(client, summary_url)).json(), "ids": ids}

    def parse(self, raw: Any, query: str, limit: int) -> list[SearchResult]:
        if not isinstance(raw, dict):
            return []
        summary = raw.get("esummary")
        if not isinstance(summary, dict):
            return []
        records = summary.get("result")
        if not isinstance(records, dict):
            return []
        ordered_ids = raw.get("ids") or records.get("uids") or []
        results: list[SearchResult] = []
        for uid in ordered_ids:
            record = records.get(str(uid))
            if not isinstance(record, dict):
                continue
            title = str(record.get("title") or "").strip()
            if not title:
                continue
            journal = str(record.get("fulljournalname") or record.get("source") or "")
            pubdate = str(record.get("pubdate") or "")
            published: datetime | None = None
            try:
                published = datetime.strptime(pubdate[:11].strip(), "%Y %b %d")
            except ValueError:
                try:
                    published = datetime.strptime(pubdate[:4], "%Y")
                except ValueError:
                    published = None
            snippet = "; ".join(part for part in (journal, pubdate) if part)
            results.append(
                self.make_result(
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                    snippet=snippet,
                    published=published,
                    raw_rank=len(results) + 1,
                )
            )
        return results
