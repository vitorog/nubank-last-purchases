__author__ = 'vitorog'

import datetime
import hashlib
import locale
import sys
import gspread
from datetime import date
from gspread import CellNotFound
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

NUBANK_LOGIN_URL = 'https://conta.nubank.com.br/#/login'
NUBANK_TRANSACTIONS_URL = 'https://conta.nubank.com.br/#/transactions'
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


def login_to_page(browser, id, password):
    username_field = browser.find_element_by_id(USER_FIELD_ID)
    password_field_id = browser.find_element_by_id(PASSWORD_FIELD_ID)
    login_button = browser.find_element(By.CLASS_NAME, NU_BUTTON_CLASS_NAME)
    username_field.send_keys(id)
    password_field_id.send_keys(password)
    login_button.click()
    print('Logging in...')


def is_logged_in(browser):
    if browser.current_url == NUBANK_TRANSACTIONS_URL:
        return True
    else:
        return False


def extract_last_purchases(browser, try_num, transactions_limit):
    purchases_list = []
    try:
        transactions = list(WebDriverWait(browser, 180).until(EC.presence_of_all_elements_located(
            (By.CLASS_NAME, TRANSACTION_CLASS_NAME))))[:transactions_limit]
        transactions = list(reversed(transactions))
        for t in transactions:
            amount = t.find_element(By.CLASS_NAME, AMOUNT_CLASS_NAME).text
            description = t.find_element(By.CLASS_NAME, DESCRIPTION_CLASS_NAME).text
            transaction_date = t.find_element(By.CLASS_NAME, TIME_CLASS_NAME).text + ' ' + str(date.today().year)
            try:
                converted_date = datetime.datetime.strptime(transaction_date, INPUT_DATE_FORMAT).strftime(
                    OUTPUT_DATE_FORMAT)
            except ValueError:
                converted_date = transaction_date

            print_spreadsheet_format(description, amount, converted_date)
            purchases_list.append({'description': description, 'amount': amount,
                                   'type': NUBANK_TAG, 'date': converted_date})

        return purchases_list

    # For some reason Nubank's webpage fails to load most of the time...
    except TimeoutException:
        log = browser.get_log('browser')
        for entry in log:
            print(entry['message'])
        if try_num > 0:
            browser.refresh()
            extract_last_purchases(browser, try_num - 1, transactions_limit)
        else:
            print('Page failed to load')
            raise TimeoutException


def print_spreadsheet_format(description, amount, transaction_date):
    t_str = build_transaction_str(description, amount, transaction_date)
    t_hash = calculate_transaction_hash(t_str)
    print(t_str + SEPARATOR + str(t_hash))


def calculate_transaction_hash(t_str):
    return int(hashlib.md5(t_str.encode('UTF-8')).hexdigest(), 16)


def build_transaction_str(description, amount, transaction_date):
    return description + SEPARATOR + amount + SEPARATOR + NUBANK_TAG + SEPARATOR + transaction_date


def set_locale():
    current_locale = locale.setlocale(locale.LC_TIME, '')
    locale.setlocale(locale.LC_TIME, current_locale)


def add_purchases_to_spreadsheet(purchases_list):
    print('Accessing spreadsheet...')
    scope = ['https://spreadsheets.google.com/feeds']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    client = gspread.authorize(creds)

    sheet = client.open('Finanças - 2017')
    worksheet = sheet.get_worksheet(0)

    last_purchases_cell = worksheet.find('Últimas Compras')
    last_purchases_row = last_purchases_cell.row
    last_purchases_col = last_purchases_cell.col

    row = last_purchases_row + 2
    col = last_purchases_col

    print('Finding last purchase stored...')
    last_purchase_index, row = get_last_purchase_index_and_row(purchases_list, row, col, worksheet)

    if last_purchase_index is -1:
        print('No new purchases detected.')
        return

    print('Updating spreadsheet with new purchases')
    for idx in range(last_purchase_index, len(purchases_list)):
        p = purchases_list[idx]
        desc = p['description']
        amount = p['amount']
        p_date = p['date']
        p_str = build_transaction_str(desc, amount, p_date)
        str_hash = calculate_transaction_hash(p_str)

        print('Inserting: ' + p_str)
        worksheet.update_cell(row, col, desc)
        worksheet.update_cell(row, col + 1, amount)
        worksheet.update_cell(row, col + 2, NUBANK_TAG)
        worksheet.update_cell(row, col + 3, p_date)
        worksheet.update_cell(row, col + 4, str_hash)

        row = row + 1

    print('Done!')


def get_last_purchase_index_and_row(purchases_list, row, col, worksheet):
    hash_values = worksheet.col_values(col + 4)
    hash_values = list(filter(None, hash_values))[1:]
    if len(hash_values) == 0:
        return 0, row

    last_purchase_index = -1
    for idx, p in enumerate(purchases_list):
        desc = p['description']
        amount = p['amount']
        p_date = p['date']
        p_str = build_transaction_str(desc, amount, p_date)
        str_hash = str(calculate_transaction_hash(p_str))

        if str_hash not in hash_values:
            row = row + idx
            last_purchase_index = idx
            break
    return last_purchase_index, row


def main():
    if len(sys.argv) < 4:
        print('Missing a parameter')
        print('Usage: python nubank_last_purchases.py ID PASS LIMIT')
        sys.exit()

    username = sys.argv[1]
    password = sys.argv[2]
    transactions_limit = int(sys.argv[3])
    browser = webdriver.PhantomJS()
    browser.implicitly_wait(180)
    browser.set_page_load_timeout(180)

    print('Accessing website...')
    browser.get(NUBANK_TRANSACTIONS_URL)
    print('Done.')
    result = ""
    set_locale()
    try:
        if not is_logged_in(browser):
            login_to_page(browser, username, password)
            print('Finished logging in.')
        num_tries = 5
        print('Extracting purchases...')
        purchases_list = extract_last_purchases(browser, num_tries, transactions_limit)
        add_purchases_to_spreadsheet(purchases_list)
        result = 'success'
    except TimeoutException as e:
        print('Process timeout')
        print(e)
        result = 'failed'
    finally:
        # print('Saving result screenshot...')
        browser.save_screenshot(result + '_' + str(datetime.datetime.now()) + '.png')
        browser.quit()


if __name__ == '__main__':
    main()
