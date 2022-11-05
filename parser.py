from time import strptime
import requests
from lxml import html
from datetime import datetime, date
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging
from time import mktime
from flask import Response
import google.cloud.logging

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

def _construct_mail(recipient: str, content: str) -> Mail:
    return Mail(
        from_email=SENDER_EMAIL,
        to_emails=recipient,
        subject=EMAIL_SUBJECT,
        html_content=content
    )

def _are_numbers_fresh(date_section: str) -> bool:
    parsed_date = "-".join(list(map(lambda x: x.strip(), date_section.split(" ")))[-3:])
    timestamp = strptime(parsed_date, "%d-%b-%Y")
    
    return datetime.fromtimestamp(mktime(timestamp)).date() != date.today()

def hello_pubsub(event, context):
    
    logging.info("Retrieving latest available Eurojackpot numbers")

    page = requests.get(RESULT_SITE)

    tree = html.fromstring(page.content)

    numbers_freshness = tree.xpath(NUMBERS_FRESHNESS_XPATH)[0]

    if (_are_numbers_fresh(numbers_freshness)):
        logging.info("Today's number are ready")

        main_numbers = tree.xpath(MAIN_NUMBERS_XPATH)[0]
        supplementary_numbers = tree.xpath(SUPPLEMENTARY_NUMBERS_XPATH)[0]

        content = f'{main_numbers} + {supplementary_numbers}'

        messages = [_construct_mail(recipient, content) for recipient in RECIPIENT_EMAILS]
        
        try:
            for message in messages:
                sg = SendGridAPIClient(SENDGRID_API_KEY)
                response = sg.send(message)
                logging.info(f'Status code: {response.status_code}, body: {response.body}')
            return Response(status=200)
        except Exception as e:
            logging.error("Error while sending mail: ", e)
            return Response(status=500)
        
    else:
        logging.warn("Numbers for today are not ready yet...")
        return Response(status=500)
