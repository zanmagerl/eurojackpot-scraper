import os
import logging
from typing import List
import requests
import google.cloud.logging

from time import strptime
from lxml import html
from datetime import datetime, date
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from time import mktime
from flask import Response

# Setups GCP logging
client = google.cloud.logging.Client()
client.setup_logging()

# Site with newest Eurojackpot results
RESULT_SITE = 'https://www.lottoland.com/en/eurojackpot/results-winning-numbers'

# XPaths
NUMBERS_FRESHNESS_XPATH = '/html/body/div[10]/div[4]/div/div/div[2]/div[2]/div[2]/div/article/ll-lottery-ctx/article/section/header/text()'
MAIN_NUMBERS_XPATH = '//@numbers'
SUPPLEMENTARY_NUMBERS_XPATH = '//@extranumbers'

# Email requirements
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
RECIPIENT_EMAILS = os.getenv('RECIPIENT_EMAILS')
EMAIL_SUBJECT = 'This week\'s Eurojackpot numbers'

# Sendgrid API key
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

def __construct_mail(recipient: str, content: str) -> Mail:
    """
    Constructs email object that is required by SendGrid library.
    :param recipient: email address of the recipient
    :param content: content of the email - in this case Eurojackpot numbers: Example: [1, 12, 34, 42, 49] + [1, 7]
    :return: SendGrid's Mail object that contains all required data
    """
    return Mail(
        from_email=SENDER_EMAIL,
        to_emails=recipient,
        subject=EMAIL_SUBJECT,
        html_content=content
    )

def __are_numbers_fresh(date_section: str) -> bool:
    """ 
    Checks if date on the page matches today's date.
    :param date_section: date section on the Eurojackpot page. Example: Friday 18 Nov 2022
    :return: True if the date is the same as today and False otherwise
    """
    parsed_date = "-".join(list(map(lambda x: x.strip(), date_section.split(" ")))[-3:])
    timestamp = strptime(parsed_date, "%d-%b-%Y")
    return datetime.fromtimestamp(mktime(timestamp)).date() == date.today()

def __get_emails() -> List[str]:
    """
    Returns list of recipient emails. Emails are given with string separated by '&'.
    :return: list of emails.
    """
    return RECIPIENT_EMAILS.split("&")

def retrieve_numbers(event, context):
    """
    Function entry point for Google Cloud Function execution lifecycle.
    :raises Exception: if numbers are not ready or there is an error with sending email. Infrastructure will then retry the execution of the function.
    :return: HTTP 200 is the numbers were successfully retrieved
    """
    
    logging.info("Retrieving latest available Eurojackpot numbers")

    page = requests.get(RESULT_SITE)

    tree = html.fromstring(page.content)

    numbers_freshness = tree.xpath(NUMBERS_FRESHNESS_XPATH)[0]

    if (__are_numbers_fresh(numbers_freshness)):
        logging.info("Today's number are ready")

        main_numbers = tree.xpath(MAIN_NUMBERS_XPATH)[0]
        supplementary_numbers = tree.xpath(SUPPLEMENTARY_NUMBERS_XPATH)[0]

        content = f'{main_numbers} + {supplementary_numbers}'

        messages = [__construct_mail(recipient, content) for recipient in __get_emails()]
        
        try:
            for message in messages:
                sg = SendGridAPIClient(SENDGRID_API_KEY)
                response = sg.send(message)
                logging.info(f'Status code: {response.status_code}, body: {response.body}')
            return Response(status=200)
        except Exception as e:
            logging.error("Error while sending mail: ", e)
            raise Exception("Unable to send mail")
        
    else:
        logging.warn("Numbers for today are not ready yet...")
        raise Exception("Numbers are not ready yet!")
