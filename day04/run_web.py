import threading
import webbrowser

from web_app import create_app


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    url = f"http://{host}:{port}"
    threading.Timer(1, webbrowser.open, args=(url,)).start()
    create_app().run(host=host, port=port, debug=False)