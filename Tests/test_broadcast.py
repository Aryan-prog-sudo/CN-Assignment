# Broadcast from one user to 5 clients — measure average delivery response time

import sys
import socket
import time
import statistics
import threading
import queue
from pathlib import Path

ProjectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ProjectRoot))

from Common.protocol import SendCommand, ReceiveCommand

HOST = "127.0.0.1"
PORT = 5000

BROADCASTER_USERNAME = "performance_broadcaster"
RECEIVER_USERNAMES = [f"performance_client_{i}" for i in range(1, 6)]  # 5 clients
NUM_TESTS = 50
MESSAGE = "Performance broadcast test"


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


def WaitForOkBroadcast(Socket):
    # The broadcaster is itself in ActiveUsers, so it also receives its own
    # pushed BROADCAST line before the OK confirmation — skip past it.
    while True:
        Response = ReceiveCommand(Socket)
        if Response is None:
            raise ConnectionError("Broadcaster connection closed unexpectedly")
        if Response.startswith("OK BROADCAST"):
            return
        if Response.startswith("BROADCAST"):
            continue
        if Response.startswith("ERR"):
            raise RuntimeError(f"Server returned an error: {Response}")


def ReceiverThreadFunction(Socket, ArrivalQueue, StopEvent):
    while not StopEvent.is_set():
        try:
            Response = ReceiveCommand(Socket)
        except OSError:
            break
        if Response is None:
            break
        if Response.startswith("BROADCAST"):
            ArrivalQueue.put(time.perf_counter_ns())


def RunTest():
    AllLatencies = []
    PerRoundAverages = []

    BroadcasterSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    BroadcasterSocket.connect((HOST, PORT))
    BroadcasterSocket.settimeout(10)
    Login(BroadcasterSocket, BROADCASTER_USERNAME)

    ReceiverSockets = []
    ReceiverQueues = []
    ReceiverThreads = []
    StopEvent = threading.Event()

    for Username in RECEIVER_USERNAMES:
        Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Sock.connect((HOST, PORT))
        Sock.settimeout(10)
        Login(Sock, Username)
        ReceiverSockets.append(Sock)

        Q = queue.Queue()
        ReceiverQueues.append(Q)

        Thread = threading.Thread(target=ReceiverThreadFunction, args=(Sock, Q, StopEvent))
        Thread.start()
        ReceiverThreads.append(Thread)

    print(f"Broadcaster and {len(RECEIVER_USERNAMES)} receivers logged in successfully\n")

    try:
        # Warmup round — discard, same reasoning as Test 1
        SendCommand(BroadcasterSocket, f"BROADCAST Warmup")
        WaitForOkBroadcast(BroadcasterSocket)
        for Q in ReceiverQueues:
            try:
                Q.get(timeout=5)
            except queue.Empty:
                pass

        print(f"Running {NUM_TESTS} broadcasts to {len(RECEIVER_USERNAMES)} clients\n")
        for TestNumber in range(1, NUM_TESTS + 1):
            StartTime = time.perf_counter_ns()
            SendCommand(BroadcasterSocket, f"BROADCAST {MESSAGE}")
            WaitForOkBroadcast(BroadcasterSocket)

            RoundLatencies = []
            for Q in ReceiverQueues:
                ArrivalTime = Q.get(timeout=5)
                LatencyMs = (ArrivalTime - StartTime) / 1_000_000
                RoundLatencies.append(LatencyMs)

            AllLatencies.extend(RoundLatencies)
            RoundAverage = statistics.mean(RoundLatencies)
            PerRoundAverages.append(RoundAverage)
            print(f"Round {TestNumber:3d}  avg response time = {RoundAverage:.3f} ms "
                  f"(min {min(RoundLatencies):.3f}, max {max(RoundLatencies):.3f})")

    finally:
        StopEvent.set()
        Logout(BroadcasterSocket)
        for Sock in ReceiverSockets:
            Logout(Sock)
        for Thread in ReceiverThreads:
            Thread.join(timeout=5)
        BroadcasterSocket.close()
        for Sock in ReceiverSockets:
            Sock.close()

    if not AllLatencies:
        raise RuntimeError("No latency measurements were recorded")

    print("\n" + "=" * 50)
    print("Test 2 - Broadcast to 5 Clients: Response Time Results")
    print("=" * 50)
    print(f"Number of clients        : {len(RECEIVER_USERNAMES)}")
    print(f"Number of broadcasts     : {NUM_TESTS}")
    print(f"Total measurements       : {len(AllLatencies)}")
    print(f"Overall average latency  : {statistics.mean(AllLatencies):.3f} ms")
    print(f"Overall median latency   : {statistics.median(AllLatencies):.3f} ms")
    print(f"Minimum latency          : {min(AllLatencies):.3f} ms")
    print(f"Maximum latency          : {max(AllLatencies):.3f} ms")
    if len(AllLatencies) > 1:
        print(f"Std deviation            : {statistics.stdev(AllLatencies):.3f} ms")
    print(f"Average of per-round avg : {statistics.mean(PerRoundAverages):.3f} ms")
    print("=" * 50)


if __name__ == "__main__":
    try:
        RunTest()
    except Exception as Error:
        print(f"\nTest Failed: {Error}")