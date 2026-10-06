# Virtual Queuing System

A Python desktop application for managing an IT help desk queue. Built with Tkinter, it lets clients join a first-come, first-served queue while an administrator calls the next person for support.

## Features

- Join with a name and a selected IT support issue.
- View a live numbered queue, including each person's issue and how many people are ahead.
- Keep all open Client and Admin windows synchronized.
- Leave the queue voluntarily, or leave automatically when the Client window closes.
- Serve the first person through the Admin screen and notify them in their Client window.
- Validate missing names, missing issues, and duplicate joins from the same Client window.

## Requirements

- Python 3 with Tkinter installed.
- A desktop environment that can display Tkinter windows.

The application uses Python's standard library; no third-party packages are required. Tkinter is normally included with the standard Python installer for Windows. Check your installation with:

```sh
python -m tkinter
```

## Getting started

Clone the repository and enter its folder:

```sh
git clone https://github.com/KarlWendi/Virtual-Queuing-System.git
cd Virtual-Queuing-System
```

Run the application:

```sh
python "First Window.py"
```

On Windows, you can also use `py` instead of `python`.

## How to use it

1. Click **Client** in the main window. Open a separate Client window for each person.
2. Enter a name, select an IT support issue, and click **Join Queue**.
3. Watch the **Current Queue** display for queue order and people ahead.
4. Click **Leave Queue**, or close the Client window, to leave.
5. Click **Admin** in the main window and use **Serve Next** to call the person at the front.
6. The called person receives a notification, and the remaining clients move up one place.

## Example

```text
Before Serve Next:
1. Adam - Wi-Fi / Network Issue (0 people ahead)
2. Sarah - Software Issue (1 people ahead)

After Serve Next:
Adam receives: "It is now your turn!"
1. Sarah - Software Issue (0 people ahead)
```

## Current scope

This is a local desktop prototype. Multiple Client windows share a queue within one running application. Separate application instances and different computers do not share the queue yet.

Queue data is stored in memory and is cleared when the application exits. The Admin screen is currently accessible without authentication. Client notifications appear as Tkinter message boxes.

## Project structure

| File | Purpose |
| --- | --- |
| `First Window.py` | Tkinter interface, queue management, and client notifications |
| `README.md` | Setup instructions and project overview |

## Manual checks

- Join from two Client windows and confirm both show the same queue.
- Leave from the first window and confirm the second client moves to position 1.
- Close a waiting Client window and confirm that person is removed.
- Serve the next client and confirm they receive a notification.
- Serve an empty queue and confirm the empty-queue message appears.
- Try joining without a name or issue and confirm validation prevents the join.

## Planned improvements

- A shared server so clients can join from different devices.
- Persistent queue storage.
- Administrator authentication.
