# 10 clients downloading a file concurrently — measure server throughput

import sys
import socket
import time
import os
import threading
from pathlib import Path

ProjectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ProjectRoot))

from Common.protocol import SendCommand, ReceiveCommand, ReceiveFileData, SendFileData, GetFileSize

HOST = "127.0.0.1"
PORT = 5000

NUM_CLIENTS = 10
FILE_SIZE_MB = 1          # change to 100 or 1000 for the other two runs
TEST_FILE_PATH = "test_upload_file.bin"
DOWNLOAD_DIR = "test_downloads"


def GenerateTestFile(Path_, SizeMB):
    if os.path.isfile(Path_) and os.path.getsize(Path_) == SizeMB * 1024 * 1024:
        return
    ChunkSize = 1024 * 1024
    with open(Path_, "wb") as File:
        for _ in range(SizeMB):
            File.write(os.urandom(ChunkSize))


def Login(Socket, Username):
    SendCommand(Socket, f"LOGIN {Username}")
    Response = ReceiveCommand(Socket)
    if Response != f"OK LOGIN {Username}":
        raise RuntimeError(f"Login failed for {Username}: {Response}")


def Logout(Socket):
    try:
        SendCommand(Socket, "LOGOUT")
        ReceiveCommand(Socket)
    except (OSError, ConnectionError):
        pass


def SetupClient(ClientNumber, FileSize, Barrier, Results, ResultsLock, StartEvent):
    Username = f"perf_dl_{ClientNumber}"
    Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    Socket.settimeout(60)

    try:
        Socket.connect((HOST, PORT))
        Login(Socket, Username)

        # Upload the test file to this client's own server-side storage first —
        # this setup step is NOT timed, only the DOWNLOAD is.
        FileName = "perf_test.bin"
        SendCommand(Socket, f"UPLOAD {FileName} {FileSize}")
        SendFileData(Socket, TEST_FILE_PATH)
        UploadResponse = ReceiveCommand(Socket)
        if not UploadResponse.startswith("OK UPLOAD"):
            raise RuntimeError(f"Upload failed for {Username}: {UploadResponse}")

        # Wait for all 10 clients to finish uploading and be ready to download together
        Barrier.wait()
        StartEvent.wait()

        LocalPath = os.path.join(DOWNLOAD_DIR, f"{Username}_downloaded.bin")

        StartTime = time.perf_counter()
        SendCommand(Socket, f"DOWNLOAD {FileName}")
        Header = ReceiveCommand(Socket)
        Parts = Header.split(' ', 3)
        if len(Parts) != 4 or Parts[0] != "OK" or Parts[1] != "DOWNLOAD":
            raise RuntimeError(f"Unexpected download header for {Username}: {Header}")
        ReceivedSize = int(Parts[3])
        ReceiveFileData(Socket, LocalPath, ReceivedSize)
        EndTime = time.perf_counter()

        Duration = EndTime - StartTime
        ThroughputMBps = (ReceivedSize / (1024 * 1024)) / Duration if Duration > 0 else float("inf")

        with ResultsLock:
            Results.append({
                "Username": Username,
                "Bytes": ReceivedSize,
                "Duration": Duration,
                "ThroughputMBps": ThroughputMBps,
                "Success": True,
            })

        print(f"[{Username}] downloaded {ReceivedSize / (1024*1024):.1f} MB "
              f"in {Duration:.3f}s ({ThroughputMBps:.2f} MB/s)")

        Logout(Socket)

    except Exception as Error:
        print(f"[{Username}] FAILED: {Error}")
        with ResultsLock:
            Results.append({"Username": Username, "Success": False, "Error": str(Error)})
    finally:
        Socket.close()


def RunTest():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    FileSizeBytes = FILE_SIZE_MB * 1024 * 1024

    print(f"Generating {FILE_SIZE_MB} MB test file...")
    GenerateTestFile(TEST_FILE_PATH, FILE_SIZE_MB)

    Barrier = threading.Barrier(NUM_CLIENTS, timeout=120)
    StartEvent = threading.Event()
    Results = []
    ResultsLock = threading.Lock()

    Threads = []
    for ClientNumber in range(1, NUM_CLIENTS + 1):
        Thread = threading.Thread(
            target=SetupClient,
            args=(ClientNumber, FileSizeBytes, Barrier, Results, ResultsLock, StartEvent)
        )
        Threads.append(Thread)
        Thread.start()

    # Give all clients a moment to reach the barrier (uploads complete), then release them together
    time.sleep(0.5)
    StartEvent.set()

    WallClockStart = time.perf_counter()
    for Thread in Threads:
        Thread.join()
    WallClockEnd = time.perf_counter()

    Successful = [R for R in Results if R.get("Success")]
    Failed = [R for R in Results if not R.get("Success")]

    print("\n" + "=" * 55)
    print(f"Test 3 - Server Throughput: {NUM_CLIENTS} concurrent downloads, {FILE_SIZE_MB} MB each")
    print("=" * 55)
    print(f"Successful downloads     : {len(Successful)}")
    print(f"Failed downloads         : {len(Failed)}")

    if Successful:
        TotalBytes = sum(R["Bytes"] for R in Successful)
        WallClockDuration = WallClockEnd - WallClockStart
        AggregateThroughputMBps = (TotalBytes / (1024 * 1024)) / WallClockDuration
        AvgPerClientThroughput = sum(R["ThroughputMBps"] for R in Successful) / len(Successful)

        print(f"Total data transferred   : {TotalBytes / (1024*1024):.1f} MB")
        print(f"Wall-clock duration      : {WallClockDuration:.3f} s")
        print(f"Aggregate server throughput : {AggregateThroughputMBps:.2f} MB/s")
        print(f"Average per-client throughput: {AvgPerClientThroughput:.2f} MB/s")
    print("=" * 55)


if __name__ == "__main__":
    try:
        RunTest()
    except Exception as Error:
        print(f"\nTest Failed: {Error}")