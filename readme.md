# Google Merchant Center Manager
This is a CLI application automates the fetching and reprocessing of data feeds, with built-in rate-limiting and error handling.
Reporting options are available in limited format.

## Features
This application was designed using Python and communciates with the Google Merchant API using gRPC methods. 
It is designed to be compliant with networking and API constraints.

### Account Info
- Audit and report on all account information and errors

### Data Sources
- Fetches and processes feeds (data sources)
- Option to automatically reprocess failed data sources

### Responsibly Developed
- **Rate Limiting**: Ensures compliance with API limits (4 requests per second)
- **Retry Strategy**: Retries on 429 errors with exponential backoff and jitter for handling API rate limits
- **Error Handling**: Logs and skips failed requests after max retries
- **Optional CLI args**: Options for automatic auditing and reporting

## Installation
To set up the Google Merchant Center Manager, complete the following steps:
1. Clone the 'GMCM' sample code from [GitHub](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository).
2. Create a folder for the authentication files within the new '/GMCM/' directory, titled 'authfiles'.
    - e.g.: <b>your-home-directory/GMCM/content/authfiles/</b>
3. Setup authentication files:
    - Go to [Google Merchant Center](https://merchants.google.com/) and obtain the API Key:
        - In Merchant Center, in the Settings menu, select Merchant API.
        - Click Authentication.
        - Click <b>'+'</b> CREATE API KEY. 
    - If prompted, read and accept the terms of service agreements. The new key downloads automatically.
        - Rename the downloaded credentials file to service-account.json.
    - Note: This filename is defined in the auth.py file, which is located in '/GMCM/' folder.
        - Move the service-account.json file to 'your-home-directory/GMCM/authfiles/' folder.
4. Setup mechant-info.json:
    - In 'your-home-directory/GMCM/authfiles/', folder create an empty merchant-info.json file.
    - In merchant-info.json, add the following text:
        - [
            {"propName": "your_acct_name", "merchantId": "acct_merchant_id"},
        ]
        - Replace <b>'your_acct_name'</b> with your account name and <b>'merchant_id'</b> with your merchant ID.
        - 'your_acct_name' is arbitrarily named and is based on your preference for display and identification.
        - 'merchant_id' is the Merchant Center merchant ID.
        - If you have multiple merchant accounts, add additional entries in the array in the same format, separated by commas:
        - [
            {"propName": "your_acct_name", "merchantId": "acct_merchant_id"},
            {"propName": "your_acct_name", "merchantId": "acct_merchant_id"},
            ..... more as needed
            ]
    - Save and close the file.

## Usage
Run the sample code: 'python you-home-directory/GMCM/main.py' (or whatever folder hierarchy you setup) and follow the prompts.
- Automated reports - Use the following arguments for automated actions:
    - '--auto feeds' = Run a status check and report all failed feed fetch attempts and item error
        - NOTE: an option for reprocessing failed feeds is provided after fetching them
        - ex: 'python you-home-directory/GMCM/main.py --auto feeds'
    - '-- auto accountissues' = Run a report and display all feeds with current status and any product error counts.
        - ex: 'python you-home-directory/GMCM/main.py --auto accountissues'
    - '--auto lperrors' = Fetch a report on all properties for all disapproved product due to landing page errors (desktop or mobile).
        - ex: 'python you-home-directory/GMCM/main.py --auto lperrors'
    - Use the '-h' or '--help' argument instead to review this list of automated options.

## License
This project is licensed under the [MIT License](LICENSE).

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Contributors
- Joe Thompson (@jopeymonster)
- https://github.com/jopeymonster


