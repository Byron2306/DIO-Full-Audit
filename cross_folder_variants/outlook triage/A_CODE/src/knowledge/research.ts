import { Page } from "playwright";

export interface Paper {
  title: string;
  authors: string[];
  year: number | null;
  abstract: string;
  url: string;
  citationCount?: number;
  venue?: string;
  pdfUrl?: string;
}

export interface WebPresence {
  platform: string;
  url: string;
  summary: string;
}

/**
 * Semantic Scholar API — free, no key required for basic use.
 * Rate limit: 1 request/second without key.
 */
export async function searchPapers(query: string, limit = 5): Promise<Paper[]> {
  try {
    const params = new URLSearchParams({
      query,
      limit: String(limit),
      fields: "title,authors,year,abstract,url,citationCount,venue,openAccessPdf",
    });
    const res = await fetch(
      `https://api.semanticscholar.org/graph/v1/paper/search?${params}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data.data || []).map((p: any) => ({
      title: p.title || "",
      authors: (p.authors || []).map((a: any) => a.name),
      year: p.year,
      abstract: p.abstract || "",
      url: p.url || "",
      citationCount: p.citationCount,
      venue: p.venue || "",
      pdfUrl: p.openAccessPdf?.url || "",
    }));
  } catch (err) {
    console.error("Semantic Scholar search error:", err);
    return [];
  }
}

export async function getPaperDetails(paperId: string): Promise<Paper | null> {
  try {
    const res = await fetch(
      `https://api.semanticscholar.org/graph/v1/paper/${paperId}?fields=title,authors,year,abstract,url,citationCount,venue,openAccessPdf,references,citations`
    );
    if (!res.ok) return null;
    const p = await res.json();
    return {
      title: p.title || "",
      authors: (p.authors || []).map((a: any) => a.name),
      year: p.year,
      abstract: p.abstract || "",
      url: p.url || "",
      citationCount: p.citationCount,
      venue: p.venue || "",
      pdfUrl: p.openAccessPdf?.url || "",
    };
  } catch {
    return null;
  }
}

export async function getAuthorPapers(authorName: string): Promise<Paper[]> {
  try {
    const searchRes = await fetch(
      `https://api.semanticscholar.org/graph/v1/author/search?query=${encodeURIComponent(authorName)}&limit=1`
    );
    if (!searchRes.ok) return [];
    const searchData = await searchRes.json();
    const authorId = searchData.data?.[0]?.authorId;
    if (!authorId) return [];

    const papersRes = await fetch(
      `https://api.semanticscholar.org/graph/v1/author/${authorId}/papers?fields=title,authors,year,abstract,url,citationCount,venue&limit=10`
    );
    if (!papersRes.ok) return [];
    const papersData = await papersRes.json();
    return (papersData.data || []).map((p: any) => ({
      title: p.title || "",
      authors: (p.authors || []).map((a: any) => a.name),
      year: p.year,
      abstract: p.abstract || "",
      url: p.url || "",
      citationCount: p.citationCount,
      venue: p.venue || "",
    }));
  } catch {
    return [];
  }
}

/**
 * Use PinchTab or Playwright to scout someone's web presence.
 * Falls back to a simple URL-fetch approach for common platforms.
 */
export async function scoutWebPresence(
  name: string,
  page?: Page
): Promise<WebPresence[]> {
  const results: WebPresence[] = [];
  const platforms = [
    { platform: "GitHub", searchUrl: `https://github.com/search?q=${encodeURIComponent(name)}&type=users` },
    { platform: "Google Scholar", searchUrl: `https://scholar.google.com/scholar?q=author:"${encodeURIComponent(name)}"` },
    { platform: "LinkedIn", searchUrl: `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(name)}` },
    { platform: "ORCID", searchUrl: `https://orcid.org/orcid-search/search?searchQuery=${encodeURIComponent(name)}` },
  ];

  if (page) {
    for (const p of platforms) {
      try {
        await page.goto(p.searchUrl, { waitUntil: "domcontentloaded", timeout: 10000 });
        await page.waitForTimeout(2000);
        const text = await page.innerText("body").catch(() => "");
        results.push({
          platform: p.platform,
          url: p.searchUrl,
          summary: text.slice(0, 500),
        });
      } catch {
        results.push({ platform: p.platform, url: p.searchUrl, summary: "Could not access" });
      }
    }
  } else {
    for (const p of platforms) {
      results.push({
        platform: p.platform,
        url: p.searchUrl,
        summary: `Search URL generated — open in browser to view results`,
      });
    }
  }

  return results;
}

export function formatPapersForContext(papers: Paper[]): string {
  if (papers.length === 0) return "No papers found.";
  return papers
    .map(
      (p, i) =>
        `${i + 1}. "${p.title}" (${p.year || "n/a"}) by ${p.authors.join(", ")}` +
        (p.citationCount ? ` [${p.citationCount} citations]` : "") +
        (p.venue ? ` — ${p.venue}` : "") +
        (p.abstract ? `\n   Abstract: ${p.abstract.slice(0, 200)}...` : "")
    )
    .join("\n\n");
}
