import { marked } from 'marked';
import DOMPurify from 'isomorphic-dompurify';

/**
 * Render GitHub-derived Markdown to sanitized HTML.
 *
 * The content is attacker-controllable (anyone with push access to a monitored
 * repository), and marked ^15 no longer sanitizes its output. Every rendered
 * string is therefore passed through DOMPurify before it can reach {@html},
 * stripping script/onerror/javascript: vectors that would otherwise steal the
 * OIDC tokens held in localStorage (stored XSS, CWE-79).
 *
 * DOMPurify is isomorphic here, so this is safe under SSR and in the browser.
 */
export function renderMarkdown(content: string): string {
  const raw = marked.parse(content) as string;
  return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
}
