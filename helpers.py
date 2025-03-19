import random
import time
import os
import sys
import re
import json
import csv
import pydoc
import requests
from datetime import datetime
import pandas as pd
from tabulate import tabulate
from urllib.parse import urljoin, urlparse

create_feed_info_message = (" - Account ID: The Merchant Center account ID (e.g. '1234567890')\n"
" - Feed name: The displayed name of the feed (e.g. 'Tennis Racquets')\n"
" - Fetch URI: The URL to fetch the feed data (e.g. 'https://www.example.com/feed.xml')\n"
" - Content Language: The language of the feed data (e.g. 'en')\n"
" - Countries: The countries the feed is targeting (e.g. 'US,CA,MX')\n"
" - Feed Label: The label for the feed (e.g. 'Tennis')\n")

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

def process_file(file_path):
    """Parses the CSV file and returns structured feed data."""
    feed_data = []
    required_headers = {"account_id","name", "url", "lang", "country", "label"}
    try:
        with open(file_path, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file, delimiter=',')  # ',' if comma-separated / '\t' if tab-separated
            if not required_headers.issubset(reader.fieldnames):
                raise ValueError(f"CSV file is missing required headers: {required_headers - set(reader.fieldnames)}")
            for row in reader:
                feed_entry = {
                    "account_id": row["account_id"], 
                    "feed_name": row["name"],
                    "fetch_uri": row["url"],
                    "content_lang": row["lang"],
                    "countries": row["country"],
                    "feed_label": row["label"]
                }
                feed_data.append(feed_entry)
    except Exception as e:
        print(f"Error processing file: {e}")
        return None
    return feed_data

"""
additional output logic for later integration:

accounts_table.to_csv("accounts_data.csv", index=False)  # Save as CSV
accounts_table.to_excel("accounts_data.xlsx", index=False)  # Save as Excel

# start time
start_time = time.time()

# time output
end_time = time.time()
execution_time = end_time - start_time
print(f"Total execution time: {execution_time}")
"""