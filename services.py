# imports
import pandas as pd
import json
import pydoc
import re
import random
import time
from datetime import datetime
from tabulate import tabulate
import helpers
from auth import Configure as ac
from google.api_core.exceptions import TooManyRequests
from google.shopping.type import Channel
from google.shopping.merchant_accounts_v1beta import (
    AccountsServiceClient, 
    GetAccountRequest, 
    AccountIssueServiceClient, 
    ListAccountIssuesRequest)
from google.shopping.merchant_datasources_v1beta import (
    DataSourcesServiceClient, 
    FileUploadsServiceClient, 
    ListDataSourcesRequest, 
    FetchDataSourceRequest, 
    GetFileUploadRequest)
from google.shopping.merchant_products_v1beta import (
    ProductsServiceClient,
    ListProductsRequest,
    GetProductRequest,
    ProductInput,
    Attributes,
    ProductInputsServiceClient,
    InsertProductInputRequest)

# accounts
def get_accounts(credentials):
    """Retrieves all top and sub-account information and returns as a dictionary and table."""
    client = AccountsServiceClient(credentials=credentials)
    account_count = 0
    merchant_ids = ac.read_merchant_ids()
    accounts_data = []
    for merchant in merchant_ids:
        prop_name = merchant.get('propName')
        merchant_id = merchant.get('merchantId')
        if not merchant_id:
            print(f"Skipping entry {prop_name} due to missing 'merchantId'")
            continue
        parent = f"accounts/{merchant_id}"
        request = GetAccountRequest(name=parent)
        try:
            response = client.get_account(request=request)
            account_info = {
                "prop": prop_name,
                "parent": parent,
                "account_id": response.account_id,
                "account_name": response.account_name,
                "time_zone": response.time_zone.id if response.time_zone else None,
                "language_code": response.language_code
            }
            accounts_data.append(account_info)
            account_count += 1
        except RuntimeError as e:
            print(f"Failed to fetch account info for {prop_name}: \n{e}")
    # transform to dict
    prop_dict = {account['prop']: account for account in accounts_data}
    # transform to df to create table
    prop_table = pd.DataFrame(accounts_data).sort_values('prop')
    return prop_dict, prop_table, account_count

def get_account_errors(credentials):
    """Retrieves all account issues for a list of merchant accounts."""
    client = AccountIssueServiceClient(credentials=credentials)
    account_issues_count = 0
    merchant_ids = ac.read_merchant_ids()
    account_issues_data = []
    for merchant in merchant_ids:
        prop_name = merchant.get("propName")
        merchant_id = merchant.get("merchantId")
        if not merchant_id:
            print(f"Merchant ID missing for {prop_name}! Skipping...")
            continue
        parent = f"accounts/{merchant_id}"
        request = ListAccountIssuesRequest(parent=parent)
        try:
            response = client.list_account_issues(request=request)
            prop_issue_count = 0  # issue tracking for specific prop
            for issue in response:        
                account_issue = {
                    "prop": prop_name,
                    "mID": merchant_id,
                    "issueID": issue.name,
                    "title": issue.title,
                    "severity": issue.severity.name,  # Convert severity enum to string ?
                    "detail": issue.detail,
                    "doc_uri": issue.documentation_uri,
                }
                account_issues_data.append(account_issue)
                account_issues_count += 1
                prop_issue_count += 1
            # print(f"'{prop_name}' has {prop_issue_count} issue(s).")
        except RuntimeError as e:
            print(f"An error occurred while fetching issues for {prop_name}:")
            print(e)
        except Exception as e:
            print(f"Unexpected error for {prop_name}: {e}")
    # sort issues by severity (CRITICAL > ERROR > SEVERITY_UNSPECIFIED > SUGGESTION).
    severity_order = {"CRITICAL": 1, "ERROR": 2, "SEVERITY_UNSPECIFIED": 3, "SUGGESTION": 4}
    account_issues_data.sort(key=lambda x: severity_order.get(x["severity"], 5))
    # transform to df table
    account_issues_table = (
        pd.DataFrame(account_issues_data).sort_values('prop') 
        if account_issues_data 
        else pd.DataFrame())
    return account_issues_data, account_issues_table, account_issues_count

# feeds / data sources
def get_feeds_list(credentials):
    """Complies the `DataSource` resources for all accounts in the merchant-info file.
    Returns a list of feed status data and a formatted DataFrame."""
    client = DataSourcesServiceClient(credentials=credentials)
    feed_count = 0
    merchant_ids = ac.read_merchant_ids()
    all_feed_data = []
    for merchant in merchant_ids:
        prop_name = merchant.get("propName")
        merchant_id = merchant.get("merchantId")
        if not merchant_id:
            print(f"Merchant ID missing for {prop_name}! Skipping...")
            continue
        parent = f"accounts/{merchant_id}"
        request = ListDataSourcesRequest(parent=parent)
        try:
            response = client.list_data_sources(request=request)
            for data_source in response.data_sources:
                feed_type = next(
                    (
                        attr.replace("_data_source", "")
                        for attr in [
                            "primary_product_data_source",
                            "supplemental_product_data_source",
                            "local_inventory_data_source",
                            "regional_inventory_data_source",
                            "promotion_data_source",
                        ]
                        if getattr(data_source, attr, None)
                    ),
                    "undefined",
                )
                url = getattr(data_source.file_input.fetch_settings, "fetch_uri", None)
                if feed_type == "undefined" and url:
                    feed_type = "review"
                prop_feed_data = {
                    "prop": prop_name,
                    "mID": merchant_id,
                    "feed_name": data_source.display_name,
                    "feed_id": data_source.data_source_id,
                    "feed_type": feed_type,
                    "url": url,
                    "feed_resource_id": data_source.name
                }
                all_feed_data.append(prop_feed_data)
                feed_count += 1
        except RuntimeError as e:
            print(f"List request failed for {prop_name}: {e}")
        except Exception as e:
            print(f"Unexpected error for {prop_name}: {e}")
    feed_table = (
        pd.DataFrame(all_feed_data).sort_values('prop')
        if all_feed_data
        else pd.DataFrame()
    )
    return all_feed_data, feed_table, feed_count

def get_feed_status(credentials, all_feed_data):
    """
    Fetches the processing status of each feed in `all_feed_data`.
    If the processing state is FAILED, collects issues and allows reprocessing.
    Implements rate limiting and retries on 429 errors.
    Returns a list of feed status data and a formatted DataFrame.
    """
    client = FileUploadsServiceClient(credentials=credentials)
    feed_status_data = []
    failed_feeds = []
    fail_count = 0
    not_fail_count = 0
    request_interval = 0.25  # 4 requests/sec limit (500 per minute)
    max_retries = 5
    base_sleep = 1.0
    for idx, feed in enumerate(all_feed_data):
        prop_name = feed["prop"]
        merchant_id = feed["mID"]
        url = feed["url"]
        upload_id = f"{feed['feed_resource_id']}/fileUploads/latest"
        request = GetFileUploadRequest(name=upload_id)
        retries = 0
        while retries <= max_retries:
            try:
                response = client.get_file_upload(request=request)
                processed_status = response.processing_state.name
                if processed_status == "FAILED" and response.issues:
                    for issue in response.issues:
                        failed_feed_data = {
                            "prop": prop_name,
                            "mID": merchant_id,
                            "feed_name": response.feed_name,
                            "feed_id": response.feed_id,
                            "status": processed_status,
                            "issue_title": issue.title,
                            "issue_severity": issue.severity.name,
                            # "issue_desc": issue.description, 
                            # "items_total": response.items_total,
                            # "items_created": response.items_created,
                            # "items_updated": response.items_updated,
                            # "upload_time": response.upload_time,
                            "feed_url": url,
                        }
                        status_data = {
                            "prop": prop_name,
                            "mID": merchant_id,
                            "feed_name": response.feed_name,
                            "feed_id": response.feed_id,
                            "status": processed_status,
                            "items_total": response.items_total,
                            "feed_url": url,
                        }
                        failed_feeds.append(failed_feed_data)
                        feed_status_data.append(status_data)
                    fail_count += 1
                else:
                    status_data = {
                        "prop": prop_name,
                        "mID": merchant_id,
                        "feed_name": response.feed_name,
                        "feed_id": response.feed_id,
                        "status": processed_status,
                        "items_total": response.items_total,
                        "feed_url": url,
                    }
                    feed_status_data.append(status_data)
                    # print(f"Prop: {prop_name} / Feed: {feed['feed_name']} - Status: {processed_status}")
                    # print(f"Prop: {prop_name} / Feed {idx + 1}/{len(all_feed_data)}: {feed['feed_name']} - Status: {processed_status}")
                    not_fail_count += 1
                time.sleep(request_interval)
                break  # if success exit retry loop
            except TooManyRequests as e:
                if retries == max_retries:
                    print(f"Max retries reached for {prop_name} / Feed: {feed['feed_name']}. Skipping...")
                    break
                wait_time = base_sleep * (2 ** retries) + random.uniform(0, 0.5)
                print(f"Rate limit reached for {prop_name} / Feed: {feed['feed_name']}, Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                retries += 1
            except Exception as e:
                error_message = str(e).split("\n")[0]
                print(f"\nERROR: {prop_name} / {feed['feed_name']} - {error_message}\n")
                break
    severity_order = {"FAILED": 1, "IN_PROGRESS": 2, "PROCESSING_STATE_UNSPECIFIED": 3, "SUCCEEDED": 4}
    feed_status_data.sort(key=lambda x: severity_order.get(x['status'], 5))
    feed_status_table = (
        pd.DataFrame(feed_status_data).sort_values("prop")
        if feed_status_data else pd.DataFrame()
    )
    return feed_status_data, feed_status_table, failed_feeds, fail_count, not_fail_count

def fetch_feed(credentials, feed_info):
    """
    Reprocesses feeds with errors by calling `fetch_data_source`.
    """
    client = DataSourcesServiceClient(credentials=credentials)
    for feed in feed_info:
        prop_name = feed["prop"]
        try:
            request = FetchDataSourceRequest(name=feed["feed_resource_id"])
            print(f"Reprocessing initiated for feed: {prop_name} / {feed['feed_name']}")
            response = client.fetch_data_source(request=request)
        except Exception as e:
            print(f"Error fetching status for: {prop_name} / {feed['feed_name']}: \n{e}")

# products
def get_product_single(credentials):
    """Gets the specified `Product` resource."""
    client = ProductsServiceClient(credentials=credentials)
    product_resource_id = input("Enter a product resource name: ")
    request = GetProductRequest(name=product_resource_id)
    try:
        response = client.get_product(request=request)
        original_product_info = response
        product_entry = {
            "feed_resource_id": response.data_source,
            "product_resource_id": response.name,
            "productID": response.offer_id,
            "product_name": str(getattr(response.attributes, "title", None)),
            "product_price": getattr(response.attributes, "price", None),
            "product_sale_price": getattr(response.attributes,"sale_price", None),
            "product_link": str(getattr(response.attributes, "link", None)),
            "mobile_link": str(getattr(response.attributes, "mobile_link", None)),
            "canonical_link": str(getattr(response.attributes, "canonical_link", None)),
            "image_link": str(getattr(response.attributes, "image_link", None)),
            "ads_redirect": str(getattr(response.attributes, "ads_redirect", None)),
            "display_ads_link": str(getattr(response.attributes, "display_ads_link", None)),
            "link_template": str(getattr(response.attributes, "link_template", None)),
            "mobile_link_template": str(getattr(response.attributes, "mobile_link_template", None)),
            "gtin": str(getattr(response.attributes, "gtin", None)),
        }
        if hasattr(response, "custom_attributes"):
            product_entry["custom_attributes"] = [
                {"name": attr.name, "value": attr.value} for attr in response.custom_attributes]
        return product_entry, original_product_info
    except RuntimeError as e:
        print("Get failed")
        print(e)

def get_product_auto(credentials, product_id):
    """Gets the specified `Product` resource from 
    a supplied CSV or processed disapproved product data"""
    client = ProductsServiceClient(credentials=credentials)
    request = GetProductRequest(name=product_id)
    try:
        response = client.get_product(request=request)
        original_product_info = response
        product_entry = {
            "feed_resource_id": response.data_source,
            "product_resource_id": response.name,
            "productID": response.offer_id,
            "product_name": str(getattr(response.attributes, "title", None)),
            "product_price": getattr(response.attributes, "price", None),
            "product_sale_price": getattr(response.attributes,"sale_price", None),
            "product_link": str(getattr(response.attributes, "link", None)),
            "mobile_link": str(getattr(response.attributes, "mobile_link", None)),
            "canonical_link": str(getattr(response.attributes, "canonical_link", None)),
            "image_link": str(getattr(response.attributes, "image_link", None)),
            "ads_redirect": str(getattr(response.attributes, "ads_redirect", None)),
            "display_ads_link": str(getattr(response.attributes, "display_ads_link", None)),
            "link_template": str(getattr(response.attributes, "link_template", None)),
            "mobile_link_template": str(getattr(response.attributes, "mobile_link_template", None)),
            "gtin": str(getattr(response.attributes, "gtin", None)),
        }
        if hasattr(response, "custom_attributes"):
            product_entry["custom_attributes"] = [
                {"name": attr.name, "value": attr.value} for attr in response.custom_attributes
            ]
        # print(f"Product: {product_entry['product_resource_id']} - success")
        return product_entry, original_product_info
    except RuntimeError as e:
        print(f"Get failed for {product_id}: {e}")
        return None

def create_product_input(product_resource_id, original_product_entry):
    """Creates a `ProductInput` resource by copying existing attributes."""
    # Product resource name/ID has the format `channel~contentLanguage~feedLabel~offerId`
    account, channel, content_lang, feed_label, offer_id = helpers.parse_input_details(
        resource=product_resource_id
    )
    attributes = getattr(original_product_entry, "attributes", Attributes())
    product_input_update = ProductInput(
        channel=Channel.ChannelEnum.ONLINE,
        offer_id=offer_id,
        content_language=content_lang,
        feed_label=feed_label,
        attributes=attributes
    )
    return product_input_update, account

def insert_product_input(credentials, product_account, product_data_source, update_insert):
    # update_item as universal param for other product field update uses
    client = ProductInputsServiceClient(credentials=credentials)
    request = InsertProductInputRequest(
        parent=product_account,
        data_source=product_data_source,
        product_input=update_insert,
        )
    try:
        response = client.insert_product_input(request=request)
        # product ID returned as response
        print(f"Input success!\n{response}")
    except RuntimeError as e:
        print ("Input failed")
        print (e)

def disapproved_products(credentials, prod_menu_choice):
    """Lists and filters the disapproved `Product` resources for a given account with pagination."""
    client = ProductsServiceClient(credentials=credentials)
    merchant_ids = ac.read_merchant_ids()
    disapproved_product_data = []    
    for merchant in merchant_ids:
        prop_name = merchant.get("propName")
        merchant_id = merchant.get("merchantId")
        if not merchant_id:
            print(f"Skipping entry {prop_name} due to missing 'merchantId'")
            continue        
        parent = f"accounts/{merchant_id}"
        page_token = None        
        while True:
            request = ListProductsRequest(parent=parent, page_token=page_token, page_size=250)
            try:
                response = client.list_products(request=request)                
                for product in response.products:
                    product_name = getattr(product.attributes, "title", None)
                    product_link = getattr(product.attributes, "link", None)
                    product_price = getattr(product.attributes, "price", None)
                    product_sale_price = getattr(product.attributes,"sale_price", None)
                    feed_label = getattr(product.attributes, "feedLabel", None)
                    mobile_link = getattr(product.attributes, "mobile_link", None)
                    canonical_link = getattr(product.attributes, "canonical_link", None)
                    image_link = getattr(product.attributes, "image_link", None)
                    ads_redirect = getattr(product.attributes, "ads_redirect", None)
                    display_ads_link = getattr(product.attributes, "display_ads_link", None)
                    link_template = getattr(product.attributes, "link_template", None)
                    mobile_link_template = getattr(product.attributes, "mobile_link_template", None)
                    gtin = getattr(product.attributes, "gtin", None)
                    advertised_price = product_sale_price if product_sale_price else product_price              
                    for destination in product.product_status.destination_statuses:
                        if not destination.disapproved_countries:
                            continue  # skip if no disapprovals
                        for issue in product.product_status.item_level_issues:
                            issue_code = issue.code if issue else ""
                            issue_severity = issue.severity.name if issue.severity else None
                            issue_attribute = issue.attribute if issue else ""
                            issue_description = issue.description if issue else ""                          
                            conditions = { # define opt conditions
                                "all_disapproved": issue_severity and issue_severity != "NOT_IMPACTED",
                                "landing_page_errors": "landing_page_error" in issue_code,
                                "broken_images": issue_code == "image_link_broken",
                                "price_updates": "price" in issue_attribute,
                                "policy_violations": "policy_violation" in issue_code,
                                "invalid_upc": "invalid_upc" in issue_code,
                                "no_impact": issue_severity == "NOT_IMPACTED",
                            }
                            if conditions.get(prod_menu_choice, False):
                                product_entry = {
                                    "prop": prop_name,
                                    "merchantID": merchant_id,
                                    "productID": product.offer_id,
                                    "sold_price": advertised_price,
                                    "product_name": product_name,
                                    "product_link": product_link,
                                    "product_resource_id": product.name,
                                    "feed_label": feed_label,                                    
                                    "i_code": issue_code,
                                    "i_severity": issue_severity,
                                    "i_attribute": issue_attribute,
                                    "i_description": issue_description,
                                    # "mobile_link": mobile_link,
                                    # "canonical_link": canonical_link,
                                    # "ads_redirect" : ads_redirect,
                                    # "display_ads_link" : display_ads_link,
                                    # "link_template" : link_template,
                                    # "mobile_link_template" : mobile_link_template,
                                }
                                # image_link or gtin if opt
                                if prod_menu_choice == "broken_images":
                                    product_entry["imageLink"] = image_link
                                if prod_menu_choice == "invalid_upc":
                                    product_entry["gtin"] = gtin
                                # remove dupes if any (due to multiple variants related to source product)                                
                                if product_entry not in disapproved_product_data:
                                  disapproved_product_data.append(product_entry)
                page_token = response.next_page_token
                if not page_token:
                    break
            except RuntimeError as e:
                print(f"List request failed for merchant {prop_name} (ID: {merchant_id})")
                print(e)
                break
    disapproved_product_count = len(disapproved_product_data)
    disapproved_product_data_table = (
        pd.DataFrame(disapproved_product_data).sort_values("prop")
        if disapproved_product_data
        else pd.DataFrame()
    )
    return disapproved_product_data, disapproved_product_data_table, disapproved_product_count

def process_lp_errors_multi(credentials):
    """Processes product entries with landing page errors 
    from a CSV or processed 'disapproved product' list."""
    print("\nLanding Page Errors Report\n"
          "Choose an option:\n"
          "1. Provide a CSV file with product_resource_id values\n"
          "2. Process all products with landing page errors\n")
    choice = input("Enter 1 or 2: ").strip()
    product_ids = []
    if choice == "1":
        file_path = input("Enter the path to the CSV file: ").strip()
        try:
            df = pd.read_csv(file_path)
            if "product_resource_id" not in df.columns:
                print("Error: CSV must contain a 'product_resource_id' column.")
                return []            
            product_ids = df["product_resource_id"].dropna().astype(str).tolist()
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return []
    elif choice == "2":
        lp_errors_data, _ = disapproved_products(credentials=credentials, prod_menu_choice="landing_page_errors")
        product_ids = [item["product_resource_id"] for item in lp_errors_data]
    else:
        print("Invalid choice. Please enter 1 or 2.")
        return []
    if not product_ids:
        print("No product IDs found to process.")
        return []
    print(f"Processing {len(product_ids)} products...")
    all_lp_errors_data = []
    for product_id in product_ids:
        try:
            product_data, original_product_entry = get_product_auto(credentials, product_id)
            if isinstance(product_data, dict):
                all_lp_errors_data.append(product_data)
            else:
                print(f"Error: Unexpected return type for {product_id}: {type(product_data)}")
        except Exception as e:
            print(f"Failed to fetch data for {product_id}: {e}")
    all_lp_errors_table = (
        pd.DataFrame(all_lp_errors_data).sort_values("product_resource_id")
        if all_lp_errors_data
        else pd.DataFrame()
    )
    return all_lp_errors_data, all_lp_errors_table