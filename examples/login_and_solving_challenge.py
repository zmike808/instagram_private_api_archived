import json
import codecs
import re
import email
import imaplib


from instagram_private_api import Client, ClientError, ClientCheckpointRequiredError


def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object


def onlogin_callback(api, new_settings_file):
    cache_settings = api.settings
    with open(new_settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('SAVED: {0!s}'.format(new_settings_file))


username = ''
password = ''
settings_file = '/path/to/file/settings_{}.json'.format(username)

CHALLENGE_EMAIL = ''
CHALLENGE_PASSWORD = ''

def get_code_from_email(username):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(CHALLENGE_EMAIL, CHALLENGE_PASSWORD)
    mail.select("inbox")
    result, data = mail.search(None, "(UNSEEN)")
    assert result == "OK", "Error1 during get_code_from_email: %s" % result
    ids = data.pop().split()
    for num in reversed(ids):
        mail.store(num, "+FLAGS", "\\Seen")  # mark as read
        result, data = mail.fetch(num, "(RFC822)")
        assert result == "OK", "Error2 during get_code_from_email: %s" % result
        msg = email.message_from_string(data[0][1].decode())
        payloads = msg.get_payload()
        if not isinstance(payloads, list):
            payloads = [msg]
        code = None
        for payload in payloads:
            body = payload.get_payload(decode=True).decode()
            if "<div" not in body:
                continue
            match = re.search(">([^>]*?({u})[^<]*?)<".format(u=username), body)
            if not match:
                continue
            print("Match from email:", match.group(1))
            match = re.search(r">(\d{6})<", body)
            if not match:
                print('Skip this email, "code" not found')
                continue
            code = match.group(1)
        return code
    return False


api = Client(username, password, on_login=lambda x: onlogin_callback(x, settings_file))
try:
    api.login()
except ClientCheckpointRequiredError as e:
    challenge_url = e.challenge_url

    challenge_pattern = r'.*challenge/(?P<account_id>\d.*)/(?P<identifier>\w.*)/'
    match = re.search(challenge_pattern, challenge_url)
    if not match:
        raise ClientError('Unable to parse challenge')

    match_dict = match.groupdict()
    account_id = match_dict['account_id']
    identifier = match_dict['identifier']

    res = api.choose_confirm_method(account_id, '1')  # confirm_method param has default value 1, you can pass 0
    magic_code = get_code_from_email(username)
    if magic_code:
        code = magic_code
    else:
        code = input('Enter code from email: ')
    api.send_challenge(account_id, identifier, code)
