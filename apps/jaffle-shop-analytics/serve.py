"""Local static preview with byte-range support for Wren Parquet snapshots."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import re

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)

    def send_head(self):
        self.byte_range = None
        path = Path(self.translate_path(self.path))
        header = self.headers.get('Range')
        if header and path.is_file():
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
            if match:
                size = path.stat().st_size
                start = int(match[1])
                end = min(int(match[2]) if match[2] else size-1, size-1)
                if start > end:
                    self.send_error(416)
                    return None
                stream = path.open('rb')
                stream.seek(start)
                self.byte_range = end-start+1
                self.send_response(206)
                self.send_header('Content-Type', self.guess_type(str(path)))
                self.send_header('Content-Length', str(self.byte_range))
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                return stream
        return super().send_head()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def copyfile(self, source, outputfile):
        if self.byte_range is not None:
            outputfile.write(source.read(self.byte_range))
        else:
            super().copyfile(source, outputfile)

if __name__ == '__main__':
    print('Jaffle Shop preview: http://127.0.0.1:4173/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 4173), Handler).serve_forever()
