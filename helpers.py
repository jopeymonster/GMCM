import random
import time
import os
import sys
import re
import json
import pydoc
import requests
from datetime import datetime
import pandas as pd
from tabulate import tabulate
from urllib.parse import urljoin, urlparse

# exceptions wrapper
def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            print_error(func.__name__, e)
        except ValueError as e:
            print_error(func.__name__, e)
        except KeyboardInterrupt as e:
            print_error(func.__name__, e)
        except FileNotFoundError as e:
            print_error(func.__name__, e)
        except AttributeError as e:
            print_error(func.__name__, )
        except Exception as e:
            print_error(func.__name__, e)
    def print_error(func_name, error):
        print(f"\nError in function '{func_name}': {repr(error)} - Exiting...\n")
    return wrapper

# user error logging
def user_error(err_type):
    if err_type == 1:
        sys.exit("Problem with MAIN loop.")
    if err_type == 2:
        sys.exit("Invalid input.")
    elif err_type in [3,4]:
        sys.exit("Problem with output data.")

def custom_input(prompt=''):
    user_input = input(prompt)
    if user_input.lower() == 'ex':
        sys.exit("\nExiting the program at user request...\n")
    return user_input

# generate timestamp
def generate_timestamp():
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # print(now_time)
    return timestamp

def display_dict(dict_data):
  print(json.dumps(dict_data, indent=2))

def display_table(table_data):
    table_output = tabulate(tabular_data=table_data, headers="keys", tablefmt="simple_grid", showindex=False)
    pydoc.pager(table_output)
    # print(table_output)

def parse_input_details(resource):
    parts = resource.split("/")
    account = "/".join(parts[:2])
    product_details = parts[-1]
    channel, content_lang, feed_label, offer_id = product_details.split("~")
    return account, channel, content_lang, feed_label, offer_id

"""
additional output logic for later integration:

accounts_table.to_csv("accounts_data.csv", index=False)  # Save as CSV
accounts_table.to_excel("accounts_data.xlsx", index=False)  # Save as Excel

"""

# start time
start_time = time.time()

# time output
end_time = time.time()
execution_time = end_time - start_time
# print(f"Total execution time: {execution_time}")