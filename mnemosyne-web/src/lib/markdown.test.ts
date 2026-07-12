import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown';

describe('renderMarkdown (stored-XSS defence, CWE-79)', () => {
  it('strips onerror handlers from raw HTML image tags', () => {
    const html = renderMarkdown('<img src=x onerror="alert(document.cookie)">');
    expect(html).not.toContain('onerror');
    expect(html.toLowerCase()).not.toContain('alert(');
  });

  it('removes <script> tags embedded in the markdown', () => {
    const html = renderMarkdown('hello\n\n<script>steal(localStorage.token)</script>');
    expect(html.toLowerCase()).not.toContain('<script');
    expect(html).not.toContain('steal(');
  });

  it('drops javascript: link schemes', () => {
    const html = renderMarkdown('[click me](javascript:alert(1))');
    expect(html.toLowerCase()).not.toContain('javascript:');
  });

  it('preserves safe markdown formatting', () => {
    const html = renderMarkdown('# Title\n\n**bold** and a [link](https://example.com)');
    expect(html).toContain('<h1');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('href="https://example.com"');
  });
});
