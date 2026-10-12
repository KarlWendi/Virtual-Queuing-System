import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERVER_URL = "http://127.0.0.1:8000"


def api_request(path, data=None):
    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = Request(
        SERVER_URL + path, data=body, headers={"Content-Type": "application/json"}
    )

    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    except HTTPError as error:
        try:
            details = json.loads(error.read().decode("utf-8"))
            message = details.get("error", f"Server error {error.code}")
        except (ValueError, AttributeError):
            message = f"Server error {error.code}"

        raise RuntimeError(message) from error

    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(
            "Cannot reach the queue server. Check that it is running."
        ) from error
