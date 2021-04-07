# Server implementation for dalec

this python script handles DNS requests send by the dalec client software.

## Prepare

To get all dependcies for this server create a virtual environment and install
them using pip
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## How to run

To start this server you have to provide an IP, port and a private key.
either specify it in the source code or use command line arguments
```
python -i <ip> -p <port> -k <path-to-private-key.pem>
```

## Options

Available Options are:
```
-h, --help            show this help message and exit
-i IP, --ip IP        Port to listen on
-p PORT, --port PORT  Port to listen on
-k KEY, --key KEY     Path to key file
-V, --version         Print version of Server
```
