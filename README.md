# Straming Video Server and Client

## Installation

On Client's machine:

```
pip install Pillow
```

## The Server

On Server's machine:

- Server.py
- ServerWorker.py
- VideoStream.py
- RtpPacket.py
- \*.Mjpeg

Run the Server:

```
python Server.py server_port
```

E.g.

```
python Server.py 4008
```

## The Client

On Client's machine:

- ClientLauncher.py
- Client.py
- RtpPacket.py

Run the Server:

```
python ClientLauncher.py server_host server_port RTP_port video_file
```

E.g.

```
python ClientLauncher.py 192.168.1.10 4008 3036 movie.Mjpeg
```
