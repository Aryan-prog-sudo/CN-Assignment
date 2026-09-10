import socket
import threading
import time
import os

HOST = '127.0.0.1'
PORT = 5000

NUM_CLIENTS = 10000
FILE_PATH = 'test.txt'

Barrier = threading.Barrier(NUM_CLIENTS)
Results = []
ResultsLock = threading.Lock()


def SendCommand(Socket, Command):
    Socket.sendall((Command + '\n').encode('utf-8'))


def ReceiveCommand(Socket):
    Data = bytearray()

    while True:
        Chunk = Socket.recv(1)

        if not Chunk:
            return None

        if Chunk == b'\n':
            break

        Data.extend(Chunk)

    return Data.decode('utf-8')


def ReceiveFileData(Socket, Size):
    BytesReceived = 0

    while BytesReceived < Size:
        Remaining = Size - BytesReceived
        Chunk = Socket.recv(min(4096, Remaining))

        if not Chunk:
            raise ConnectionError(
                "Connection closed during file transfer"
            )

        BytesReceived += len(Chunk)

    return BytesReceived


def SendFileData(Socket, FilePath):
    with open(FilePath, 'rb') as File:
        while True:
            Data = File.read(4096)

            if not Data:
                break

            Socket.sendall(Data)


def ReceiveUntil(Socket, ExpectedResponse):
    while True:
        Message = ReceiveCommand(Socket)

        if Message is None:
            raise ConnectionError("Server disconnected")

        # This is the response we are waiting for
        if Message == ExpectedResponse:
            return

        # Another private message arrived first
        if Message.startswith("MSG "):
            print(f"    Incoming message: {Message}")
            continue

        # Another broadcast arrived
        if Message.startswith("BROADCAST "):
            print(f"    Incoming broadcast: {Message}")
            continue

        # A file arrived while we were waiting
        if Message.startswith("INCOMING "):
            Parts = Message.split(' ', 3)

            if len(Parts) != 4:
                raise Exception(
                    f"Malformed INCOMING message: {Message}"
                )

            Sender = Parts[1]
            FileName = Parts[2]

            try:
                FileSize = int(Parts[3])
            except ValueError:
                raise Exception(
                    f"Invalid file size: {Parts[3]}"
                )

            ReceiveFileData(Socket, FileSize)

            print(
                f"    Incoming file: {FileName} "
                f"from {Sender} ({FileSize} bytes)"
            )

            continue

        # Anything else is unexpected
        print(f"    Ignoring message: {Message}")


def TestClient(ClientNumber):
    UserName = f"testuser{ClientNumber}"
    Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        Socket.connect((HOST, PORT))

        # -------------------------
        # LOGIN
        # -------------------------

        SendCommand(Socket, f"LOGIN {UserName}")

        Response = ReceiveCommand(Socket)

        if Response != f"OK LOGIN {UserName}":
            raise Exception(f"Login failed: {Response}")

        print(f"[{UserName}] LOGIN successful")

        # Wait for all clients
        Barrier.wait()

        # -------------------------
        # MSG
        # -------------------------

        TargetNumber = (ClientNumber % NUM_CLIENTS) + 1
        TargetUser = f"testuser{TargetNumber}"

        StartTime = time.perf_counter()

        SendCommand(
            Socket,
            f"MSG {TargetUser} Hello from {UserName}"
        )

        ReceiveUntil(
            Socket,
            f"OK MSG {TargetUser}"
        )

        EndTime = time.perf_counter()

        print(
            f"[{UserName}] MSG successful "
            f"({(EndTime - StartTime) * 1000:.2f} ms)"
        )

        # Synchronize before SEND
        Barrier.wait()

        # -------------------------
        # SEND
        # -------------------------

        FileSize = os.path.getsize(FILE_PATH)

        StartTime = time.perf_counter()

        SendCommand(
            Socket,
            f"SEND {TargetUser} test.txt {FileSize}"
        )

        SendFileData(Socket, FILE_PATH)

        ReceiveUntil(
            Socket,
            f"OK SEND {TargetUser} test.txt"
        )

        EndTime = time.perf_counter()

        print(
            f"[{UserName}] SEND successful "
            f"({(EndTime - StartTime) * 1000:.2f} ms)"
        )

        # Record success
        with ResultsLock:
            Results.append(True)

        # Wait for all SENDs to finish
        Barrier.wait()

        # -------------------------
        # LOGOUT
        # -------------------------

        SendCommand(Socket, "LOGOUT")

        ReceiveUntil(Socket, "OK LOGOUT")

        print(f"[{UserName}] LOGOUT successful")

    except Exception as Error:
        print(f"[{UserName}] FAILED: {Error}")

        with ResultsLock:
            Results.append(False)

    finally:
        Socket.close()


def Main():
    if not os.path.isfile(FILE_PATH):
        print(f"ERROR: {FILE_PATH} not found")
        return

    print("=" * 50)
    print(f"Starting concurrency test with {NUM_CLIENTS} clients")
    print("=" * 50)

    Threads = []

    StartTime = time.perf_counter()

    for ClientNumber in range(1, NUM_CLIENTS + 1):
        Thread = threading.Thread(
            target=TestClient,
            args=(ClientNumber,)
        )

        Threads.append(Thread)
        Thread.start()

    for Thread in Threads:
        Thread.join()

    EndTime = time.perf_counter()

    print()
    print("=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)

    Successful = sum(Results)
    Failed = len(Results) - Successful

    print(f"Successful clients: {Successful}")
    print(f"Failed clients:     {Failed}")
    print(f"Total time:         {(EndTime - StartTime):.3f} seconds")

    if Failed == 0:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")


if __name__ == "__main__":
    Main()