"""
Resources:
https://pattern-match.com/blog/2018/10/30/serverless-slackbot-using-aws-chalice/
"""
import logging
import urllib.request
from urllib.parse import parse_qs
from chalice import Chalice
import boto3
import time

app = Chalice(app_name='slack_interface_aws')
app.debug = True

client_sm = boto3.client('sagemaker',
region_name='us-east-1',
aws_access_key_id='',
aws_secret_access_key='')

"""
Functions
"""
def process_raw_body(raw_body):
    parsed_raw_body = parse_qs(raw_body)
    text = ''
    if parsed_raw_body.get('text'):
        text = parsed_raw_body.get('text')[0]
    return text

def list_notebooks():
    response = client_sm.list_notebook_instances()
    instances = response['NotebookInstances']
    return instances

def get_status_notebook(status):
    if status == 'InService':
        return '🟢'
    return '🔴'

def get_color_notebook(status):
    if status == 'InService':
        return '#36a64f'
    elif status == 'Stopped':
        return '#ff1a1a'
    else:
        return '#ff471a'

def format_list_notebooks(instances):
    text = ''
    for instance in instances:
        text += f'{get_status_notebook(instance["NotebookInstanceStatus"])}<=====>{instance["InstanceType"]}  :  {instance["NotebookInstanceName"]}\n'
    return text

def build_attachments_notebook(instances):
    attachments = []
    for instance in instances:
        attachment = {
            'text' : f'*{instance["NotebookInstanceName"]}*',
            'color' : get_color_notebook(instance["NotebookInstanceStatus"])
        }
        attachments.append(attachment)
    return attachments

def check_instance(instance_name, instances):
    for instance in instances:
        if instance_name == instance['NotebookInstanceName']:
            return True
    return False

def collect_notebook_url(instance_name):
    response = client_sm.create_presigned_notebook_instance_url(NotebookInstanceName=instance_name)
    url = response["AuthorizedUrl"]
    # url = url.replace('.aws','.aws/lab')
    return url

"""
Application
"""

@app.route('/test-command', methods=['POST'], content_types=['application/json','application/x-www-form-urlencoded'])
def test_command():
    response_command = {
        "statusCode": 200,
        "response_type": 'ephemeral',
    }
    instances = list_notebooks()
    attachments = build_attachments_notebook(instances)

    response_command['text'] = "There is the list of available notebooks <https://google.com|this is a link> `/please feed`"
    response_command['attachments'] = attachments
    return response_command

@app.route('/start-notebook', methods=['POST'], content_types=['application/json','application/x-www-form-urlencoded'])
def start_notebook():
    response_command = {
        "statusCode": 200,
        "response_type": 'ephemeral',
    }

    raw_request = app.current_request.raw_body.decode()
    app.log.debug('/start-notebook:event:',raw_request)
    raw_body = app.current_request.raw_body.decode()
    text = process_raw_body(raw_body)

    instances = list_notebooks()
    if text == '':
        response_command['text'] = "There is the list of available notebooks"
        attachments = build_attachments_notebook(instances)
        response_command['attachments'] = attachments
    else:
        if check_instance(text, instances):
            response = client_sm.start_notebook_instance(NotebookInstanceName=text)
            response_command['text'] = f'🎆 The notebook will be available in a few minutes\n You will get the url of the notebook with the command: `/connect-notebook {text}`'
        else:
            response_command['text'] = 'Bad name for the notebook.\nThere is the list of available notebooks:\n'
            attachments = build_attachments_notebook(instances)
            response_command['attachments'] = attachments
    return response_command

@app.route('/connect-notebook', methods=['POST'], content_types=['application/json','application/x-www-form-urlencoded'])
def connect_notebook():
    response_command = {
        "statusCode": 200,
        "response_type": 'ephemeral',
    }

    raw_request = app.current_request.raw_body.decode()
    app.log.debug('/connect-notebook:event:',raw_request)
    raw_body = app.current_request.raw_body.decode()
    text = process_raw_body(raw_body)

    instances = list_notebooks()
    if text == '':
        response_command['text'] = "There is the list of available notebooks"
        attachments = build_attachments_notebook(instances)
        response_command['attachments'] = attachments
    else:
        if check_instance(text, instances):
            response = client_sm.describe_notebook_instance(NotebookInstanceName=text)
            if response['NotebookInstanceStatus'] == 'InService':
                url = collect_notebook_url(text)
                response_command['text'] = f'🎆 The notebook is available at this url: <{url}|LINK>\n'
            elif response['NotebookInstanceStatus'] == 'Stopped':
                response_command['text'] = f'🎆 The notebook is not ON, please start it with the command `/start-notebook {text}`'
            else:
                response_command['text'] = f'The engine is starting be patient'
        else:
            response_command['text'] = 'Bad name for the notebook.\nThere is the list of available notebooks:\n'
            attachments = build_attachments_notebook(instances)
            response_command['attachments'] = attachments
    return response_command

@app.route('/stop-notebook', methods=['POST'], content_types=['application/json','application/x-www-form-urlencoded'])
def stop_notebook():
    response_command = {
        "statusCode": 200,
        "response_type": 'ephemeral',
    }

    raw_request = app.current_request.raw_body.decode()
    app.log.debug('/stop-notebook:event:',raw_request)
    raw_body = app.current_request.raw_body.decode()
    text = process_raw_body(raw_body)

    instances = list_notebooks()
    if text == '':
        count_inservice_instance = 0
        for instance in instances:
            if instance["NotebookInstanceStatus"] == 'InService':
                instance_to_stop = instance["NotebookInstanceName"]
                count_inservice_instance += 1

        if count_inservice_instance == 1:
            response = client_sm.stop_notebook_instance(NotebookInstanceName=instance_to_stop)
            response_command['text'] = f'💥 The notebook {instance_to_stop} will be shutdown in a few minutes 👋'
        else:
            response_command['text'] = 'Bad name for the notebook.\nThere is the list of available notebooks:\n'
            attachments = build_attachments_notebook(instances)
    elif check_instance(text, instances):
        response = client_sm.stop_notebook_instance(NotebookInstanceName=text)
        response_command['text'] = f'💥 The notebook {text} will be shutdown in a few minutes 👋'
    else:
        response_command['text'] = 'Bad name for the notebook.\nThere is the list of available notebooks:\n'
        attachments = build_attachments_notebook(instances)
    return response_command
