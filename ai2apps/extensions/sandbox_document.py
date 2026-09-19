"""Deliver verified classic script/style assets without opaque-frame HTTP auth.

This does not grant network access or same-origin privileges to the document.
Only package-relative assets resolved by the caller's digest verifier are read.
"""
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit


def inline_sandbox_assets(document: str, resource: str, read_verified) -> str:
    class Document(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.output = []
            self.script = False
            self.deferred = []
            self.total = len(document.encode())

        def asset(self, url):
            parsed = urlsplit(url)
            path = unquote(parsed.path)
            if parsed.scheme or parsed.netloc or path.startswith('/') or '\\' in path:
                raise ValueError('Sandbox assets must be package-relative')
            if not path or '..' in PurePosixPath(path).parts:
                raise ValueError('Invalid sandbox asset path')
            target = str(PurePosixPath(resource).parent / path)
            value = read_verified(target)
            self.total += len(value.encode())
            if self.total > 4 * 1024 * 1024:
                raise ValueError('Sandbox document is too large')
            return value

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == 'script' and values.get('src'):
                if values.get('type', '').lower() not in ('', 'text/javascript', 'application/javascript'):
                    raise ValueError('Only classic sandbox scripts can be inlined')
                code = self.asset(values['src'])
                if '</script' in code.lower():
                    raise ValueError('Unsafe script terminator')
                rendered = '<script>' + code + '</script>'
                # Inline scripts ignore defer: preserve execution after body parsing.
                if 'defer' in values:
                    self.deferred.append(rendered)
                else:
                    self.output.append(rendered)
                self.script = True
            elif tag == 'link' and values.get('rel', '').lower() == 'stylesheet' and values.get('href'):
                css = self.asset(values['href'])
                if '</style' in css.lower():
                    raise ValueError('Unsafe style terminator')
                self.output.append('<style>' + css + '</style>')
            else:
                self.output.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            if tag == 'script' and self.script:
                self.script = False
                return
            if tag == 'body':
                self.output.extend(self.deferred)
                self.deferred.clear()
            self.output.append(f'</{tag}>')

        def handle_data(self, data):
            if not self.script:
                self.output.append(data)

        def handle_entityref(self, name):
            self.output.append(f'&{name};')

        def handle_charref(self, name):
            self.output.append(f'&#{name};')

        def handle_decl(self, decl):
            self.output.append(f'<!{decl}>')

        def handle_comment(self, data):
            self.output.append(f'<!--{data}-->')

    parser = Document()
    parser.feed(document)
    parser.close()
    parser.output.extend(parser.deferred)
    return ''.join(parser.output)
