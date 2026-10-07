import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from uuid import uuid4


# Shared queue data
queue = []
queue_lock = Lock()

client_statuses = {}

support_options = [
    "Password / Account Issue",
    "Wi-Fi / Network Issue",
    "Software Issue",
    "Hardware Issue",
    "Printing Issue",
    "Email Issue",
    "Other"
]


class QueueRequestHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    # Return the current queue
    def do_GET(self):
        if self.path == "/queue":
            with queue_lock:
                clients = [
                    {
                        "name": client["name"],
                        "issue": client["issue"],
                        "position": position,
                        "people_ahead": position - 1
                    }
                    for position, client in enumerate(queue, start=1)
                ]

            self.send_json({"queue": clients})
        
        elif self.path.startswith("/status/"):
            client_id = self.path[len("/status/"):]

            with queue_lock:
                status = client_statuses.get(client_id)
                position = None

                if status == "waiting":
                    for index, client in enumerate(queue):
                        if client["id"] == client_id:
                            position = index + 1
                            break

            if status is None:
                self.send_json(
                    {"error": "Client not found"},
                    status=404
                )
            else:
                self.send_json({
                    "id": client_id,
                    "status": status,
                    "position": position,
                    "people_ahead": (
                        position - 1 if position is not None else None
                    )
                })

        else:
            self.send_json(
                {"error": "Page not found"},
                status=404
            )

    # Add a client to the queue
    def do_POST(self):
        if self.path not in ("/join", "/leave", "/serve"):
            self.send_json(
                {"error": "Page not found"},
                status=404
            )
            return

        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )
        except ValueError:
            self.send_json(
                {"error": "Invalid request length"},
                status=400
            )
            return

        if not 0 < content_length <= 4096:
            self.send_json(
                {"error": "Invalid request size"},
                status=400
            )
            return

        try:
            data = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(
                {"error": "Invalid JSON"},
                status=400
            )
            return

        if not isinstance(data, dict):
            self.send_json(
                {"error": "Expected a JSON object"},
                status=400
            )
            return



        # Serve Next
        if self.path == "/serve":
            with queue_lock:
                if queue:
                    client = queue.pop(0)
                    client_statuses[client["id"]] = "served"
                else:
                    client = None

            if client is None:
                self.send_json(
                    {"error": "There is nobody waiting"},
                    status=409
                )
            else:
                self.send_json({
                    "message": "Client called",
                    "id": client["id"],
                    "name": client["name"],
                    "issue": client["issue"]
                })

            return

        # Leave Queue
        if self.path == "/leave":
            client_id = data.get("id")

            if not isinstance(client_id, str) or not client_id.strip():
                self.send_json(
                    {"error": "Please provide a client ID"},
                    status=400
                )
                return

            removed_client = None

            with queue_lock:
                for index, client in enumerate(queue):
                    if client["id"] == client_id:
                        removed_client = queue.pop(index)
                        client_statuses[client["id"]] = "left"
                        break


            if removed_client is None:
                self.send_json(
                    {"error": "Client not found in queue"},
                    status=404
                )
            else:
                self.send_json({
                    "message": "You have left the queue",
                    "name": removed_client["name"]
                })

            return

        name = data.get("name")
        issue = data.get("issue")

        if not isinstance(name, str) or not name.strip():
            self.send_json(
                {"error": "Please enter your name"},
                status=400
            )
            return

        if not isinstance(issue, str) or issue not in support_options:
            self.send_json(
                {"error": "Please select an IT support issue"},
                status=400
            )
            return

        client = {
            "id": str(uuid4()),
            "name": name.strip(),
            "issue": issue
        }

        with queue_lock:
            queue.append(client)
            client_statuses[client["id"]] = "waiting"
            position = len(queue)

        self.send_json(
            {
                "id": client["id"],
                "name": client["name"],
                "issue": client["issue"],
                "position": position,
                "people_ahead": position - 1
            },
            status=201
        )


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8000),
        QueueRequestHandler
    )

    print("Queue server running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping the server.")
    finally:
        server.server_close()