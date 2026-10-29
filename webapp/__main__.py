"""python -m webapp starts the local application and opens its browser page."""

import argparse
import json
import sys
import threading
import urllib.request
import webbrowser


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="ЕЯЗиС: лабораторные в браузере")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Порт должен быть от 1024 до 65535")
    import uvicorn

    from webapp.server import create_app

    url = f"http://127.0.0.1:{args.port}"
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
            if json.load(response).get("app") == "eyazis-web":
                print("Приложение уже запущено:", url)
                if not args.no_browser:
                    webbrowser.open(url)
                return
    except (OSError, ValueError):
        pass
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=args.port, log_level="info")
    )

    def open_when_ready() -> None:
        import time

        for _ in range(100):
            if server.started:
                webbrowser.open(url)
                return
            if server.should_exit:
                return
            time.sleep(0.1)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    print("ЕЯЗиС:", url, "· Ctrl+C — остановить сервер")
    server.run()


if __name__ == "__main__":
    main()
