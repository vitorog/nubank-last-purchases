__author__ = 'vitorog'

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import selenium.webdriver.support.ui as ui
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import  TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import sys
import datetime
import locale
from datetime import date

NUBANK_LOGIN_URL = 'https://conta.nubank.com.br/#/login'
NUBANK_TRANSACTIONS_URL = 'https://conta.nubank.com.br/#/transactions';
USER_FIELD_ID = 'username'
PASSWORD_FIELD_ID = 'input_001'
NU_BUTTON_CLASS_NAME = 'nu-button'
FEED_TABLE_ID = 'feedTable'
EVENT_CARD_CLASS_NAME = 'event-card'
TRANSACTION_CLASS_NAME = 'transaction'
DESCRIPTION_CLASS_NAME = 'description'
AMOUNT_CLASS_NAME = 'amount'
TIME_CLASS_NAME = 'time'
INPUT_DATE_FORMAT = '%d %b %Y'
OUTPUT_DATE_FORMAT = '%d/%m/%Y'
NUBANK_TAG = 'Nubank'
SEPARATOR = ';'
TRANSACTIONS_LIMIT = 10


def login_to_page(browser, id, password):
    username_field = browser.find_element_by_id(USER_FIELD_ID)
    password_field_id = browser.find_element_by_id(PASSWORD_FIELD_ID)
    login_button = browser.find_element(By.CLASS_NAME, NU_BUTTON_CLASS_NAME)
    username_field.send_keys(id)
    password_field_id.send_keys(password)
    login_button.click()

def is_logged_in(browser):
    if browser.current_url == NUBANK_TRANSACTIONS_URL:
        return True
    else:
        return False

def extract_last_purchases(browser, try_num):
    try:
        transactions = list(WebDriverWait(browser, 30).until(EC.presence_of_all_elements_located(
            (By.CLASS_NAME, TRANSACTION_CLASS_NAME))))[:TRANSACTIONS_LIMIT]
        transactions = list(reversed(transactions))
        for t in transactions:
            amount = t.find_element(By.CLASS_NAME, AMOUNT_CLASS_NAME).text
            description = t.find_element(By.CLASS_NAME, DESCRIPTION_CLASS_NAME).text
            transaction_date = t.find_element(By.CLASS_NAME, TIME_CLASS_NAME).text + ' ' + str(date.today().year)
            converted_date = datetime.datetime.strptime(transaction_date, INPUT_DATE_FORMAT).strftime(
                OUTPUT_DATE_FORMAT)
            print_spreadsheet_format(description, amount, converted_date)
    # For some reason Nubank's webpage fails to load most of the time...
    except TimeoutException:
        log = browser.get_log('browser')
        for entry in log:
            print entry['message']
        if try_num > 0:
            browser.refresh()
            extract_last_purchases(browser, try_num - 1)
        else:
            print 'Page failed to load'
            raise TimeoutException

def print_spreadsheet_format(description, amount, transaction_date):
    print description + SEPARATOR + amount + SEPARATOR + NUBANK_TAG + SEPARATOR + transaction_date

def set_locale():
    current_locale = locale.setlocale(locale.LC_TIME, '')
    locale.setlocale(locale.LC_TIME, current_locale)

def main():
    if len(sys.argv) < 3:
        print('Missing id and pass')
        print('Usage: python nubank_last_purchases.py ID PASS')
        sys.exit()

    id = sys.argv[1]
    password = sys.argv[2]
    d = DesiredCapabilities.CHROME
    d['loggingPrefs'] = {'browser': 'ALL'}
    #browser = webdriver.PhantomJS()
    browser = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', desired_capabilities=d)
    print('Accessing website...')
    browser.get(NUBANK_TRANSACTIONS_URL)
    print('Done.')
    result = ""
    set_locale()
    try:
        if not is_logged_in(browser):
            login_to_page(browser, id, password)
        num_tries = 5
        extract_last_purchases(browser, num_tries)
        result = 'success'
    except TimeoutException as e:
        print('Process timeout')
        result = 'failed'
    finally:
        #print('Saving result screenshot...')
        #browser.save_screenshot(result + '_' + str(datetime.datetime.now()) + '.png')
        browser.quit()


if __name__ == '__main__':
    main()

