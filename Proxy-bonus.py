# Include the libraries for socket and system calls
import socket
import sys
import os
import argparse
import re
import time
from email.utils import parsedate_to_datetime

# 1MB buffer size
BUFFER_SIZE = 1000000

# Get the IP address and Port number to use for this web proxy server
parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='the IP Address Of Proxy Server')
parser.add_argument('port', help='the port number of the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = int(args.port)

# Create a server socket, bind it to a port and start listening
try:
    # Create a server socket
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Created socket')
except:
    print('Failed to create socket')
    sys.exit()

try:
    # Bind the server socket to a host and port
    serverSocket.bind((proxyHost, proxyPort))
    print('Port is bound')
except:
    print('Port is already in use')
    sys.exit()

try:
    # Listen on the server socket
    serverSocket.listen(5)
    print('Listening to socket')
except:
    print('Failed to listen')
    sys.exit()

# continuously accept connections
while True:
    print('Waiting for connection...')
    clientSocket = None

    # Accept connection from client and store in the clientSocket
    try:
        clientSocket, clientAddr = serverSocket.accept()
        print('Received a connection')
    except:
        print('Failed to accept connection')
        sys.exit()

    # Get HTTP request from client
    message_bytes = clientSocket.recv(BUFFER_SIZE)
    message = message_bytes.decode('utf-8')
    print('Received request:')
    print('< ' + message)

    # Extract the method, URI and version of the HTTP client request
    requestParts = message.split()
    method = requestParts[0]
    URI = requestParts[1]
    version = requestParts[2]

    print('Method:\t\t' + method)
    print('URI:\t\t' + URI)
    print('Version:\t' + version)
    print('')

    # Handle the port and extract hostname/resource
    port = 80  # Default port
    if ':' in URI:
        parts = URI.split(':', 1)
        URI = parts[0]  # Extract the hostname part
        port = int(parts[1].split('/')[0])  # Extract the port number

    # Get the requested resource from URI
    URI = re.sub('^(/?)http(s?)://', '', URI, count=1)  # Remove http(s)://
    URI = URI.replace('/..', '')  # Remove parent directory changes

    # Split hostname from resource name
    resourceParts = URI.split('/', 1)
    hostname = resourceParts[0]
    resource = '/'
    
    if len(resourceParts) == 2:
     # Resource is absolute URI with hostname and resource
        resource = resource + resourceParts[1]

    print('Requested Resource:\t' + resource)

    #Check if the cached file is still fresh
    try:
        cacheLocation = './' + hostname + resource
        if cacheLocation.endswith('/'):
            cacheLocation = cacheLocation + 'default'
#Constructs a cache file path based on the requested resource.
#If the resource is a directory that is ending with /, then it appends 'default' to store the content properly.

        print('Cache location:\t\t' + cacheLocation)
        if os.path.isfile(cacheLocation):
            
            #Check if the cache is fresh
            with open(cacheLocation, "rb") as cacheFile: 
                cacheData = cacheFile.readlines() #Checks if the requested resource is already cached and reads the cached file into cacheData
                #Check for Expires header in the cache file 
                if 'Expires' in str(cacheData):
                    #Assuming we have a way to extract Expires date
                    expire_header = re.search(r'Expires: (.+)', str(cacheData))
                    #Searches for an Expires header in the cached response.

                    if expire_header:
                        expire_time = parsedate_to_datetime(expire_header.group(1))
                        current_time = time.time()
                        #Converts the expiration date into a timestamp.

                        #If the cache has expired, fetch a new copy
                        if expire_time.timestamp() < current_time:
                            raise Exception("Cache expired")
                        #If the cache has expired, fetching from the origin server.
                print('Cache hit! Loading from cache file: ' + cacheLocation) 
                # ProxyServer finds a cache hit
                # Send back response to client 
                clientSocket.sendall(b''.join(cacheData))
                print('Sent to the client:') #If the cache is valid, it sends the cached response to the client.
                print('> ' + str(cacheData))
    except:
        #Cache miss or expired cache: Get resource from origin server
        originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        
        try:
            # Get the IP address for a hostname
            address = socket.gethostbyname(hostname)
            originServerSocket.connect((address, port))  #Use the port from URL or default
             # Connect to the origin server
            print('Connected to origin Server')
            #Connects to the origin server using the obtained IP and port.
            
            originServerRequest = f'GET {resource} HTTP/1.1\r\n' #Constructs an HTTP GET request. 
            originServerRequestHeader = f'Host: {hostname}\r\nConnection: close\r\n'
# Create origin server request line and headers to send
# and store in originServerRequestHeader and originServerRequest
# originServerRequest is the first line in the request and
# originServerRequestHeader is the second line in the request
            # Construct the request to send to the origin server
            request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'
            # Send the request to the origin server
            originServerSocket.sendall(request.encode())
            
            # Receive the response from the origin server
            response = originServerSocket.recv(BUFFER_SIZE)
            clientSocket.sendall(response)

            # Prefetch files such as images from the main HTML page
            if 'text/html' in response.decode('utf-8'):
                prefetch_files = re.findall(r'(href|src)=[\'"]?([^\'" >]+)', response.decode('utf-8'))
                for _, file in prefetch_files: #If the response is an HTML page then it extracts linked files using regular expressions.
                    #Skips files already in cache
                    if file not in [hostname + resource]:
                        file_response = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        file_response.connect((address, port))
                        file_request = f'GET {file} HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\n\r\n' 
                        file_response.sendall(file_request.encode())  
                        #Sends an HTTP GET request for the file.
                        #Opens a new socket connection to fetch each linked file.
                        
                        file_data = file_response.recv(BUFFER_SIZE)
                        cacheFileLocation = './' + hostname + file
                        if not os.path.exists(os.path.dirname(cacheFileLocation)):
                            os.makedirs(os.path.dirname(cacheFileLocation))
                        with open(cacheFileLocation, 'wb') as cacheFile:
                            cacheFile.write(file_data)
                        file_response.close()
                        #Saves the pre-fetched resource in the cache.
            
            # Save the origin response in the cache file
            cacheDir, file = os.path.split(cacheLocation) #Creates necessary directories for the cache.
            if not os.path.exists(cacheDir):
                os.makedirs(cacheDir)
            with open(cacheLocation, 'wb') as cacheFile:
                cacheFile.write(response)
            #Writes the origin server's response to the cache.
        
        except OSError as err:
            print('Origin server request failed. ' + str(err)) 
        originServerSocket.close()
        clientSocket.shutdown(socket.SHUT_WR)
    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
