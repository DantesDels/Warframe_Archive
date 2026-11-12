"""Raw markup handling: sanitization, links and emphasis.

Sub-modules (one file = one responsibility):
    * ``html``      : HTML tag conversion and comment/transclusion removal;
    * ``blocks``    : file/image references, tables and code block stripping;
    * ``links``     : MediaWiki/URL links -> readable text;
    * ``emphasis``  : Wikitext bold/italic -> Markdown;
    * ``site_html`` : official-site HTML document -> Markdown (``HtmlCleaner``).
"""
