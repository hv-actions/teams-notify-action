import os
import json
import yaml
import requests
import re
import requests

#Define Empty section input
sections_input = ""
#---

#Fetching json for step details
steps_input = os.environ.get('STEPS_JSON')
webhook_input = os.environ.get('TEAMS_WEBHOOK_URL')
job_status_input = os.environ.get('JOB_STATUS')
# ---

#Create message footer
github_event_actor = os.environ.get('GITHUB_ACTOR')
event_actor_icon_url = f"https://github.com/{github_event_actor}.png"
response = requests.get(event_actor_icon_url, allow_redirects=True)
# Get the final redirected URL (the URL after all redirects)
github_user_icon = response.url
# ---

# Set github event name "push, pull_request.. etc "
github_event_name = os.environ.get('GITHUB_EVENT_NAME')
# ---

#Set Commit message details 
github_event_head_url = os.environ.get('GITHUB_EVENT_HEAD_COMMIT_URL')
github_event_head_commit_message = os.environ.get('GITHUB_EVENT_HEAD_COMMIT_MESSAGE')
github_server_url = os.environ.get('GITHUB_SERVER_URL')
github_repository = os.environ.get('GITHUB_REPOSITORY')
github_event_pull_request_number = os.environ.get('GITHUB_PULL_REQUEST_NUMBER')
github_branch = os.environ.get('GITHUB_BRANCH_REF')
github_run_id = os.environ.get('GITHUB_RUN_ID')
# ---

#sonar login details
sonar_host_url = os.environ.get('SONAR_HOST_URL')
sonar_project_key = os.environ.get('SONAR_PROJECT_KEY')
# ---

#Set Workflow details Url
workflow_url = f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"

#Set Commit message for notification
if github_event_name not in ["pull_request", "pull_request_target"]:
    if not github_event_head_url:
        details = "Details"
    else:
        details = github_event_head_url

    commit = github_event_head_commit_message
    if not commit:
        commit = f"''Triggered by {github_event_name}''"
    else:
        commit = f"''{commit[:27]}...''"
elif github_event_name == "pull_request" or github_event_name == "pull_request_target":
    details = f"{github_server_url}/{github_repository}/pull/{github_event_pull_request_number}"
    commit = f"''Triggered by {github_event_name}''"


# This code checks a JSON file to ensure that data coming in as string input is enclosed within double quotes. 
# It does this by using regular expressions to identify and add double quotes to unquoted values that appear within JSON key-value pairs.
def add_double_quotes(match):
    return f'"{match.group(0)}"'

steps_input = re.sub(r'(?<!")(\w+)(?=:)', add_double_quotes, steps_input)
steps_input = re.sub(r'(?<=: )(\w+)(?=[,\n])', add_double_quotes, steps_input)
# --

#Tracking all steps for Push event and other than push
def step_track(steps_input):
    if 'Build' not in steps_input:
        steps_input['Build'] = {'outputs': {}, 'outcome': 'skipped', 'conclusion': 'skipped'}
    if 'Sonarqube' not in steps_input:
        steps_input['Sonarqube'] = {'outputs': {}, 'outcome': 'skipped', 'conclusion': 'skipped'}
    if 'Unit_Test' not in steps_input:
        steps_input['Unit_Test'] = {'outputs': {}, 'outcome': 'skipped', 'conclusion': 'skipped'}
        
    # Define desired sequence based on event type
    if github_event_name != "pull_request" and github_event_name != "pull_request_target":
        if 'Citadel' not in steps_input:
            steps_input['Citadel'] = {'outputs': {}, 'outcome': 'skipped', 'conclusion': 'skipped'}
        desired_sequence = ['Build', 'Unit_Test', 'Citadel', 'Sonarqube']
    else:
        desired_sequence = ['Build', 'Unit_Test', 'Sonarqube']

    # Formating steps in desired sequence
    desired_sequence_data = {key: steps_input[key] for key in desired_sequence if key in steps_input}

    #Adding remaining step at end other than desired sequence
    for key, value in steps_input.items():
        if key not in desired_sequence:
            desired_sequence_data[key] = value

    return desired_sequence_data

#Sonar Url generation
if sonar_host_url and sonar_project_key:
    if github_event_name == "pull_request" or github_event_name == "pull_request_target":
        generate_sonarqube_url = f"{sonar_host_url}/dashboard?id={sonar_project_key}&pullRequest={github_event_pull_request_number}"
    else:
        generate_sonarqube_url = f"{sonar_host_url}/dashboard?id={sonar_project_key}&branch={github_branch}"
else:
    generate_sonarqube_url = ""

# Unit Test Url link from honeycomb
generated_unit_test_url = os.environ.get('UNIT_TEST_URL')

# Function to Replace link in message
def replace_values_with_links(data,sonarqube_url,unit_test_url): 
    for item in data:
        if item['name'] == 'Unit_Test' and item['value'] != '❌ SKIP' and unit_test_url:
            item['value'] = f'<a href="{unit_test_url}">{item["value"]}</a>'
        elif item['name'] == 'Sonarqube' and item['value'] != '❌ SKIP' and sonarqube_url:
            item['value'] = f'<a href="{sonarqube_url}">{item["value"]}</a>'
    return data

#Creating teams message Structure using json_payload
json_payload = {
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "summary": "Honeycomb Teams Notification",
    "sections": [],
    "potentialAction": []
}

# Adding green and red line based on job status in messsage Box
theme_color = {"themeColor": "00FF00" if job_status_input == "success" else "FF0000"}

json_payload.update(theme_color)

emoji_map = {
    'success': '✅ OK',
    'failure': '💥 FAIL',
    'skipped': '❌ SKIP'
}

# Set message content
if sections_input:
    json_payload["sections"] = yaml.safe_load(sections_input)
else:
    json_payload["sections"].extend([
        {"text": f"<a href='{details}'>Details</a>"},
        {"text": f"<h3>Commit message : {commit}</h3>"},
        {"text": f"<h3>Branch : {github_branch}</h3>"},
        {"text": f"Event: <a href='{workflow_url}'>{github_event_name}"}
    
    ])

    if steps_input:
        final_dict= {}
        steps_input = step_track(json.loads(steps_input))
        for key, value in steps_input.items():
            for k, v in value.items():
                if k == 'outcome':
                    value[k] = emoji_map.get(v, v)
                    final_dict[key] = value[k]
                                   
        fact_list = [{'name': key, 'value': value} for key, value in final_dict.items() if not any(char.isdigit() for char in key)]
        json_payload["sections"].append({"text": "<h2><strong>Workflow Steps</strong></h2>"})
        
        #Updating fact_list with link
        final_fact_list = replace_values_with_links(fact_list,generate_sonarqube_url,generated_unit_test_url)
        
        #Setting Steps Names and status icon
        json_payload["sections"].append({"facts": final_fact_list})
        
        #Setting footer of message
        json_payload["sections"].append({"text": f'<img src="{github_user_icon}" style="width: 20px; height: 20px;"> by {github_event_actor}'})

def teams_message_send(webhook_input, json_payload):
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(webhook_input, json=json_payload, headers=headers)
        response.raise_for_status()  # Raise an exception for 4xx and 5xx HTTP status codes
        print('Request sent successfully')
        print('Response:', response.text)
    except requests.exceptions.RequestException as e:
        print('Error sending the request:', e)

#Calling funtion to send message
teams_message_send(webhook_input, json_payload)

# You can set the JSON payload as an output variable if needed
json_payload_str = json.dumps(json_payload, indent=2)
print('jsonPayload:', json_payload_str)
