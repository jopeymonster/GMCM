# imports
from __future__ import print_function
import time
import json
import sys
import argparse
from datetime import datetime
from typing import Tuple, Union, Optional, Dict, List, Any
from tabulate import tabulate
import auth
from auth import Configure as ac
import services
import helpers


def main_menu():
    # init
    timestamp = helpers.generate_timestamp()
    print("\n----- Google Merchant Center Manager by JDT using Merchant API and gRPC -----\n"
          "                 ------------- TESTING -------------\n")
    print("Authorizing access and initalizing services...")
    credentials = auth.authorize()
    print("Authorization approved, retrieving account information...")
    prop_dict, prop_table, account_count = services.get_accounts(credentials)
    while True:
        print("Please choose an option from the list below:\n"
              "1. Accounts Info Review - display accounts info\n"
              "2. Account Issues Audit - retrieve any account wide problems\n"
              "3. Feeds Report - fetch datasources for feeds review\n"
              "4. Product Report - request all or specific product level issues\n"
              # "5. Products Update - TESTING LP\n"
              "ex = Exit at any time")
        menu_choice = helpers.custom_input("\nSelect an option from above to execute the corresponding test: ").lower().strip()
        if menu_choice == "1":
            print(f"Total number of accounts: {account_count}\n")
            print("Display Property Info?")
            output_opt = input("Yes or No (Y or N): ").lower().strip()
            if output_opt == "y":
                helpers.display_table(table_data=prop_table)
            print("Save property info to a CSV file?")
            save_opt = input("Yes or No (Y or N): ").lower().strip()
            if save_opt == "y":
                prop_list_filename = f"property_mca_list-{timestamp}.csv"
                print(f"\nSaving file for review as {prop_list_filename}\n")
                prop_table.to_csv(prop_list_filename, index=False)
            else:
                break
        elif menu_choice == "2":
            get_account_issues(credentials, prop_dict, prop_table, account_count)
        elif menu_choice == "3":
            feeds_report(credentials)
        elif menu_choice == "4":
            products_report(credentials)
        elif menu_choice =="5":
            products_update(credentials)
        else:
            print("Please select a valid option.")

def get_account_issues(credentials, prop_dict, prop_table, account_count):
    timestamp = helpers.generate_timestamp()
    start_time = time.time()
    print("Account information obtained... retrieving all account issues...")
    account_issues_data, account_issues_table, account_issues_count = services.get_account_errors(credentials)
    end_time = time.time()

    # Output testing for account_errors
    """ 
    print("\nOutputting raw account_errors data for review: \n")
    features.display_dict(dict_data=account_issues_data)
    """    
    execution_time = f"Total execution time: {round(end_time - start_time, 2)} seconds"
    print(f"Errors compiled, time and date of request: {timestamp}\n"
          f"Total number of account issues: {account_issues_count}\n"
          f"{execution_time}\n"
          "View account errors report?")
    output_opt = input("Yes or No (Y or N): ").lower().strip()
    if output_opt == "y":
        helpers.display_table(table_data=account_issues_table)
    print("Save property info to a CSV file?")
    save_opt = input("Yes or No (Y or N): ").lower().strip()
    if save_opt == "y":
        account_issues_filename = f"account_errors-{timestamp}.csv"
        print(f"\nSaving file for review as {account_issues_filename}\n")
        account_issues_table.to_csv(account_issues_filename, index=False)

def feeds_report(credentials):
    timestamp = helpers.generate_timestamp()
    start_time_fetch = time.time()
    print("Fetching feed data...")
    all_feed_data, feed_table, feed_count = services.get_feeds_list(credentials)
    print("Feed data obtained, processing statuses...")
    feed_status_data, feed_status_table, failed_feeds, fail_count, not_fail_count = services.get_feed_status(credentials, all_feed_data)
    end_time_fetch = time.time()
    # Output testing for feed_report
    """
    print("\nOutputting raw feed_status_data for review: \n")
    services.display_dict(dict_data=feed_status_data)
    """
    print(f"There were {not_fail_count} feeds without issues :) ")
    total_time_fetch = float(round(end_time_fetch - start_time_fetch, 2))
    total_time_fetch_string = f"Time fetching feeds: {total_time_fetch} seconds"
    print(f"Feed fetching complete!\n")
    reprocess_start_time = time.time()
    if fail_count > 0:
        print(f"\nBUT there are {fail_count} FAILED feeds...\n")
        print("Would you like to view the failed feed data?")
        view_fails = input("Enter Y to retry, N to exit: ").strip().upper()
        if view_fails == "Y":
            # print(failed_feeds)
            # helpers.display_table(table_data=failed_feeds)
            # display without pydoc for easy review (short list)
            table_output = tabulate(tabular_data=failed_feeds, headers="keys", tablefmt="simple_grid", showindex=False)
            print(table_output)
        print("\nWould you like to fetch them for reprocessing?")
        retry = input("Enter Y to retry, N to exit: ").strip().upper()
        if retry == "Y":
            print("\nReprocessing failed feeds...")
            services.fetch_feed(credentials, feed_info=failed_feeds)
            print("Reprocessing complete!\n")
    reprocess_end_time = time.time()
    reprocess_total_time = round(reprocess_end_time - reprocess_start_time, 2)
    reprocess_total_time_string = f"Time for reprocessing: {reprocess_total_time} seconds"
    total_feed_processing_time = float(round(total_time_fetch + reprocess_total_time, 2))
    total_feed_processing_time_string = f"Total feed processing execution time: {total_feed_processing_time}"
    print(f"Feed report complete, time and date of request: {timestamp}\n"
          f"Total number of feeds: {feed_count}\n"
          f"Feeds without problems: {not_fail_count}\n"
          f"Number of FAILED feeds: {fail_count}\n"
          f"{total_time_fetch_string}\n"
          f"{reprocess_total_time_string}\n"
          f"{total_feed_processing_time_string}\n")
    print("Would you like to view the results?\n"
          "Enter Y for viewing options, N to return to main menu, or ex to quit immediately")
    view_choice = input("Enter an option from above, Y or N: ").strip().upper()
    if view_choice == "Y":
        print("\nHow would you like to view the feed report?\n"
            "1. View a table on screen\n"
            "2. Download a CSV of the report\n")
        report_choice = input("Select 1 or 2: ").strip().upper()
        if report_choice == "1":
            helpers.display_table(table_data=feed_status_table)
        elif report_choice == "2":
            feeds_status_filename = f"feeds_status-{timestamp}.csv"
            print(f"\nSaving file for review as {feeds_status_filename}\n")
            feed_table.to_csv(feeds_status_filename, index=False)
    elif view_choice == "N":
        print("\nReturning to main menu...")
    else:
        print("Please select a valid option.")

def products_report(credentials):
    timestamp = helpers.generate_timestamp()
    while True:
        print("Products List Options: \n"
            "1. Retrieve all disapproved product issues\n"
            "2. Mobile and desktop landing page errors\n"
            "3. Broken image links\n"
            "4. Price display updates\n"
            "5. Policy violations\n"
            "6. Invalid GTIN/UPC audit\n"
            "7. Other issues (non-impactful)\n"
            "8. Get info for a single product\n"
            # "9. Get info for multiple products\n"
            "ex. Type 'EX' at anytime to quit\n")
        prod_menu_opt = helpers.custom_input("Select a number option from the above (e.g. 1, 2, 3, etc... ):  ").strip()
        if prod_menu_opt == "1":
            prod_menu_choice = "all_disapproved"
        elif prod_menu_opt == "2":
            prod_menu_choice = "landing_page_errors"
        elif prod_menu_opt == "3":
            prod_menu_choice = "broken_images"
        elif prod_menu_opt == "4":
            prod_menu_choice = "price_updates"
        elif prod_menu_opt == "5":
            prod_menu_choice = "policy_violations"
        elif prod_menu_opt == "6":
            prod_menu_choice = "invalid_upc"
        elif prod_menu_opt == "7":
            prod_menu_choice = "no_impact"
        elif prod_menu_choice == "8":
            product_entry, original_product_entry = services.get_product_single(credentials)
            print("Success, product details: \n")
            print(json.dumps(product_entry, indent=2))
            # print (original_product_entry)
        # elif prod_menu_choice == "9":   
        else:
            print("Select from the numbered options only (1-9)")
        print(f"Executing {prod_menu_choice} report...")
        start_time = time.time()
        disapproved_product_data, disapproved_product_data_table, disapproved_product_count = services.disapproved_products(credentials, prod_menu_choice)
        end_time = time.time()
        execution_time = f"Total execution time: {round(end_time - start_time, 2)} seconds"
        print(f"Disapproved products compiled, time and date of request: {timestamp}\n"
              f"Total number of disapproved products: {disapproved_product_count}\n"
              f"{execution_time}\n"
              "View products errors report?")
        output_opt = input("Yes or No (Y or N): ").lower().strip()
        if output_opt == "y":
            helpers.display_table(table_data=disapproved_product_data_table)
        print("Save report info to a CSV file?")
        save_opt = input("Yes or No (Y or N): ").lower().strip()
        if save_opt == "y":
            disapproved_product_data_filename = f"{prod_menu_choice}-{timestamp}.csv"
            print(f"\nSaving file for review as {disapproved_product_data_filename}\n")
            disapproved_product_data_table.to_csv(disapproved_product_data_filename, index=False)

def products_update(credentials):
    """
    DO NOT USE
    For creating or inserting using API
    Cannot use API methods to update products from feed files
    """
    start_time = time.time()
    timestamp = helpers.generate_timestamp()
    while True:
        print("Update Product Info Options\n"
              "TESTING - Update the landing page URLs for: \n"
              "1. Multiple products via disapproved report or CSV\n"
              "2. A single product using the product_resource_id\n"
              "ex. Type 'EX' at anytime to quit\n")
        product_update_choice = helpers.custom_input("Enter 1 or 2: ").strip()
        if product_update_choice == "1":
            all_lp_errors_data, all_lp_errors_table = services.process_lp_errors_multi(credentials)
            # Output testing for all_lp_errors_data
            # input("Press ENTER to display product data...")
            # print(all_lp_errors_data)
            # services.display_dict(dict_data=all_lp_errors_data)
            # helpers.display_table(table_data=all_lp_errors_table)
        if product_update_choice == "2":
            product_entry, original_product_entry = services.get_product_single(credentials)
            product_link = product_entry["product_link"]
            product_resource_id = product_entry["product_resource_id"]
            product_data_source = product_entry["feed_resource_id"]
            print("Product fetch success, validate info below for reprocessing...\n"
                  f"Product LP URL: {product_link}\n"
                  f"Resource ID: {product_resource_id}\n"
                  f"Feed ID: {product_data_source}\n")
            update_opt = input("Update disapproved product? Y or N: ").lower().strip()
            if update_opt == "y":
                product_input_update, account = services.create_product_input(product_resource_id, original_product_entry)
                print("Review product data for updating: \n"
                      f"Original product info: \n{original_product_entry}\n"
                      f"Product insert info: \n{product_input_update}\n")
                input("Press ENTER to send update request...")
                services.insert_product_input(
                    credentials,
                    product_account=account,
                    product_data_source=product_data_source, 
                    update_insert=product_input_update,
                    )
            else:
                break
        else:
            print("Select option 1 or 2")
        end_time = time.time()
        execution_time = f"Total execution time: {round(end_time - start_time, 2)} seconds"

def auto_exec(main_flags: argparse.Namespace):
    timestamp = helpers.generate_timestamp()    
    print("\n----- Google Merchant Center Manager by JDT using Merchant API and gRPC -----\n")
    print("Authorizing access...")
    credentials = auth.authorize()
    print("Authorization approved, initalizing services...")
    if main_flags.auto == "feeds":
        print("\n------------- AUTOMODE = FEED REPORT -------------\n")
        feeds_report(credentials)
    elif main_flags.auto == "accountissues":
        print("\n------------- AUTOMODE = ACCOUNT ISSUES REPORT -------------\n")
        prop_dict, prop_table, account_count = services.get_accounts(credentials)
        get_account_issues(credentials, prop_dict, prop_table, account_count)
    elif main_flags.auto == "lperrors":
        print("\n------------- AUTOMODE = PRODUCT ERRORS REPORT -------------\n")
        prod_menu_choice = "landing_page_errors"
        print(f"Executing {prod_menu_choice} report...")
        start_time = time.time()
        disapproved_product_data, disapproved_product_data_table, disapproved_product_count = services.disapproved_products(credentials, prod_menu_choice)
        end_time = time.time()
        execution_time = f"Total execution time: {round(end_time - start_time, 2)} seconds"
        print(f"Disapproved products compiled, time and date of request: {timestamp}\n"
              f"Total number of disapproved products: {disapproved_product_count}\n"
              f"{execution_time}\n"
              "View product errors report?")
        output_opt = input("Yes or No (Y or N): ").lower().strip()
        if output_opt == "y":
            helpers.display_table(table_data=disapproved_product_data_table)
        print("Save report info to a CSV file?")
        save_opt = input("Yes or No (Y or N): ").lower().strip()
        if save_opt == "y":
            disapproved_product_data_filename = f"{prod_menu_choice}-{timestamp}.csv"
            print(f"\nSaving file for review as {disapproved_product_data_filename}\n")
            disapproved_product_data_table.to_csv(disapproved_product_data_filename, index=False)
    else:
        print(f"Invalid argument input: {main_flags}\n"
              "Please try again, use '--help' for more info.")
        sys.exit(1)

@helpers.handle_exceptions
def main() -> None:
    parser = argparse.ArgumentParser(
        prog='GMCM',
        description='Google Merchant Center Manager',
        epilog='Developed by Joe Thompson',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--auto',
        choices=['feeds','accountissues','lperrors'],
        help=("Automated startup options:\n"
              "feeds = Report all failed feed fetch attempts with option to reprocess any failures\n"
              "accountissues = Retrieve all account wide issues violating specifications or rules\n"
              "lperrors = Generates a report of all disapproved products due to landing_page_error\n")
    )
    main_flags: argparse.Namespace = parser.parse_args()
    if main_flags.auto is None:
        main_menu()
    else:
        auto_exec(main_flags)

if __name__ == '__main__':
    main()