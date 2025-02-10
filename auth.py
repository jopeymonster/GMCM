"""
This file authenticates either via a provided service-account.json file, a
stored OAuth2 refresh token, or creates credentials and stores a refresh token
via a provided client-secrets.json file.

This example works with web OAuth client ID types.

https://console.cloud.google.com

IMPORTANT: For web app clients types, you must add "http://127.0.0.1" to the
"Authorized redirect URIs" list in your Google Cloud Console project before
running this example.
"""

# imports
from __future__ import print_function
import hashlib
import re
import socket
import urllib.parse
import sys
import os
import json
from typing import Tuple, Union, Optional, Dict, List, Any
from tabulate import tabulate
import google.auth
import google.oauth2
from google.oauth2 import service_account
from google_auth_oauthlib.flow import Flow


# If using Web flow, the redirect URL must match exactly what’s configured in
# GCP for the OAuth client.
_SCOPE = "https://www.googleapis.com/auth/content"
_SERVER = "127.0.0.1"
_PORT = 8080
_REDIRECT_URI = f"http://{_SERVER}:{_PORT}"

"""Discovers proper authorization files and creates a config object for validating credentials"""
class Configure(object):

    def get_config(self):
        config_path = os.path.dirname(os.path.realpath(__file__))
        config_dir = os.path.join(config_path, "authfiles")
        service_account_path = os.path.join(config_dir, "service-account.json")
        client_secrets_path = os.path.join(config_dir, "client-secrets.json")
        token_path = "token.json"
        config_object = {
            "service_account_path": service_account_path,
            "client_secrets_path": client_secrets_path,
            "token_path": token_path,
        }
        return config_object
    
    def read_merchant_ids() -> List[Any]:
        idfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "authfiles", "merchant-info.json")
        # print(idfile)
        if os.path.isfile(idfile):
            with open(idfile, 'r') as file:
                merchant_ids = json.load(file)
            return merchant_ids
        else:
            print("MC File not found or missing IDs in file.")
            exit(1)

class Storage(object):
  """Simple store for refresh token-based clients."""
  def __init__(self, config, scopes):
    self._config = config
    self._scopes = scopes

  def get(self):
    """Attempts to retrieve the currently stored token.

    Returns:
      An instance of google.oauth2.credentials.Credentials if token
      retrieval succeeds, or None if it fails for any reason.
    """
    try:
      with open(self._config["token_path"], "r") as infile:
        token = json.load(infile)
      client_info = self.retrieve_client_config()["web"]
      credentials = google.oauth2.credentials.Credentials(
          None,
          client_id=client_info["client_id"],
          client_secret=client_info["client_secret"],
          refresh_token=token["refresh_token"],
          token_uri=client_info["token_uri"],
          scopes=self._scopes)
      full_token_path = os.path.join(os.getcwd(), self._config["token_path"])
      # Access tokens aren't stored (and may be expired even if we did), so
      # we'll need to refresh to ensure we have valid credentials.
      try:
        credentials.refresh(google.auth.transport.requests.Request())
        print(f"Using stored credentials from {full_token_path}.")
        return credentials
      except google.auth.exceptions.RefreshError:
        print(f"The stored credentials in the file {full_token_path} cannot "
              "be refreshed ,please delete `token.json` and retry.")
        return None
    except (IOError, ValueError, KeyError):
      return None

  def put(self, credentials):
    """Stores the provided credentials into the appropriate file.

    Args:
      credentials: an instance of google.oauth2.credentials.Credentials.
    """
    print("Attempting to store token")
    token = {"refresh_token": credentials.refresh_token}
    with open(self._config["token_path"], "w") as outfile:
      json.dump(token, outfile, sort_keys=True, indent=2,
                separators=(",", ": "))
    print("Token stored sucessfully")

  def retrieve_client_config(self):
    """Attempts to retrieve the client secret data.

    Returns:
      The client secret data in JSON form if the retrieval succeeds,
      or exits with an error if retrieval fails.
    """
    try:
      with open(self._config["client_secrets_path"], "r") as json_file:
        client_config_json = json.load(json_file)
      if "web" not in client_config_json:
        print("Please read the note about OAuth2 client IDs in the "
              "top-level README.")
        sys.exit(1)
      return client_config_json
    except FileNotFoundError:
      print("Please read the note about OAuth2 client IDs in the "
            "top-level README.")
      sys.exit(1)

# generate_user_credentials
def get_credentials_from_token(config):
  """Generates OAuth2 refresh token from stored local token file."""
  credentials = Storage(config, _SCOPE).get()
  return credentials

def get_credentials_from_client_secrets(config):
  """Generates OAuth2 refresh token using the Web application flow.

  To retrieve the necessary client_secrets JSON file, first
  generate OAuth 2.0 credentials of type Web application in the
  Google Cloud Console (https://console.cloud.google.com).
  Make sure "http://_SERVER:_PORT" is included the list of
  "Authorized redirect URIs" for this client ID."

  Starts a basic server and initializes an auth request.

  Args:
    config: an instance of the Configuration object.

  Returns:
    Credentials used to authenticate with the Merchant API.
  """
  # A list of API scopes to include in the auth request, see:
  # https://developers.google.com/identity/protocols/oauth2/scopes
  scopes = [_SCOPE]
  # A path to where the client secrets JSON file is located
  # on the machine running this example.
  client_secrets_path = config["client_secrets_path"]
  flow = Flow.from_client_secrets_file(client_secrets_path, scopes=scopes)
  flow.redirect_uri = _REDIRECT_URI
  # Create an anti-forgery state token as described here:
  # https://developers.google.com/identity/protocols/OpenIDConnect#createxsrftoken
  passthrough_val = hashlib.sha256(os.urandom(1024)).hexdigest()
  authorization_url, state = flow.authorization_url(
      access_type="offline",
      state=passthrough_val,
      prompt="consent",
      include_granted_scopes="true",
  )
  print(f"Your state token is: {state}\n")
  # Prints the authorization URL so you can paste into your browser. In a
  # typical web application you would redirect the user to this URL, and they
  # would be redirected back to "redirect_url" provided earlier after
  # granting permission.
  print("Paste this URL into your browser: ")
  print(authorization_url)
  print(f"\nWaiting for authorization and callback to: {_REDIRECT_URI}")
  # Retrieves an authorization code by opening a socket to receive the
  # redirect request and parsing the query parameters set in the URL.
  code = urllib.parse.unquote(get_authorization_code(passthrough_val))
  # Passes the code back into the OAuth module to get a refresh token.
  flow.fetch_token(code=code)
  refresh_token = flow.credentials.refresh_token
  print(f"\nYour refresh token is: {refresh_token}\n")
  # Stores the provided credentials into the appropriate file.
  storage = Storage(config, scopes)
  storage.put(flow.credentials)
  return flow.credentials

def get_authorization_code(passthrough_val):
  """Opens a socket to handle a single HTTP request containing auth tokens.

  Args:
    passthrough_val: an anti-forgery token used to verify the request
      received by the socket.

  Returns:
    a str access token from the Google Auth service.
  """
  # Opens a socket at _SERVER:_PORT and listen for a request.
  sock = socket.socket()
  sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  sock.bind((_SERVER, _PORT))
  sock.listen(1)
  connection, address = sock.accept()
  print(f"Socket address: {address}")
  data = connection.recv(1024)
  # Parses the raw request to retrieve the URL query parameters.
  params = parse_raw_query_params(data)
  try:
    if not params.get("code"):
      # If no code is present in the query params then there will be an
      # error message with more details.
      error = params.get("error")
      message = f"Failed to retrieve authorization code. Error: {error}"
      raise ValueError(message)
    elif params.get("state") != passthrough_val:
      message = "State token does not match the expected state."
      raise ValueError(message)
    else:
      message = "Authorization code was successfully retrieved."
  except ValueError as error:
    print(error)
    sys.exit(1)
  finally:
    response = (
        "HTTP/1.1 200 OK\n"
        "Content-Type: text/html\n\n"
        f"<b>{message}</b>"
        "<p>Please check the console output.</p>\n"
    )
    connection.sendall(response.encode())
    connection.close()
  return params.get("code")

def parse_raw_query_params(data):
  """Parses a raw HTTP request to extract its query params as a dict.

  Note that this logic is likely irrelevant if you're building OAuth logic
  into a complete web application, where response parsing is handled by a
  framework.

  Args:
    data: raw request data as bytes.

  Returns:
    a dict of query parameter key value pairs.
  """
  # Decodes the request into a utf-8 encoded string.
  decoded = data.decode("utf-8")
  # Uses a regular expression to extract the URL query parameters string.
  params = re.search(r"GET\s\/\?(.*) ", decoded).group(1)
  # Splits the parameters to isolate the key/value pairs.
  pairs = [pair.split("=") for pair in params.split("&")]
  # Converts pairs to a dict to make it easy to access the values.
  return {key: val for key, val in pairs}

# main auth logic
def authorize():
  """Generates OAuth2 credentials."""
  # Gets the configuration object that has the paths on the local machine to
  # the `service-account.json`, `token.json`, and `client-secrets.json` files.
  config = Configure().get_config()
  service_account_path = config["service_account_path"]
  print("Configuring service account credentials.")
  if os.path.isfile(service_account_path):
    print("Service account credentials found. Attempting to authenticate.")
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path,
        scopes=[_SCOPE])
    return credentials
  else:
    print("Service account credentials not found.")
    full_token_path = os.path.join(os.getcwd(), config["token_path"])
    print(f"Attempting to use stored token data.")
    if os.path.isfile(config["token_path"]):
      print("Token file found.")
      print("Attempting to use token file to authenticate")
      return get_credentials_from_token(config)
    else:
      print("Token file not found.")
      client_secrets_path = config["client_secrets_path"]
      print(f"Configuring client secrets credentials.")
      if os.path.isfile(client_secrets_path):
        print("Client secrets file found.")
        print("Attempting to use client secrets to authenticate")
        return get_credentials_from_client_secrets(config)
      else:
        print("Service account file, token file, and client secrets "
              "file do not exist. Please follow the instructions in "
              "the top level ReadMe to create a service account or "
              "client secrets file.")
        exit(1)