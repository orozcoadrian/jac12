import email
import logging
import os
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

import requests
from robobrowser import RoboBrowser


class ForeclosuresInfrastructure(object):
    @staticmethod
    def get_items_resp_from_req(url):
        r = requests.get(url)
        content = r.content
        return content


class FileSystemInfrastructure(object):
    @staticmethod
    def save_content_to_file(file_path, open_mode, r_text):
        with open(file_path, open_mode) as handle:
            handle.write(r_text)

    @staticmethod
    def save_lines_to_file(file_path, open_mode, content_):
        with open(file_path, open_mode) as handle:
            for bl in content_:
                handle.write(bl)


class BclerkPublicRecordsInfrastructure(object):
    @staticmethod
    def get_resp_from_request(request_info):
        # request_info = self.get_request_info(case)
        browser = RoboBrowser(history=True, parser='html.parser')
        browser.open(request_info['uri'])
        form = browser.get_forms()[0]
        for k, v in request_info['form'].items():
            form[k].value = v
        browser.submit_form(form)
        resp = browser.response

        resp_text = resp.text
        return resp_text


class BclerkEfactsInfrastructure(object):
    @staticmethod
    def get_case_info_resp_from_req(data_, headers_, stream_, timeout_, url_):
        r = requests.post(url_, data_, headers=headers_,
                          stream=stream_, timeout=timeout_)
        return r

    @staticmethod
    def get_reg_actions_resp_from_req(data_, headers_, url_):
        r = requests.get(url_, data_,
                         headers=headers_, stream=True)
        r_text = r.text
        return r_text


class BcpaoInfrastructure(object):
    @staticmethod
    def get_res_from_req(req):
        logging.debug('***** before requests.get 1')
        ret = requests.get(req['url'], headers=req['headers'], timeout=10)
        logging.debug('*** after')
        return ret

    @staticmethod
    def get_acct_by_legal_resp_from_req(url2, headers):
        logging.debug('***** before requests.get 2')
        ret = requests.get(url2, headers=headers, timeout=10)  # timeout in seconds
        logging.debug('*** after')
        return ret


class TaxesInfrastructure(object):
    @staticmethod
    def get_resp_from_req(url):
        r = requests.post(url, data='', headers='', stream=True, timeout=10)
        return r.content


class EmailInfrastructure(object):
    @staticmethod
    def send_mail(username, password, send_from, send_to, subject, text, files, server="localhost"):
        assert isinstance(send_to, list)
        assert isinstance(files, list)

        msg = MIMEMultipart()
        msg['From'] = send_from
        msg['To'] = COMMASPACE.join(send_to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(text, 'html'))

        for f in files:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(f, "rb").read())
            email.encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
            msg.attach(part)

        smtp = smtplib.SMTP(server)
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.close()
