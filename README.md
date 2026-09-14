# CN-Assignment


## Running

Run all commands from the repository root so the `Common` package resolves
correctly.

**Start the server:**

```bash
python -m Server.Server
```

The server listens on `0.0.0.0:5000` by default.

**Start a client** (in a separate terminal, run once per user):

```bash
python -m Client.Client
```

You'll be prompted for a username, then dropped into an interactive prompt.

## Client Commands

| Command       | Example                      | Description                                                                                |
| ------------- | ---------------------------- | ------------------------------------------------------------------------------------------ |
| `LIST`      | `LIST`                     | Show currently active users                                                                |
| `MSG`       | `MSG bob hello there`      | Send a private message to`bob`                                                           |
| `BROADCAST` | `BROADCAST exam postponed` | Send a message to every connected user                                                     |
| `UPLOAD`    | `UPLOAD ./notes.pdf`       | Upload a local file to your server storage                                                 |
| `DOWNLOAD`  | `DOWNLOAD notes.pdf`       | Download a file from your server storage (saved to`Downloads/`)                          |
| `SEND`      | `SEND bob ./notes.pdf`     | Send a file directly to`bob` (queued if `bob` is offline, delivered on his next login) |
| `LOGOUT`    | `LOGOUT`                   | Disconnect gracefully                                                                      |

Files received via `SEND` are saved to `Received/`.

## Running the Performance Tests

With the server running, from the repository root:

```bash
python Tests/test_rtt.py           # Test 1: RTT
python Tests/test_broadcast.py      # Test 2: broadcast to 5 clients
python Tests/test_throughput.py     # Test 3: concurrent download throughput
python Tests/concurrency_test.py    # Stress test
```

`test_throughput.py` generates its own test file at the size configured by
`FILE_SIZE_MB` inside the script; clear `Storage/` between runs at different
sizes to avoid stale files from a previous run.

## Notes

- Server storage layout: `Storage/<username>/` for a user's own uploaded files,
  `Storage/pending/<username>/` for files queued via SEND while that user was
  offline, `Storage/.send_temp/` for transient staging during a live SEND.
- The client requires a background listener thread to receive unsolicited
  pushes (forwarded messages, incoming files); see the technical report for
  the full architecture rationale.
