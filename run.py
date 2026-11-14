"""Run with: python run.py --open"""
import argparse
import threading
import webbrowser
from src.api.server import create_server

def main():
    parser = argparse.ArgumentParser(description='LawExplore local development server')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open',action='store_true')
    args = parser.parse_args()
    try:
        server = create_server(port=args.port)
    except OSError as e:
        raise SystemExit('Port unavailable; try --port 8766. ' + str(e))
    url = 'http://127.0.0.1:%s' % server.server_port
    print('LawExplore: ' + url + ' (Ctrl+C to stop)', flush=True)
    if args.open:
        threading.Timer(0.5, lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
